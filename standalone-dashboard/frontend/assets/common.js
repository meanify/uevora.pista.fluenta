// Shared helpers for the dashboards: header, API access, formatting, charts.
const PAGES=[['index.html','Início'],['01_pulso_alentejo.html','Pulso do Alentejo'],['02_raio_x_concelho.html','Raio-X do concelho'],
['03_radar_mercados.html','Radar de mercados'],['04_mapa_oportunidades.html','Mapa de oportunidades'],['05_alentejo_em_numeros.html','Alentejo em números'],
['06_barometro_empresario.html','Barómetro do empresário'],['07_noites_e_quartos.html','Noites e quartos']];
const MESES=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
const MESES_LONGOS=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];

(function header(){
  const page=location.pathname.split('/').pop()||'index.html';
  const el=document.querySelector('header.top');
  if(!el)return;
  el.innerHTML='<div class="top-in"><div class="brand">Turismo no Alentejo<small>Pista Digital · Universidade de Évora · fonte INE</small></div><nav class="pages" aria-label="Dashboards">'+
    PAGES.map(([h,t])=>'<a href="'+h+'"'+(h===page?' aria-current="page"':'')+'>'+t+'</a>').join('')+'</nav></div>';
})();

const V=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C={anil:V('--anil'),ocre:V('--ocre'),oliva:V('--oliva'),neg:V('--neg'),ink2:V('--ink-2'),ink3:V('--ink-3'),grid:V('--grid'),surface:V('--surface'),soft:V('--anil-soft')};
if(window.Chart){
  Chart.defaults.locale='pt-PT';Chart.defaults.color=C.ink3;Chart.defaults.font.family='"Public Sans",system-ui,sans-serif';Chart.defaults.font.size=11;
  Chart.defaults.plugins.legend.display=false;Chart.defaults.maintainAspectRatio=false;Chart.defaults.responsive=true;
  // Only change the duration: replacing Chart.defaults.animation drops the colour
  // interpolator, and any chart updated mid-animation then throws "this._fn is not a function".
  Chart.defaults.animation.duration=matchMedia('(prefers-reduced-motion: reduce)').matches?0:400;
}
const AX=(o={})=>({x:{grid:{display:false},ticks:{autoSkip:false},...(o.x||{})},y:{grid:{color:C.grid},border:{display:false},...(o.y||{})}});
const HAX=(o={})=>({x:{grid:{color:C.grid},border:{display:false},...(o.x||{})},y:{grid:{display:false},...(o.y||{})}});
function alpha(hex,a){const h=hex.replace('#','');const n=parseInt(h.length===3?h.split('').map(c=>c+c).join(''):h,16);return `rgba(${n>>16&255},${n>>8&255},${n&255},${a})`}

const isNum=v=>typeof v==='number'&&isFinite(v);
const fmt=(v,d=0)=>isNum(v)?Number(v).toLocaleString('pt-PT',{minimumFractionDigits:d,maximumFractionDigits:d}):'–';
const fmtPct=(v,d=1)=>isNum(v)?fmt(v,d)+'%':'–';
// Signed number; a value that rounds to zero gets no sign ("0,0%", never "−0,0%").
const fmtSigned=(v,d=1,suf='%')=>{if(!isNum(v))return '–';const r=Number(v.toFixed(d));return (r>0?'+':r<0?'−':'')+fmt(Math.abs(r),d)+suf};
function fmtBig(v){if(!isNum(v))return '–';const a=Math.abs(v);
  if(a>=1e9)return fmt(v/1e9,2)+' mil M';if(a>=1e6)return fmt(v/1e6,2)+' M';if(a>=1e4)return fmt(v/1e3,0)+' mil';return fmt(v,0)}
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Shorter INE country labels for chart axes.
const SHORT={'Reino Unido da Grã-Bretanha e Irlanda do Norte':'Reino Unido','Estados Unidos da América':'EUA','Países Baixos (Reino dos)':'Países Baixos','Coreia (República da)':'Coreia do Sul','Região Autónoma da Madeira':'Madeira','Região Autónoma dos Açores':'Açores','Área Metropolitana de Lisboa':'A. M. Lisboa'};
const short=s=>SHORT[s]||s;

