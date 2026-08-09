#!/usr/bin/env python3
import json, os, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENTSO_API='https://web-api.tp.entsoe.eu/api'
NED_API='https://api.ned.nl/v1/utilizations'
TENNET_METERED='https://api.tennet.eu/publications/v1/metered-injections'
TENNET_BALANCE='https://api.tennet.eu/publications/v1/balance-delta-high-res'
NL='10YNL----------L'
BORDERS={'DE':'10Y1001A1001A82H','BE':'10YBE----------2','GB':'10YGB-0000A-000','NO2':'10YNO-2--------T','DK1':'10YDK-1--------W'}
PROVINCES={1:'Groningen',2:'Friesland',3:'Drenthe',4:'Overijssel',5:'Flevoland',6:'Gelderland',7:'Utrecht',8:'Noord-Holland',9:'Zuid-Holland',10:'Zeeland',11:'Noord-Brabant',12:'Limburg'}
OFFSHORE={28:'Luchterduinen',29:'Prinses Amalia',30:'Egmond aan Zee',31:'Gemini',33:'Borssele 1&2',34:'Borssele 3&4',35:'Hollandse Kust Zuid',36:'Hollandse Kust Noord'}
OUT=Path('data/live.json')
ENTSO_TOKEN=os.getenv('ENTSO_E_TOKEN','').strip()
NED_TOKEN=os.getenv('NED_TOKEN','').strip()
TENNET_TOKEN=os.getenv('TENNET_TOKEN','').strip()


class ApiError(RuntimeError):
    pass


def get_json(url,params,headers=None):
    req=urllib.request.Request(url+'?'+urllib.parse.urlencode(params),headers=headers or {})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            body=e.read().decode('utf-8','replace').strip().replace('\n',' ')[:500]
        except Exception:
            body=''
        detail=f'HTTP {e.code} {e.reason}'
        if body:detail+=f': {body}'
        raise ApiError(detail) from e


def utc_window(hours=8):
    now=datetime.now(timezone.utc); start=now-timedelta(hours=hours)
    return start.strftime('%Y-%m-%dT%H:%M:%SZ'),now.strftime('%Y-%m-%dT%H:%M:%SZ')


def ned_records(point,type_id,activity=1,days=2):
    if not NED_TOKEN:return []
    today=datetime.now(timezone.utc).date(); start=today-timedelta(days=days); end=today+timedelta(days=1)
    p={'point':point,'type':type_id,'granularity':4,'granularitytimezone':1,'classification':2,'activity':activity,
       'validfrom[after]':start.isoformat(),'validfrom[strictly_before]':end.isoformat(),'itemsPerPage':1000}
    d=get_json(NED_API,p,{'X-AUTH-TOKEN':NED_TOKEN,'Accept':'application/ld+json'})
    if isinstance(d,list):return d
    return d.get('hydra:member') or d.get('member') or d.get('data') or []


def latest_ned(point,type_id,activity=1):
    rows=ned_records(point,type_id,activity)
    rows=[r for r in rows if r.get('capacity') is not None and r.get('validfrom')]
    if not rows:return None
    r=max(rows,key=lambda x:x['validfrom'])
    return {'mw':float(r['capacity'])/1000.0,'validfrom':r['validfrom'],'validto':r.get('validto'),'lastupdate':r.get('lastupdate')}


def tennet_json(url,hours=8):
    if not TENNET_TOKEN:return None
    date_from,date_to=utc_window(hours)
    return get_json(url,{'date_from':date_from,'date_to':date_to},{'apikey':TENNET_TOKEN,'Accept':'application/json'})


def walk(obj,path=''):
    if isinstance(obj,dict):
        for k,v in obj.items():yield from walk(v,f'{path}.{k}' if path else k)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from walk(v,f'{path}[{i}]')
    else:yield path,obj


def latest_tennet_metered():
    # TenneT rejects overly large live-query windows. Eight hours is enough to
    # survive normal publication delays while remaining within the API contract.
    d=tennet_json(TENNET_METERED,8)
    if not d:return None
    candidates=[];timestamps=[]
    for path,val in walk(d):
        key=path.lower()
        if isinstance(val,(int,float)) and any(x in key for x in ('quantity','volume','value','injection','load','power')):
            if not any(x in key for x in ('sequence','position','price')):candidates.append((path,float(val)))
        if isinstance(val,str) and any(x in key for x in ('time','date','start','valid')):
            if 't' in val and ('z' in val.lower() or '+' in val):timestamps.append(val)
    if not candidates:return None
    preferred=[x for x in candidates if any(w in x[0].lower() for w in ('metered','injection','load','quantity'))]
    value=(preferred or candidates)[-1][1]
    if abs(value)>200000:value/=1000.0
    return {'mw':value,'measured_at':timestamps[-1] if timestamps else None,'raw_field':(preferred or candidates)[-1][0]}


