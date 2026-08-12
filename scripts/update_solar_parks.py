#!/usr/bin/env python3
"""Build ground-mounted solar park data from WUR geometry + RVO SDE capacity.

WUR is authoritative for land-based park geometry. RVO SDE projects provide
registered project capacity/status. We only publish >=25 MWp parks when a
high-confidence match can be made; area is never converted to MWp.
"""
from __future__ import annotations
import io,json,re,sys,unicodedata
from pathlib import Path
import requests
import pandas as pd
import geopandas as gpd
from bs4 import BeautifulSoup

WUR_API='https://zenodo.org/api/records/17349176'
RVO_PAGE='https://www.rvo.nl/subsidies-financiering/sde/aanvragen/feiten-en-cijfers'
OUT=Path('data/solar-parks.json')
THRESHOLD=25.0

def norm(v):
    s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def find_col(cols,*needles):
    for c in cols:
        n=norm(c)
        if all(x in n for x in needles): return c
    return None

def download_sources():
    meta=requests.get(WUR_API,timeout=60).json()
    f=next(x for x in meta['files'] if x['key'].lower().endswith('.gpkg'))
    gpkg=requests.get(f['links']['content'],timeout=120).content
    html=requests.get(RVO_PAGE,timeout=60).text
    soup=BeautifulSoup(html,'html.parser')
    a=next((a for a in soup.find_all('a',href=True) if 'SDE-projecten in beheer' in a.get_text(' ',strip=True)),None)
    if not a: raise RuntimeError('RVO SDE-projecten download link not found')
    url=requests.compat.urljoin(RVO_PAGE,a['href'])
    xlsx=requests.get(url,timeout=120).content
    return gpkg,xlsx,url,f['links']['content']

def read_rvo(raw):
    book=pd.ExcelFile(io.BytesIO(raw))
    frames=[]
    for sheet in book.sheet_names:
        df=pd.read_excel(book,sheet_name=sheet)
        if len(df.columns)>2: frames.append(df)
    if not frames: raise RuntimeError('No usable RVO sheets')
    # Prefer sheet containing solar technology and capacity columns.
    return max(frames,key=lambda d: sum('zon' in norm(x) or 'solar' in norm(x) for x in d.astype(str).head(50).values.ravel()))

def main():
    gpkg,xlsx,rvo_url,wur_url=download_sources()
    tmp=Path('/tmp/solar-parks.gpkg'); tmp.write_bytes(gpkg)
    wur=gpd.read_file(tmp).to_crs(4326)
    rvo=read_rvo(xlsx)
    cols=list(rvo.columns)
    tech=find_col(cols,'techn') or find_col(cols,'categorie')
    cap=find_col(cols,'vermogen') or find_col(cols,'capaciteit')
    status=find_col(cols,'status') or find_col(cols,'fase')
    municipality=find_col(cols,'gemeente')
    name=find_col(cols,'project') or find_col(cols,'installatie') or find_col(cols,'locatie')
    if not tech or not cap or not municipality:
        raise RuntimeError(f'RVO schema unsupported: tech={tech}, cap={cap}, municipality={municipality}; columns={cols}')
    rr=rvo[rvo[tech].astype(str).str.contains('zon|solar|pv',case=False,na=False)].copy()
    # Parse capacity conservatively. RVO exports may use kW or MW; infer from header.
    vals=pd.to_numeric(rr[cap].astype(str).str.replace('.','',regex=False).str.replace(',','.',regex=False),errors='coerce')
    rr['_mw']=vals/1000 if 'kw' in norm(cap) and 'mw' not in norm(cap) else vals
    if status:
        live=rr[status].astype(str).str.contains('productie|gerealiseerd|operationeel|in gebruik',case=False,na=False)
        if live.any(): rr=rr[live]
    wmun=find_col(wur.columns,'gemeente') or find_col(wur.columns,'municip')
    if not wmun: raise RuntimeError(f'WUR municipality column missing: {list(wur.columns)}')
    wur['_mun']=wur[wmun].map(norm)
    rr['_mun']=rr[municipality].map(norm)
    parks=[]; ambiguous=0
    for _,g in wur.iterrows():
        candidates=rr[(rr['_mun']==g['_mun']) & (rr['_mw']>=THRESHOLD)]
        if len(candidates)!=1:
            if len(candidates)>1: ambiguous+=1
            continue
        p=candidates.iloc[0]; c=g.geometry.centroid
        parks.append({'name':str(p[name]) if name else f"Zonnepark {g[wmun]}",'lat':round(c.y,6),'lon':round(c.x,6),'capacity_mwp':round(float(p['_mw']),3),'status':'operationeel','municipality':str(g[wmun]),'area_ha':round(float(g.geometry.area),6),'capacity_source':'RVO SDE-projecten in beheer','geometry_source':'WUR Solar Parks 2025','match_quality':'municipality_unique_ge25mw'})
    parks.sort(key=lambda x:x['capacity_mwp'],reverse=True)
    out={'schema_version':1,'threshold_mwp':THRESHOLD,'method':'WUR land-based solar geometry matched to unique operational RVO SDE solar project >=25 MWp within the same municipality. No hectare-to-MWp estimation. Ambiguous matches are excluded.','sources':{'wur':wur_url,'rvo':rvo_url},'stats':{'wur_parks':len(wur),'rvo_solar_rows':len(rr),'published_ge25mwp':len(parks),'ambiguous_municipalities':ambiguous},'parks':parks}
    if len(wur)<100: raise RuntimeError(f'Implausibly few WUR parks: {len(wur)}')
    if len(rr)<100: raise RuntimeError(f'Implausibly few RVO solar projects: {len(rr)}')
    if not parks: raise RuntimeError('No high-confidence >=25 MWp solar matches; refusing empty publish')
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out['stats'],indent=2))
if __name__=='__main__': main()
