(function(){
const DETAIL_ZOOM=8.7;
let totalStations=null;
function kvOf(f){return (f?.properties||{}).SPANNINGSNIVEAU||''}
function overviewVoltage(kv){return kv==='380 kV'||kv==='220 kV'}
function activeVoltageSet(){return new Set([...document.querySelectorAll('.filters input[type=checkbox][value]:checked')].map(x=>x.value))}
function sync(){
 if(typeof map==='undefined')return;
 const detail=map.getZoom()>=DETAIL_ZOOM,active=activeVoltageSet(),flowOn=document.querySelector('#flowToggle')?.checked!==false,cableOn=document.querySelector('#cableToggle')?.checked!==false;
 if(typeof flowPaths!=='undefined')for(const l of flowPaths){const kv=kvOf(l.__flowFeature),lod=detail||overviewVoltage(kv),enabled=lod&&active.has(kv)&&(!l.__flowCable||cableOn)&&flowOn;l.setStyle({opacity:enabled?.96:0,weight:enabled?Math.max(3,typeof lineWeight==='function'?lineWeight(l.__flowFeature.properties):3):0})}
 if(typeof lineLayers!=='undefined')for(const group of lineLayers)group.eachLayer(l=>{const kv=kvOf(l.feature),show=active.has(kv)&&(detail||overviewVoltage(kv));l.setStyle({opacity:show?.72:0,weight:show?(typeof lineWeight==='function'?lineWeight(l.feature.properties):2):0})});
 if(typeof cableLayers!=='undefined')for(const group of cableLayers)group.eachLayer(l=>{const kv=kvOf(l.feature),show=cableOn&&active.has(kv)&&(detail||overviewVoltage(kv));l.setStyle({opacity:show?.55:0,weight:show?(typeof lineWeight==='function'?lineWeight(l.feature.properties):2):0})});
 const counter=document.querySelector('#stationCount');if(counter){if(totalStations===null){const n=parseInt(counter.textContent.replace(/\D/g,''),10);if(Number.isFinite(n)&&n>0)totalStations=n}if(totalStations!==null){counter.textContent=detail?totalStations.toLocaleString('nl-NL'):`0 / ${totalStations.toLocaleString('nl-NL')}`;counter.title=detail?'Stations zichtbaar':'Stations verborgen op landelijk overzicht; zichtbaar vanaf zoom 8,7'}}
}
function boot(){if(typeof map==='undefined')return;map.on('zoomend',sync);document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',()=>setTimeout(sync,0)));const timer=setInterval(sync,300);setTimeout(()=>clearInterval(timer),10000);sync()}
setTimeout(boot,0);
})();