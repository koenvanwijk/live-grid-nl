#!/usr/bin/env python3
"""Build realised ground-mounted solar data from ROM3D Zon op Kaart.

All realised physical parks with usable capacity are published. The frontend applies
zoom-dependent LOD; >=25 MWp remains the national overview threshold.
"""
from __future__ import annotations
import json, math, re, unicodedata
from pathlib import Path
import requests
DASHBOARD_ITEM='704215ca2235496395ce0a30355e61a5'; ARCGIS='https://www.arcgis.com/sharing/rest/content/items'; OUT=Path('data/solar-parks.json'); OVERVIEW_THRESHOLD=25.0; TIMEOUT=60
def norm(v):
 s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower(); return re.sub(r'[^a-z0-9]+',' ',s).strip()
def get_json(url,params=None):
 r=requests.get(url,params=params,timeout=TIMEOUT); r.raise_for_status(); d=r.json()
 if 'error' in d: raise RuntimeError(f'ArcGIS error for {r.url}: {d["error"]}')
 return d
def walk(obj):
 if isinstance(obj,dict):
  yield obj
  for v in obj.values(): yield from walk(v)
 elif isinstance(obj,list):
  for v in obj: yield from walk(v)
def item_data(i): return get_json(f'{ARCGIS}/{i}/data',{'f':'json'})
def item_metadata(i): return get_json(f'{ARCGIS}/{i}',{'f':'json'})
def discover_item_ids(obj):
 ids=set()
 for d in walk(obj):
  for k,v in d.items():
   if k.lower() in ('itemid','item_id','webmap','webmapid') and isinstance(v,str) and re.fullmatch(r'[0-9a-fA-F]{32}',v): ids.add(v)
 return ids
def discover_services(obj):
 urls=set()
 for d in walk(obj):
  for v in d.values():
   if isinstance(v,str) and re.match(r'https://.+/(?:FeatureServer|MapServer)(?:/\d+)?(?:\?.*)?$',v,re.I): urls.add(v.split('?')[0].rstrip('/'))
 return urls
def resolve_services():
 root=item_data(DASHBOARD_ITEM); services=discover_services(root); seen={DASHBOARD_ITEM}; queue=list(discover_item_ids(root))
 while queue:
  iid=queue.pop(0)
  if iid in seen: continue
  seen.add(iid)
  try:
   metadata=item_metadata(iid); u=metadata.get('url')
   if isinstance(u,str) and re.search(r'/(?:FeatureServer|MapServer)(?:/\d+)?$',u,re.I): services.add(u.rstrip('/'))
   data=item_data(iid)
  except Exception as e: print(f'skip linked item {iid}: {e}'); continue
  services|=discover_services(data); queue += [x for x in discover_item_ids(data) if x not in seen]
 if not services: raise RuntimeError('No ArcGIS service found')
 return sorted(services)
def layer_urls(service):
 if re.search(r'/(?:FeatureServer|MapServer)/\d+$',service,re.I): return [service]
 return [f'{service}/{x["id"]}' for x in get_json(service,{'f':'json'}).get('layers',[]) if x.get('id') is not None]
def field_for(fields,*groups):
 c=[(f.get('name',''),norm(f.get('name','')+' '+f.get('alias',''))) for f in fields]
 for g in groups:
  for name,n in c:
   if all(t in n for t in g): return name
def capacity_mw(value,field_name,field_alias=''):
 if value is None:return None
 if isinstance(value,str): value=value.replace('.','').replace(',','.')
 try:x=float(value)
 except (TypeError,ValueError):return None
 label=norm(field_name+' '+field_alias)
 if 'kw' in label and 'mw' not in label:x/=1000
 elif 'watt' in label and 'megawatt' not in label:x/=1_000_000
 return x if 0<x<5000 else None
def lonlat(g): return (float(g['x']),float(g['y'])) if g and 'x' in g and 'y' in g else None
def haversine(a,b):
 lat1,lon1=a;lat2,lon2=b;p1,p2=map(math.radians,(lat1,lat2));dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2;return 12742*math.asin(math.sqrt(h))
