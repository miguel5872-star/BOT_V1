"""
Genera index.html: panel interactivo autocontenido.

Sin librerias externas ni peticiones de red: los datos se incrustan en el HTML,
de modo que funciona igual con doble clic en local que servido por GitHub Pages.

Nota sobre la granularidad: el bot marca una vez por ciclo (por defecto cada
hora), asi que la resolucion nativa es esa. No hay datos por minuto ni por
segundo, y el panel no finge tenerlos: ofrece rango temporal y agregacion.

    python grafica.py
"""
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
PAPEL = os.path.join(RAIZ, "papel")
SALIDA = os.path.join(RAIZ, "index.html")
H_TENENCIA = 48


def cargar_curva():
    p = os.path.join(PAPEL, "curva.csv")
    if not os.path.exists(p):
        return pd.DataFrame()
    d = pd.read_csv(p, parse_dates=["fecha"]).drop_duplicates("ts")
    return d.sort_values("ts").reset_index(drop=True)


def cargar_registro():
    p = os.path.join(PAPEL, "registro.jsonl")
    if not os.path.exists(p):
        return [], [], None
    aperturas, cierres, init = [], [], None
    with open(p, encoding="utf-8") as fh:
        for linea in fh:
            try:
                ev = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if ev.get("tipo") == "apertura":
                aperturas.append(ev)
            elif ev.get("tipo") == "cierre":
                cierres.append(ev)
            elif ev.get("tipo") == "init":
                init = ev
    return aperturas, cierres, init


def cargar_estado():
    p = os.path.join(PAPEL, "estado.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def construir_tramos(aperturas, cierres, estado):
    """Une aperturas con cierres para pintar la linea temporal."""
    por_id = {c["tramo"]: c for c in cierres}
    abiertos = {t["id"]: t for t in estado.get("tramos", [])}
    out = []
    for a in aperturas:
        i = a["tramo"]
        c = por_id.get(i)
        out.append({
            "id": i,
            "ini": a["ts"],
            "fin": c["ts"] if c else None,
            "horas": c["horas_reales"] if c else None,
            "ret": c["retorno_bruto"] if c else None,
            "tardio": bool(c.get("cierre_tardio")) if c else False,
            "peso": a.get("peso"),
            "n": len(a.get("largos", [])) + len(a.get("cortos", [])),
            "abierto": i in abiertos,
        })
    return out


def posiciones_abiertas(estado):
    out = []
    for t in estado.get("tramos", []):
        out.append({
            "id": t["id"], "ini": t["abierto_ms"], "peso": t["peso"],
            "largos": sorted(t.get("largos", {}).keys()),
            "cortos": sorted(t.get("cortos", {}).keys()),
        })
    return out


d = cargar_curva()
aperturas, cierres, init = cargar_registro()
estado = cargar_estado()
tramos = construir_tramos(aperturas, cierres, estado)
abiertas = posiciones_abiertas(estado)
capital = (estado.get("capital_inicial")
           or (init or {}).get("capital") or 10000.0)
apal = estado.get("apalancamiento") or (init or {}).get("apalancamiento") or 3.0

datos = {
    "capital": capital,
    "apalancamiento": apal,
    "tenencia": H_TENENCIA,
    "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    "serie": [] if d.empty else [
        {"t": int(r.ts), "p": float(r.patrimonio), "r": float(r.retorno_acum_pct),
         "l": float(r.latente), "e": float(r.efectivo),
         "n": int(r.tramos_abiertos)} for r in d.itertuples()],
    "tramos": tramos,
    "abiertas": abiertas,
    "cierres": [{"t": c["ts"], "id": c["tramo"], "h": c["horas_reales"],
                 "r": c["retorno_bruto"], "peso": c.get("peso"),
                 "tardio": bool(c.get("cierre_tardio")),
                 "nl": c.get("n_largos"), "ns": c.get("n_cortos")}
                for c in cierres],
}

