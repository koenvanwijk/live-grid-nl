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
async function boot(){
 try{
  const [sr,pr,gr]=await Promise.all([fetch(T),fetch('data/provinces.json?'+Date.now()),fetch('data/large-plants.json?'+Date.now())]);
  if(!sr.ok||!pr.ok||!gr.ok)return;
  const stations=(await sr.json()).features||[], provinces=(await pr.json()).provinces||[], plants=(await gr.json()).plants||[];
  const lv=eligible(stations,['110 kV','150 kV']), hv=eligible(stations,['220 kV','380 kV','150 kV']);
  // Large plants are explicit injections and are connected to the nearest suitable high-voltage station(s).
  for(const p of plants){
    const candidates=nearest(hv,[p.lat,p.lon],2); const target=candidates[0];
    const m=addMarker(p.lat,p.lon,{radius:Math.max(5,Math.min(11,4+Math.sqrt(p.capacity_mw)/8)),color:'#ffb15a',weight:1.5,fillColor:'#d86c1d',fillOpacity:.82},`<b>${p.name}</b><small>${p.type} · ${p.capacity_mw.toLocaleString('nl-NL')} MW geïnstalleerd</small><small>${p.operator} · ${p.province}</small><small>Modelkoppeling: ${target?stationName(target):'geen station gevonden'}${target?' · '+kv(target):''}</small><small>Actuele unitproductie: nog niet publiek gekoppeld</small>`);
    if(target){const q=stationPoint(target);const l=L.polyline([[p.lat,p.lon],q],{color:'#ffb15a',weight:1.2,opacity:.55,dashArray:'3 6'}).addTo(map);layers.push(l)}
  }
  // <100 MW generation is reported per province but electrically distributed over several real 110/150-kV stations.
  for(const p of provinces){
    const targets=nearest(lv,[p.lat,p.lon],Math.min(5,Math.max(3,p.types.length)));
    targets.forEach((s,i)=>{const q=stationPoint(s);const share=1/targets.length;addMarker(q[0],q[1],{radius:3.2,color:'#c79cff',weight:1,fillColor:'#7248b7',fillOpacity:.78},`<b>${p.name} · regionale injectie</b><small>${stationName(s)} · ${kv(s)}</small><small>Bucket: ${p.types.join(', ')}</small><small>Modelgewicht: ${(share*100).toFixed(0)}% van provinciale &lt;100 MW-bucket over ${targets.length} stations</small><small>Dit is een allocatiepunt, geen openbare SCADA-meting.</small>`)});
  }
  const filters=document.querySelector('.filters');
  if(filters&&!document.querySelector('#injectionToggle')){const lab=document.createElement('label');lab.innerHTML='<input id="injectionToggle" type="checkbox" checked><i class="swatch" style="background:#c79cff"></i>productie / regionale injecties';filters.prepend(lab);lab.querySelector('input').addEventListener('change',e=>layers.forEach(x=>x.setStyle&&x.setStyle({opacity:e.target.checked?undefined:0,fillOpacity:e.target.checked?undefined:0,weight:e.target.checked?undefined:0})))}
 }catch(e){console.warn('injection model',e)}
}
setTimeout(boot,1200);
})();