def latest_tennet_balance():
    d=tennet_json(TENNET_BALANCE,1)
    if not d:return None
    fields={}
    for path,val in walk(d):
        leaf=path.split('.')[-1].split('[')[0]
        if isinstance(val,(int,float)) and leaf in ('power_afrr_in','power_afrr_out','power_igcc_in','power_igcc_out','power_mfrrda_in','power_mfrrda_out','power_picasso_in','power_picasso_out'):
            fields[leaf]=float(val)
    if not fields:return None
    up=sum(v for k,v in fields.items() if k.endswith('_in'))
    down=sum(v for k,v in fields.items() if k.endswith('_out'))
    return {'up_mw':round(up,1),'down_mw':round(down,1),'delta_mw':round(up-down,1),**fields}


def entso_request(params):
    q={'securityToken':ENTSO_TOKEN,**params};url=ENTSO_API+'?'+urllib.parse.urlencode(q)
    with urllib.request.urlopen(url,timeout=30) as r:return r.read()


def points(xml_bytes):
    root=ET.fromstring(xml_bytes);vals=[]
    for el in root.iter():
        if el.tag.endswith('quantity'):
            try:vals.append(float(el.text))
            except (TypeError,ValueError):pass
    return vals


def entso_last(params):
    vals=points(entso_request(params));return vals[-1] if vals else None


def entso_window():
    now=datetime.now(timezone.utc);start=now-timedelta(hours=6);end=now+timedelta(hours=1);fmt='%Y%m%d%H%M';return start.strftime(fmt),end.strftime(fmt)


def border_flow(other,start,end):
    inbound=entso_last({'documentType':'A11','in_Domain':other,'out_Domain':NL,'periodStart':start,'periodEnd':end}) or 0.0
    outbound=entso_last({'documentType':'A11','in_Domain':NL,'out_Domain':other,'periodStart':start,'periodEnd':end}) or 0.0
    return inbound-outbound


def main():
    OUT.parent.mkdir(parents=True,exist_ok=True);now=datetime.now(timezone.utc)
    data={'status':'no-data','generated_at':now.isoformat(),'measured_at':None,'load_mw':None,'generation_mw':None,'net_import_mw':None,'border_flows':{},
          'generation_by_province':{},'offshore_wind_mw':{},'tennet':{},'sources':[],'warnings':[]}

    if TENNET_TOKEN:
        try:
            m=latest_tennet_metered()
            if m:
                data['load_mw']=round(m['mw'],1);data['measured_at']=m.get('measured_at');data['tennet']['metered_injections']=m
        except Exception as e:data['warnings'].append('TenneT metered injections: '+str(e))
        try:
            b=latest_tennet_balance()
            if b:data['tennet']['balance_delta']=b
        except Exception as e:data['warnings'].append('TenneT balance delta high res: '+str(e))
        data['sources'].append('TenneT')

    if NED_TOKEN:
        try:
            load=latest_ned(0,59,2)
            if load:
                data['ned_load_mw']=round(load['mw'],1)
                if data['load_mw'] is None:data['load_mw']=data['ned_load_mw'];data['measured_at']=load['validfrom']
        except Exception as e:data['warnings'].append('NED load: '+str(e))
        try:
            mix=latest_ned(0,27,1)
            if mix:data['generation_mw']=round(mix['mw'],1);data['measured_at']=max(filter(None,[data['measured_at'],mix['validfrom']]))
        except Exception as e:data['warnings'].append('NED generation: '+str(e))
        for pid,name in PROVINCES.items():
            bucket={}
            for type_id,key in ((1,'wind_onshore_mw'),(2,'solar_mw')):
                try:
                    x=latest_ned(pid,type_id,1)
                    if x:bucket[key]=round(x['mw'],1);bucket['measured_at']=x['validfrom']
                except Exception as e:data['warnings'].append(f'NED {name} {key}: {e}')
            if bucket:data['generation_by_province'][name]=bucket
        for pid,name in OFFSHORE.items():
            try:
                x=latest_ned(pid,17,1)
                if x:data['offshore_wind_mw'][name]={'mw':round(x['mw'],1),'measured_at':x['validfrom']}
            except Exception as e:data['warnings'].append(f'NED offshore {name}: {e}')
        data['sources'].append('NED')

    if ENTSO_TOKEN:
        start,end=entso_window()
        for label,domain in BORDERS.items():
            try:data['border_flows'][label]=round(border_flow(domain,start,end),1)
            except Exception as e:data['warnings'].append(f'ENTSO-E {label}: {e}')
        if data['border_flows']:data['net_import_mw']=round(sum(data['border_flows'].values()),1)
        data['sources'].append('ENTSO-E')

    if data['load_mw'] is not None or data['generation_mw'] is not None or data['tennet'] or data['generation_by_province'] or data['offshore_wind_mw'] or data['border_flows']:
        data['status']='ok'
    elif not NED_TOKEN and not TENNET_TOKEN and not ENTSO_TOKEN:
        data['status']='token-missing';data['warnings'].append('Configure NED_TOKEN and TENNET_TOKEN in GitHub Actions secrets.')
    else:data['status']='error'
    if not data['measured_at'] and data['status']=='ok':data['measured_at']=now.replace(minute=(now.minute//15)*15,second=0,microsecond=0).isoformat()
    OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');print(json.dumps(data,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
