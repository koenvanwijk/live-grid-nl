(()=>{
  const UNKNOWN='#7f8b96';
  const hasFlow=country=>!!(lastLive&&lastLive.border_flows&&Object.prototype.hasOwnProperty.call(lastLive.border_flows,country)&&Number.isFinite(Number(lastLive.border_flows[country])));
  const capacityWidth=ic=>{const mw=Number(ic.capacity_mw)||700;return Math.max(2.5,Math.min(9,1.5+mw/550))};
  addInterconnectors=function(){for(const ic of window.NL_INTERCONNECTORS||[]){const known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;const line=L.polyline([ic.from,ic.to],{color:known?utilizationColor(interconnectorUtil(ic,mw)):UNKNOWN,weight:capacityWidth(ic),opacity:.95,dashArray:'12 10',className:known?(into?'xborder-in':'xborder-out'):''}).bindPopup(`<b>${ic.name}</b><small>${ic.type}${ic.capacity_mw?` · ${ic.capacity_mw.toLocaleString('nl-NL')} MW nominale capaciteit`:''}</small><small>${known?`${Math.abs(mw).toLocaleString('nl-NL')} MW · ${into?'naar Nederland':'uit Nederland'}`:'Geen actuele flowmeting · grijs'}</small><small>${ic.note}</small>`,{className:'grid-popup'}).addTo(map);line.__ic=ic;interconnectorLayers.push(line)}};
  refreshInterconnectors=function(){for(const l of interconnectorLayers){const ic=l.__ic,known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;l.setStyle({color:known?utilizationColor(interconnectorUtil(ic,mw)):UNKNOWN,weight:capacityWidth(ic)});const p=l.getElement?.();if(p){p.classList.remove('xborder-in','xborder-out');if(known)p.classList.add(into?'xborder-in':'xborder-out')}}};

  const flags=[];
  const flagSize=ic=>{const mw=Math.max(0,Number(ic.capacity_mw)||700);return Math.max(20,Math.min(44,15+0.52*Math.sqrt(mw)))};
  const makeIcon=ic=>{const size=flagSize(ic),w=size*1.28;return L.divIcon({className:'interconnector-flag',html:`<span style="font-size:${size}px;line-height:1">${ic.flag}</span>`,iconSize:[w,size],iconAnchor:[w/2,size/2]})};
  for(const ic of window.NL_INTERCONNECTORS||[]){if(!ic.flag||!ic.to)continue;const marker=L.marker(ic.to,{icon:makeIcon(ic),interactive:false,zIndexOffset:600}).addTo(map);flags.push(marker)}
  const toggle=document.querySelector('#crossBorderToggle');
  const sync=()=>{const on=toggle?.checked!==false;for(const marker of flags){if(on){if(!map.hasLayer(marker))marker.addTo(map)}else if(map.hasLayer(marker))map.removeLayer(marker)}for(const l of interconnectorLayers)l.setStyle({opacity:on?.95:0,weight:on?capacityWidth(l.__ic):0})};
  document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',sync));
  sync();
})();