def fetch_candidate_layer(url):
 meta=get_json(url,{'f':'json'}); fields=meta.get('fields',[]); cap=field_for(fields,('vermogen',),('capacity',),('mwp',),('kwp',)); realised=field_for(fields,('gerealiseerd',),('gerealisee',),('realisatie','jaar'),('jaar','realisatie'),('status',)); municipality=field_for(fields,('gemeente',),('municipality',)); province=field_for(fields,('provincie',),('province',)); name=field_for(fields,('project','naam'),('naam',),('name',))
 if not cap or not realised:return None
 rows=[];offset=0
 while True:
  d=get_json(f'{url}/query',{'f':'json','where':'1=1','outFields':'*','returnGeometry':'true','outSR':4326,'resultOffset':offset,'resultRecordCount':500,'orderByFields':meta.get('objectIdField')});page=d.get('features',[])
  if not page:break
  rows.extend(page);offset+=len(page)
  if not d.get('exceededTransferLimit'):break
 alias={f.get('name',''):f.get('alias','') for f in fields}; parsed=[]
 for f in rows:
  a=f.get('attributes') or {};xy=lonlat(f.get('geometry'));mw=capacity_mw(a.get(cap),cap,alias.get(cap,''));rv=a.get(realised);rn=norm(rv);live=(isinstance(rv,(int,float)) and float(rv)>0) or rn in ('ja','yes','true') or bool(re.search(r'gerealiseerd|operationeel|in gebruik|realised|operational',rn))
  if not xy or mw is None or not live:continue
  lon,lat=xy
  if 50.6<=lat<=53.7 and 3.0<=lon<=7.4: parsed.append({'lat':lat,'lon':lon,'mw':mw,'name':str(a.get(name) or '').strip(),'municipality':str(a.get(municipality) or '').strip(),'province':str(a.get(province) or '').strip()})
 return {'url':url,'capacity_field':cap,'realised_field':realised,'rows':parsed,'raw_count':len(rows)} if parsed else None
def aggregate(rows):
 groups=[]
 for r in sorted(rows,key=lambda x:(x['municipality'],x['lat'],x['lon'])):
  match=None
  for g in groups:
   if r['municipality'] and g['municipality'] and norm(r['municipality'])!=norm(g['municipality']):continue
   if haversine((r['lat'],r['lon']),(g['lat'],g['lon']))<=.35:match=g;break
  if match is None:groups.append({'lat':r['lat'],'lon':r['lon'],'capacity_mwp':r['mw'],'municipality':r['municipality'],'province':r['province'],'names':[r['name']] if r['name'] else [],'records':1})
  else:
   total=match['capacity_mwp']+r['mw'];match['lat']=(match['lat']*match['capacity_mwp']+r['lat']*r['mw'])/total;match['lon']=(match['lon']*match['capacity_mwp']+r['lon']*r['mw'])/total;match['capacity_mwp']=total;match['records']+=1
   if r['name'] and r['name'] not in match['names']:match['names'].append(r['name'])
 parks=[]
 for g in groups:
  name=next((n for n in g['names'] if n),None) or (f"Zonnepark {g['municipality']}" if g['municipality'] else 'Zonnepark');parks.append({'name':name,'lat':round(g['lat'],6),'lon':round(g['lon'],6),'capacity_mwp':round(g['capacity_mwp'],3),'status':'operationeel','municipality':g['municipality'],'province':g['province'],'subsidy_records':g['records'],'source':'ROM3D Zon op Kaart','match_quality':'arcgis_physical_location_aggregate'})
 return sorted(parks,key=lambda x:x['capacity_mwp'],reverse=True)
def main():
 candidates=[]
 for service in resolve_services():
  try:
   for layer in layer_urls(service):
    try:
     c=fetch_candidate_layer(layer)
     if c:candidates.append(c)
    except Exception as e:print(f'skip layer {layer}: {e}')
  except Exception as e:print(f'skip service {service}: {e}')
 if not candidates:raise RuntimeError('No usable Zon op Kaart layer')
 best=max(candidates,key=lambda c:len(c['rows']));parks=aggregate(best['rows'])
 if len(best['rows'])<100 or len(parks)<100:raise RuntimeError('Implausibly small solar dataset')
 overview=[p for p in parks if p['capacity_mwp']>=OVERVIEW_THRESHOLD]
 out={'schema_version':3,'overview_threshold_mwp':OVERVIEW_THRESHOLD,'method':'ROM3D realised projects; co-located subsidy records within 350 m aggregated. Full realised set published for frontend zoom LOD.','sources':{'dashboard_item':DASHBOARD_ITEM,'layer':best['url']},'stats':{'arcgis_records':best['raw_count'],'realised_records_with_capacity':len(best['rows']),'physical_parks':len(parks),'overview_ge25mwp':len(overview),'overview_capacity_mwp':round(sum(p['capacity_mwp'] for p in overview),3)},'parks':parks};OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out['stats'],indent=2))
if __name__=='__main__':main()
