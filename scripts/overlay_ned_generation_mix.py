#!/usr/bin/env python3
"""Add fresh NED comparison data without breaking an aligned ENTSO-E balance.

If update_live.py produced a complete timestamp-aligned ENTSO-E national balance,
NED stays an independent load/generation cross-check and remains the regional
source for province data. Only when ENTSO-E alignment is unavailable does NED
become the national headline fallback.
"""
from __future__ import annotations

import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

NED_API='https://api.ned.nl/v1/utilizations'
PATH=Path('data/live.json')
TOKEN=os.getenv('NED_TOKEN','').strip()
MAX_AGE_MINUTES=90
NED_TYPES=[(19,'B05','Steenkool','derived'),(18,'B04','Gas','derived'),(20,'B14','Kernenergie','derived'),(2,'B16','Zon','modelled'),(51,'B18','Wind op zee','modelled'),(21,'B17','Afval','derived'),(25,'B01','Biomassa','derived'),(26,'B20','Overig','derived'),(1,'B19','Wind op land','modelled')]

def parse_time(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except ValueError:return None

def age_minutes(value,now=None):
    ts=parse_time(value)
    if ts is None:return None
    return max(0.0,((now or datetime.now(timezone.utc))-ts).total_seconds()/60.0)
def fresh(row,now=None):
    age=age_minutes(row.get('validfrom'),now);return age is not None and age<=MAX_AGE_MINUTES

def request_latest(type_id,activity=1):
    now=datetime.now(timezone.utc);start=now.date().isoformat();end=(now.date()).isoformat()
    params={'point':0,'type':type_id,'granularity':4,'granularitytimezone':1,'classification':2,'activity':activity,'validfrom[after]':(now.date()).isoformat(),'validfrom[strictly_before]':(now.replace(day=now.day)+__import__('datetime').timedelta(days=1)).date().isoformat(),'itemsPerPage':1,'order[validfrom]':'desc'}
    req=urllib.request.Request(NED_API+'?'+urllib.parse.urlencode(params),headers={'X-AUTH-TOKEN':TOKEN,'Accept':'application/ld+json','User-Agent':'live-grid-nl/1.0 (+https://github.com/koenvanwijk/live-grid-nl)'})
    with urllib.request.urlopen(req,timeout=30) as response:data=json.load(response)
    rows=data if isinstance(data,list) else data.get('hydra:member') or data.get('member') or data.get('data') or []
    return rows[0] if rows else None

def to_mix_row(ned_row,code,name,provenance):
    if not ned_row or ned_row.get('capacity') is None or not fresh(ned_row):return None
    try:mw=float(ned_row['capacity'])/1000.0
    except (TypeError,ValueError):return None
    if mw<0:return None
    ts=ned_row.get('validfrom')
    return {'code':code,'name':name,'mw':round(mw,1),'source':'NED','provenance':provenance,'temporal':'actual','measured_at':ts,'interval_start':ts,'interval_end':ned_row.get('validto'),'published_at':ned_row.get('lastupdate')}

def fresh_ned_value(type_id,activity,label,warnings):
    try:
        row=request_latest(type_id,activity)
        if row and row.get('capacity') is not None and fresh(row):return round(float(row['capacity'])/1000.0,1),row.get('validfrom'),row.get('validto'),row.get('lastupdate')
        warnings.append(f'NED {label}: no fresh current value')
    except Exception as exc:warnings.append(f'NED {label}: {exc}')
    return None,None,None,None

def preserve_tennet(data):
    m=data.get('tennet',{}).get('metered_injections') or {}
    if m.get('mw') is None:return
    data['tennet_transmission_load_mw']=round(float(m['mw']),1);data['tennet_transmission_load_measured_at']=m.get('measured_at')

def set_ned_comparison(data,key,value,ts,end=None,published=None):
    if value is None:return
    data[key]=value;data[key+'_measured_at']=ts
    data.setdefault('observations',{}).setdefault('comparison',{})[key]={'value':value,'unit':'MW','provenance':'measured' if key=='ned_load_mw' else 'derived','temporal':'actual','source':'NED','measured_at':ts,'interval_start':ts,'interval_end':end,'published_at':published}

def apply_ned_fallback(data,load,load_ts,total,total_ts):
    if data.get('national_balance_source')=='ENTSO-E aligned':return
    if load is not None:data['load_mw']=load;data['load_mw_measured_at']=load_ts
    if total is not None:data['generation_mw']=total;data['generation_mw_measured_at']=total_ts
    data['national_balance_source']='NED partial fallback'
    times=[x for x in (load_ts,total_ts) if x]
    if times:data['measured_at']=max(times)

def main():
    if not TOKEN:
        print('NED_TOKEN missing: keeping collector data');return
    data=json.loads(PATH.read_text());warnings=data.setdefault('warnings',[]);preserve_tennet(data)
    load,load_ts,load_end,load_pub=fresh_ned_value(59,2,'load',warnings)
    total,total_ts,total_end,total_pub=fresh_ned_value(27,1,'generation total',warnings)
    set_ned_comparison(data,'ned_load_mw',load,load_ts,load_end,load_pub)
    set_ned_comparison(data,'ned_generation_mw',total,total_ts,total_end,total_pub)
    if data.get('load_mw') is not None and load is not None:data['ned_load_delta_mw']=round(load-float(data['load_mw']),1)
    if data.get('generation_mw') is not None and total is not None:data['ned_generation_delta_mw']=round(total-float(data['generation_mw']),1)
    apply_ned_fallback(data,load,load_ts,total,total_ts)

    # Keep NED per-source detail as a comparison dataset; never replace aligned ENTSO-E mix.
    rows=[]
    for type_id,code,name,prov in NED_TYPES:
        try:
            row=to_mix_row(request_latest(type_id,1),code,name,prov)
            if row:rows.append(row)
        except Exception as exc:warnings.append(f'NED generation mix {name}: {exc}')
    if rows:data['ned_generation_mix']=sorted(rows,key=lambda r:r['mw'],reverse=True)

    if all(data.get(k) is not None for k in ('load_mw','generation_mw','net_import_mw')):
        data['balance_residual_mw']=round(float(data['load_mw'])-float(data['generation_mw'])-float(data['net_import_mw']),1)
        data['balance_equation']='vraag = opwek + netto import + restverschil'
    PATH.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    print('national balance:',data.get('national_balance_source'),'@',data.get('balance_timestamp'))
    print('NED comparison load/generation:',load,total)
    print('balance residual:',data.get('balance_residual_mw'))

if __name__=='__main__':main()
