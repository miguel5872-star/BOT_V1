"""
Genera index.html: un panel autocontenido con la curva de patrimonio, el
drawdown y las metricas. Sin librerias externas ni peticiones de red, para que
funcione igual abierto en local o servido por GitHub Pages.

    python grafica.py
"""
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
PAPEL = os.path.join(RAIZ, "papel")
CURVA = os.path.join(PAPEL, "curva.csv")
REGISTRO = os.path.join(PAPEL, "registro.jsonl")
ESTADO = os.path.join(PAPEL, "estado.json")
SALIDA = os.path.join(RAIZ, "index.html")


def leer():
    if not os.path.exists(CURVA):
        return None
    d = pd.read_csv(CURVA, parse_dates=["fecha"]).drop_duplicates("ts")
    return d.set_index("fecha").sort_index()


def poli(xs, ys, w, h, x0, x1, y0, y1):
    """Convierte series a coordenadas de un SVG."""
    if x1 == x0:
        x1 = x0 + 1
    if y1 == y0:
        y1 = y0 + 1
    px = [(x - x0) / (x1 - x0) * w for x in xs]
    py = [h - (y - y0) / (y1 - y0) * h for y in ys]
    return " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py))


def grafico(d, columna, color, relleno, titulo, sufijo="%", cero=True):
    if len(d) < 2:
        return f'<div class="vacio">{titulo}: hacen falta al menos 2 marcas</div>'
    W, H = 900, 220
    xs = d.index.astype("int64").to_numpy() / 1e9
    ys = d[columna].to_numpy(dtype=float)
    y0, y1 = float(np.nanmin(ys)), float(np.nanmax(ys))
    margen = max((y1 - y0) * 0.12, 0.05)
    y0, y1 = y0 - margen, y1 + margen
    if cero and y0 > 0:
        y0 = 0
    if cero and y1 < 0:
        y1 = 0
    pts = poli(xs, ys, W, H, xs[0], xs[-1], y0, y1)
    base = H - (0 - y0) / (y1 - y0) * H if y0 <= 0 <= y1 else H
    area = f"0,{base:.1f} {pts} {W},{base:.1f}"
    ticks = ""
    for frac in (0, .25, .5, .75, 1):
        v = y1 - frac * (y1 - y0)
        y = frac * H
        ticks += (f'<line x1="0" y1="{y:.1f}" x2="{W}" y2="{y:.1f}" class="rej"/>'
                  f'<text x="4" y="{y-4:.1f}" class="eje">{v:+.2f}{sufijo}</text>')
    fechas = ""
    for frac in (0, .5, 1):
        i = int(frac * (len(d) - 1))
        fechas += (f'<text x="{frac*W:.0f}" y="{H+16}" class="eje" '
                   f'text-anchor="{"start" if frac==0 else "end" if frac==1 else "middle"}">'
                   f'{d.index[i]:%d %b %H:%M}</text>')
    return f"""<div class="tarjeta">
  <h3>{titulo}</h3>
  <svg viewBox="0 0 {W} {H+24}" preserveAspectRatio="none" class="svg">
    {ticks}
    <polyline points="{area}" fill="{relleno}" stroke="none"/>
    <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"
              stroke-linejoin="round"/>
    {fechas}
  </svg>
</div>"""


def metricas(d):
    if d is None or len(d) == 0:
        return {}
    eq = d["patrimonio"] / d["patrimonio"].iloc[0]
    dd = (eq / eq.cummax() - 1) * 100
    dia = d["patrimonio"].resample("1D").last().dropna().pct_change().dropna()
    m = {"Patrimonio": f"{d['patrimonio'].iloc[-1]:,.2f} USDT",
         "Retorno": f"{d['retorno_acum_pct'].iloc[-1]:+.3f}%",
         "Max drawdown": f"{dd.min():.2f}%",
         "Marcas": f"{len(d)}",
         "Dias": f"{len(dia)}",
         "Tramos abiertos": f"{int(d['tramos_abiertos'].iloc[-1])}/3"}
    if len(dia) > 2 and dia.std() > 0:
        m["Retorno diario"] = f"{dia.mean()*100:+.3f}%"
        m["Volatilidad diaria"] = f"{dia.std()*100:.3f}%"
        m["Sharpe anualizado"] = f"{dia.mean()/dia.std()*np.sqrt(365):.2f}"
        m["Dias positivos"] = f"{(dia>0).mean()*100:.0f}%"
    return m, dd


def cierres():
    if not os.path.exists(REGISTRO):
        return [], 0
    filas, tardios = [], 0
    with open(REGISTRO, encoding="utf-8") as fh:
        for linea in fh:
            ev = json.loads(linea)
            if ev.get("tipo") == "cierre":
                filas.append(ev)
                tardios += bool(ev.get("cierre_tardio"))
    return filas[-12:][::-1], tardios


def abiertas():
    if not os.path.exists(ESTADO):
        return []
    e = json.load(open(ESTADO, encoding="utf-8"))
    return [{"id": t["id"], "abierto": t["abierto"][:16],
             "n": len(t["largos"]) + len(t["cortos"]),
             "peso": t["peso"]} for t in e.get("tramos", [])]


d = leer()
ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

if d is None or len(d) == 0:
    cuerpo = '<div class="vacio">Todavia no hay marcas. Ejecuta <code>python bot.py step</code>.</div>'
    resumen = ""
