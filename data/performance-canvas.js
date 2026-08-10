(()=>{
  try{if(typeof map!=='undefined')map.options.preferCanvas=true}catch(e){}
  window.INTERNAL_FLOW_ZOOM=11.35;
  const style=document.createElement('style');
  style.textContent=`.leaflet-overlay-pane path.flow-forward,.leaflet-overlay-pane path.flow-reverse{display:none!important}`;
  document.head.appendChild(style);
  function activeVoltages(){return new Set([...document.querySelectorAll('.filters input[type=checkbox][value]:checked')].map(x=>x.value))}
  function syncBaseLines(){
    try{if(typeof lineLayers==='undefined')return;const active=activeVoltages();for(const group of lineLayers)group.eachLayer(l=>{const kv=(l.feature?.properties||{}).SPANNINGSNIVEAU||'',show=active.has(kv);l.setStyle({color:typeof assetColor!=='undefined'?assetColor:'#8293a3',opacity:show?.72:0,weight:show&&typeof lineWeight==='function'?lineWeight(l.feature.properties):0})})}catch(e){console.warn('base grid style',e)}
  }
  function removeInternalFlowOverlays(){try{if(typeof flowPaths==='undefined'||typeof map==='undefined')return;for(const l of flowPaths)if(map.hasLayer(l))map.removeLayer(l)}catch(e){console.warn('remove internal flow overlays',e)}}
  function syncAll(){syncBaseLines();removeInternalFlowOverlays()}
  function boot(){if(typeof map==='undefined')return;map.on('zoomend',syncAll);document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',()=>setTimeout(syncAll,0)));const timer=setInterval(syncAll,200);setTimeout(()=>{syncAll();clearInterval(timer)},15000)}
  setTimeout(boot,0);
})();