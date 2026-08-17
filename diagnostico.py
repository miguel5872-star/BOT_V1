"""
¿Que APIs de exchange son alcanzables desde este runner?
Muchos exchanges bloquean por geografia (Bybit y Binance no sirven a IPs de
Estados Unidos) y los runners de GitHub estan en Azure US. Esto lo comprueba
en vez de suponerlo.
"""
import json
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0"})


def probar(nombre, url, params=None, clave=None):
    t0 = time.time()
    try:
        r = S.get(url, params=params or {}, timeout=20)
        ms = (time.time() - t0) * 1000
        cuerpo = r.text[:120].replace("\n", " ")
        ok = r.status_code == 200
        n = ""
        if ok and clave:
            try:
                j = r.json()
                for k in clave.split("."):
                    j = j[k] if not k.isdigit() else j[int(k)]
                n = f" ({len(j)} elementos)" if hasattr(j, "__len__") else ""
            except Exception:
                pass
        estado = "OK " if ok else "FALLO"
        print(f"  {estado} {nombre:<24} HTTP {r.status_code}  {ms:6.0f} ms{n}")
        if not ok:
            print(f"        -> {cuerpo}")
        return ok
    except Exception as e:
        print(f"  FALLO {nombre:<24} excepcion: {str(e)[:90]}")
        return False


print("=" * 78)
print("DIAGNOSTICO DE CONECTIVIDAD DESDE EL RUNNER")
print("=" * 78)

try:
    ip = S.get("https://api.ipify.org?format=json", timeout=15).json()["ip"]
    print(f"  IP publica del runner: {ip}")
    geo = S.get(f"https://ipapi.co/{ip}/json/", timeout=15).json()
    print(f"  Pais: {geo.get('country_name')} ({geo.get('country_code')})   "
          f"region: {geo.get('region')}   org: {str(geo.get('org'))[:50]}")
except Exception as e:
    print(f"  no se pudo determinar la IP: {str(e)[:80]}")

print("\n  Perpetuos con funding (lo que necesita la estrategia):")
r = {}
r["bybit"] = probar("Bybit", "https://api.bybit.com/v5/market/tickers",
                    {"category": "linear"}, "result.list")
r["binance"] = probar("Binance futuros", "https://fapi.binance.com/fapi/v1/premiumIndex")
r["okx"] = probar("OKX", "https://www.okx.com/api/v5/public/instruments",
                  {"instType": "SWAP"}, "data")
r["gate"] = probar("Gate.io", "https://api.gateio.ws/api/v4/futures/usdt/contracts")
r["mexc"] = probar("MEXC", "https://contract.mexc.com/api/v1/contract/detail", None, "data")
r["bitget"] = probar("Bitget", "https://api.bitget.com/api/v2/mix/market/tickers",
                     {"productType": "usdt-futures"}, "data")
r["kucoin"] = probar("KuCoin futuros",
                     "https://api-futures.kucoin.com/api/v1/contracts/active", None, "data")
r["hyperliquid"] = probar("Hyperliquid (meta)", "https://api.hyperliquid.xyz/info")
r["dydx"] = probar("dYdX v4", "https://indexer.dydx.trade/v4/perpetualMarkets")

print("\n  Datos historicos:")
probar("data.binance.vision", "https://data.binance.vision/")
probar("Bybit funding hist", "https://api.bybit.com/v5/market/funding/history",
       {"category": "linear", "symbol": "BTCUSDT", "limit": 5})
probar("Gate funding hist", "https://api.gateio.ws/api/v4/futures/usdt/funding_rate",
       {"contract": "BTC_USDT", "limit": 5})
probar("MEXC funding hist",
       "https://contract.mexc.com/api/v1/contract/funding_rate/history",
       {"symbol": "BTC_USDT", "page_size": 5})

print("\n" + "=" * 78)
sirven = [k for k, v in r.items() if v]
print(f"  ALCANZABLES: {', '.join(sirven) if sirven else 'NINGUNO'}")
print(f"  BLOQUEADOS : {', '.join(k for k, v in r.items() if not v)}")
print("=" * 78)
if not sirven:
    print("  Ningun exchange responde desde este runner. Hace falta ejecutar")
    print("  desde otra ubicacion (VPS fuera de EEUU, Oracle Cloud free tier,")
    print("  o una maquina propia).")