HTML = """<title>Panel — bot de papel de funding</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{
  --bg:#faf9f7; --panel:#ffffff; --linea:#e8e5e0; --linea2:#f2efeb;
  --tx:#1a1917; --tx2:#6a675f; --tx3:#96938a;
  --acento:#2b6cb0; --acentoSuave:rgba(43,108,176,.10);
  --pos:#1f7a4d; --posSuave:rgba(31,122,77,.12);
  --neg:#b3453a; --negSuave:rgba(179,69,58,.12);
  --avisoBg:#fdf6e3; --avisoTx:#8a6d1f; --avisoBd:#e8dcb8;
  --sombra:0 1px 2px rgba(20,18,15,.05),0 1px 8px rgba(20,18,15,.04);
  --r:10px;
}
@media (prefers-color-scheme:dark){:root:not([data-tema="claro"]){
  --bg:#121214; --panel:#1a1a1d; --linea:#2a2a2e; --linea2:#232326;
  --tx:#eceae6; --tx2:#9b988f; --tx3:#6e6b64;
  --acento:#6aa9e0; --acentoSuave:rgba(106,169,224,.12);
  --pos:#5cbd8a; --posSuave:rgba(92,189,138,.14);
  --neg:#e0796e; --negSuave:rgba(224,121,110,.14);
  --avisoBg:#2a2415; --avisoTx:#d9be6a; --avisoBd:#443a1e;
  --sombra:0 1px 2px rgba(0,0,0,.3);
}}
:root[data-tema="oscuro"]{
  --bg:#121214; --panel:#1a1a1d; --linea:#2a2a2e; --linea2:#232326;
  --tx:#eceae6; --tx2:#9b988f; --tx3:#6e6b64;
  --acento:#6aa9e0; --acentoSuave:rgba(106,169,224,.12);
  --pos:#5cbd8a; --posSuave:rgba(92,189,138,.14);
  --neg:#e0796e; --negSuave:rgba(224,121,110,.14);
  --avisoBg:#2a2415; --avisoTx:#d9be6a; --avisoBd:#443a1e;
  --sombra:0 1px 2px rgba(0,0,0,.3);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);
  font:14px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
  padding:22px 18px 60px;-webkit-font-smoothing:antialiased}
.env{max-width:1120px;margin:0 auto}
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}

header{display:flex;align-items:flex-start;justify-content:space-between;
  gap:16px;flex-wrap:wrap;margin-bottom:20px}
h1{font-size:19px;font-weight:640;letter-spacing:-.015em}
.sub{color:var(--tx2);font-size:12.5px;margin-top:3px}
.chip{display:inline-flex;align-items:center;gap:6px;background:var(--panel);
  border:1px solid var(--linea);border-radius:999px;padding:4px 11px;
  font-size:12px;color:var(--tx2)}
.punto{width:6px;height:6px;border-radius:50%;background:var(--pos)}
.btema{background:var(--panel);border:1px solid var(--linea);color:var(--tx2);
  border-radius:8px;padding:6px 11px;cursor:pointer;font-size:12.5px;
  font-family:inherit}
.btema:hover{color:var(--tx);border-color:var(--tx3)}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
  gap:10px;margin-bottom:18px}
.kpi{background:var(--panel);border:1px solid var(--linea);border-radius:var(--r);
  padding:13px 15px;box-shadow:var(--sombra)}
.kpi .et{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--tx3);font-weight:600;margin-bottom:5px}
.kpi .va{font-size:21px;font-weight:600;letter-spacing:-.02em;line-height:1.15}
.kpi .nt{font-size:11.5px;color:var(--tx2);margin-top:3px}
.pos{color:var(--pos)} .neg{color:var(--neg)} .neu{color:var(--tx)}

.barra{display:flex;gap:14px;flex-wrap:wrap;align-items:center;
  margin-bottom:14px}
.grupo{display:flex;align-items:center;gap:7px}
.grupo>span{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--tx3);font-weight:600}
.seg{display:inline-flex;background:var(--panel);border:1px solid var(--linea);
  border-radius:8px;overflow:hidden}
.seg button{background:none;border:none;border-right:1px solid var(--linea);
  color:var(--tx2);padding:5px 11px;font-size:12.5px;cursor:pointer;
  font-family:inherit;font-variant-numeric:tabular-nums}
.seg button:last-child{border-right:none}
.seg button:hover{color:var(--tx);background:var(--linea2)}
.seg button[aria-pressed="true"]{background:var(--acento);color:#fff;
  font-weight:560}

.tarj{background:var(--panel);border:1px solid var(--linea);
  border-radius:var(--r);padding:16px 18px 12px;margin-bottom:14px;
  box-shadow:var(--sombra)}
.tarj h2{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--tx3);font-weight:640;margin-bottom:2px}
.tarj .h2n{font-size:12px;color:var(--tx2);margin-bottom:12px}
.lienzo{position:relative;width:100%}
svg{display:block;width:100%;overflow:visible}
.rej{stroke:var(--linea2);stroke-width:1}
.ejeTx{fill:var(--tx3);font-size:10.5px;font-family:inherit;
  font-variant-numeric:tabular-nums}
.cruz{stroke:var(--tx3);stroke-width:1;stroke-dasharray:3 3}
.tip{position:absolute;pointer-events:none;background:var(--panel);
  border:1px solid var(--linea);border-radius:8px;padding:8px 11px;
  font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.14);white-space:nowrap;
  opacity:0;transition:opacity .1s;z-index:5}
.tip b{font-weight:600;font-variant-numeric:tabular-nums}
.tip .f{color:var(--tx3);font-size:11px;margin-bottom:3px}

table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th{text-align:left;font-size:10.5px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--tx3);font-weight:640;padding:0 12px 8px 0;
  white-space:nowrap}
td{padding:7px 12px 7px 0;border-top:1px solid var(--linea2);font-size:13px}
tbody tr:hover{background:var(--linea2)}
.der{text-align:right}
.eti{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:5px;
  background:var(--avisoBg);color:var(--avisoTx);border:1px solid var(--avisoBd);
  font-weight:560}
.simb{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}
.simb span{font-size:11px;background:var(--linea2);color:var(--tx2);
  padding:2px 6px;border-radius:5px;font-family:ui-monospace,monospace}
details{margin-top:8px}
summary{cursor:pointer;font-size:12px;color:var(--tx2);list-style:none}
summary::-webkit-details-marker{display:none}
summary:before{content:"▸ ";color:var(--tx3)}
details[open] summary:before{content:"▾ "}
.vacio{padding:34px;text-align:center;color:var(--tx2);font-size:13.5px}
.aviso{background:var(--avisoBg);border:1px solid var(--avisoBd);
  color:var(--avisoTx);border-radius:var(--r);padding:11px 14px;
  font-size:12.5px;margin-bottom:14px}
footer{color:var(--tx3);font-size:11.5px;margin-top:26px;
  border-top:1px solid var(--linea);padding-top:14px;line-height:1.65}
.dosCol{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:800px){.dosCol{grid-template-columns:1fr}}
</style>

<div class="env">
  <header>
    <div>
      <h1>Bot de papel · momentum de funding</h1>
      <div class="sub" id="sub"></div>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
      <span class="chip"><span class="punto"></span><span id="estado"></span></span>
      <button class="btema" id="btema">Tema</button>
    </div>
  </header>

  <div id="avisos"></div>
  <div class="kpis" id="kpis"></div>

  <div class="barra">
    <div class="grupo"><span>Rango</span>
      <div class="seg" id="rango"></div></div>
    <div class="grupo"><span>Agregación</span>
      <div class="seg" id="agreg"></div></div>
  </div>

  <div class="tarj">
    <h2>Patrimonio</h2>
    <div class="h2n" id="tituloEq"></div>
    <div class="lienzo" id="cEq"><div class="tip" id="tipEq"></div></div>
  </div>

  <div class="dosCol">
    <div class="tarj">
      <h2>Drawdown</h2>
      <div class="h2n">Caída desde el máximo previo</div>
      <div class="lienzo" id="cDd"><div class="tip" id="tipDd"></div></div>
    </div>
    <div class="tarj">
      <h2>Retorno por periodo</h2>
      <div class="h2n" id="tituloBar"></div>
      <div class="lienzo" id="cBar"><div class="tip" id="tipBar"></div></div>
    </div>
  </div>

  <div class="tarj">
    <h2>Línea temporal de tramos</h2>
    <div class="h2n">Tres carteras solapadas, cada una con 48 h de tenencia,
      abriéndose cada 16 h</div>
    <div class="lienzo" id="cTr"><div class="tip" id="tipTr"></div></div>
  </div>

  <div class="tarj" id="tAb"></div>
  <div class="tarj" id="tCi"></div>

  <footer>
    <b>Estrategia</b> · funding acumulado de 72 h sobre los perpetuos USDT con
    volumen suficiente; largo el 20% con la señal más alta, corto el 20% más
    baja, mismo nocional en cada pata. Tres tramos solapados de 48 h.
    Costes aplicados: 0,05% de comisión y 0,05% de deslizamiento por lado.<br>
    <b>Datos</b> · API pública de producción de Bybit. Dinero ficticio.
    El registro encadena hashes SHA-256; <code>python bot.py verificar</code>
    comprueba que no se ha reescrito.<br>
    Esto no es asesoramiento financiero.
  </footer>
</div>

<script>
const D = __DATOS__;
const $ = s => document.querySelector(s);
const fnum = (v,d=2) => v.toLocaleString('es-ES',{minimumFractionDigits:d,maximumFractionDigits:d});
const fpc  = (v,d=2) => (v>=0?'+':'') + fnum(v,d) + '%';
const fh   = t => new Date(t).toLocaleString('es-ES',{day:'2-digit',month:'short',
              hour:'2-digit',minute:'2-digit',timeZone:'UTC'});
const fd   = t => new Date(t).toLocaleDateString('es-ES',{day:'2-digit',month:'short',timeZone:'UTC'});

let RANGO = 'todo', AGREG = 'nativa';
const RANGOS = [['24h',24],['7d',24*7],['30d',24*30],['todo',null]];
const AGREGS = [['nativa',0],['1h',1],['4h',4],['1d',24]];

/* ── tema ─────────────────────────────────────────────────── */
$('#btema').onclick = () => {
  const r = document.documentElement;
  const a = r.getAttribute('data-tema');
  const oscuro = a ? a==='oscuro'
    : matchMedia('(prefers-color-scheme:dark)').matches;
  r.setAttribute('data-tema', oscuro ? 'claro' : 'oscuro');
  pintar();
};

/* ── preparacion de datos ─────────────────────────────────── */
function filtrada(){
  let s = D.serie;
  if(!s.length) return [];
  const h = RANGOS.find(r=>r[0]===RANGO)[1];
  if(h){ const corte = s[s.length-1].t - h*3600e3; s = s.filter(p=>p.t>=corte); }
  const paso = AGREGS.find(a=>a[0]===AGREG)[1];
  if(paso>0 && s.length>1){
    const ms = paso*3600e3, cubos = new Map();
    s.forEach(p=>{ cubos.set(Math.floor(p.t/ms)*ms, p); });
    s = [...cubos.entries()].sort((a,b)=>a[0]-b[0]).map(([k,v])=>({...v,t:k}));
  }
  return s;
}
function serieDd(s){
  let pico = -Infinity;
  return s.map(p=>{ pico = Math.max(pico,p.p); return {t:p.t, v:(p.p/pico-1)*100}; });
}
function barras(s){
  if(s.length<2) return [];
  const paso = AGREGS.find(a=>a[0]===AGREG)[1] || 24;
  const ms = Math.max(paso,1)*3600e3, cubos = new Map();
  s.forEach(p=>{ const k = Math.floor(p.t/ms)*ms;
    if(!cubos.has(k)) cubos.set(k,{ini:p.p,fin:p.p}); else cubos.get(k).fin = p.p; });
  const arr = [...cubos.entries()].sort((a,b)=>a[0]-b[0]);
  const out = [];
  for(let i=1;i<arr.length;i++)
    out.push({t:arr[i][0], v:(arr[i][1].fin/arr[i-1][1].fin-1)*100});
  return out;
}

/* ── motor de graficos ────────────────────────────────────── */
function ejeY(min,max,n=4){
  if(min===max){min-=1;max+=1;}
  const paso=(max-min)/n, out=[];
  for(let i=0;i<=n;i++) out.push(min+paso*i);
  return out;
}
function marcoX(s,W){
  if(s.length<2) return [];
  const t0=s[0].t,t1=s[s.length-1].t, out=[];
  for(const f of [0,.25,.5,.75,1]){
    const t=t0+(t1-t0)*f;
    out.push({x:f*W, txt:(t1-t0)>3*86400e3?fd(t):fh(t)});
  }
  return out;
}
function linea(cont,tip,datos,acc,color,relleno,sufijo,fmt){
  cont.querySelectorAll('svg').forEach(e=>e.remove());
  if(datos.length<2){
    const v=document.createElement('div'); v.className='vacio';
    v.textContent='Hacen falta al menos 2 marcas para dibujar.';
    v.dataset.tmp='1'; cont.querySelectorAll('[data-tmp]').forEach(e=>e.remove());
    cont.appendChild(v); return;
  }
  cont.querySelectorAll('[data-tmp]').forEach(e=>e.remove());
  const W=Math.max(cont.clientWidth||900,320),H=230,PL=54,PB=22;
  const xs=datos.map(d=>d.t), ys=datos.map(acc);
  const t0=xs[0],t1=xs[xs.length-1];
  let y0=Math.min(...ys),y1=Math.max(...ys);
  // el margen se calcula sobre el RANGO, no sobre el valor absoluto: si no,
  // una curva alrededor de 10.000 se aplasta contra un eje de +-200
  const rango=y1-y0;
  const m=rango>0?rango*.14:Math.max(Math.abs(y1)*.001,1e-6);
  y0-=m; y1+=m;
  if(sufijo==='%'){ if(y0>0) y0=0; if(y1<0) y1=0; }
  const px=t=>PL+(t-t0)/(t1-t0||1)*(W-PL);
  const py=v=>(H-PB)-(v-y0)/(y1-y0||1)*(H-PB);
  const pts=datos.map((d,i)=>`${px(xs[i]).toFixed(1)},${py(ys[i]).toFixed(1)}`).join(' ');
  const base=py(Math.max(y0,Math.min(0,y1)));
  let g='';
  for(const v of ejeY(y0,y1)){
    const y=py(v);
    g+=`<line x1="${PL}" y1="${y.toFixed(1)}" x2="${W}" y2="${y.toFixed(1)}" class="rej"/>`+
       `<text x="${PL-7}" y="${(y+3.5).toFixed(1)}" class="ejeTx" text-anchor="end">${fmt(v)}</text>`;
  }
  for(const t of marcoX(datos,W-PL))
    g+=`<text x="${(PL+t.x).toFixed(0)}" y="${H-4}" class="ejeTx" text-anchor="middle">${t.txt}</text>`;
  const svg=`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
    ${g}
    <polygon points="${PL},${base.toFixed(1)} ${pts} ${W},${base.toFixed(1)}" fill="${relleno}"/>
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.8"
      stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
    <g id="hov"><line class="cruz" y1="0" y2="${H-PB}" style="opacity:0"/>
      <circle r="3.5" fill="${color}" style="opacity:0"/></g>
    <rect x="${PL}" y="0" width="${W-PL}" height="${H-PB}" fill="transparent" id="cap"/>
  </svg>`;
  cont.insertAdjacentHTML('afterbegin',svg);
  const s=cont.querySelector('svg'), hov=s.querySelector('#hov'),
        ln=hov.querySelector('line'), ci=hov.querySelector('circle');
  s.querySelector('#cap').addEventListener('mousemove',ev=>{
    const r=s.getBoundingClientRect();
    const tx=t0+((ev.clientX-r.left)/r.width*W-PL)/(W-PL)*(t1-t0);
    let k=0,mej=Infinity;
    datos.forEach((d,i)=>{const dd=Math.abs(d.t-tx); if(dd<mej){mej=dd;k=i;}});
    const X=px(xs[k]),Y=py(ys[k]);
    ln.setAttribute('x1',X); ln.setAttribute('x2',X); ln.style.opacity=.6;
    ci.setAttribute('cx',X); ci.setAttribute('cy',Y); ci.style.opacity=1;
    tip.innerHTML=`<div class="f">${fh(datos[k].t)} UTC</div><b>${fmt(ys[k])}</b>`;
    tip.style.opacity=1;
    const izq=(X/W)*r.width;
    tip.style.left=Math.min(Math.max(izq-tip.offsetWidth/2,0),r.width-tip.offsetWidth)+'px';
    tip.style.top=Math.max((Y/H)*r.height-tip.offsetHeight-10,0)+'px';
  });
  s.addEventListener('mouseleave',()=>{tip.style.opacity=0;
    ln.style.opacity=0; ci.style.opacity=0;});
}
function barrasGraf(cont,tip,datos){
  cont.querySelectorAll('svg,[data-tmp]').forEach(e=>e.remove());
  if(!datos.length){
    cont.insertAdjacentHTML('afterbegin',
      '<div class="vacio" data-tmp="1">Aún no hay periodos completos.</div>'); return;
  }
  const W=Math.max(cont.clientWidth||900,320),H=230,PL=54,PB=22;
  const ys=datos.map(d=>d.v);
  let y0=Math.min(0,...ys),y1=Math.max(0,...ys);
  const m=Math.max((y1-y0)*.16,1e-6); y0-=m; y1+=m;
  const py=v=>(H-PB)-(v-y0)/(y1-y0||1)*(H-PB);
  const an=Math.max((W-PL)/datos.length*.62,1.5);
  let g='';
  for(const v of ejeY(y0,y1)){
    const y=py(v);
    g+=`<line x1="${PL}" y1="${y.toFixed(1)}" x2="${W}" y2="${y.toFixed(1)}" class="rej"/>`+
       `<text x="${PL-7}" y="${(y+3.5).toFixed(1)}" class="ejeTx" text-anchor="end">${fpc(v,2)}</text>`;
  }
  const c0=py(0);
  datos.forEach((d,i)=>{
    const x=PL+(i+.5)/datos.length*(W-PL), y=py(d.v);
    const col=d.v>=0?'var(--pos)':'var(--neg)';
    g+=`<rect x="${(x-an/2).toFixed(1)}" y="${Math.min(y,c0).toFixed(1)}"
        width="${an.toFixed(1)}" height="${Math.max(Math.abs(y-c0),1).toFixed(1)}"
        fill="${col}" rx="1" data-i="${i}"/>`;
  });
  for(const t of marcoX(datos,W-PL))
    g+=`<text x="${(PL+t.x).toFixed(0)}" y="${H-4}" class="ejeTx" text-anchor="middle">${t.txt}</text>`;
  cont.insertAdjacentHTML('afterbegin',
    `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${g}</svg>`);
  const s=cont.querySelector('svg'), r0=()=>s.getBoundingClientRect();
  s.querySelectorAll('rect[data-i]').forEach(rect=>{
    rect.addEventListener('mousemove',ev=>{
      const d=datos[+rect.dataset.i], r=r0();
      tip.innerHTML=`<div class="f">${fd(d.t)} UTC</div><b class="${d.v>=0?'pos':'neg'}">${fpc(d.v,3)}</b>`;
      tip.style.opacity=1;
      tip.style.left=Math.min(Math.max(ev.clientX-r.left-tip.offsetWidth/2,0),r.width-tip.offsetWidth)+'px';
      tip.style.top=Math.max(ev.clientY-r.top-tip.offsetHeight-12,0)+'px';
    });
  });
  s.addEventListener('mouseleave',()=>tip.style.opacity=0);
}
function timeline(cont,tip){
  cont.querySelectorAll('svg,[data-tmp]').forEach(e=>e.remove());
  const tr=D.tramos;
  if(!tr.length){ cont.insertAdjacentHTML('afterbegin',
    '<div class="vacio" data-tmp="1">Todavía no se ha abierto ningún tramo.</div>'); return; }
  const ahora=Date.now();
  const t0=Math.min(...tr.map(t=>t.ini));
  const t1=Math.max(ahora,...tr.map(t=>t.fin||ahora));
  const W=Math.max(cont.clientWidth||900,320),fila=26,H=tr.length*fila+30,PL=54;
  const px=t=>PL+(t-t0)/(t1-t0||1)*(W-PL);
  let g='';
  for(const f of [0,.25,.5,.75,1]){
    const x=PL+f*(W-PL), t=t0+(t1-t0)*f;
    g+=`<line x1="${x.toFixed(0)}" y1="0" x2="${x.toFixed(0)}" y2="${H-26}" class="rej"/>`+
       `<text x="${x.toFixed(0)}" y="${H-8}" class="ejeTx" text-anchor="middle">${fd(t)}</text>`;
  }
  tr.forEach((t,i)=>{
    const y=i*fila+6, x1=px(t.ini), x2=px(t.fin||ahora);
    const col=t.abierto?'var(--acento)':(t.ret>=0?'var(--pos)':'var(--neg)');
    const op=t.abierto?.55:.85;
    g+=`<text x="${PL-7}" y="${y+13}" class="ejeTx" text-anchor="end">T${t.id}</text>`+
       `<rect x="${x1.toFixed(1)}" y="${y}" width="${Math.max(x2-x1,3).toFixed(1)}"
        height="15" rx="4" fill="${col}" opacity="${op}" data-i="${i}"/>`;
    if(t.tardio) g+=`<text x="${(x2+5).toFixed(1)}" y="${y+12}" class="ejeTx"
        fill="var(--avisoTx)">tardío</text>`;
  });
  cont.insertAdjacentHTML('afterbegin',
    `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${g}</svg>`);
  const s=cont.querySelector('svg');
  s.querySelectorAll('rect[data-i]').forEach(rect=>{
    rect.addEventListener('mousemove',ev=>{
      const t=tr[+rect.dataset.i], r=s.getBoundingClientRect();
      tip.innerHTML=`<div class="f">Tramo ${t.id} · ${t.n} posiciones · peso ${fnum(t.peso,2)}x</div>`+
        (t.abierto?`abierto desde ${fh(t.ini)}<br><b>en curso</b>`
          :`${fh(t.ini)} → ${fh(t.fin)}<br><b class="${t.ret>=0?'pos':'neg'}">${fpc(t.ret*100,3)}</b> en ${fnum(t.horas,1)} h`);
      tip.style.opacity=1;
      tip.style.left=Math.min(Math.max(ev.clientX-r.left-tip.offsetWidth/2,0),r.width-tip.offsetWidth)+'px';
      tip.style.top=Math.max(ev.clientY-r.top-tip.offsetHeight-12,0)+'px';
    });
  });
  s.addEventListener('mouseleave',()=>tip.style.opacity=0);
}

/* ── metricas y tablas ────────────────────────────────────── */
function kpis(s){
  const c=$('#kpis');
  if(!s.length){ c.innerHTML=''; return; }
  const ult=s[s.length-1], pri=s[0];
  const dd=serieDd(s), ddmin=Math.min(...dd.map(d=>d.v));
  const porDia=new Map();
  D.serie.forEach(p=>porDia.set(new Date(p.t).toISOString().slice(0,10),p.p));
  const dias=[...porDia.entries()].sort();
  const rets=[]; for(let i=1;i<dias.length;i++) rets.push(dias[i][1]/dias[i-1][1]-1);
  const med=rets.length?rets.reduce((a,b)=>a+b,0)/rets.length:0;
  const sd=rets.length>1?Math.sqrt(rets.reduce((a,b)=>a+(b-med)**2,0)/(rets.length-1)):0;
  const sharpe=sd>0?med/sd*Math.sqrt(365):null;
  const pos=rets.length?rets.filter(r=>r>0).length/rets.length*100:null;
  const rr=(ult.p/pri.p-1)*100;
  const expo=ult.n*(D.apalancamiento/3);
  const tarj=(et,va,cl,nt)=>`<div class="kpi"><div class="et">${et}</div>
    <div class="va ${cl||'neu'}">${va}</div>${nt?`<div class="nt">${nt}</div>`:''}</div>`;
  c.innerHTML =
    tarj('Patrimonio', fnum(ult.p)+' <span style="font-size:13px;color:var(--tx2)">USDT</span>','neu',
         'Capital inicial '+fnum(D.capital,0)) +
    tarj('Retorno del rango', fpc(rr,3), rr>=0?'pos':'neg', RANGO==='todo'?'desde el inicio':'últimas '+RANGO) +
    tarj('Retorno total', fpc(ult.r,3), ult.r>=0?'pos':'neg','acumulado') +
    tarj('Max drawdown', fnum(ddmin,2)+'%', ddmin<-0.001?'neg':'neu','en el rango') +
    tarj('Sharpe', sharpe===null?'—':fnum(sharpe,2), sharpe===null?'neu':(sharpe>0?'pos':'neg'),
         rets.length>2?`${rets.length} días`:'faltan días') +
    tarj('Días positivos', pos===null?'—':fnum(pos,0)+'%','neu', rets.length+' días') +
    tarj('Exposición', fnum(expo,2)+'x','neu', ult.n+' de 3 tramos') +
    tarj('Latente', fnum(ult.l,2),Math.abs(ult.l)<.005?'neu':(ult.l>=0?'pos':'neg'),'sin realizar');
}
function tablas(){
  const ab=D.abiertas;
  $('#tAb').innerHTML = `<h2>Posiciones abiertas</h2>
    <div class="h2n">${ab.length} tramo${ab.length===1?'':'s'} en curso</div>` +
    (ab.length? ab.map(t=>{
      const edad=(Date.now()-t.ini)/3600e3;
      return `<div style="padding:9px 0;border-top:1px solid var(--linea2)">
        <b>Tramo ${t.id}</b> · peso ${fnum(t.peso,2)}x ·
        <span class="num">${fnum(edad,1)} h</span> de ${D.tenencia} h
        <span style="color:var(--tx2)">(cierra en ${fnum(Math.max(D.tenencia-edad,0),1)} h)</span>
        <details><summary>${t.largos.length} largos · ${t.cortos.length} cortos</summary>
          <div style="margin-top:7px;font-size:11.5px;color:var(--pos)">LARGOS</div>
          <div class="simb">${t.largos.map(s=>`<span>${s.replace('USDT','')}</span>`).join('')}</div>
          <div style="margin-top:9px;font-size:11.5px;color:var(--neg)">CORTOS</div>
          <div class="simb">${t.cortos.map(s=>`<span>${s.replace('USDT','')}</span>`).join('')}</div>
        </details></div>`;}).join('')
      : '<div class="vacio">Sin posiciones abiertas.</div>');

  const ci=[...D.cierres].reverse();
  const tardios=ci.filter(c=>c.tardio).length;
  $('#tCi').innerHTML = `<h2>Cierres de tramo</h2>
    <div class="h2n">${ci.length} cerrado${ci.length===1?'':'s'}${tardios?` · ${tardios} con retraso`:''}</div>` +
    (ci.length? `<table><thead><tr><th>Cierre</th><th>Tramo</th><th>Duración</th>
      <th class="der">Bruto</th><th class="der">Cesta</th></tr></thead><tbody>` +
      ci.slice(0,25).map(c=>`<tr><td>${fh(c.t)}</td><td>T${c.id}</td>
        <td>${fnum(c.h,1)} h ${c.tardio?'<span class="eti">tardío</span>':''}</td>
        <td class="der ${c.r>=0?'pos':'neg'}">${fpc(c.r*100,3)}</td>
        <td class="der">${c.nl}L / ${c.ns}C</td></tr>`).join('') + '</tbody></table>'
      : '<div class="vacio">Ningún tramo ha cerrado todavía. El primero vence a las 48 h.</div>');
}
function avisos(){
  const a=[], s=D.serie;
  const ab=D.abiertas.length;
  if(ab<3) a.push(`Solo hay <b>${ab} de 3 tramos</b> abiertos: la exposición es
    ${fnum(ab*(D.apalancamiento/3),2)}x en vez de ${fnum(D.apalancamiento,0)}x y la volatilidad
    es mayor que la de la estrategia validada. Se completa en las primeras 32 h.`);
  const dias=new Set(s.map(p=>new Date(p.t).toISOString().slice(0,10))).size;
  if(dias<14) a.push(`Llevas <b>${dias} día${dias===1?'':'s'}</b> de registro. El retorno
    esperado es +0,185% diario contra 0,67% de volatilidad, así que el ruido supera
    a la señal por tres en el corto plazo: no interpretes nada antes de dos semanas.`);
  const t=D.cierres.filter(c=>c.tardio).length;
  if(t) a.push(`<b>${t} cierre${t===1?'':'s'} con retraso</b>: hubo huecos de ejecución
    y esos tramos duraron más de 48 h.`);
  $('#avisos').innerHTML=a.map(x=>`<div class="aviso">${x}</div>`).join('');
}

/* ── render ───────────────────────────────────────────────── */
function segmentos(){
  $('#rango').innerHTML=RANGOS.map(([k])=>
    `<button data-k="${k}" aria-pressed="${k===RANGO}">${k}</button>`).join('');
  $('#agreg').innerHTML=AGREGS.map(([k])=>
    `<button data-k="${k}" aria-pressed="${k===AGREG}">${k}</button>`).join('');
  $('#rango').querySelectorAll('button').forEach(b=>b.onclick=()=>{RANGO=b.dataset.k;pintar();});
  $('#agreg').querySelectorAll('button').forEach(b=>b.onclick=()=>{AGREG=b.dataset.k;pintar();});
}
function pintar(){
  segmentos();
  const s=filtrada();
  $('#sub').innerHTML = D.serie.length
    ? `${D.serie.length} marcas · desde ${fh(D.serie[0].t)} UTC · generado ${D.generado} UTC`
    : 'Sin datos todavía';
  $('#estado').textContent = D.abiertas.length
    ? `${D.abiertas.length}/3 tramos activos` : 'en espera';
  $('#tituloEq').textContent = `Valor de la cartera · ${s.length} puntos`;
  $('#tituloBar').textContent = AGREG==='nativa'
    ? 'Variación entre marcas consecutivas' : `Variación por bloque de ${AGREG}`;
  avisos(); kpis(s); tablas();
  const rg = s.length? Math.max(...s.map(p=>p.p))-Math.min(...s.map(p=>p.p)) : 1;
  const dec = rg>=200?0 : rg>=20?1 : rg>=2?2 : 3;
  linea($('#cEq'),$('#tipEq'),s,p=>p.p,'var(--acento)','var(--acentoSuave)','',
        v=>fnum(v,dec));
  const dd=serieDd(s);
  linea($('#cDd'),$('#tipDd'),dd,p=>p.v,'var(--neg)','var(--negSuave)','%',
        v=>fnum(v,2)+'%');
  barrasGraf($('#cBar'),$('#tipBar'),barras(s));
  timeline($('#cTr'),$('#tipTr'));
}
pintar();
let temporizador;
addEventListener('resize',()=>{clearTimeout(temporizador);
  temporizador=setTimeout(pintar,140);});
</script>
"""

html = HTML.replace("__DATOS__", json.dumps(datos, ensure_ascii=False,
                                            separators=(",", ":")))
with open(SALIDA, "w", encoding="utf-8") as fh:
    fh.write(html)
print(f"Panel generado: {SALIDA}  ({len(html)/1024:.0f} KB, "
      f"{len(datos['serie'])} marcas, {len(datos['cierres'])} cierres)")
