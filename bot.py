"""
Bot de papel de momentum de funding. Pensado para correr en la nube sin
maquina propia encendida.

  - Senal y precios: API publica de PRODUCCION de Bybit. Sin cuenta ni clave.
  - Ejecucion: simulada, con comision y deslizamiento explicitos.
  - Registro: cadena de hashes SHA-256, imposible de reescribir sin que se note.

Comandos:
    python bot.py step        un ciclo (marcar a mercado, cerrar y abrir tramos)
    python bot.py report      resumen del historial
    python bot.py posiciones  que hay abierto ahora
    python bot.py verificar   integridad de la cadena de hashes
    python bot.py readme      regenera el README con el estado actual
"""
import argparse
import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

RAIZ = os.path.dirname(os.path.abspath(__file__))
PAPEL = os.path.join(RAIZ, "papel")
os.makedirs(PAPEL, exist_ok=True)
ESTADO = os.path.join(PAPEL, "estado.json")
REGISTRO = os.path.join(PAPEL, "registro.jsonl")
CURVA = os.path.join(PAPEL, "curva.csv")

BASE = "https://api.bybit.com"

# Parametros fijados por el backtest. No tocar sin volver a validar.
CAPITAL_INICIAL = 10_000.0
APALANCAMIENTO = 3.0
H_TENENCIA = 48
FRACCION = 0.20
N_TRAMOS = 3
CAP_FUNDING = 0.005
MIN_SIMBOLOS = 40
MIN_TURNOVER = 250_000
COMISION = 0.0005
DESLIZAMIENTO = 0.0005
TOLERANCIA_H = 2.0          # margen antes de marcar un cierre como tardio

_local = threading.local()


def ses():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update({"User-Agent": "paper-bot/2.0"})
    return _local.s


def ahora_ms():
    return int(time.time() * 1000)


def ahora_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(ruta, params, intentos=5):
    for k in range(intentos):
        try:
            r = ses().get(BASE + ruta, params=params, timeout=30)
            if r.status_code == 200:
                j = r.json()
                if j.get("retCode") == 0:
                    return j["result"]
            time.sleep(0.4 * (k + 1))
        except requests.RequestException:
            time.sleep(0.5 * (k + 1))
    return None


# ─────────────────────────────────────────────────────────── mercado
def universo():
    r = get("/v5/market/tickers", {"category": "linear"})
    if not r:
        raise RuntimeError("no se pudo leer tickers de Bybit")
    d = pd.DataFrame(r["list"])
    d["turnover24h"] = pd.to_numeric(d["turnover24h"], errors="coerce")
    d["lastPrice"] = pd.to_numeric(d["lastPrice"], errors="coerce")
    d = d[d["symbol"].str.endswith("USDT") & (d["turnover24h"] >= MIN_TURNOVER)]
    return d.set_index("symbol")[["lastPrice", "turnover24h"]].dropna()


def _datos_simbolo(sym, desde):
    """funding acumulado 72h y retorno 72h de un simbolo."""
    f = get("/v5/market/funding/history",
            {"category": "linear", "symbol": sym, "limit": 30})
    k = get("/v5/market/kline",
            {"category": "linear", "symbol": sym, "interval": "60", "limit": 80})
    if not f or not f.get("list") or not k or not k.get("list"):
        return None
    v = [float(x["fundingRate"]) for x in f["list"]
         if int(x["fundingRateTimestamp"]) >= desde]
    velas = sorted(k["list"], key=lambda x: int(x[0]))
    if not v or len(velas) < 73:
        return None
    return sym, sum(v), float(velas[-1][4]) / float(velas[-73][4]) - 1


def construir_cesta():
    u = universo()
    syms = u.index.tolist()
    desde = ahora_ms() - 72 * 3600_000
    filas = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(_datos_simbolo, s, desde) for s in syms]
        for fu in as_completed(futs):
            r = fu.result()
            if r:
                filas.append(r)
    d = pd.DataFrame(filas, columns=["symbol", "funding72", "ret72"]).set_index("symbol")
    d = d.join(u["lastPrice"]).dropna()
    d = d[d["funding72"].abs() < CAP_FUNDING]
    if len(d) < MIN_SIMBOLOS:
        raise RuntimeError(f"solo {len(d)} simbolos validos, minimo {MIN_SIMBOLOS}")
    x = d["ret72"].rank(pct=True)
    y = d["funding72"].rank(pct=True)
    d["senal"] = y - np.polyfit(x, y, 1)[0] * x
    k = max(int(len(d) * FRACCION), 5)
    o = d.sort_values("senal")
    return (o.tail(k)["lastPrice"].to_dict(),
            o.head(k)["lastPrice"].to_dict(), len(d))


