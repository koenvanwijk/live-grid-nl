(()=>{
  const UNKNOWN='#7f8b96';
  const COUNTRY_CAPACITY={DE:4000,BE:1700,GB:1000,NO2:700,DK1:700};
  const countryName={DE:'Duitsland',BE:'België',GB:'Groot-Brittannië',NO2:'Noorwegen',DK1:'Denemarken'};
  const hasFlow=country=>!!(lastLive&&lastLive.border_flows&&Object.prototype.hasOwnProperty.call(lastLive.border_flows,country)&&Number.isFinite(Number(lastLive.border_flows[country])));
  const capacityWidth=ic=>{const mw=Number(ic.capacity_mw)||700;return Math.max(2.5,Math.min(9,1.5+mw/550))};
  const countryCapacity=country=>COUNTRY_CAPACITY[country]||null;
  const utilization=(country,mw)=>{const cap=countryCapacity(country);return cap?Math.min(1,Math.abs(mw)/cap):0};
  const colorFor=(country,mw)=>utilizationColor(utilization(country,mw));
  function flagPopup(ic){
    const known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,cap=countryCapacity(ic.country),into=mw>=0;
    const pct=known&&cap?Math.round(Math.abs(mw)/cap*100):null;
    const flowText=known?`${Math.abs(mw).toLocaleString('nl-NL')} MW · ${into?'import naar Nederland':'export uit Nederland'}`:'Geen actuele grensflow beschikbaar';
    const capacityText=cap?`${cap.toLocaleString('nl-NL')} MW totale grenscapaciteit`:'Totale grenscapaciteit onbekend';
    const provenance=known?'gemeten · ENTSO-E':'statisch · configuratie';
    const temporal=known?'gerealiseerd interval':'geen tijdreeks';
    const explain=ic.country==='DE'?'ENTSO-E publiceert de actuele NL–DE stroom als totaal voor de marktgrens. De verdeling over de vier fysieke corridors is daarom niet als echte meting beschikbaar.':ic.type?.includes('HVDC')?'Dit is een afzonderlijke HVDC-interconnector; de actuele grensstroom kan direct aan deze verbinding worden gekoppeld.':'De actuele waarde geldt voor de grensverbinding zoals deze in de gebruikte bron is gepubliceerd.';
    return `<b>${ic.flag} ${countryName[ic.country]||ic.country}</b><small>${ic.name} · ${ic.type}</small><small>${flowText}</small><small>${capacityText}${pct!=null?` · ${pct}% benut`:''}</small><small style="color:${known?colorFor(ic.country,mw):UNKNOWN};font-weight:750">${known?'kaartkleur = benutting':'grijs = geen actuele flow'}</small><small class="provenance-line provenance-${known?'measured':'static'}">${provenance}</small><small class="temporal-line temporal-${known?'actual':'none'}">${temporal}</small><small>${explain}</small><small>${ic.note||''}</small>`;
  }
  addInterconnectors=function(){for(const ic of window.NL_INTERCONNECTORS||[]){const known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;const line=L.polyline([ic.from,ic.to],{color:known?colorFor(ic.country,mw):UNKNOWN,weight:capacityWidth(ic),opacity:.95,dashArray:'12 10',className:known?(into?'xborder-in':'xborder-out'):''}).bindPopup(flagPopup(ic),{className:'grid-popup'}).addTo(map);line.__ic=ic;interconnectorLayers.push(line)}};
  refreshInterconnectors=function(){for(const l of interconnectorLayers){const ic=l.__ic,known=hasFlow(ic.country),mw=known?Number(lastLive.border_flows[ic.country]):0,into=mw>=0;l.setStyle({color:known?colorFor(ic.country,mw):UNKNOWN,weight:capacityWidth(ic)});l.setPopupContent(flagPopup(ic));const p=l.getElement?.();if(p){p.classList.remove('xborder-in','xborder-out');if(known)p.classList.add(into?'xborder-in':'xborder-out')}}};

  const flags=[];
  const sizeFor=ic=>{const mw=Number(ic.capacity_mw)||700;const s=Math.max(22,Math.min(42,17+Math.sqrt(mw)*.42));return Math.round(s)};
  const makeIcon=ic=>{const s=sizeFor(ic);return L.divIcon({className:'interconnector-flag',html:`<span style="font-size:${Math.round(s*.72)}px;line-height:1">${ic.flag}</span>`,iconSize:[s,s],iconAnchor:[s/2,s/2]})};
  for(const ic of window.NL_INTERCONNECTORS||[]){if(!ic.flag||!ic.to)continue;const marker=L.marker(ic.to,{icon:makeIcon(ic),interactive:true,zIndexOffset:600}).bindPopup(()=>flagPopup(ic),{className:'grid-popup'}).addTo(map);marker.__ic=ic;flags.push(marker)}
  const toggle=document.querySelector('#crossBorderToggle');
  const sync=()=>{const on=toggle?.checked!==false;for(const marker of flags){if(on){if(!map.hasLayer(marker))marker.addTo(map)}else if(map.hasLayer(marker))map.removeLayer(marker)}for(const l of interconnectorLayers)l.setStyle({opacity:on?.95:0,weight:on?capacityWidth(l.__ic):0})};
  document.querySelectorAll('.filters input').forEach(el=>el.addEventListener('change',sync));
  sync();
})();