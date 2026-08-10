(function(){
const layers=[],dots=[];
let live={},running=false;
function mw(country){return Number(live?.border_flows?.[country])||0}
function color(u){return u>=.8?'#ff5964':u>=.5?'#ffca59':'#49eca0'}
function width(cap){const c=Math.max(300,Number(cap)||700);return Math.max(2.5,Math.min(9,2.2+2.25*Math.sqrt(c/700)))}
function clear(){for(const l of layers.concat(dots)){try{map.removeLayer(l)}catch(e){}}layers.length=0;dots.length=0}
function removeLegacy(){map.eachLayer(l=>{if(l.__ic){try{map.removeLayer(l)}catch(e){}}})}
function visible(){return document.querySelector('#crossBorderToggle')?.checked!==false}
function point(a,b,t){return[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]}
function isPhysicalGermany(ic){return ic?.country==='DE'&&String(ic.id||'').startsWith('DE-')}
function render(){
 clear();removeLegacy();
 const on=visible();
 for(const ic of window.NL_INTERCONNECTORS||[]){
  // Germany's four physical corridors are drawn once by flow-particles.js as
  // static physical links. ENTSO-E only exposes the measured NL-DE border total,
  // so drawing that same total on every corridor would be both duplicate UI and
  // semantically wrong.
  if(isPhysicalGermany(ic))continue;
  const flow=mw(ic.country),cap=Number(ic.capacity_mw)||0,u=cap?Math.min(1,Math.abs(flow)/cap):0,into=flow>=0,w=width(cap);
  const line=L.polyline([ic.from,ic.to],{color:color(u),weight:w,opacity:on?.88:0,lineCap:'round'}).addTo(map);
  line.bindPopup(`<b>${ic.name}</b><small>${ic.type} · ${cap?cap.toLocaleString('nl-NL')+' MW capaciteit':'capaciteit onbekend'}</small><small>${Math.abs(flow).toLocaleString('nl-NL')} MW · ${into?'import naar Nederland':'export uit Nederland'}</small><small>Elke bewegende stip ≈ 100 MW actuele grensstroom.</small><small>${ic.note||''}</small>`,{className:'grid-popup'});
  layers.push(line);
  const n=Math.min(50,Math.round(Math.abs(flow)/100));
  for(let i=0;i<n;i++){
   const d=L.circleMarker(ic.from,{radius:2.35,color:'#eef6ff',weight:.7,fillColor:color(u),fillOpacity:.98,opacity:on?1:0,interactive:false,pane:'markerPane'}).addTo(map);
   d.__flow={ic,phase:i/Math.max(1,n),into};dots.push(d);
  }
 }
 if(!running){running=true;requestAnimationFrame(animate)}
}
function animate(ts){
 const speed=.000055;
 for(const d of dots){
  const {ic,phase,into}=d.__flow;
  let t=(phase+ts*speed)%1;
  if(into)t=1-t;
  d.setLatLng(point(ic.from,ic.to,t));
 }
 requestAnimationFrame(animate)
}
async function refresh(){
 try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(r.ok)live=await r.json()}catch(e){}
 render();
}
setTimeout(refresh,1800);
setInterval(refresh,60000);
const toggle=document.querySelector('#crossBorderToggle');if(toggle)toggle.addEventListener('change',()=>{const on=visible();for(const l of layers)l.setStyle({opacity:on?.88:0});for(const d of dots)d.setStyle({opacity:on?1:0,fillOpacity:on?.98:0})});
})();