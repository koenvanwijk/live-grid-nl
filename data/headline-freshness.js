(()=>{
function ageMin(ts){if(!ts)return null;const t=new Date(ts).getTime();return Number.isFinite(t)?Math.max(0,Math.round((Date.now()-t)/60000)):null}
function ageText(ts){const m=ageMin(ts);if(m==null)return'tijd onbekend';return m<60?`${m} min`:`${Math.floor(m/60)}u ${m%60}m`}
function metricLabel(id,text,source,ts){const el=document.querySelector(id);const span=el?.parentElement?.querySelector('span');if(span)span.textContent=`${text} · ${source} · ${ageText(ts)}`}
function ensureDetails(){const grid=document.querySelector('.system-grid');if(!grid)return null;let el=document.querySelector('#headlineFreshnessDetails');if(!el){el=document.createElement('div');el.id='headlineFreshnessDetails';el.className='note';el.style.marginTop='10px';grid.insertAdjacentElement('afterend',el)}return el}
function fmt(v){return Number.isFinite(Number(v))?Math.round(Number(v)).toLocaleString('nl-NL'):'—'}
function signed(v){const n=Number(v);return Number.isFinite(n)?`${n>0?'+':''}${fmt(n)}`:'—'}
let lastData=null;
function netMode(){try{return localStorage.getItem('netSource')||'auto'}catch(e){return 'auto'}}
function cycleNetMode(){const o=['auto','ned','entso'];try{localStorage.setItem('netSource',o[(o.indexOf(netMode())+1)%o.length])}catch(e){}}
function ensureNetToggle(onClick){const tile=document.querySelector('#netMW')?.parentElement;if(!tile)return null;let b=document.querySelector('#netSourceToggle');if(!b){b=document.createElement('button');b.id='netSourceToggle';b.type='button';b.style.cssText='margin-top:5px;font:9px/1.2 inherit;letter-spacing:.03em;background:rgba(127,157,184,.14);color:inherit;border:1px solid rgba(127,157,184,.35);border-radius:6px;padding:2px 7px;cursor:pointer;white-space:nowrap';b.addEventListener('click',onClick);tile.appendChild(b)}return b}
function render(d){if(!d||d.status!=='ok')return;lastData=d;
 const loadTs=d.load_mw_measured_at||d.observations?.system?.load?.measured_at||d.measured_at;
 const genTs=d.generation_mw_measured_at||d.observations?.system?.generation?.measured_at||d.measured_at;
 const netTs=d.entso_balance_timestamp||d.observations?.system?.net_import?.measured_at||d.measured_at;
 const nedHeadline=String(d.national_balance_source||'').startsWith('NED national totals');
 metricLabel('#loadMW','vraag MW',nedHeadline?'NED':'bron',loadTs);metricLabel('#genMW','opwek MW',nedHeadline?'NED':'bron',genTs);
 const nedExport=Number(d.expected_net_export_mw),entsoExport=Number(d.entso_physical_net_export_mw);
 const haveNed=Number.isFinite(nedExport),haveEntso=Number.isFinite(entsoExport);
 const nedAge=Math.max(ageMin(loadTs)??0,ageMin(genTs)??0),entsoAge=ageMin(netTs);
 // Physical ENTSO A11 is the true measured border flow, so prefer it while
 // reasonably fresh; fall back to the NED-derived surplus when it is badly
 // stale or missing. A manual override (localStorage) wins over the default.
 const autoPick=(haveEntso&&entsoAge!=null&&entsoAge<=120)?'entso':(haveNed?'ned':(haveEntso?'entso':null));
 const mode=netMode();
 const chosen=(mode==='ned'&&haveNed)?'ned':(mode==='entso'&&haveEntso)?'entso':autoPick;
 const val=chosen==='ned'?nedExport:chosen==='entso'?entsoExport:NaN;
 const valTs=chosen==='ned'?((ageMin(loadTs)??0)>=(ageMin(genTs)??0)?loadTs:genTs):netTs;
 const srcTxt=chosen==='ned'?'NED · afgeleid':'ENTSO-E A11 · gemeten';
 const netMWel=document.querySelector('#netMW');if(netMWel&&Number.isFinite(val))netMWel.textContent=fmt(Math.abs(val));
 const netLabel=document.querySelector('#netLabel');if(netLabel)netLabel.textContent=Number.isFinite(val)?`${val<0?'netto import':'netto export'} MW · ${srcTxt} · ${ageText(valTs)}`:'netto import/export niet beschikbaar';
 const tog=ensureNetToggle(()=>{cycleNetMode();if(lastData)render(lastData)});if(tog)tog.textContent=mode==='auto'?`bron: auto (${chosen==='ned'?'NED':chosen==='entso'?'ENTSO':'—'}) · wissel`:`bron: ${mode==='ned'?'NED':'ENTSO'} (vast) · wissel`;
 const ages=[loadTs,genTs].map(ageMin).filter(Number.isFinite);if(ages.length){const age=document.querySelector('#age');if(age)age.textContent=`${Math.max(...ages)} min`;const span=age?.parentElement?.querySelector('span');if(span)span.textContent='NED hoofdwaarden'}
 const details=ensureDetails();if(!details)return;
 const expected=Number(d.expected_net_export_mw),physical=Number(d.entso_physical_net_export_mw),gap=Number(d.cross_border_balance_gap_mw);
 const entsoLoad=Number(d.entso_load_mw),entsoGen=Number(d.entso_generation_mw),entsoTs=d.entso_balance_timestamp;
 const tMw=d.tennet_transmission_load_mw,tTs=d.tennet_transmission_load_measured_at,tAge=ageMin(tTs),stale=tAge!=null&&tAge>30;
 const expectedDir=expected>=0?'export':'import',physicalDir=physical>=0?'export':'import';
 details.innerHTML=`<b>NED nationale totalen</b> · vraag en opwek uit dezelfde Nederlandse systeemdefinitie<br>${Number.isFinite(expected)?`NED verwacht netto ${expectedDir}: ${fmt(Math.abs(expected))} MW`:''}${Number.isFinite(physical)?`<br>ENTSO-E A11 fysieke ${physicalDir}: ${fmt(Math.abs(physical))} MW`:''}${Number.isFinite(gap)?`<br>verschil tussen NED-implicatie en beschikbare A11-grensstromen: ${signed(gap)} MW`:''}${Number.isFinite(entsoLoad)&&Number.isFinite(entsoGen)?`<br><small>ENTSO-E referentie${entsoTs?` ${new Date(entsoTs).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})}`:''}: A65 load ${fmt(entsoLoad)} MW · A75 opwek ${fmt(entsoGen)} MW; niet gebruikt als nationale balans.</small>`:''}${tMw!=null?`<br><small>TenneT transmissienet-belasting: ${fmt(tMw)} MW · ${ageText(tTs)}${stale?' · verouderd, niet gebruikt voor de headline':''}</small>`:''}<br><small>NED bepaalt de nationale vraag/opwek; ENTSO-E A11 bepaalt de beschikbare fysieke grensstromen. Een resterend verschil wordt expliciet getoond en niet meer als fictief balans-restverschil dichtgerekend.</small>`;
}
async function refresh(){try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(r.ok)render(await r.json())}catch(e){console.warn('headline freshness',e)}}
setTimeout(refresh,600);setInterval(refresh,60000);
})();
