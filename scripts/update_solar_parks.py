#!/usr/bin/env python3
"""Build ground-mounted solar park data from WUR geometry + RVO SDE capacity."""
from __future__ import annotations
import io,json,re,unicodedata
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

def zenodo_download_url(file_meta):
    links=file_meta.get('links') or {}
    url=links.get('self') or links.get('content')
    if not url:
        raise RuntimeError(f"Zenodo file has no downloadable link: key={file_meta.get('key')!r}, links={sorted(links)}")
    return url

def get_bytes(url,timeout):
    r=requests.get(url,timeout=timeout)
    r.raise_for_status()
    if not r.content: raise RuntimeError(f'Empty download: {url}')
    return r.content

def download_sources():
    mr=requests.get(WUR_API,timeout=60); mr.raise_for_status(); meta=mr.json()
    f=next((x for x in meta.get('files',[]) if str(x.get('key','')).lower().endswith('.gpkg')),None)
    if not f: raise RuntimeError(f"WUR Zenodo record has no .gpkg file; files={[x.get('key') for x in meta.get('files',[])]}")
    wur_url=zenodo_download_url(f); gpkg=get_bytes(wur_url,120)
    hr=requests.get(RVO_PAGE,timeout=60); hr.raise_for_status(); soup=BeautifulSoup(hr.text,'html.parser')
    a=next((a for a in soup.find_all('a',href=True) if 'SDE-projecten in beheer' in a.get_text(' ',strip=True)),None)
    if not a: raise RuntimeError('RVO SDE-projecten download link not found')
    url=requests.compat.urljoin(RVO_PAGE,a['href']); xlsx=get_bytes(url,120)
    return gpkg,xlsx,url,wur_url

def header_traits(values):
    cells=[norm(v) for v in values if pd.notna(v)]
    text=' | '.join(cells)
    has_geo=('gemeente' in text or 'plaats' in text)
    has_kind=any(t in text for t in ('technologie','techniek','categorie','thema'))
    has_cap=any(t in text for t in ('vermogen','capaciteit'))
    has_proj=any(t in text for t in ('project','installatie','locatie'))
    has_status=any(t in text for t in ('status','fase'))
    score=sum((has_geo,has_kind,has_cap,has_proj,has_status))
    return score,has_geo,has_kind,has_cap

def read_rvo(raw):
    """Detect the actual table header and ignore title/footnote rows."""
    book=pd.ExcelFile(io.BytesIO(raw)); candidates=[]; diagnostics=[]
    for sheet in book.sheet_names:
        preview=pd.read_excel(book,sheet_name=sheet,header=None,nrows=120)
        for idx,row in preview.iterrows():
            score,geo,kind,cap=header_traits(row.tolist())
            if score:
                diagnostics.append((score,sheet,int(idx),[str(x) for x in row.tolist() if pd.notna(x)][:5]))
            if geo and kind and cap:
                candidates.append((score,sheet,int(idx)))
    if not candidates:
        top=sorted(diagnostics,reverse=True)[:8]
        raise RuntimeError(f'Could not detect RVO table header; top candidate rows={top}')
    score,sheet,header_row=max(candidates,key=lambda x:x[0])
    df=pd.read_excel(book,sheet_name=sheet,header=header_row)
    df=df.dropna(how='all')
    return df

def main():
    gpkg,xlsx,rvo_url,wur_url=download_sources()
    tmp=Path('/tmp/solar-parks.gpkg'); tmp.write_bytes(gpkg)
    wur=gpd.read_file(tmp).to_crs(4326); rvo=read_rvo(xlsx); cols=list(rvo.columns)
    tech=find_col(cols,'techn') or find_col(cols,'categorie') or find_col(cols,'thema')
    cap=find_col(cols,'vermogen') or find_col(cols,'capaciteit')
    status=find_col(cols,'status') or find_col(cols,'fase')
    municipality=find_col(cols,'gemeente') or find_col(cols,'plaats')
    name=find_col(cols,'project') or find_col(cols,'installatie') or find_col(cols,'locatie')
    if not tech or not cap or not municipality:
        raise RuntimeError(f'RVO schema unsupported: tech={tech}, cap={cap}, municipality={municipality}; columns={cols}')
    rr=rvo[rvo[tech].astype(str).str.contains('zon|solar|pv',case=False,na=False)].copy()
    vals=pd.to_numeric(rr[cap].astype(str).str.replace('.','',regex=False).str.replace(',','.',regex=False),errors='coerce')
    rr['_mw']=vals/1000 if 'kw' in norm(cap) and 'mw' not in norm(cap) else vals
    if status:
        live=rr[status].astype(str).str.contains('productie|gerealiseerd|operationeel|in gebruik',case=False,na=False)
        if live.any(): rr=rr[live]
    wmun=find_col(wur.columns,'gemeente') or find_col(wur.columns,'municip')
    if not wmun: raise RuntimeError(f'WUR municipality column missing: {list(wur.columns)}')
    wur['_mun']=wur[wmun].map(norm); rr['_mun']=rr[municipality].map(norm)
    parks=[]; ambiguous=0
    for _,g in wur.iterrows():
        candidates=rr[(rr['_mun']==g['_mun']) & (rr['_mw']>=THRESHOLD)]
        if len(candidates)!=1:
            if len(candidates)>1: ambiguous+=1
            continue
        p=candidates.iloc[0]; c=g.geometry.centroid
        parks.append({'name':str(p[name]) if name else f"Zonnepark {g[wmun]}",'lat':round(c.y,6),'lon':round(c.x,6),'capacity_mwp':round(float(p['_mw']),3),'status':'operationeel','municipality':str(g[wmun]),'capacity_source':'RVO SDE-projecten in beheer','geometry_source':'WUR Solar Parks 2025','match_quality':'municipality_unique_ge25mw'})
    parks.sort(key=lambda x:x['capacity_mwp'],reverse=True)
    out={'schema_version':1,'threshold_mwp':THRESHOLD,'method':'WUR land-based solar geometry matched to unique operational RVO SDE solar project >=25 MWp within the same municipality. No hectare-to-MWp estimation. Ambiguous matches are excluded.','sources':{'wur':wur_url,'rvo':rvo_url},'stats':{'wur_parks':len(wur),'rvo_solar_rows':len(rr),'published_ge25mwp':len(parks),'ambiguous_municipalities':ambiguous},'parks':parks}
    if len(wur)<100: raise RuntimeError(f'Implausibly few WUR parks: {len(wur)}')
    if len(rr)<100: raise RuntimeError(f'Implausibly few RVO solar projects: {len(rr)}')
    if not parks: raise RuntimeError('No high-confidence >=25 MWp solar matches; refusing empty publish')
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out['stats'],indent=2))
if __name__=='__main__': main()