// Sets the text and class of a KPI delta: positive is good unless invert is true.
function delta(el,v,text,invert=false){el.textContent=text;el.classList.remove('up','dn');if(isNum(v)&&v!==0)el.classList.add((v>0)!==invert?'up':'dn')}
const $=id=>document.getElementById(id);
const setText=(id,t)=>{$(id).textContent=t};

function params(){return Object.fromEntries(new URLSearchParams(location.search))}
function saveParams(p){const q=new URLSearchParams(p).toString();history.replaceState(null,'',q?'?'+q:location.pathname)}

function status(msg,err=false){const el=$('status');if(!el)return;el.textContent=msg||'';el.classList.toggle('err',!!err)}
const RESTART='O servidor dos dashboards está a correr uma versão antiga do código. Pare-o (Ctrl+C) e volte a iniciá-lo em standalone-dashboard com: ../.venv/bin/python dashboards.py — depois recarregue a página.';
let staleServer=false;
async function api(name,p={}){
  document.body.classList.add('loading');
  try{
    const r=await fetch('/api/'+name+'?'+new URLSearchParams(p));
    let j;try{j=await r.json()}catch(e){throw new Error('Resposta inválida do servidor ('+r.status+').')}
    // An old server has no route for new dashboards and sends no "versao".
    if(r.status===404&&/desconhecido/.test(j.erro||''))throw new Error(RESTART);
    if(!r.ok)throw new Error(j.erro||('Erro '+r.status));
    staleServer=staleServer||j.servidor_desatualizado===true||!('versao' in j);
    if(staleServer)status(RESTART,true);else if(window.Chart)status('');
    return j;
  }catch(e){
    status(e.message.includes('fetch')?'Não foi possível contactar o servidor dos dashboards. Inicie-o com: python dashboards.py':e.message,true);throw e;
  }finally{document.body.classList.remove('loading')}
}
// Error handler for a page's init()/load(): API errors are already shown by
// api(); a drawing error (often a page newer than the server) is shown here.
function fail(e){
  console.error(e);
  const el=$('status');if(el&&el.classList.contains('err')&&el.textContent)return;
  status('Não foi possível desenhar a página ('+(e&&e.message||e)+'). '+(staleServer?RESTART:'Se os ficheiros foram atualizados, reinicie o servidor dos dashboards e recarregue a página.'),true);
}
// Filter handlers call load() without .catch(); surface their errors too.
addEventListener('unhandledrejection',e=>fail(e.reason));
// Like api(), but resolves to null when a newer call started meanwhile, so a
// slow old response never redraws over the charts of a newer filter choice.
let apiSeq=0;
async function apiLatest(name,p={}){const my=++apiSeq;const j=await api(name,p);return my===apiSeq?j:null}

function fillSelect(el,values,selected,label=v=>v){
  el.innerHTML=values.map(v=>'<option value="'+esc(v)+'"'+(String(v)===String(selected)?' selected':'')+'>'+esc(label(v))+'</option>').join('');
}

// Territory toggle: NUTS 2024 excludes Lezíria do Tejo, NUTS 2013 includes it.
function territoryToggle(el,value,onChange){
  el.querySelectorAll('button').forEach(b=>{b.setAttribute('aria-pressed',b.dataset.t===value);
    b.onclick=()=>{el.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));onChange(b.dataset.t)}});
}

// Draws a chart, or a message in its place when no dataset has a value.
// config.empty overrides the message.
const charts={};
const hasValue=v=>v!=null&&(typeof v!=='object'||(isNum(v.x)&&isNum(v.y)))&&(typeof v==='object'||isNum(v));
function chart(id,config){
  const canvas=$(id),box=canvas.parentNode;
  // Destroy whatever chart owns the canvas.
  const old=window.Chart&&Chart.getChart(canvas);if(old)old.destroy();
  delete charts[id];
  let msg=box.querySelector('.chart-empty');
  if(!msg){msg=document.createElement('p');msg.className='chart-empty';box.appendChild(msg)}
  const empty=!config.data.datasets.some(d=>d.data.some(hasValue));
  msg.textContent=empty?(config.empty||'Sem dados publicados para esta seleção.'):'';
  msg.hidden=!empty;canvas.style.visibility=empty?'hidden':'';
  if(empty||!window.Chart)return null;
  delete config.empty;
  charts[id]=new Chart(canvas,config);return charts[id];
}
// Fits a horizontal bar chart to its number of bars so labels are never skipped.
function fitBars(id,n,per=24,min=180){$(id).parentNode.style.height=Math.max(min,n*per+50)+'px'}
if(!window.Chart&&document.querySelector('canvas'))addEventListener('DOMContentLoaded',()=>status('Os gráficos não carregaram: não foi possível obter a biblioteca Chart.js (cdnjs.cloudflare.com). Verifique a ligação à internet ou a firewall.',true));

