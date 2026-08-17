(()=>{
function ageMin(ts){if(!ts)return null;const t=new Date(ts).getTime();return Number.isFinite(t)?Math.max(0,Math.round((Date.now()-t)/60000)):null}
function ageText(ts){const m=ageMin(ts);if(m==null)return'tijd onbekend';return m<60?`${m} min`:`${Math.floor(m/60)}u ${m%60}m`}
function metricLabel(id,text,source,ts){const el=document.querySelector(id);const span=el?.parentElement?.querySelector('span');if(span)span.textContent=`${text} · ${source} · ${ageText(ts)}`}
function ensureDetails(){const grid=document.querySelector('.system-grid');if(!grid)return null;let el=document.querySelector('#headlineFreshnessDetails');if(!el){el=document.createElement('div');el.id='headlineFreshnessDetails';el.className='note';el.style.marginTop='10px';grid.insertAdjacentElement('afterend',el)}return el}
function fmt(v){return Number.isFinite(Number(v))?Math.round(Number(v)).toLocaleString('nl-NL'):'—'}
function render(d){if(!d||d.status!=='ok')return;
 const loadTs=d.load_mw_measured_at||d.observations?.system?.load?.measured_at;
 const genTs=d.generation_mw_measured_at||d.observations?.system?.generation?.measured_at;
 const netTs=d.net_import_mw_measured_at||d.observations?.system?.net_import?.measured_at;
 metricLabel('#loadMW','vraag MW',d.observations?.system?.load?.source||'NED',loadTs);
 metricLabel('#genMW','opwek MW',d.observations?.system?.generation?.source||'NED',genTs);
 const netLabel=document.querySelector('#netLabel');if(netLabel)netLabel.textContent=`${Number(d.net_import_mw)<0?'netto export':'netto import'} MW · ENTSO-E · ${ageText(netTs)}`;
 const ages=[loadTs,genTs,netTs].map(ageMin).filter(Number.isFinite);if(ages.length){const age=document.querySelector('#age');if(age)age.textContent=`${Math.max(...ages)} min`;const span=age?.parentElement?.querySelector('span');if(span)span.textContent='oudste hoofdwaarde'}
 const details=ensureDetails();if(!details)return;
 const tMw=d.tennet_transmission_load_mw, tTs=d.tennet_transmission_load_measured_at;const tAge=ageMin(tTs);const stale=tAge!=null&&tAge>30;
 const residual=Number(d.balance_residual_mw),hasResidual=Number.isFinite(residual);const residualBad=hasResidual&&Math.abs(residual)>500;
 details.innerHTML=`<b>Broncontrole</b><br>${tMw!=null?`TenneT transmissienet-belasting: ${fmt(tMw)} MW · ${ageText(tTs)}${stale?' · <b>verouderd, niet gebruikt als vraag</b>':''}`:'TenneT transmissienet-belasting: niet beschikbaar'}${hasResidual?`<br>Systeembalans restverschil: ${residual>0?'+':''}${fmt(residual)} MW${residualBad?' · <b>let op: definities/tijdstippen sluiten niet volledig aan</b>':''}`:''}`;
}
async function refresh(){try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(r.ok)render(await r.json())}catch(e){console.warn('headline freshness',e)}}
setTimeout(refresh,2600);setInterval(refresh,60000);
})();
