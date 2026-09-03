(()=>{
  const UNKNOWN='#7f8b96';
  const COUNTRY_CAPACITY={DE:4000,BE:1700,GB:1000,NO2:700,DK1:700};
  const countryName={DE:'Duitsland',BE:'België',GB:'Groot-Brittannië',NO2:'Noorwegen',DK1:'Denemarken'};
  // Inline SVG flags: emoji country flags do not render on Windows, so draw
  // them ourselves for identical rendering on every platform (viewBox 0 0 60 45).
  const FLAG_ART={
    DE:'<rect width="60" height="15" fill="#000"/><rect y="15" width="60" height="15" fill="#D00"/><rect y="30" width="60" height="15" fill="#FFCE00"/>',
    BE:'<rect width="20" height="45" fill="#000"/><rect x="20" width="20" height="45" fill="#FDDA24"/><rect x="40" width="20" height="45" fill="#EF3340"/>',
    DK1:'<rect width="60" height="45" fill="#C8102E"/><rect x="18" width="7" height="45" fill="#fff"/><rect y="19" width="60" height="7" fill="#fff"/>',
    NO2:'<rect width="60" height="45" fill="#BA0C2F"/><rect x="15" width="11" height="45" fill="#fff"/><rect y="17" width="60" height="11" fill="#fff"/><rect x="18" width="5" height="45" fill="#00205B"/><rect y="20" width="60" height="5" fill="#00205B"/>',
    GB:'<rect width="60" height="45" fill="#012169"/><path d="M0,0 L60,45 M60,0 L0,45" stroke="#fff" stroke-width="9"/><path d="M0,0 L60,45 M60,0 L0,45" stroke="#C8102E" stroke-width="4"/><path d="M30,0 V45 M0,22.5 H60" stroke="#fff" stroke-width="15"/><path d="M30,0 V45 M0,22.5 H60" stroke="#C8102E" stroke-width="9"/>',
  };
  let _flagId=0;
  function flagSvg(country,px,inline){
    const art=FLAG_ART[country];
    if(!art)return '';
    const h=Math.round(px*0.72),id='fr'+(++_flagId);
    const box=inline?`display:inline-block;vertical-align:-2px;margin-right:4px`:'display:block';
    return `<svg width="${px}" height="${h}" viewBox="0 0 60 45" style="${box}"><defs><clipPath id="${id}"><rect width="60" height="45" rx="6"/></clipPath></defs><g clip-path="url(#${id})">${art}<rect width="60" height="45" rx="6" fill="none" stroke="rgba(255,255,255,.5)" stroke-width="2"/></g></svg>`;
  }
  const countryCapacity=country=>COUNTRY_CAPACITY[country]||null;
  const countryConnectorCount=country=>(window.NL_INTERCONNECTORS||[]).filter(x=>x.country===country).length||1;
  const effectiveCapacity=ic=>{const own=Number(ic.capacity_mw);if(Number.isFinite(own)&&own>0)return own;const total=countryCapacity(ic.country);return total?total/countryConnectorCount(ic.country):700};
  const hasFlow=country=>!!(lastLive&&lastLive.border_flows&&Object.prototype.hasOwnProperty.call(lastLive.border_flows,country)&&Number.isFinite(Number(lastLive.border_flows[country])));
  const capacityWidth=ic=>{const mw=effectiveCapacity(ic);return Math.max(2.5,Math.min(9,1.5+mw/550))};
  const utilization=(country,mw)=>{const cap=countryCapacity(country);return cap?Math.min(1,Math.abs(mw)/cap):0};
  const colorFor=(country,mw)=>utilizationColor(utilization(country,mw));
  function flagPopup(ic){const known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,cap=countryCapacity(ic.country),into=mw>=0,pct=known&&cap?Math.round(Math.abs(mw)/cap*100):null;const explain=ic.country==='DE'?'ENTSO-E publiceert de actuele NL–DE stroom als totaal voor de marktgrens. De verdeling over de vier fysieke corridors is daarom afgeleid.':ic.type?.includes('HVDC')?'Dit is een afzonderlijke HVDC-interconnector.':'De actuele waarde geldt voor de marktgrens.';return `<b>${flagSvg(ic.country,18,true)}${countryName[ic.country]||ic.country}</b><small>${ic.name} · ${ic.type}</small><small>${known?`${Math.abs(mw).toLocaleString('nl-NL')} MW · ${into?'import naar Nederland':'export uit Nederland'}`:'Geen actuele grensflow beschikbaar'}</small><small>${cap?`${cap.toLocaleString('nl-NL')} MW totale grenscapaciteit`:''}${pct!=null?` · ${pct}% benut`:''}</small><small style="color:${known?colorFor(ic.country,mw):UNKNOWN};font-weight:750">${known?'kaartkleur = benutting':'grijs = geen actuele flow'}</small><small class="provenance-line provenance-${known?'measured':'static'}">${known?'gemeten · ENTSO-E':'statisch · configuratie'}</small><small class="temporal-line temporal-${known?'actual':'none'}">${known?'gerealiseerd interval':'geen tijdreeks'}</small><small>${explain}</small><small>${ic.note||''}</small>`}
  addInterconnectors=function(){for(const ic of window.NL_INTERCONNECTORS||[]){const known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;const line=L.polyline([ic.from,ic.to],{color:known?colorFor(ic.country,mw):UNKNOWN,weight:capacityWidth(ic),opacity:.95,dashArray:'12 10',className:known?(into?'xborder-in':'xborder-out'):''}).bindPopup(flagPopup(ic),{className:'grid-popup'}).addTo(map);line.__ic=ic;interconnectorLayers.push(line)}};
  refreshInterconnectors=function(){for(const l of interconnectorLayers){const ic=l.__ic,known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;l.setStyle({color:known?colorFor(ic.country,mw):UNKNOWN,weight:capacityWidth(ic)});l.setPopupContent(flagPopup(ic));const p=l.getElement?.();if(p){p.classList.remove('xborder-in','xborder-out');if(known)p.classList.add(into?'xborder-in':'xborder-out')}}};

  if(!map.getPane('interconnectorFlags')){
    const pane=map.createPane('interconnectorFlags');
    pane.style.zIndex='690';
    pane.style.pointerEvents='auto';
  }
  const style=document.createElement('style');
  style.textContent='.interconnector-flag{background:transparent!important;border:0!important;cursor:pointer!important;pointer-events:auto!important;touch-action:manipulation}.interconnector-flag span{display:flex;width:100%;height:100%;align-items:center;justify-content:center;pointer-events:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,.75))}';
  document.head.appendChild(style);

  const flags=[];const sizeFor=ic=>window.capacityDiameter(effectiveCapacity(ic));const makeIcon=ic=>{const s=sizeFor(ic);return L.divIcon({className:'interconnector-flag',html:`<span>${flagSvg(ic.country,Math.round(s*0.9))}</span>`,iconSize:[s,s],iconAnchor:[s/2,s/2]})};
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