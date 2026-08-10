(()=>{
  const UNKNOWN='#7f8b96';
  const COUNTRY_CAPACITY={DE:4000,BE:1700,GB:1000,NO2:700,DK1:700};
  const countryName={DE:'Duitsland',BE:'België',GB:'Groot-Brittannië',NO2:'Noorwegen',DK1:'Denemarken'};
  const countryCapacity=country=>COUNTRY_CAPACITY[country]||null;
  const countryConnectorCount=country=>(window.NL_INTERCONNECTORS||[]).filter(x=>x.country===country).length||1;
  const effectiveCapacity=ic=>{const own=Number(ic.capacity_mw);if(Number.isFinite(own)&&own>0)return own;const total=countryCapacity(ic.country);return total?total/countryConnectorCount(ic.country):700};
  const hasFlow=country=>!!(lastLive&&lastLive.border_flows&&Object.prototype.hasOwnProperty.call(lastLive.border_flows,country)&&Number.isFinite(Number(lastLive.border_flows[country])));
  const capacityWidth=ic=>{const mw=effectiveCapacity(ic);return Math.max(2.5,Math.min(9,1.5+mw/550))};
  const utilization=(country,mw)=>{const cap=countryCapacity(country);return cap?Math.min(1,Math.abs(mw)/cap):0};
  const colorFor=(country,mw)=>utilizationColor(utilization(country,mw));
  function flagPopup(ic){const known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,cap=countryCapacity(ic.country),into=mw>=0,pct=known&&cap?Math.round(Math.abs(mw)/cap*100):null;const explain=ic.country==='DE'?'ENTSO-E publiceert de actuele NL–DE stroom als totaal voor de marktgrens. De verdeling over de vier fysieke corridors is daarom afgeleid.':ic.type?.includes('HVDC')?'Dit is een afzonderlijke HVDC-interconnector.':'De actuele waarde geldt voor de marktgrens.';return `<b>${ic.flag} ${countryName[ic.country]||ic.country}</b><small>${ic.name} · ${ic.type}</small><small>${known?`${Math.abs(mw).toLocaleString('nl-NL')} MW · ${into?'import naar Nederland':'export uit Nederland'}`:'Geen actuele grensflow beschikbaar'}</small><small>${cap?`${cap.toLocaleString('nl-NL')} MW totale grenscapaciteit`:''}${pct!=null?` · ${pct}% benut`:''}</small><small style="color:${known?colorFor(ic.country,mw):UNKNOWN};font-weight:750">${known?'kaartkleur = benutting':'grijs = geen actuele flow'}</small><small class="provenance-line provenance-${known?'measured':'static'}">${known?'gemeten · ENTSO-E':'statisch · configuratie'}</small><small class="temporal-line temporal-${known?'actual':'none'}">${known?'gerealiseerd interval':'geen tijdreeks'}</small><small>${explain}</small><small>${ic.note||''}</small>`}
  addInterconnectors=function(){for(const ic of window.NL_INTERCONNECTORS||[]){const known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;const line=L.polyline([ic.from,ic.to],{color:known?colorFor(ic.country,mw):UNKNOWN,weight:capacityWidth(ic),opacity:.95,dashArray:'12 10',className:known?(into?'xborder-in':'xborder-out'):''}).bindPopup(flagPopup(ic),{className:'grid-popup'}).addTo(map);line.__ic=ic;interconnectorLayers.push(line)}};
  refreshInterconnectors=function(){for(const l of interconnectorLayers){const ic=l.__ic,known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;l.setStyle({color:known?colorFor(ic.country,mw):UNKNOWN,weight:capacityWidth(ic)});l.setPopupContent(flagPopup(ic));const p=l.getElement?.();if(p){p.classList.remove('xborder-in','xborder-out');if(known)p.classList.add(into?'xborder-in':'xborder-out')}}};

  // Put flags in their own pane above animated canvases and ordinary markers.
  // This also gives them a stable hit target on touch devices.
  if(!map.getPane('interconnectorFlags')){
    const pane=map.createPane('interconnectorFlags');
    pane.style.zIndex='690';
    pane.style.pointerEvents='auto';
  }
  const style=document.createElement('style');
  style.textContent='.interconnector-flag{background:transparent!important;border:0!important;cursor:pointer!important;pointer-events:auto!important;touch-action:manipulation}.interconnector-flag span{display:flex;width:100%;height:100%;align-items:center;justify-content:center;pointer-events:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,.75))}';
  document.head.appendChild(style);

  const flags=[];const sizeFor=ic=>Math.round(17+capacityWidth(ic)*4);const makeIcon=ic=>{const s=sizeFor(ic);return L.divIcon({className:'interconnector-flag',html:`<span style="font-size:${Math.round(s*.78)}px;line-height:1">${ic.flag}</span>`,iconSize:[s,s],iconAnchor:[s/2,s/2]})};
  for(const ic of window.NL_INTERCONNECTORS||[]){
    if(!ic.flag||!ic.to)continue;
    const marker=L.marker(ic.to,{icon:makeIcon(ic),interactive:true,pane:'interconnectorFlags',keyboard:true,riseOnHover:true,riseOffset:1000,title:`${countryName[ic.country]||ic.country} · ${ic.name}`})
      .bindPopup(()=>flagPopup(ic),{className:'grid-popup',autoPan:true})
      .addTo(map);
    marker.__ic=ic;
    marker.__flagSize=sizeFor(ic);
    marker.on('click',e=>{L.DomEvent.stopPropagation(e);marker.setPopupContent(flagPopup(ic));marker.openPopup()});
    flags.push(marker);
  }
  const toggle=document.querySelector('#crossBorderToggle');
  const sync=()=>{const on=toggle?.checked!==false;for(const marker of flags){const wanted=sizeFor(marker.__ic);if(marker.__flagSize!==wanted){marker.setIcon(makeIcon(marker.__ic));marker.__flagSize=wanted}if(on){if(!map.hasLayer(marker))marker.addTo(map)}else if(map.hasLayer(marker))map.removeLayer(marker)}for(const l of interconnectorLayers)l.setStyle({opacity:on?.95:0,weight:on?capacityWidth(l.__ic):0})};
  toggle?.addEventListener('change',sync);
  map.on('zoomend',sync);
  setTimeout(sync,2500);
  sync();
})();