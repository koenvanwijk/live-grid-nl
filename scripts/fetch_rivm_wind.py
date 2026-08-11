#!/usr/bin/env python3
"""Fetch RIVM turbine power WFS and build validated Dutch onshore wind data."""
import json, math, pathlib, urllib.parse, urllib.request

WFS='https://data.rivm.nl/geo/alo/wfs'
TYPE='alo:rivm_windturbines_vermogen_actueel'
OUT=pathlib.Path(__file__).resolve().parents[1]/'data'/'onshore-wind-rivm.json'
MIN_CLUSTER_MW=25.0
LINK_KM=2.5
MAX_CLUSTER_RADIUS_KM=8.0

def fetch():
    q=urllib.parse.urlencode({'service':'WFS','version':'2.0.0','request':'GetFeature','typeNames':TYPE,'outputFormat':'application/json','srsName':'EPSG:4326'})
    with urllib.request.urlopen(WFS+'?'+q,timeout=90) as r:return json.load(r)

def num(v):
    try:
        if isinstance(v,str):v=v.replace(',','.').strip()
        return float(v)
    except (TypeError,ValueError):return None

def power_mw(props):
    for key in ('kw','vermogen_kw','power_kw'):
        x=num(props.get(key))
        if x is not None and x>0:return x/1000.0
    for key in ('mw','vermogen_mw','power_mw'):
        x=num(props.get(key))
        if x is not None and x>0:return x
    for k,v in props.items():
        lk=k.lower();x=num(v)
        if x is None or x<=0:continue
        if 'vermogen' in lk or 'power' in lk:return x/1000.0 if x>100 else x
    return None

def lonlat(g):
    if not g or g.get('type')!='Point':return None
    c=g.get('coordinates')
    if not isinstance(c,list) or len(c)<2:return None
    x,y=float(c[0]),float(c[1])
    if 3<=x<=8 and 50<=y<=54:return x,y
    if 50<=x<=54 and 3<=y<=8:return y,x
    return None

def is_dutch_onshore(props,lon,lat):
    land=str(props.get('land') or '').strip().lower()
    surface=str(props.get('ondergrond') or '').strip().lower()
    if land not in ('nederland','netherlands','nl'):return False
    if surface and surface!='land':return False
    return 3.2<=lon<=7.3 and 50.7<=lat<=53.7

def dist(a,b):
    lat1,lat2=math.radians(a['lat']),math.radians(b['lat']);dlat=lat2-lat1;dlon=math.radians(b['lon']-a['lon'])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 12742*math.asin(math.sqrt(h))

def centroid(group):
    w=sum(p['capacity_mw'] for p in group) or len(group)
    return {'lat':sum(p['lat']*p['capacity_mw'] for p in group)/w,'lon':sum(p['lon']*p['capacity_mw'] for p in group)/w}

def connected_groups(points):
    n=len(points);parent=list(range(n))
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
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
    return list(groups.values())

def split_long_chain(group):
    c=centroid(group)
    far=max((dist(c,p) for p in group),default=0)
    if far<=MAX_CLUSTER_RADIUS_KM or len(group)<4:return [group]
    a=max(group,key=lambda p:dist(c,p));b=max(group,key=lambda p:dist(a,p))
    left=[];right=[]
    for p in group:(left if dist(p,a)<=dist(p,b) else right).append(p)
    if not left or not right:return [group]
    return split_long_chain(left)+split_long_chain(right)

def cluster(points):
    groups=[]
    for g in connected_groups(points):groups.extend(split_long_chain(g))
    out=[]
    for g in groups:
        mw=sum(p['capacity_mw'] for p in g)
        if mw<MIN_CLUSTER_MW:continue
        c=centroid(g)
        out.append({'id':f'rivm-cluster-{len(out)+1}','lat':round(c['lat'],6),'lon':round(c['lon'],6),'capacity_mw':round(mw,3),'turbines':len(g),'source':'RIVM Windturbines – vermogen','status':'operationeel','cluster_method':f'proximity {LINK_KM} km; max radius {MAX_CLUSTER_RADIUS_KM} km'})
    return sorted(out,key=lambda x:x['capacity_mw'],reverse=True)

def main():
    raw=fetch();features=raw.get('features',[]);pts=[];no_power=0;bad_geometry=0;excluded=0
    print(f'RIVM raw features: {len(features)}')
    for f in features:
        props=f.get('properties',{});ll=lonlat(f.get('geometry'))
        if not ll:bad_geometry+=1;continue
        lon,lat=ll
        if not is_dutch_onshore(props,lon,lat):excluded+=1;continue
        mw=power_mw(props)
        if not mw:no_power+=1;continue
        pts.append({'id':str(f.get('id','')),'lat':round(lat,6),'lon':round(lon,6),'capacity_mw':round(mw,4),'name':props.get('naam'),'type':props.get('wt_type'),'municipality':props.get('gem_naam'),'province':props.get('prov_naam'),'source_date':props.get('datum')})
    total=round(sum(p['capacity_mw'] for p in pts),2);clusters=cluster(pts)
    print(f'RIVM parsed: {len(pts)} onshore; {total} MW; no_power={no_power}; bad_geometry={bad_geometry}; excluded={excluded}; clusters>=25MW={len(clusters)}')
    if not features:raise RuntimeError('RIVM WFS returned zero raw features')
    if len(pts)<1500 or not 4000<=total<=10000:raise RuntimeError(f'RIVM ingest implausible: {len(pts)} turbines, {total} MW')
    if len(clusters)<10:raise RuntimeError(f'RIVM clustering implausible: only {len(clusters)} clusters >=25 MW')
    data={'source':{'provider':'RIVM','dataset':'Windturbines – vermogen','wfs_type':TYPE,'license':'publiek domein'},'generated_from_wfs':True,'threshold_mw':MIN_CLUSTER_MW,'cluster_link_km':LINK_KM,'max_cluster_radius_km':MAX_CLUSTER_RADIUS_KM,'raw_feature_count':len(features),'turbine_count':len(pts),'total_onshore_mw':total,'turbines_without_power':no_power,'bad_geometry':bad_geometry,'excluded_non_dutch_or_offshore':excluded,'clusters_ge_25mw':len(clusters),'clusters':clusters,'turbines':pts}
    OUT.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
if __name__=='__main__':main()
