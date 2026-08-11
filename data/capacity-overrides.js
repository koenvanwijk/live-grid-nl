(()=>{
  // app.js defines offshoreIcon before starting its async boot. Replace that
  // renderer with the shared capacity scale before the offshore fetch resolves.
  if(typeof offshoreIcon==='function'){
    offshoreIcon=function(cap){
      const size=window.capacityDiameter(cap);
      return L.divIcon({
        className:'offshore-wind-icon-wrap',
        iconSize:[size,size],
        iconAnchor:[size/2,size/2],
        html:`<div class="offshore-wind-icon" style="width:${size}px;height:${size}px;font-size:${Math.max(13,size*.52)}px" aria-hidden="true"><span class="wind-rotor">✣</span><span class="wind-mast"></span></div>`
      });
    };
  }
})();
