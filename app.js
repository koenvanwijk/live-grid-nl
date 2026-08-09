const TennetBase='https://services-eu1.arcgis.com/WjozPuR5ROn6NZE8/ArcGIS/rest/services/TenneT_Assets_Hoogspanning/FeatureServer';
const map=L.map('map',{zoomControl:false,preferCanvas:true}).setView([52.18,5.35],7.35);
L.control.zoom({position:'bottomright'}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap &copy; CARTO · Grid assets: TenneT TSO B.V.'}).addTo(map);

const palette={'380 kV':'#ff5964','220 kV':'#8ddd70','150 kV':'#35a7ff','110 kV':'#d8e5ee'};
const lineLayers=[],cableLayers=[];
let stationLayer;

function endpoint(layer){return `${TennetBase}/${layer}/query?where=1%3D1&outFields=*&outSR=4326&returnGeometry=true&f=geojson`}
function voltage(p){return p.SPANNINGSNIVEAU||'Onbekend'}
function colorFor(p){return palette[voltage(p)]||'#8698a8'}
function lineWeight(p){const v=voltage(p);return v==='380 kV'?3.4:v==='220 kV'?2.7:v==='150 kV'?2.2:1.7}
function popup(feature,type){const p=feature.properties||{};const name=p.OBJECTOMSCHRIJVING||p.STATIONID||type;return `<b>${name||type}</b><small>${voltage(p)} · ${p.STATUS||'status onbekend'}</small><small>Bron: TenneT TSO B.V.</small>`}
async function getGeoJSON(layer){const r=await fetch(endpoint(layer));if(!r.ok)throw new Error(`TenneT laag ${layer}: HTTP ${r.status}`);return r.json()}

function addLines(data,isCable=false){
  const target=isCable?cableLayers:lineLayers;
  const layer=L.geoJSON(data,{style:f=>({color:colorFor(f.properties),weight:lineWeight(f.properties),opacity:isCable?.7:.92,dashArray:isCable?'4 5':null,lineCap:'round'}),onEachFeature:(f,l)=>l.bindPopup(popup(f,isCable?'Ondergrondse kabel':'Hoogspanningslijn'),{className:'grid-popup'})}).addTo(map);
  target.push(layer);return data.features?.length||0;
}
function addStations(data){
  stationLayer=L.geoJSON(data,{style:f=>({color:colorFor(f.properties),weight:1.5,fillColor:'#08131f',fillOpacity:.55}),onEachFeature:(f,l)=>{l.bindPopup(popup(f,'Hoogspanningsstation'),{className:'grid-popup'});const p=f.properties||{};if(p.STATIONID)l.bindTooltip(p.STATIONID,{permanent:false,direction:'top',className:'station-label'});}}).addTo(map);
  return data.features?.length||0;
}
function applyFilters(){
  const active=new Set([...document.querySelectorAll('.filters input[type=checkbox][value]:checked')].map(x=>x.value));
  for(const group of lineLayers)group.eachLayer(l=>{const show=active.has(voltage(l.feature.properties));l.setStyle({opacity:show?.92:0,weight:show?lineWeight(l.feature.properties):0});});
  const cableOn=document.querySelector('#cableToggle').checked;
  for(const group of cableLayers)group.eachLayer(l=>{const show=cableOn&&active.has(voltage(l.feature.properties));l.setStyle({opacity:show?.7:0,weight:show?lineWeight(l.feature.properties):0});});
  if(stationLayer)stationLayer.eachLayer(l=>{const show=active.has(voltage(l.feature.properties));l.setStyle({opacity:show?1:0,fillOpacity:show?.55:0});});
}
document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',applyFilters));

function fmtMW(v){return Number.isFinite(v)?Math.round(v).toLocaleString('nl-NL'):'—'}
function ageLabel(ts){if(!ts)return '—';const m=Math.max(0,Math.round((Date.now()-new Date(ts).getTime())/60000));return m<60?`${m} min`:`${Math.floor(m/60)}u ${m%60}m`}
function renderLive(data){
  const source=document.querySelector('#liveSource');
  if(!data||data.status!=='ok'){
    source.textContent=data?.status==='token-missing'?'token nodig':'niet beschikbaar';
    document.querySelector('#liveBadge').classList.add('stale');
    document.querySelector('#borderFlows').innerHTML='<div class="placeholder">ENTSO-E live data nog niet geconfigureerd</div>';
    document.querySelector('#updated').textContent='TenneT topologie · live systeemdata wacht op token';
    return;
  }
  const load=Number(data.load_mw),gen=Number(data.generation_mw),net=Number(data.net_import_mw);
  document.querySelector('#loadMW').textContent=fmtMW(load);
  document.querySelector('#genMW').textContent=fmtMW(gen);
  document.querySelector('#netMW').textContent=fmtMW(Math.abs(net));
  document.querySelector('#netLabel').textContent=net>=0?'netto import MW':'netto export MW';
  document.querySelector('#age').textContent=ageLabel(data.measured_at||data.generated_at);
  document.querySelector('#updated').textContent=`ENTSO-E · ${new Intl.DateTimeFormat('nl-NL',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Amsterdam'}).format(new Date(data.measured_at||data.generated_at))}`;
  const rows=Object.entries(data.border_flows||{}).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).map(([country,mw])=>{
    const n=Number(mw),into=n>=0;return `<div class="flow-row"><span class="country">${country}</span><span class="arrow ${into?'in':'out'}">${into?'→ NL':'NL →'}</span><strong>${fmtMW(Math.abs(n))}</strong></div>`;
  }).join('');
  document.querySelector('#borderFlows').innerHTML=rows||'<div class="placeholder">geen grensdata</div>';
  source.textContent='ENTSO-E';
}
async function loadLive(){try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(r.ok)renderLive(await r.json());else renderLive(null)}catch(e){console.warn(e);renderLive(null)}}

async function boot(){
  const status=document.querySelector('#status');
  loadLive();
  try{
    status.textContent='Officiële TenneT-assets laden…';
    const [overhead,cables,stations]=await Promise.all([getGeoJSON(2),getGeoJSON(3),getGeoJSON(5)]);
    document.querySelector('#lineCount').textContent=(addLines(overhead,false)+addLines(cables,true)).toLocaleString('nl-NL');
    document.querySelector('#stationCount').textContent=addStations(stations).toLocaleString('nl-NL');
    status.textContent='TenneT-net actief';setTimeout(()=>status.style.opacity=.55,2800);
  }catch(err){console.error(err);status.textContent='Kon TenneT-data niet laden';}
}
function tick(){document.querySelector('#clock').textContent=new Intl.DateTimeFormat('nl-NL',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false,timeZone:'Europe/Amsterdam'}).format(new Date());}
setInterval(tick,1000);setInterval(loadLive,60000);tick();boot();
