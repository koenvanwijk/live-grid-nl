const STATIC_CACHE='nl-grid-static-v17';
const RUNTIME_CACHE='nl-grid-runtime-v17';
const STATIC_ASSETS=['./','./index.html','./styles.css?v=13','./app.js?v=12','./data/performance-canvas.js?v=2','./data/interconnectors.js?v=4','./data/injections.js?v=6','./data/interconnector-flow.js?v=2','./data/flow-particles.js?v=5','./data/overview-lod.js?v=3','./data/border-flow-details.css?v=1','./data/border-flow-details.js?v=1','./manifest.webmanifest','./icon.svg'];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(STATIC_CACHE).then(cache=>cache.addAll(STATIC_ASSETS)).then(()=>self.skipWaiting()));
});

self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>![STATIC_CACHE,RUNTIME_CACHE].includes(k)).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});

function isLiveData(url){return url.pathname.endsWith('/data/live.json')}
function isCacheableRuntime(url){return url.origin===self.location.origin||url.hostname.endsWith('cartocdn.com')||url.hostname==='unpkg.com'||url.hostname.endsWith('arcgis.com')||url.hostname.endsWith('pdok.nl')}

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const url=new URL(event.request.url);
  if(isLiveData(url)){event.respondWith(fetch(event.request,{cache:'no-store'}));return}
  if(!isCacheableRuntime(url))return;
  event.respondWith(caches.match(event.request).then(cached=>{const network=fetch(event.request).then(response=>{if(response&&(response.ok||response.type==='opaque')){const copy=response.clone();caches.open(RUNTIME_CACHE).then(cache=>cache.put(event.request,copy))}return response}).catch(()=>cached);return cached||network}));
});
