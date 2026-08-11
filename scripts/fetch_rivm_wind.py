#!/usr/bin/env python3
"""Fetch current RIVM turbine power WFS and build lightweight onshore wind data.

Outputs individual onshore turbines and spatial clusters >=25 MW.  Clustering is
purely geographic (single-link, 2.5 km) and therefore deliberately does not
invent wind-park names.  Offshore points are excluded with a conservative
Netherlands land bounding/polygon-free heuristic; exact offshore rendering is
handled by the existing offshore source.
"""
import json, math, pathlib, urllib.parse, urllib.request

WFS='https://data.rivm.nl/geo/alo/wfs'
TYPE='alo:rivm_windturbines_vermogen_actueel'
OUT=pathlib.Path(__file__).resolve().parents[1]/'data'/'onshore-wind-rivm.json'
MIN_CLUSTER_MW=25.0
LINK_KM=2.5

def fetch():
    q=urllib.parse.urlencode({'service':'WFS','version':'2.0.0','request':'GetFeature','typeNames':TYPE,'outputFormat':'application/json','srsName':'EPSG:4326'})
    with urllib.request.urlopen(WFS+'?'+q,timeout=90) as r:return json.load(r)

def num(v):
    try:
        if isinstance(v,str): v=v.replace(',','.').strip()
        return float(v)
    except:return None

def power_mw(props):
    # RIVM schemas have changed names/casing over time; inspect semantic keys.
    for k,v in props.items():
        lk=k.lower()
        if 'vermogen' in lk or lk in ('power','power_kw','vermogen_kw','vermogen_mw'):
            x=num(v)
            if x is None: continue
            # turbine values >100 are overwhelmingly kW rather than MW
            return x/1000.0 if x>100 else x
    return None

def lonlat(g):
    if not g:return None
    c=g.get('coordinates')
    if g.get('type')=='Point' and isinstance(c,list) and len(c)>=2:return float(c[0]),float(c[1])
    return None

def likely_onshore(lon,lat):
    # Keep NL mainland/islands; remove obvious North Sea offshore fleet.
    # RIVM itself warns offshore coordinates are less accurate, and the app has
    # a dedicated offshore source. Wadden coastal/on-island turbines remain.
    if not (3.25<=lon<=7.25 and 50.70<=lat<=53.65): return False
    # North Sea west of Dutch coast, with latitude-dependent conservative edge.
    coast=((50.7,3.35),(51.4,3.55),(51.9,4.0),(52.2,4.35),(52.6,4.55),(53.0,4.75),(53.65,5.1))
    for (a,x1),(b,x2) in zip(coast,coast[1:]):
        if a<=lat<=b:
            edge=x1+(x2-x1)*(lat-a)/(b-a)
            return lon>=edge
    return True

def dist(a,b):
    lat1,lat2=math.radians(a['lat']),math.radians(b['lat']);dlat=lat2-lat1;dlon=math.radians(b['lon']-a['lon'])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 12742*math.asin(math.sqrt(h))

def cluster(points):
    n=len(points); parent=list(range(n))
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[b]=a
    # grid index avoids O(n²) across the whole country
    cells={}
    for i,p in enumerate(points):cells.setdefault((int(p['lat']/.03),int(p['lon']/.05)),[]).append(i)
    for i,p in enumerate(points):
        cy,cx=int(p['lat']/.03),int(p['lon']/.05)
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                for j in cells.get((cy+dy,cx+dx),[]):
                    if j>i and dist(p,points[j])<=LINK_KM:union(i,j)
    groups={}
    for i,p in enumerate(points):groups.setdefault(find(i),[]).append(p)
    out=[]
    for g in groups.values():
        mw=sum(p['capacity_mw'] for p in g)
        if mw<MIN_CLUSTER_MW:continue
        w=mw or len(g)
        out.append({'id':f"rivm-cluster-{len(out)+1}",'lat':sum(p['lat']*p['capacity_mw'] for p in g)/w,'lon':sum(p['lon']*p['capacity_mw'] for p in g)/w,'capacity_mw':round(mw,3),'turbines':len(g),'source':'RIVM Windturbines – vermogen','status':'operationeel','cluster_method':f'single-link <= {LINK_KM} km'})
    return sorted(out,key=lambda x:x['capacity_mw'],reverse=True)

def main():
    raw=fetch(); pts=[]
    for f in raw.get('features',[]):
        ll=lonlat(f.get('geometry')); mw=power_mw(f.get('properties',{}))
        if not ll or not mw or mw<=0:continue
        lon,lat=ll
        if not likely_onshore(lon,lat):continue
        pts.append({'id':str(f.get('id','')),'lat':lat,'lon':lon,'capacity_mw':round(mw,4)})
    clusters=cluster(pts)
    data={'source':{'provider':'RIVM','dataset':'Windturbines – vermogen','wfs_type':TYPE,'license':'publiek domein'},'generated_from_wfs':True,'threshold_mw':MIN_CLUSTER_MW,'cluster_link_km':LINK_KM,'turbine_count':len(pts),'total_onshore_mw':round(sum(p['capacity_mw'] for p in pts),2),'clusters_ge_25mw':len(clusters),'clusters':clusters,'turbines':pts}
    OUT.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
    print(f"RIVM: {len(pts)} onshore turbines, {data['total_onshore_mw']} MW, {len(clusters)} clusters >=25 MW")
if __name__=='__main__':main()
