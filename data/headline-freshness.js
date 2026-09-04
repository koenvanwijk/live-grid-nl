(()=>{
function ageMin(ts){if(!ts)return null;const t=new Date(ts).getTime();return Number.isFinite(t)?Math.max(0,Math.round((Date.now()-t)/60000)):null}
function ageText(ts){const m=ageMin(ts);if(m==null)return'tijd onbekend';return m<60?`${m} min`:`${Math.floor(m/60)}u ${m%60}m`}
function metricLabel(id,text,source,ts){const el=document.querySelector(id);const span=el?.parentElement?.querySelector('span');if(span)span.textContent=`${text} · ${source} · ${ageText(ts)}`}
function ensureDetails(){const grid=document.querySelector('.system-grid');if(!grid)return null;let el=document.querySelector('#headlineFreshnessDetails');if(!el){el=document.createElement('div');el.id='headlineFreshnessDetails';el.className='note';el.style.marginTop='10px';grid.insertAdjacentElement('afterend',el)}return el}
function fmt(v){return Number.isFinite(Number(v))?Math.round(Number(v)).toLocaleString('nl-NL'):'—'}
function signed(v){const n=Number(v);return Number.isFinite(n)?`${n>0?'+':''}${fmt(n)}`:'—'}
function render(d){if(!d||d.status!=='ok')return;
 const loadTs=d.load_mw_measured_at||d.observations?.system?.load?.measured_at||d.measured_at;
 const genTs=d.generation_mw_measured_at||d.observations?.system?.generation?.measured_at||d.measured_at;
 const netTs=d.entso_balance_timestamp||d.observations?.system?.net_import?.measured_at||d.measured_at;
 const nedHeadline=String(d.national_balance_source||'').startsWith('NED national totals');
 metricLabel('#loadMW','vraag MW',nedHeadline?'NED':'bron',loadTs);metricLabel('#genMW','opwek MW',nedHeadline?'NED':'bron',genTs);
 const netLabel=document.querySelector('#netLabel');if(netLabel)netLabel.textContent=`${Number(d.net_import_mw)<0?'netto export':'netto import'} MW · ENTSO-E A11 · ${ageText(netTs)}`;
 const ages=[loadTs,genTs].map(ageMin).filter(Number.isFinite);if(ages.length){const age=document.querySelector('#age');if(age)age.textContent=`${Math.max(...ages)} min`;const span=age?.parentElement?.querySelector('span');if(span)span.textContent='NED hoofdwaarden'}
 const details=ensureDetails();if(!details)return;
 const expected=Number(d.expected_net_export_mw),physical=Number(d.entso_physical_net_export_mw),gap=Number(d.cross_border_balance_gap_mw);
 const entsoLoad=Number(d.entso_load_mw),entsoGen=Number(d.entso_generation_mw),entsoTs=d.entso_balance_timestamp;
 const tMw=d.tennet_transmission_load_mw,tTs=d.tennet_transmission_load_measured_at,tAge=ageMin(tTs),stale=tAge!=null&&tAge>30;
 const expectedDir=expected>=0?'export':'import',physicalDir=physical>=0?'export':'import';
 details.innerHTML=`<b>NED nationale totalen</b> · vraag en opwek uit dezelfde Nederlandse systeemdefinitie<br>${Number.isFinite(expected)?`NED verwacht netto ${expectedDir}: ${fmt(Math.abs(expected))} MW`:''}${Number.isFinite(physical)?`<br>ENTSO-E A11 fysieke ${physicalDir}: ${fmt(Math.abs(physical))} MW`:''}${Number.isFinite(gap)?`<br>verschil tussen NED-implicatie en beschikbare A11-grensstromen: ${signed(gap)} MW`:''}${Number.isFinite(entsoLoad)&&Number.isFinite(entsoGen)?`<br><small>ENTSO-E referentie${entsoTs?` ${new Date(entsoTs).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})}`:''}: A65 load ${fmt(entsoLoad)} MW · A75 opwek ${fmt(entsoGen)} MW; niet gebruikt als nationale balans.</small>`:''}${tMw!=null?`<br><small>TenneT transmissienet-belasting: ${fmt(tMw)} MW · ${ageText(tTs)}${stale?' · verouderd, niet gebruikt voor de headline':''}</small>`:''}<br><small>NED bepaalt de nationale vraag/opwek; ENTSO-E A11 bepaalt de beschikbare fysieke grensstromen. Een resterend verschil wordt expliciet getoond en niet meer als fictief balans-restverschil dichtgerekend.</small>`;
}
async function refresh(){try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(r.ok)render(await r.json())}catch(e){console.warn('headline freshness',e)}}
setTimeout(refresh,2600);setInterval(refresh,60000);
})();
