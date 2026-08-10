(function(){
const DETAIL_ZOOM=8.7,FLOW_ZOOM=11.35;
let totalStations=null,totalConnections=null,captured=false;
const lowVoltageLayers=[];
function kvOf(f){return (f?.properties||{}).SPANNINGSNIVEAU||''}
function overviewVoltage(kv){return kv==='380 kV'||kv==='220 kV'}
function activeVoltageSet(){return new Set([...document.querySelectorAll('.filters input[type=checkbox][value]:checked')].map(x=>x.value))}
function remember(layer,kind){if(!layer||layer.__lodRemembered)return;const kv=kvOf(layer.feature||layer.__flowFeature);if(!overviewVoltage(kv)){layer.__lodRemembered=true;layer.__lodKind=kind;lowVoltageLayers.push(layer)}}
function colorBaseLine(l){
 if(!l?.feature||typeof modeledUtilization!=='function'||typeof utilizationColor!=='function')return;
 const u=modeledUtilization(l.feature);
 l.setStyle({color:utilizationColor(u),opacity:l.__lodKind==='cable'?.68:.82,weight:typeof lineWeight==='function'?lineWeight(l.feature.properties):2});
}
function colorAllBaseLines(){
 if(typeof lineLayers!=='undefined')for(const group of lineLayers)group.eachLayer(colorBaseLine);
 if(typeof cableLayers!=='undefined')for(const group of cableLayers)group.eachLayer(l=>{l.__lodKind='cable';colorBaseLine(l)});
}
function capture(){
 if(captured||typeof map==='undefined')return;
 let found=0;
 if(typeof lineLayers!=='undefined')for(const group of lineLayers)group.eachLayer(l=>{remember(l,'line');found++});
 if(typeof cableLayers!=='undefined')for(const group of cableLayers)group.eachLayer(l=>{remember(l,'cable');found++});
 if(typeof flowPaths!=='undefined')for(const l of flowPaths){remember(l,'flow');found++}
 if(found>0){captured=true;totalConnections=found;colorAllBaseLines()}
}
function shouldShow(layer,detail,deepFlow,active,flowOn,cableOn){const kv=kvOf(layer.feature||layer.__flowFeature);if(!active.has(kv))return false;if(layer.__lodKind==='flow')return deepFlow&&flowOn&&(!layer.__flowCable||cableOn);if(!detail&&!overviewVoltage(kv))return false;if(layer.__lodKind==='cable')return cableOn;return true}
function sync(){
 if(typeof map==='undefined')return;
 capture();
 const zoom=map.getZoom(),detail=zoom>=DETAIL_ZOOM,deepFlow=zoom>=FLOW_ZOOM,active=activeVoltageSet(),flowOn=document.querySelector('#flowToggle')?.checked!==false,cableOn=document.querySelector('#cableToggle')?.checked!==false;
 colorAllBaseLines();
 for(const l of lowVoltageLayers){const show=shouldShow(l,detail,deepFlow,active,flowOn,cableOn);if(show){if(!map.hasLayer(l))l.addTo(map);if(l.__lodKind!=='flow')colorBaseLine(l)}else if(map.hasLayer(l))map.removeLayer(l)}
 if(typeof flowPaths!=='undefined')for(const l of flowPaths){const kv=kvOf(l.__flowFeature);if(!overviewVoltage(kv))continue;const enabled=deepFlow&&active.has(kv)&&flowOn&&(!l.__flowCable||cableOn);if(enabled){if(!map.hasLayer(l))l.addTo(map);l.setStyle({opacity:.96,weight:Math.max(3,typeof lineWeight==='function'?lineWeight(l.__flowFeature.properties):3)})}else if(map.hasLayer(l))map.removeLayer(l)}
 const counter=document.querySelector('#stationCount');if(counter){if(totalStations===null){const n=parseInt(counter.textContent.replace(/\D/g,''),10);if(Number.isFinite(n)&&n>0)totalStations=n}if(totalStations!==null){counter.textContent=detail?totalStations.toLocaleString('nl-NL'):`0 / ${totalStations.toLocaleString('nl-NL')}`;counter.title=detail?'Stations zichtbaar':'Stations verborgen op landelijk overzicht; zichtbaar vanaf zoom 8,7'}}
 const lineCounter=document.querySelector('#lineCount');if(lineCounter){if(totalConnections===null){const n=parseInt(lineCounter.textContent.replace(/\D/g,''),10);if(Number.isFinite(n)&&n>0)totalConnections=n}if(totalConnections!==null){if(detail)lineCounter.textContent=totalConnections.toLocaleString('nl-NL');else{let visible=0;if(typeof lineLayers!=='undefined')for(const g of lineLayers)g.eachLayer(l=>{if(overviewVoltage(kvOf(l.feature))&&map.hasLayer(l))visible++});if(typeof cableLayers!=='undefined')for(const g of cableLayers)g.eachLayer(l=>{if(overviewVoltage(kvOf(l.feature))&&map.hasLayer(l))visible++});lineCounter.textContent=`${visible.toLocaleString('nl-NL')} / ${totalConnections.toLocaleString('nl-NL')}`;lineCounter.title='Alleen 380/220 kV op landelijk overzicht; 150/110 kV pas vanaf zoom 8,7. Kleuren blijven zichtbaar; extra flowdetail pas vanaf zoom 11,35.'}}}
}
function boot(){if(typeof map==='undefined')return;map.on('zoomend',sync);document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',()=>setTimeout(sync,0)));const timer=setInterval(sync,250);setTimeout(()=>clearInterval(timer),12000);sync()}
setTimeout(boot,0);
})();