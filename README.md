# Bot de papel — momentum de funding

Registro público y verificable de una estrategia de mercado neutral sobre
perpetuos de altcoin. **Dinero ficticio.** No es asesoramiento financiero.

## Estado actual

<!--ESTADO-->
| Metrica | Valor |
|---|---|
| Patrimonio | **9,993.47 USDT** |
| Retorno acumulado | **-0.065%** |
| Max drawdown | -0.70% |
| Marcas / dias | 8 / 1 |
| Tramos abiertos | 2/3 |
| Cierres tardios | 0 |

Ultima actualizacion: **2026-08-18 03:31 UTC**  
Hash del registro: `7aab9c5f803321c57c81ca367921cd826c5ab7f1`
<!--/ESTADO-->

## Estado del despliegue

**El cron de GitHub Actions esta desactivado.** Los runners de GitHub corren en
Azure US y los dos exchanges donde la estrategia tiene senal explotable
rechazan esas IP:

```
Bybit    HTTP 403  "CloudFront is configured to block access from your country"
Binance  HTTP 451  "Service unavailable from a restricted location"
```

Se probaron los exchanges que si responden desde el runner, y la senal alli es
mucho mas debil:

| Exchange | Simbolos | Sharpe | Correlacion con Binance |
|---|---|---|---|
| Binance | 345 | 6,59 | — |
| Bybit | 391 | 5,27 | +0,58 |
| Bitget | 404 | 1,56 | +0,34 |
| Gate.io | 203 | 1,59 | +0,11 |
| MEXC | 161 | 1,13 | +0,26 |

Bitget tiene tantos simbolos como Bybit y aun asi rinde un tercio, luego no es
un problema de tamano del universo: en los mercados profundos el funding
refleja presion real de posicionamiento, mientras que en los secundarios el
perpetuo sigue a Binance y su funding es una senal rezagada.

Para reactivarlo hace falta un runner fuera de EEUU. Ver `diagnostico.py` y
`diagnostico_resultado.txt`.

## Qué hace

Ordena unos 400 perpetuos USDT por el funding acumulado de las últimas 72 horas,
residualizado contra el retorno de 72 horas. Se pone largo del 20% con la señal
más alta y corto del 20% más bajo, con el mismo nocional en cada pata, así que la
exposición neta al mercado es cero por construcción.

Mantiene tres sub-carteras solapadas con 48 horas de tenencia, abriendo una nueva
cada 16 horas. Ese solapamiento es lo que elimina el riesgo de fase: una sola
cartera rebalanceada cada 48 h da resultados muy distintos según el día en que
empiece.

| Parámetro | Valor |
|---|---|
| Universo | perpetuos USDT de Bybit con volumen ≥ 250.000 USDT/24h |
| Señal | funding 72h residualizado contra retorno 72h, por rangos |
| Selección | 20% superior en largo, 20% inferior en corto |
| Tenencia | 48 h, en 3 tramos desfasados 16 h |
| Filtro | descarta \|funding 72h\| > 0,5% |
| Apalancamiento | 3x |
| Costes aplicados | 0,05% comisión + 0,05% deslizamiento por lado |

## Arquitectura y por qué

**La señal y los precios vienen de la API pública de producción de Bybit**, sin
cuenta, sin clave y sin KYC. No se usa ninguna testnet para generar la señal, y
por una razón medida: en la testnet de Bybit el volumen mediano de 24 h es 0 y
solo el 9,6% de los precios están dentro de ±1% del real. En la de Binance los
precios sí son fieles (100% dentro de ±1%) pero el funding tiene una dispersión
3,5 veces mayor que la real y una correlación de rango de solo +0,43 — y el
funding *es* la señal.

**La ejecución es simulada en local** contra precios reales, con comisión y
deslizamiento explícitos. Eso mide el rendimiento sin depender de liquidez
ficticia.

## Verificabilidad

Cada evento de `papel/registro.jsonl` incluye el hash SHA-256 del anterior, así
que forma una cadena. El workflow hace commit tras cada ciclo, con lo que las
posiciones quedan con marca de tiempo del servidor de GitHub **antes** de que se
conozca el resultado. Reescribir el pasado rompe la cadena y `verificar` lo
detecta.

```bash
python bot.py verificar
```

## Ficheros

| Fichero | Contenido |
|---|---|
| `papel/curva.csv` | una fila por marca: patrimonio, latente, retorno acumulado |
| `papel/registro.jsonl` | eventos encadenados: aperturas, cierres, marcas |
| `papel/estado.json` | posiciones vivas |

Los cierres registran las horas reales de tenencia y se marcan como
`cierre_tardio` si superan las 48 h previstas más 2 de margen, de modo que
cualquier hueco de ejecución queda declarado en lugar de disimulado.

## Uso local

```bash
pip install -r requirements.txt
python bot.py step
python bot.py report
python bot.py posiciones
```

## Expectativa

El backtest sobre 105 días dio Sharpe 5,27 con datos de Bybit y 6,59 con datos
de Binance, correlación +0,58 entre ambos. La expectativa realista en operación
es Sharpe 2-3: el backtest no incluye deslizamiento real, ni límites de
capacidad, ni un giro de régimen. Este registro existe para medir esa diferencia.
