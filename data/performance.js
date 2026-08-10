(function(){
const STATION_ZOOM=8.7;
let lastState=null;
function syncStations(){
  try{
    if(typeof map==='undefined'||typeof stationLayer==='undefined'||!stationLayer)return;
    const show=map.getZoom()>=STATION_ZOOM;
    if(show===lastState)return;
    lastState=show;
    if(show){if(!map.hasLayer(stationLayer))stationLayer.addTo(map)}
    else if(map.hasLayer(stationLayer))map.removeLayer(stationLayer);
    const el=document.querySelector('#stationCount');
    if(el)el.title=show?'Stations zichtbaar':'Stations worden vanaf zoom 8,7 weergegeven voor betere performance';
  }catch(e){console.warn('station LOD',e)}
}
function boot(){
  if(typeof map==='undefined')return;
  map.on('zoomend',syncStations);
  syncStations();
  const timer=setInterval(()=>{syncStations();if(typeof stationLayer!=='undefined'&&stationLayer)clearInterval(timer)},250);
  setTimeout(()=>clearInterval(timer),10000);
}
setTimeout(boot,0);
})();