// Draws the label of each scatter/bubble point next to it.
const pointLabels=(labels,color=()=>C.ink2)=>({id:'lbl',afterDatasetsDraw(c){const x=c.ctx;x.save();x.font='11px "Public Sans",sans-serif';
  c.getDatasetMeta(0).data.forEach((p,i)=>{x.fillStyle=color(i);x.fillText(labels[i],p.x+(p.options.radius||6)+4,p.y+4)});x.restore()}});

// Heatmap as a CSS grid. rows: [{nome, valores}], one value per column.
// opts.scale "row": each row is indexed to its own maximum (= 100) and the index is
// shown; "global" (default): colour by the overall maximum and show opts.show(v).
// Missing values show opts.missing (default "conf.", INE confidential).
function heatmap(cols,rows,opts={}){
  const scale=opts.scale||'global',show=opts.show||(v=>fmt(v)),missing=opts.missing||'conf.',lw=opts.labelWidth||130;
  const titles=opts.titles||cols,tip=opts.tip||(v=>fmt(v));
  const gmax=Math.max(0,...rows.flatMap(r=>r.valores.filter(isNum)));
  let h='<div class="hm" style="grid-template-columns:'+lw+'px repeat('+cols.length+',minmax(0,1fr))"><div></div>';
  h+=cols.map((c,i)=>'<div class="hm-h" title="'+esc(titles[i])+'">'+esc(c)+'</div>').join('');
  rows.forEach(r=>{
    const max=scale==='row'?Math.max(0,...r.valores.filter(isNum)):gmax;
    h+='<div class="hm-l" title="'+esc(r.nome)+'">'+esc(r.nome)+'</div>';
    h+=r.valores.map((v,i)=>{
      if(!isNum(v)||!max)return '<div class="hm-c conf">'+missing+'</div>';
      const x=Math.round(v/max*100);
      return '<div class="hm-c" title="'+esc(r.nome+' · '+titles[i]+': '+tip(v))+'" style="background:color-mix(in srgb,var(--anil) '+x+'%,var(--anil-soft));color:'+(x>55?'var(--surface)':'var(--ink)')+'">'+(scale==='row'?x:show(v))+'</div>'}).join('')});
  return h+'</div>';
}

// Metadata footer on every page: source, update date, status, territory.
// d: an API payload (atualizado, carregado_em, territorio); territorio overrides it.
function footerMeta(d,territorio){
  let el=$('meta');
  if(!el){el=document.createElement('footer');el.className='meta';el.id='meta';document.querySelector('main').after(el)}
  const day=v=>v?new Date(v+'T00:00:00').toLocaleDateString('pt-PT'):'–';
  const parts=[['Fonte','INE, indicadores do alojamento turístico (Pista Digital)'],['Atualizado',day(d.atualizado)],
    ['Lido da base de dados',d.carregado_em?new Date(d.carregado_em*1000).toLocaleString('pt-PT'):'–'],
    ['Estado','o último ano publicado pelo INE pode ser provisório'],
    ['Território',territorio||d.territorio||'Alentejo NUTS II, salvo indicação']];
  el.innerHTML=parts.map(([k,v])=>'<span><strong>'+k+'</strong> '+esc(v)+'</span>').join('');
}
function loadedNote(ts){const el=$('loaded');if(el&&ts)el.textContent='Dados lidos da base de dados Pista Digital em '+new Date(ts*1000).toLocaleString('pt-PT')+'.'}
