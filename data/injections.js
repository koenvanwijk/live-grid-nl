(function(){
const layers=[];
const T='https://services-eu1.arcgis.com/WjozPuR5ROn6NZE8/ArcGIS/rest/services/TenneT_Assets_Hoogspanning/FeatureServer/5/query?where=1%3D1&outFields=*&outSR=4326&returnGeometry=true&f=geojson';
function dist(a,b){const x=(a[1]-b[1])*Math.cos((a[0]+b[0])*Math.PI/360),y=a[0]-b[0];return Math.hypot(x,y)}
function stationPoint(f){const g=f.geometry;if(!g)return null;if(g.type==='Point')return[g.coordinates[1],g.coordinates[0]];if(g.type==='Polygon'){const r=g.coordinates[0];return[r.reduce((s,p)=>s+p[1],0)/r.length,r.reduce((s,p)=>s+p[0],0)/r.length]}return null}
function stationName(f){const p=f.properties||{};return p.STATIONID||p.OBJECTOMSCHRIJVING||'TenneT station'}
function kv(f){return (f.properties||{}).SPANNINGSNIVEAU||''}
function eligible(stations,levels){return stations.filter(f=>levels.includes(kv(f))&&stationPoint(f))}
function nearest(stations,pt,n){return stations.map(f=>({f,d:dist(pt,stationPoint(f))})).sort((a,b)=>a.d-b.d).slice(0,n).map(x=>x.f)}
function addMarker(lat,lon,opts,popup){const l=L.circleMarker([lat,lon],opts).bindPopup(popup,{className:'grid-popup'}).addTo(map);layers.push(l);return l}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function sourceCode(type){type=(type||'').toLowerCase();if(type.includes('nuclear'))return'B14';if(type.includes('coal'))return'B05';if(type.includes('gas')||type.includes('wkk'))return'B04';if(type.includes('biomass'))return'B01';return null}
function liveForPlant(p,live,plants){
 const code=sourceCode(p.type),total=Number(live?.generation_by_type?.[code]);
 if(!code||!Number.isFinite(total))return{mw:null,provenance:'static',source:'capaciteitsregister',derivation:null};
 const same=plants.filter(x=>sourceCode(x.type)===code),cap=same.reduce((s,x)=>s+Number(x.capacity_mw||0),0);
 if(!cap)return{mw:null,provenance:'static',source:'capaciteitsregister',derivation:null};
 return{mw:Math.max(0,Math.min(Number(p.capacity_mw),total*Number(p.capacity_mw)/cap)),provenance:'derived',source:'ENTSO-E',measured_at:live?.provenance?.plant_generation?.measured_at||live?.measured_at,derivation:'Landelijke productie van dit brandstoftype pro-rata verdeeld naar opgesteld vermogen.'};
}
function pieIcon(p,state){
 const cap=Number(p.capacity_mw)||0,mw=Number(state.mw),hasLive=Number.isFinite(mw),ratio=hasLive&&cap?Math.max(0,Math.min(1,mw/cap)):0,size=Math.max(22,Math.min(48,18+Math.sqrt(cap)*.72)),deg=ratio*360;
 const label=hasLive?`${Math.round(mw).toLocaleString('nl-NL')} MW`:'alleen capaciteit';
 return L.divIcon({className:'generation-pie-wrap',iconSize:[size,size],iconAnchor:[size/2,size/2],html:`<div class="generation-pie provenance-${state.provenance}" style="width:${size}px;height:${size}px;--fill:${deg}deg" title="${esc(p.name)}: ${esc(label)} / ${cap.toLocaleString('nl-NL')} MW"><span></span></div>`});
}
function provenanceLabel(kind){return kind==='measured'?'gemeten':kind==='derived'?'afgeleid':'capaciteit / statisch'}
async function boot(){
 try{
  const [sr,pr,gr,lr]=await Promise.all([fetch(T),fetch('data/provinces.json'),fetch('data/large-plants.json'),fetch('data/live.json?'+Date.now(),{cache:'no-store'})]);
  if(!sr.ok||!pr.ok||!gr.ok)return;
  const stations=(await sr.json()).features||[],provinces=(await pr.json()).provinces||[],plants=(await gr.json()).plants||[],live=lr.ok?await lr.json():{};
  const lv=eligible(stations,['110 kV','150 kV']),hv=eligible(stations,['220 kV','380 kV','150 kV']);
  for(const p of plants){
    const candidates=nearest(hv,[p.lat,p.lon],2),target=candidates[0],state=liveForPlant(p,live,plants),mw=state.mw,ratio=Number.isFinite(mw)&&p.capacity_mw?mw/p.capacity_mw:null;
    const actual=Number.isFinite(mw)?`Actueel: ca. ${Math.round(mw).toLocaleString('nl-NL')} MW · ${Math.round(ratio*100)}%`:'Geen actuele unitproductie beschikbaar';
    const provenance=`<small class="provenance-line provenance-${state.provenance}">${provenanceLabel(state.provenance)}${state.source?` · ${state.source}`:''}</small>`;
    const derivation=state.derivation?`<small>${state.derivation}</small>`:'';
    const popup=`<b>${p.name}</b><small>${p.type} · ${p.capacity_mw.toLocaleString('nl-NL')} MW geïnstalleerd</small><small>${actual}</small>${provenance}${derivation}<small>${p.operator} · ${p.province}</small><small>Netkoppeling: ${target?stationName(target):'geen station gevonden'}${target?' · '+kv(target):''}</small>`;
    const m=L.marker([p.lat,p.lon],{icon:pieIcon(p,state)}).bindPopup(popup,{className:'grid-popup'}).addTo(map);layers.push(m);
    if(target){const q=stationPoint(target);const l=L.polyline([[p.lat,p.lon],q],{color:'#ffb15a',weight:1.2,opacity:.55,dashArray:'3 6'}).addTo(map);layers.push(l)}
  }
  for(const p of provinces){
    const targets=nearest(lv,[p.lat,p.lon],Math.min(5,Math.max(3,p.types.length)));
    targets.forEach(s=>{const q=stationPoint(s),share=1/targets.length;addMarker(q[0],q[1],{radius:3.2,color:'#c79cff',weight:1,fillColor:'#7248b7',fillOpacity:.78},`<b>${p.name} · regionale injectie</b><small>${stationName(s)} · ${kv(s)}</small><small>Bucket: ${p.types.join(', ')}</small><small>Modelgewicht: ${(share*100).toFixed(0)}% van provinciale &lt;100 MW-bucket over ${targets.length} stations</small><small class="provenance-line provenance-derived">afgeleid · NED + TenneT</small><small>NED regionale productie verdeeld over nabijgelegen echte 110/150-kV stations; geen stations-SCADA.</small>`)});
  }
  const filters=document.querySelector('.filters');
  if(filters&&!document.querySelector('#injectionToggle')){const lab=document.createElement('label');lab.innerHTML='<input id="injectionToggle" type="checkbox" checked><i class="swatch" style="background:#c79cff"></i>productie / regionale injecties';filters.prepend(lab);lab.querySelector('input').addEventListener('change',e=>layers.forEach(x=>{if(x.setOpacity)x.setOpacity(e.target.checked?1:0);if(x.setStyle)x.setStyle({opacity:e.target.checked?undefined:0,fillOpacity:e.target.checked?undefined:0,weight:e.target.checked?undefined:0})}))}
 }catch(e){console.warn('injection model',e)}
}
setTimeout(boot,1200);
})();