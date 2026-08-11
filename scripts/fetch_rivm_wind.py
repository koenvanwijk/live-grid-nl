#!/usr/bin/env python3
"""Fetch RIVM turbine power WFS and build onshore wind data.

This pipeline is intentionally strict: an empty or implausible ingest is an error
and must never be committed as a successful refresh.
"""
import json, math, pathlib, urllib.parse, urllib.request

WFS='https://data.rivm.nl/geo/alo/wfs'
TYPE='alo:rivm_windturbines_vermogen_actueel'
OUT=pathlib.Path(__file__).resolve().parents[1]/'data'/'onshore-wind-rivm.json'
MIN_CLUSTER_MW=25.0
LINK_KM=2.5

def fetch():
    q=urllib.parse.urlencode({'service':'WFS','version':'2.0.0','request':'GetFeature','typeNames':TYPE,'outputFormat':'application/json','srsName':'EPSG:4326'})
    with urllib.request.urlopen(WFS+'?'+q,timeout=90) as r:
        raw=json.load(r)
    features=raw.get('features',[])
    print(f'RIVM raw features: {len(features)}; top-level keys: {list(raw)[:12]}')
    if features:
        sample=features[0]
        print('RIVM sample geometry:',json.dumps(sample.get('geometry'),ensure_ascii=False)[:500])
        print('RIVM sample properties:',json.dumps(sample.get('properties',{}),ensure_ascii=False)[:2000])
    return raw

def num(v):
    try:
        if isinstance(v,str): v=v.replace(',','.').strip()
        return float(v)
    except (TypeError,ValueError):return None

def power_mw(props):
    candidates=[]
    for k,v in props.items():
        lk=k.lower()
        if 'vermogen' in lk or 'power' in lk:
            x=num(v)
            if x is not None:candidates.append((lk,x))
    # Prefer explicitly named MW/kW fields, then generic vermogen/power.
    for lk,x in candidates:
        if 'mw' in lk:return x
    for lk,x in candidates:
        if 'kw' in lk:return x/1000.0
    for lk,x in candidates:
        if x>100:return x/1000.0
        if 0<x<30:return x
    return None

def lonlat(g):
    if not g:return None
    c=g.get('coordinates')
    if g.get('type')=='Point' and isinstance(c,list) and len(c)>=2:
        x,y=float(c[0]),float(c[1])
        # EPSG:4326 can be returned as lon/lat or lat/lon depending on WFS axis rules.
        if 3<=x<=8 and 50<=y<=54:return x,y
        if 50<=x<=54 and 3<=y<=8:return y,x
        return x,y
    return None

def likely_onshore(lon,lat):
    if not (3.25<=lon<=7.25 and 50.70<=lat<=53.65): return False
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
        out.append({'id':f"rivm-cluster-{len(out)+1}",'lat':sum(p['lat']*p['capacity_mw'] for p in g)/mw,'lon':sum(p['lon']*p['capacity_mw'] for p in g)/mw,'capacity_mw':round(mw,3),'turbines':len(g),'source':'RIVM Windturbines – vermogen','status':'operationeel','cluster_method':f'single-link <= {LINK_KM} km'})
    return sorted(out,key=lambda x:x['capacity_mw'],reverse=True)

def main():
    raw=fetch(); pts=[]; no_power=0; bad_geometry=0; off_or_outside=0
    for f in raw.get('features',[]):
        ll=lonlat(f.get('geometry'))
        if not ll:
            bad_geometry+=1;continue
        mw=power_mw(f.get('properties',{}))
        if not mw or mw<=0:
            no_power+=1;continue
        lon,lat=ll
        if not likely_onshore(lon,lat):
            off_or_outside+=1;continue
        props=f.get('properties',{})
        pts.append({'id':str(f.get('id','')),'lat':round(lat,6),'lon':round(lon,6),'capacity_mw':round(mw,4),'name':props.get('naam') or props.get('Naam') or props.get('windpark') or props.get('Windpark')})
    total=round(sum(p['capacity_mw'] for p in pts),2)
    clusters=cluster(pts)
    print(f'RIVM parsed: {len(pts)} onshore; {total} MW; no_power={no_power}; bad_geometry={bad_geometry}; outside/offshore={off_or_outside}; clusters>=25MW={len(clusters)}')
    if len(raw.get('features',[]))==0:raise RuntimeError('RIVM WFS returned zero raw features')
    if len(pts)<500 or total<1000:raise RuntimeError(f'RIVM ingest implausible: {len(pts)} turbines, {total} MW')
    data={'source':{'provider':'RIVM','dataset':'Windturbines – vermogen','wfs_type':TYPE,'license':'publiek domein'},'generated_from_wfs':True,'threshold_mw':MIN_CLUSTER_MW,'cluster_link_km':LINK_KM,'turbine_count':len(pts),'total_onshore_mw':total,'turbines_without_power':no_power,'bad_geometry':bad_geometry,'excluded_offshore_or_outside':off_or_outside,'clusters_ge_25mw':len(clusters),'clusters':clusters,'turbines':pts}
    OUT.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
if __name__=='__main__':main()
