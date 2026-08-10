(()=>{
  try{if(typeof map!=='undefined')map.options.preferCanvas=true}catch(e){}
  window.INTERNAL_FLOW_ZOOM=11.35;

  const style=document.createElement('style');
  style.textContent=`
    .leaflet-overlay-pane path.flow-forward,
    .leaflet-overlay-pane path.flow-reverse,
    .leaflet-overlay-pane path.offshore-flow,
    .leaflet-overlay-pane path.xborder-in,
    .leaflet-overlay-pane path.xborder-out{
      animation:none!important;
      filter:none!important;
      will-change:auto!important;
    }
  `;
  document.head.appendChild(style);

  function activeVoltages(){
    return new Set([...document.querySelectorAll('.filters input[type=checkbox][value]:checked')].map(x=>x.value));
  }

  function syncBaseColors(){
    try{
      if(typeof lineLayers==='undefined'||typeof modeledUtilization!=='function'||typeof utilizationColor!=='function')return;
      const active=activeVoltages();
      for(const group of lineLayers)group.eachLayer(l=>{
        const f=l.feature,kv=(f?.properties||{}).SPANNINGSNIVEAU||'';
        const show=active.has(kv);
        l.setStyle({
          color:utilizationColor(modeledUtilization(f)),
          opacity:show?.72:0,
          weight:show&&typeof lineWeight==='function'?lineWeight(f.properties):0
        });
      });
    }catch(e){console.warn('base grid colors',e)}
  }

  function syncInternalFlows(){
    try{
      if(typeof flowPaths==='undefined'||typeof map==='undefined')return;
      const deep=map.getZoom()>=window.INTERNAL_FLOW_ZOOM;
      const flowOn=document.querySelector('#flowToggle')?.checked!==false;
      const cableOn=document.querySelector('#cableToggle')?.checked!==false;
      const active=activeVoltages();
      for(const l of flowPaths){
        const kv=(l?.__flowFeature?.properties||{}).SPANNINGSNIVEAU||'';
        const show=deep&&flowOn&&active.has(kv)&&(!l.__flowCable||cableOn);
        if(show){
          if(!map.hasLayer(l))l.addTo(map);
          if(typeof flowStyle==='function')l.setStyle(flowStyle(l.__flowFeature));
        }else if(map.hasLayer(l))map.removeLayer(l);
      }
    }catch(e){console.warn('internal flow LOD',e)}
  }

  function syncAll(){syncBaseColors();syncInternalFlows()}

  function boot(){
    if(typeof map==='undefined')return;
    map.on('zoomend',syncAll);
    document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',()=>setTimeout(syncAll,0)));
    const timer=setInterval(syncAll,200);
    setTimeout(()=>{syncAll();clearInterval(timer)},15000);
    // Live data refresh changes the modeled direction/utilization. Keep the cheap
    // base layer colors in sync without re-enabling the heavy flow overlay.
    setInterval(syncBaseColors,5000);
  }
  setTimeout(boot,0);
})();