# ─────────────────────────────────────────────────────────── estado
def cargar():
    if not os.path.exists(ESTADO):
        return None
    with open(ESTADO, encoding="utf-8") as fh:
        return json.load(fh)


def guardar(e):
    tmp = ESTADO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(e, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, ESTADO)


def hash_anterior():
    if not os.path.exists(REGISTRO) or os.path.getsize(REGISTRO) == 0:
        return "0" * 64
    with open(REGISTRO, "rb") as fh:
        ultima = fh.readlines()[-1]
    return json.loads(ultima)["hash"]


def anotar(ev):
    ev["hash_anterior"] = hash_anterior()
    ev["hash"] = hashlib.sha256(
        json.dumps(ev, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with open(REGISTRO, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")


def valor_tramo(tr, precios):
    rl = [precios[s] / p0 - 1 for s, p0 in tr["largos"].items()
          if s in precios and p0 > 0]
    rs = [precios[s] / p0 - 1 for s, p0 in tr["cortos"].items()
          if s in precios and p0 > 0]
    if not rl or not rs:
        return 0.0, len(rl), len(rs)
    return (float(np.mean(rl)) - float(np.mean(rs))) / 2, len(rl), len(rs)


def inicializar():
    e = {"capital_inicial": CAPITAL_INICIAL, "efectivo": CAPITAL_INICIAL,
         "apalancamiento": APALANCAMIENTO, "creado": ahora_iso(),
         "tramos": [], "paso": 0, "pasos_ejecutados": 0}
    guardar(e)
    anotar({"tipo": "init", "ts": ahora_ms(), "fecha": ahora_iso(),
            "capital": CAPITAL_INICIAL, "apalancamiento": APALANCAMIENTO,
            "parametros": {"H": H_TENENCIA, "fraccion": FRACCION,
                           "tramos": N_TRAMOS, "cap_funding": CAP_FUNDING,
                           "comision": COMISION, "deslizamiento": DESLIZAMIENTO,
                           "min_turnover": MIN_TURNOVER}})
    print(f"Inicializado: {CAPITAL_INICIAL:,.0f} USDT a {APALANCAMIENTO}x")
    return e


# ─────────────────────────────────────────────────────────── comandos
def cmd_step(args):
    e = cargar() or inicializar()
    t = ahora_ms()
    precios = universo()["lastPrice"].to_dict()

    vivos = []
    for tr in e["tramos"]:
        edad = (t - tr["abierto_ms"]) / 3600_000
        v, nl, ns = valor_tramo(tr, precios)
        tr["valor_actual"] = v
        if edad >= H_TENENCIA:
            tardio = edad > H_TENENCIA + TOLERANCIA_H
            neto = v * tr["peso"] - tr["coste_cierre"]
            e["efectivo"] += neto * e["capital_inicial"]
            anotar({"tipo": "cierre", "ts": t, "fecha": ahora_iso(),
                    "tramo": tr["id"], "horas_reales": round(edad, 2),
                    "horas_previstas": H_TENENCIA, "cierre_tardio": tardio,
                    "retorno_bruto": round(v, 6), "peso": tr["peso"],
                    "coste": round(tr["coste_cierre"], 6),
                    "n_largos": nl, "n_cortos": ns})
            marca = "  [TARDIO]" if tardio else ""
            print(f"  cerrado tramo {tr['id']} tras {edad:.1f}h: "
                  f"bruto {v*100:+.3f}%  neto {neto*100:+.4f}%{marca}")
        else:
            vivos.append(tr)
    e["tramos"] = vivos

    cadencia = H_TENENCIA / N_TRAMOS
    ultimo = max([tr["abierto_ms"] for tr in e["tramos"]], default=0)
    toca = (not e["tramos"]) or (t - ultimo) / 3600_000 >= cadencia - 0.5
    if toca and len(e["tramos"]) < N_TRAMOS:
        largos, cortos, n_univ = construir_cesta()
        peso = e["apalancamiento"] / N_TRAMOS
        tr = {"id": e["paso"], "abierto_ms": t, "abierto": ahora_iso(),
              "largos": largos, "cortos": cortos, "peso": peso,
              "coste_cierre": 2 * (COMISION + DESLIZAMIENTO) * peso,
              "valor_actual": 0.0}
        e["tramos"].append(tr)
        e["paso"] += 1
        anotar({"tipo": "apertura", "ts": t, "fecha": ahora_iso(),
                "tramo": tr["id"], "peso": peso, "universo": n_univ,
                "largos": sorted(largos), "cortos": sorted(cortos)})
        print(f"  abierto tramo {tr['id']}: {len(largos)}L/{len(cortos)}C "
              f"(universo {n_univ})")

    latente = sum(tr["valor_actual"] * tr["peso"] for tr in e["tramos"])
    patrimonio = e["efectivo"] + latente * e["capital_inicial"]
    e["pasos_ejecutados"] = e.get("pasos_ejecutados", 0) + 1
    guardar(e)

    fila = {"fecha": ahora_iso(), "ts": t,
            "efectivo": round(e["efectivo"], 2),
            "latente": round(latente * e["capital_inicial"], 2),
            "patrimonio": round(patrimonio, 2),
            "retorno_acum_pct": round((patrimonio / e["capital_inicial"] - 1) * 100, 4),
            "tramos_abiertos": len(e["tramos"])}
    pd.DataFrame([fila]).to_csv(CURVA, mode="a", index=False,
                                header=not os.path.exists(CURVA))
    anotar({"tipo": "marca", **fila})
    print(f"  patrimonio {patrimonio:,.2f} USDT "
          f"({(patrimonio/e['capital_inicial']-1)*100:+.3f}%)  "
          f"tramos {len(e['tramos'])}/{N_TRAMOS}")


def resumen_dict():
    if not os.path.exists(CURVA):
        return None
    d = pd.read_csv(CURVA, parse_dates=["fecha"]).drop_duplicates("ts")
    d = d.set_index("fecha").sort_index()
    eq = d["patrimonio"] / d["patrimonio"].iloc[0]
    dd = (eq / eq.cummax() - 1)
    dia = d["patrimonio"].resample("1D").last().dropna().pct_change().dropna()
    r = {"inicio": d.index[0], "ultimo": d.index[-1], "marcas": len(d),
         "patrimonio": d["patrimonio"].iloc[-1],
         "retorno": d["retorno_acum_pct"].iloc[-1], "dd": dd.min() * 100,
         "tramos": int(d["tramos_abiertos"].iloc[-1]), "dias": len(dia)}
    if len(dia) > 2 and dia.std() > 0:
        r.update({"dia_medio": dia.mean() * 100, "vol": dia.std() * 100,
                  "sharpe": dia.mean() / dia.std() * np.sqrt(365),
                  "pos": (dia > 0).mean() * 100})
    return r


def cmd_report(args):
    r = resumen_dict()
    if not r:
        print("Aun no hay historial.")
        return
    print("=" * 72)
    print("BOT DE PAPEL - MOMENTUM DE FUNDING")
    print("=" * 72)
    print(f"  inicio ............. {r['inicio']:%Y-%m-%d %H:%M} UTC")
    print(f"  ultima marca ....... {r['ultimo']:%Y-%m-%d %H:%M} UTC")
    print(f"  marcas / dias ...... {r['marcas']} / {r['dias']}")
    print(f"  patrimonio ......... {r['patrimonio']:,.2f} USDT")
    print(f"  retorno acumulado .. {r['retorno']:+.3f}%")
    print(f"  max drawdown ....... {r['dd']:.2f}%")
    print(f"  tramos abiertos .... {r['tramos']}/{N_TRAMOS}")
    if "sharpe" in r:
        print(f"  retorno diario ..... {r['dia_medio']:+.3f}%")
        print(f"  volatilidad diaria . {r['vol']:.3f}%")
        print(f"  Sharpe anualizado .. {r['sharpe']:.2f}")
        print(f"  dias positivos ..... {r['pos']:.0f}%")
    else:
        print("  (Sharpe y demas aparecen con 3+ dias de historial)")
    print(f"\n  ultimo hash: {hash_anterior()[:32]}...")


def cmd_posiciones(args):
    e = cargar()
    if not e or not e["tramos"]:
        print("Sin tramos abiertos.")
        return
    precios = universo()["lastPrice"].to_dict()
    t = ahora_ms()
    print("=" * 72)
    print("POSICIONES ABIERTAS")
    print("=" * 72)
    total = 0.0
    for tr in e["tramos"]:
        v, nl, ns = valor_tramo(tr, precios)
        edad = (t - tr["abierto_ms"]) / 3600_000
        aporte = v * tr["peso"] * e["capital_inicial"]
        total += aporte
        print(f"\n  tramo {tr['id']}  abierto {tr['abierto'][:16]}  "
              f"{edad:.1f}h de {H_TENENCIA}h  (cierra en {H_TENENCIA-edad:.1f}h)")
        print(f"    peso {tr['peso']:.2f}x   {nl}L / {ns}C   "
              f"bruto {v*100:+.3f}%   aporte {aporte:+,.2f} USDT")
    print(f"\n  latente {total:+,.2f}   patrimonio "
          f"{e['efectivo'] + total:,.2f} USDT")


def cmd_verificar(args):
    if not os.path.exists(REGISTRO):
        print("No hay registro.")
        return
    prev, n, malos = "0" * 64, 0, 0
    with open(REGISTRO, encoding="utf-8") as fh:
        for linea in fh:
            ev = json.loads(linea)
            h = ev.pop("hash")
            if ev.get("hash_anterior") != prev:
                malos += 1
            if hashlib.sha256(json.dumps(ev, sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest() != h:
                malos += 1
            prev, n = h, n + 1
    print(f"Registros: {n}   inconsistencias: {malos}")
    print("Cadena integra." if malos == 0 else "CADENA ROTA.")


def cmd_readme(args):
    r = resumen_dict()
    plantilla = os.path.join(RAIZ, "README.md")
    tardios = 0
    if os.path.exists(REGISTRO):
        with open(REGISTRO, encoding="utf-8") as fh:
            tardios = sum(1 for l in fh if '"cierre_tardio": true' in l)
    if r:
        est = [
            f"| Patrimonio | **{r['patrimonio']:,.2f} USDT** |",
            f"| Retorno acumulado | **{r['retorno']:+.3f}%** |",
            f"| Max drawdown | {r['dd']:.2f}% |",
            f"| Marcas / dias | {r['marcas']} / {r['dias']} |",
            f"| Tramos abiertos | {r['tramos']}/{N_TRAMOS} |",
            f"| Cierres tardios | {tardios} |",
        ]
        if "sharpe" in r:
            est += [f"| Retorno diario medio | {r['dia_medio']:+.3f}% |",
                    f"| Volatilidad diaria | {r['vol']:.3f}% |",
                    f"| Sharpe anualizado | {r['sharpe']:.2f} |",
                    f"| Dias positivos | {r['pos']:.0f}% |"]
        bloque = ("| Metrica | Valor |\n|---|---|\n" + "\n".join(est) +
                  f"\n\nUltima actualizacion: **{r['ultimo']:%Y-%m-%d %H:%M} UTC**  \n"
                  f"Hash del registro: `{hash_anterior()[:40]}`")
    else:
        bloque = "_Sin datos todavia._"

    texto = open(plantilla, encoding="utf-8").read() if os.path.exists(plantilla) else ""
    ini, fin = "<!--ESTADO-->", "<!--/ESTADO-->"
    if ini in texto and fin in texto:
        a = texto.index(ini) + len(ini)
        b = texto.index(fin)
        texto = texto[:a] + "\n" + bloque + "\n" + texto[b:]
        open(plantilla, "w", encoding="utf-8").write(texto)
        print("README actualizado.")
    else:
        print("No se encontraron los marcadores <!--ESTADO--> en el README.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for nombre, fn in [("step", cmd_step), ("report", cmd_report),
                       ("posiciones", cmd_posiciones), ("verificar", cmd_verificar),
                       ("readme", cmd_readme)]:
        sub.add_parser(nombre).set_defaults(func=fn)
    a = p.parse_args()
    a.func(a)
