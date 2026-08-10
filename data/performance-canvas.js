(()=>{
  // app.js creates the map before its async ArcGIS requests resolve. Switching the
  // renderer here means the thousands of grid vectors that arrive afterwards use
  // one canvas instead of thousands of animated SVG DOM nodes.
  try{if(typeof map!=='undefined')map.options.preferCanvas=true}catch(e){}

  // The internal flow overlay used CSS stroke animations on every grid segment.
  // Direction is already represented by the live particle layers where meaningful;
  // thousands of independent SVG animations are prohibitively expensive on mobile.
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

  // 110/150 kV already have a base topology layer. Do not keep a second coloured
  // flow copy of those thousands of segments; retain the flow overlay only for
  // the 220/380 kV backbone.
  function pruneLowVoltageFlowCopies(){
    try{
      if(typeof flowPaths==='undefined'||typeof map==='undefined')return;
      for(let i=flowPaths.length-1;i>=0;i--){
        const l=flowPaths[i],kv=(l?.__flowFeature?.properties||{}).SPANNINGSNIVEAU||'';
        if(kv==='110 kV'||kv==='150 kV'){
          if(map.hasLayer(l))map.removeLayer(l);
          flowPaths.splice(i,1);
        }
      }
    }catch(e){console.warn('performance flow prune',e)}
  }
  const timer=setInterval(pruneLowVoltageFlowCopies,200);
  setTimeout(()=>{pruneLowVoltageFlowCopies();clearInterval(timer)},15000);
})();