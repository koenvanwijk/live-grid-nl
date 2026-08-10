(()=>{
  // app.js creates the map before its async ArcGIS requests resolve. Switching the
  // renderer here means the thousands of grid vectors that arrive afterwards use
  // one canvas instead of thousands of SVG DOM nodes.
  try{if(typeof map!=='undefined')map.options.preferCanvas=true}catch(e){}

  // Internal network flow is intentionally a deep-zoom detail. Keeping thousands
  // of coloured flow copies alive while viewing the whole country is wasteful and
  // adds no useful information. Four zoom steps from the default view is ~11.35.
  window.INTERNAL_FLOW_ZOOM=11.35;

  // CSS path animation is disabled globally. The actual MW particles on offshore
  // and interconnectors use their dedicated canvas renderer instead.
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

  function syncInternalFlows(){
    try{
      if(typeof flowPaths==='undefined'||typeof map==='undefined')return;
      const deep=map.getZoom()>=window.INTERNAL_FLOW_ZOOM;
      const flowOn=document.querySelector('#flowToggle')?.checked!==false;
      const cableOn=document.querySelector('#cableToggle')?.checked!==false;
      const active=new Set([...document.querySelectorAll('.filters input[type=checkbox][value]:checked')].map(x=>x.value));
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

  function boot(){
    if(typeof map==='undefined')return;
    map.on('zoomend',syncInternalFlows);
    document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',()=>setTimeout(syncInternalFlows,0)));
    const timer=setInterval(syncInternalFlows,200);
    setTimeout(()=>{syncInternalFlows();clearInterval(timer)},15000);
  }
  setTimeout(boot,0);
})();