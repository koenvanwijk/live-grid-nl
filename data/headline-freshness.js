(()=>{
function ageMin(ts){if(!ts)return null;const t=new Date(ts).getTime();return Number.isFinite(t)?Math.max(0,Math.round((Date.now()-t)/60000)):null}
function ageText(ts){const m=ageMin(ts);if(m==null)return'tijd onbekend';return m<60?`${m} min`:`${Math.floor(m/60)}u ${m%60}m`}
function metricLabel(id,text,source,ts){const el=document.querySelector(id);const span=el?.parentElement?.querySelector('span');if(span)span.textContent=`${text} · ${source} · ${ageText(ts)}`}
function ensureDetails(){const grid=document.querySelector('.system-grid');if(!grid)return null;let el=document.querySelector('#headlineFreshnessDetails');if(!el){el=document.createElement('div');el.id='headlineFreshnessDetails';el.className='note';el.style.marginTop='10px';grid.insertAdjacentElement('afterend',el)}return el}
function fmt(v){return Number.isFinite(Number(v))?Math.round(Number(v)).toLocaleString('nl-NL'):'—'}
function signed(v){const n=Number(v);return Number.isFinite(n)?`${n>0?'+':''}${fmt(n)}`:'—'}
function render(d){if(!d||d.status!=='ok')return;
 const balanceTs=d.balance_timestamp||d.measured_at;
 const loadTs=d.observations?.system?.load?.measured_at||balanceTs,genTs=d.observations?.system?.generation?.measured_at||balanceTs,netTs=d.observations?.system?.net_import?.measured_at||balanceTs;
 const aligned=d.national_balance_source==='ENTSO-E aligned';const source=aligned?'ENTSO-E':'fallback';
 metricLabel('#loadMW','vraag MW',source,loadTs);metricLabel('#genMW','opwek MW',source,genTs);
 const netLabel=document.querySelector('#netLabel');if(netLabel)netLabel.textContent=`${Number(d.net_import_mw)<0?'netto export':'netto import'} MW · ${source} · ${ageText(netTs)}`;
 const ages=[loadTs,genTs,netTs].map(ageMin).filter(Number.isFinite);if(ages.length){const age=document.querySelector('#age');if(age)age.textContent=`${Math.max(...ages)} min`;const span=age?.parentElement?.querySelector('span');if(span)span.textContent=aligned?'balansmoment':'oudste hoofdwaarde'}
 const details=ensureDetails();if(!details)return;
 const residual=Number(d.balance_residual_mw),hasResidual=Number.isFinite(residual),tol=Math.max(150,Number(d.load_mw||0)*.02),bad=hasResidual&&Math.abs(residual)>tol;
 const nl=d.ned_load_mw,ng=d.ned_generation_mw,ld=d.ned_load_delta_mw,gd=d.ned_generation_delta_mw;
 const tMw=d.tennet_transmission_load_mw,tTs=d.tennet_transmission_load_measured_at,tAge=ageMin(tTs),stale=tAge!=null&&tAge>30;
 details.innerHTML=`<b>${aligned?'ENTSO-E systeembalans':'Broncontrole'}</b>${aligned?` · één tijdstip ${new Date(balanceTs).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})}`:''}<br>${hasResidual?`restverschil: ${signed(residual)} MW${bad?' · <b>balans sluit nog niet</b>':' · balans binnen tolerantie'}`:''}${nl!=null?`<br>NED controle vraag: ${fmt(nl)} MW${Number.isFinite(Number(ld))?` (${signed(ld)} MW t.o.v. ENTSO-E)`:''}`:''}${ng!=null?`<br>NED controle opwek: ${fmt(ng)} MW${Number.isFinite(Number(gd))?` (${signed(gd)} MW t.o.v. ENTSO-E)`:''}`:''}${tMw!=null?`<br>TenneT transmissienet-belasting: ${fmt(tMw)} MW · ${ageText(tTs)}${stale?' · verouderd':''}`:''}<br><small>NED blijft bron voor provinciale zon/wind; de drie nationale hoofdwaarden worden bij voorkeur niet tussen bronnen gemengd.</small>`;
}
async function refresh(){try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(r.ok)render(await r.json())}catch(e){console.warn('headline freshness',e)}}
setTimeout(refresh,2600);setInterval(refresh,60000);
})();
