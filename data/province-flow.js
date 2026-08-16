(()=>{
const T='https://services-eu1.arcgis.com/WjozPuR5ROn6NZE8/ArcGIS/rest/services/TenneT_Assets_Hoogspanning/FeatureServer/5/query?where=1%3D1&outFields=*&outSR=4326&returnGeometry=true&f=geojson';
const CENTERS={'Groningen':[53.22,6.57],'Friesland':[53.16,5.78],'Drenthe':[52.95,6.62],'Overijssel':[52.43,6.45],'Flevoland':[52.52,5.48],'Gelderland':[52.05,5.87],'Utrecht':[52.09,5.12],'Noord-Holland':[52.60,4.90],'Zuid-Holland':[52.00,4.48],'Zeeland':[51.49,3.85],'Noord-Brabant':[51.57,5.08],'Limburg':[51.20,5.95]};
const layers=[];let stations=[],lastData=null,demandModel=null;
const style=document.createElement('style');style.textContent='.leaflet-overlay-pane path.province-balance{stroke-dasharray:6 10!important;stroke-linecap:round!important;animation:province-balance-flow 1.3s linear infinite;filter:drop-shadow(0 0 2px rgba(255,255,255,.18))}@keyframes province-balance-flow{to{stroke-dashoffset:-16}}';document.head.appendChild(style);
function clear(){while(layers.length){const x=layers.pop();if(map.hasLayer(x))map.removeLayer(x)}}
function point(f){const g=f?.geometry;if(!g)return null;if(g.type==='Point')return[g.coordinates[1],g.coordinates[0]];if(g.type==='Polygon'){const r=g.coordinates?.[0]||[];if(!r.length)return null;return[r.reduce((s,p)=>s+p[1],0)/r.length,r.reduce((s,p)=>s+p[0],0)/r.length]}return null}
function stationName(f){const p=f?.properties||{};return p.STATIONID||p.OBJECTOMSCHRIJVING||'TenneT station'}
function kv(f){return (f?.properties||{}).SPANNINGSNIVEAU||''}
function dist(a,b){const x=(a[1]-b[1])*Math.cos((a[0]+b[0])*Math.PI/360),y=a[0]-b[0];return Math.hypot(x,y)}
function nearest(pt){return stations.map(f=>({f,p:point(f)})).filter(x=>x.p).sort((a,b)=>dist(pt,a.p)-dist(pt,b.p))[0]||null}
function renewable(p){return Number(p?.wind_onshore_mw||0)+Number(p?.solar_mw||0)}
function enabled(){return document.querySelector('#provinceFlowToggle')?.checked!==false}
function visible(){return enabled()&&map.getZoom()<11.1}
function weight(mw){return Math.max(1.5,Math.min(8,1.1+Math.sqrt(Math.max(0,mw))/6.5))}
function demandByProvince(totalMW,when=new Date()){
 if(!demandModel||!(totalMW>0))return{};
 const hour=when.getHours(),weekend=when.getDay()===0||when.getDay()===6,period=weekend?'weekend':'weekday',raw={};let sum=0;
 for(const [name,p] of Object.entries(demandModel.provinces||{})){
  const prof=demandModel.profiles?.[p.profile]?.[period]||[];
  const factor=Number(prof[hour]||1),base=Number(p.population||0)*factor;
  raw[name]=base;sum+=base;
 }
 if(!(sum>0))return{};
 return Object.fromEntries(Object.entries(raw).map(([n,v])=>[n,totalMW*v/sum]));
}
function popup(name,bucket,demandMW,target){
 const wind=Number(bucket?.wind_onshore_mw||0),solar=Number(bucket?.solar_mw||0),gen=wind+solar,net=gen-demandMW,coverage=demandMW>0?100*gen/demandMW:0,ts=bucket?.measured_at,dir=net>=0?'overschot hernieuwbaar':'tekort t.o.v. vraagmodel';
 return `<b>Provinciale hernieuwbare balans</b><small>${name}</small><small>⚡ geschatte vraag ${Math.round(demandMW).toLocaleString('nl-NL')} MW · ☀+🌬 ${Math.round(gen).toLocaleString('nl-NL')} MW</small><small>☀ ${Math.round(solar).toLocaleString('nl-NL')} MW · 🌬 ${Math.round(wind).toLocaleString('nl-NL')} MW · dekking ${Math.round(coverage)}%</small><small><b>${dir}:</b> ${Math.round(Math.abs(net)).toLocaleString('nl-NL')} MW</small><small>Visualisatie via ${stationName(target.f)} · ${kv(target.f)}</small><small class="provenance-line provenance-derived">vraag: gemodelleerd uit live NL-vraag + CBS bevolkingsgewicht + uur/dagprofiel</small><small class="provenance-line provenance-measured">zon/wind: actuele provinciale NED-productie</small><small class="temporal-line temporal-actual">actueel${ts?` · ${new Date(ts).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})}`:''}</small><small>Andere provinciale opwek (gas, kern, biomassa enz.) zit niet in deze balans. De route is géén gemeten fysieke lijn- of provinciegrensstroom.</small>`;
}
function draw(){
 clear();if(!lastData||!stations.length||!demandModel||!visible())return;
 const total=Number(lastData.load_mw||lastData.ned_load_mw||0);if(!(total>0))return;
 const demand=demandByProvince(total,new Date(lastData.measured_at||Date.now())),p=lastData.generation_by_province||{};
 for(const [name,center] of Object.entries(CENTERS)){
  const bucket=p[name],gen=renewable(bucket),dm=Number(demand[name]||0);if(!(dm>0)||!bucket)continue;
  const target=nearest(center);if(!target)continue;
  const net=gen-dm,surplus=net>=0,a=surplus?center:target.p,b=surplus?target.p:center,color=surplus?'#70e58b':'#ffb454';
  const line=L.polyline([a,b],{color,weight:weight(Math.abs(net)),opacity:.68,className:'province-balance',interactive:true}).bindPopup(popup(name,bucket,dm,target),{className:'grid-popup'}).addTo(map);layers.push(line);
 }
}
async function refresh(){try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;lastData=await r.json();draw()}catch(e){console.warn('province demand balance',e)}}
async function boot(){try{
 const [sr,mr]=await Promise.all([fetch(T),fetch(`data/province-demand-model.json?t=${Date.now()}`,{cache:'no-store'})]);if(!sr.ok)throw new Error(`TenneT stations HTTP ${sr.status}`);if(!mr.ok)throw new Error(`province demand model HTTP ${mr.status}`);
 stations=(await sr.json()).features.filter(f=>['110 kV','150 kV','220 kV','380 kV'].includes(kv(f))&&point(f));demandModel=await mr.json();
 const filters=document.querySelector('.filters');if(filters&&!document.querySelector('#provinceFlowToggle')){const l=document.createElement('label');l.innerHTML='<input id="provinceFlowToggle" type="checkbox" checked><i class="swatch" style="background:linear-gradient(90deg,#70e58b 50%,#ffb454 50%)"></i>provinciale hernieuwbare balans';filters.prepend(l);l.querySelector('input').addEventListener('change',draw)}
 await refresh();map.on('zoomend',draw);setInterval(refresh,60000);
 }catch(e){console.warn('province demand balance',e)}}
setTimeout(boot,2200);
})();