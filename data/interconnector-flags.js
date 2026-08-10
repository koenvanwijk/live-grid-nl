(()=>{
  const flags=[];
  const makeIcon=flag=>L.divIcon({className:'interconnector-flag',html:`<span>${flag}</span>`,iconSize:[28,22],iconAnchor:[14,11]});
  for(const ic of window.NL_INTERCONNECTORS||[]){
    if(!ic.flag||!ic.to)continue;
    const marker=L.marker(ic.to,{icon:makeIcon(ic.flag),interactive:false,zIndexOffset:600}).addTo(map);
    flags.push(marker);
  }
  const toggle=document.querySelector('#crossBorderToggle');
  const sync=()=>{const on=toggle?.checked!==false;for(const marker of flags){if(on){if(!map.hasLayer(marker))marker.addTo(map)}else if(map.hasLayer(marker))map.removeLayer(marker)}};
  toggle?.addEventListener('change',sync);
  sync();
})();
