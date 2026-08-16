(()=>{
const CENTERS={'Groningen':[53.22,6.57],'Friesland':[53.16,5.78],'Drenthe':[52.95,6.62],'Overijssel':[52.43,6.45],'Flevoland':[52.52,5.48],'Gelderland':[52.05,5.87],'Utrecht':[52.09,5.12],'Noord-Holland':[52.60,4.90],'Zuid-Holland':[52.00,4.48],'Zeeland':[51.49,3.85],'Noord-Brabant':[51.57,5.08],'Limburg':[51.20,5.95]};
const EDGES=[['Groningen','Friesland'],['Groningen','Drenthe'],['Friesland','Flevoland'],['Drenthe','Overijssel'],['Overijssel','Flevoland'],['Overijssel','Gelderland'],['Flevoland','Noord-Holland'],['Flevoland','Gelderland'],['Noord-Holland','Utrecht'],['Noord-Holland','Zuid-Holland'],['Utrecht','Gelderland'],['Utrecht','Zuid-Holland'],['Gelderland','Noord-Brabant'],['Gelderland','Limburg'],['Zuid-Holland','Noord-Brabant'],['Zuid-Holland','Zeeland'],['Zeeland','Noord-Brabant'],['Noord-Brabant','Limburg']];
const layers=[];let lastData=null,demandModel=null,rafIds=[];
const style=document.createElement('style');style.textContent='.leaflet-overlay-pane path.province-flow-line{stroke-linecap:round!important;filter:drop-shadow(0 0 2px rgba(255,214,90,.28))}.province-flow-node{background:#ffd65a;border:1px solid rgba(7,17,28,.72);border-radius:50%;box-shadow:0 0 7px rgba(255,214,90,.45)}';document.head.appendChild(style);
function clear(){for(const id of rafIds)cancelAnimationFrame(id);rafIds=[];while(layers.length){const x=layers.pop();if(map.hasLayer(x))map.removeLayer(x)}}
function renewable(p){return Number(p?.wind_onshore_mw||0)+Number(p?.solar_mw||0)}
function enabled(){return document.querySelector('#provinceFlowToggle')?.checked!==false}
function visible(){return enabled()&&map.getZoom()<11.1}
function weight(mw){return Math.max(1.5,Math.min(8,1.2+Math.sqrt(Math.max(0,mw))/5.7))}
function demandByProvince(totalMW,when=new Date()){
 if(!demandModel||!(totalMW>0))return{};
 const hour=when.getHours(),weekend=when.getDay()===0||when.getDay()===6,period=weekend?'weekend':'weekday',raw={};let sum=0;
 for(const [name,p] of Object.entries(demandModel.provinces||{})){
  const prof=demandModel.profiles?.[p.profile]?.[period]||[];
  const factor=Number(prof[hour]||1),base=Number(p.population||0)*factor;
  raw[name]=base;sum+=base;
 }
 if(!(sum>0))return{};
 return Object.fromEntries(Object.entries(raw).map(([n,v])=>[n,totalMW*v/sum]));
}
function adjacency(){const a={};for(const n of Object.keys(CENTERS))a[n]=[];for(const [x,y] of EDGES){a[x].push(y);a[y].push(x)}return a}
function shortestPath(from,to,adj){const q=[[from]],seen=new Set([from]);while(q.length){const path=q.shift(),n=path[path.length-1];if(n===to)return path;for(const m of adj[n]||[]){if(!seen.has(m)){seen.add(m);q.push([...path,m])}}}return null}
function edgeKey(a,b){return a<b?`${a}|${b}`:`${b}|${a}`}
function routeRedistribution(balance){
 const adj=adjacency(),surplus=Object.entries(balance).filter(([,v])=>v>0.5).map(([n,v])=>({n,mw:v})).sort((a,b)=>b.mw-a.mw),deficit=Object.entries(balance).filter(([,v])=>v<-.5).map(([n,v])=>({n,mw:-v})).sort((a,b)=>b.mw-a.mw),edgeFlow={};
 for(const s of surplus){while(s.mw>.5){const choices=deficit.filter(d=>d.mw>.5).map(d=>({d,path:shortestPath(s.n,d.n,adj)})).filter(x=>x.path).sort((a,b)=>a.path.length-b.path.length||b.d.mw-a.d.mw);if(!choices.length)break;const {d,path}=choices[0],mw=Math.min(s.mw,d.mw);s.mw-=mw;d.mw-=mw;for(let i=0;i<path.length-1;i++){const a=path[i],b=path[i+1],key=edgeKey(a,b),sign=a<b?1:-1;edgeFlow[key]=(edgeFlow[key]||0)+sign*mw}}
 }
 return Object.entries(edgeFlow).map(([key,signed])=>{const [a,b]=key.split('|');return signed>=0?{from:a,to:b,mw:signed}:{from:b,to:a,mw:-signed}}).filter(x=>x.mw>=5);
}
function nodePopup(name,bucket,demandMW,expectedRenewable){const wind=Number(bucket?.wind_onshore_mw||0),solar=Number(bucket?.solar_mw||0),gen=wind+solar,share=gen-expectedRenewable,coverage=demandMW>0?100*gen/demandMW:0;return `<b>${name}</b><small>geschat gebruik ${Math.round(demandMW).toLocaleString('nl-NL')} MW · zon+wind ${Math.round(gen).toLocaleString('nl-NL')} MW</small><small>☀ ${Math.round(solar).toLocaleString('nl-NL')} MW · 🌬 ${Math.round(wind).toLocaleString('nl-NL')} MW · dekking ${Math.round(coverage)}%</small><small><b>hernieuwbare afwijking:</b> ${share>=0?'+':''}${Math.round(share).toLocaleString('nl-NL')} MW t.o.v. evenredige verdeling naar vraag</small><small class="provenance-line provenance-derived">vraag: live NL-vraag verdeeld met CBS + uur/dagprofiel</small><small class="provenance-line provenance-measured">zon/wind: actuele provinciale NED-productie</small>`}
function flowPopup(flow){return `<b>Gemodelleerde provinciale hernieuwbare flow</b><small>${flow.from} → ${flow.to} · ca. ${Math.round(flow.mw).toLocaleString('nl-NL')} MW</small><small class="provenance-line provenance-modelled">route uit provinciale hernieuwbare overschotten/tekorten</small><small>De totale actuele zon+wind wordt eerst naar geschatte provinciale vraag verdeeld. Afwijkingen worden over een vereenvoudigd buurprovincienetwerk gebalanceerd.</small><small>Dit is géén gemeten fysieke stroom op deze provinciegrens of TenneT-lijn.</small>`}
function movingDot(a,b,mw){const r=Math.max(2.2,Math.min(4.5,1.7+Math.sqrt(mw)/16)),dot=L.circleMarker(a,{radius:r,weight:0,fillOpacity:.95,fillColor:'#ffd65a',interactive:false}).addTo(map);layers.push(dot);let t=Math.random(),last=performance.now();const tick=now=>{if(!map.hasLayer(dot))return;const dt=Math.min(50,now-last);last=now;t=(t+dt*(0.000055+Math.min(mw,1000)*0.000000012))%1;dot.setLatLng([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]);rafIds.push(requestAnimationFrame(tick))};rafIds.push(requestAnimationFrame(tick))}
function draw(){
 clear();if(!lastData||!demandModel||!visible())return;
 const totalLoad=Number(lastData.load_mw||lastData.ned_load_mw||0);if(!(totalLoad>0))return;
 const when=new Date(lastData.measured_at||Date.now()),demand=demandByProvince(totalLoad,when),p=lastData.generation_by_province||{},names=Object.keys(CENTERS),totalRenewable=names.reduce((s,n)=>s+renewable(p[n]),0);if(!(totalRenewable>0))return;
 const balance={};for(const n of names){const dm=Number(demand[n]||0),expected=totalRenewable*(dm/totalLoad),actual=renewable(p[n]);balance[n]=actual-expected}
 for(const f of routeRedistribution(balance)){const a=CENTERS[f.from],b=CENTERS[f.to],line=L.polyline([a,b],{color:'#ffd65a',weight:weight(f.mw),opacity:.56,dashArray:'5 9',interactive:true,className:'province-flow-line'}).bindPopup(flowPopup(f),{className:'grid-popup'}).addTo(map);layers.push(line);movingDot(a,b,f.mw)}
 for(const n of names){const bucket=p[n];if(!bucket)continue;const dm=Number(demand[n]||0),expected=totalRenewable*(dm/totalLoad),net=balance[n],s=Math.max(8,Math.min(16,8+Math.sqrt(Math.abs(net))/5)),m=L.circleMarker(CENTERS[n],{radius:s/2,color:'#ffd65a',weight:1,fillColor:net>=0?'#70e58b':'#ffb454',fillOpacity:.9,interactive:true}).bindPopup(nodePopup(n,bucket,dm,expected),{className:'grid-popup'}).addTo(map);layers.push(m)}
}
async function refresh(){try{const r=await fetch(`data/live.json?t=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;lastData=await r.json();draw()}catch(e){console.warn('province renewable flow',e)}}
async function boot(){try{const mr=await fetch(`data/province-demand-model.json?t=${Date.now()}`,{cache:'no-store'});if(!mr.ok)throw new Error(`province demand model HTTP ${mr.status}`);demandModel=await mr.json();const filters=document.querySelector('.filters');if(filters&&!document.querySelector('#provinceFlowToggle')){const l=document.createElement('label');l.innerHTML='<input id="provinceFlowToggle" type="checkbox" checked><i class="swatch" style="background:#ffd65a"></i>provinciale hernieuwbare flow';filters.prepend(l);l.querySelector('input').addEventListener('change',draw)}await refresh();map.on('zoomend',draw);setInterval(refresh,60000)}catch(e){console.warn('province renewable flow',e)}}
setTimeout(boot,2200);
})();