else:
    m, dd = metricas(d)
    d = d.copy()
    d["drawdown"] = dd
    resumen = "".join(
        f'<div class="m"><span class="k">{k}</span><span class="v">{v}</span></div>'
        for k, v in m.items())
    lista, tardios = cierres()
    tabla = ""
    if lista:
        filas = "".join(
            f"<tr><td>{c['fecha'][:16]}</td><td>{c['tramo']}</td>"
            f"<td>{c['horas_reales']:.1f} h{' ⚠' if c.get('cierre_tardio') else ''}</td>"
            f"<td class=\"{'pos' if c['retorno_bruto']>0 else 'neg'}\">"
            f"{c['retorno_bruto']*100:+.3f}%</td>"
            f"<td>{c.get('n_largos','?')}L / {c.get('n_cortos','?')}C</td></tr>"
            for c in lista)
        tabla = f"""<div class="tarjeta"><h3>Ultimos cierres de tramo</h3>
        <table><tr><th>Fecha</th><th>Tramo</th><th>Duracion</th>
        <th>Bruto</th><th>Cesta</th></tr>{filas}</table>
        <p class="nota">Cierres tardios acumulados: {tardios}
        (un tramo se marca tardio si supera 48 h + 2 de margen, senal de que
        hubo un hueco de ejecucion)</p></div>"""
    ab = abiertas()
    tabla_ab = ""
    if ab:
        filas = "".join(f"<tr><td>{t['id']}</td><td>{t['abierto']}</td>"
                        f"<td>{t['n']} posiciones</td><td>{t['peso']:.2f}x</td></tr>"
                        for t in ab)
        tabla_ab = f"""<div class="tarjeta"><h3>Tramos abiertos</h3>
        <table><tr><th>Id</th><th>Abierto</th><th>Cesta</th><th>Peso</th></tr>
        {filas}</table></div>"""
    cuerpo = (grafico(d, "retorno_acum_pct", "var(--linea)", "var(--area)",
                      "Retorno acumulado")
              + grafico(d, "drawdown", "var(--rojo)", "var(--areaRojo)",
                        "Drawdown", cero=True)
              + tabla_ab + tabla)

html = f"""<title>Bot de papel — momentum de funding</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root {{
  --fondo:#fbfbfa; --texto:#1c1b19; --suave:#6b6960; --borde:#e3e1dc;
  --tarjeta:#ffffff; --linea:#2f6f4f; --area:rgba(47,111,79,.12);
  --rojo:#a33b32; --areaRojo:rgba(163,59,50,.12); --rej:#efedea;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --fondo:#17171a; --texto:#eceae5; --suave:#9a978e; --borde:#2c2c30;
    --tarjeta:#1e1e22; --linea:#63b58a; --area:rgba(99,181,138,.14);
    --rojo:#e0736a; --areaRojo:rgba(224,115,106,.14); --rej:#26262a;
  }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:24px 16px 48px; background:var(--fondo); color:var(--texto);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
.env {{ max-width:940px; margin:0 auto; }}
h1 {{ font-size:22px; margin:0 0 4px; letter-spacing:-.01em; }}
.sub {{ color:var(--suave); font-size:13px; margin:0 0 22px; }}
.res {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px; background:var(--borde); border:1px solid var(--borde);
  border-radius:10px; overflow:hidden; margin-bottom:22px; }}
.m {{ background:var(--tarjeta); padding:12px 14px; display:flex;
  flex-direction:column; gap:3px; }}
.k {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--suave); }}
.v {{ font-size:19px; font-variant-numeric:tabular-nums; }}
.tarjeta {{ background:var(--tarjeta); border:1px solid var(--borde);
  border-radius:10px; padding:16px 18px; margin-bottom:18px; }}
h3 {{ font-size:13px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--suave); margin:0 0 12px; font-weight:600; }}
.svg {{ width:100%; height:auto; display:block; overflow:visible; }}
.rej {{ stroke:var(--rej); stroke-width:1; }}
.eje {{ fill:var(--suave); font-size:11px; font-family:inherit; }}
table {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }}
th {{ text-align:left; font-size:11px; text-transform:uppercase;
  letter-spacing:.05em; color:var(--suave); font-weight:600;
  padding:0 10px 8px 0; }}
td {{ padding:6px 10px 6px 0; border-top:1px solid var(--borde); font-size:14px; }}
.pos {{ color:var(--linea); }} .neg {{ color:var(--rojo); }}
.vacio {{ background:var(--tarjeta); border:1px dashed var(--borde);
  border-radius:10px; padding:28px; text-align:center; color:var(--suave); }}
.nota {{ font-size:12px; color:var(--suave); margin:12px 0 0; }}
code {{ background:var(--rej); padding:2px 6px; border-radius:4px; font-size:13px; }}
footer {{ color:var(--suave); font-size:12px; margin-top:26px;
  border-top:1px solid var(--borde); padding-top:14px; }}
</style>
<div class="env">
  <h1>Bot de papel — momentum de funding</h1>
  <p class="sub">Mercado neutral sobre perpetuos USDT. Dinero ficticio.
     Generado el {ahora}.</p>
  <div class="res">{resumen}</div>
  {cuerpo}
  <footer>
    Estrategia: funding acumulado de 72 h, largo el 20% superior y corto el 20%
    inferior, tres tramos solapados de 48 h. Costes aplicados: 0,05% de comision
    y 0,05% de deslizamiento por lado.<br>
    Esto no es asesoramiento financiero.
  </footer>
</div>"""

open(SALIDA, "w", encoding="utf-8").write(html)
print(f"Panel generado: {SALIDA}")
