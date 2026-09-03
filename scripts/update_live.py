#!/usr/bin/env python3
import json, os, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER_AGENT='live-grid-nl/1.0 (+https://github.com/koenvanwijk/live-grid-nl)'
RETRY_STATUS={502,503,504}
ENTSO_API='https://web-api.tp.entsoe.eu/api'
NED_API='https://api.ned.nl/v1/utilizations'
TENNET_METERED='https://api.tennet.eu/publications/v1/metered-injections'
TENNET_BALANCE='https://api.tennet.eu/publications/v1/balance-delta-high-res/latest'
NL='10YNL----------L'
BORDERS={'DE':'10Y1001A1001A82H','BE':'10YBE----------2','GB':'10YGB-0000A-000','NO2':'10YNO-2--------T','DK1':'10YDK-1--------W'}
CORE_BORDERS=('DE','BE')
PROVINCES={1:'Groningen',2:'Friesland',3:'Drenthe',4:'Overijssel',5:'Flevoland',6:'Gelderland',7:'Utrecht',8:'Noord-Holland',9:'Zuid-Holland',10:'Zeeland',11:'Noord-Brabant',12:'Limburg'}
OFFSHORE={28:'Luchterduinen',29:'Prinses Amalia',30:'Egmond aan Zee',31:'Gemini',33:'Borssele 1&2',34:'Borssele 3&4',35:'Hollandse Kust Zuid',36:'Hollandse Kust Noord'}
PSR_NAMES={'B01':'Biomassa','B02':'Bruinkool','B03':'Kolengas','B04':'Gas','B05':'Steenkool','B06':'Olie','B07':'Olieschalie','B08':'Turf','B09':'Geothermie','B10':'Pompaccumulatie','B11':'Waterkracht rivier','B12':'Waterkracht reservoir','B13':'Getijden/zee','B14':'Kernenergie','B15':'Overig hernieuwbaar','B16':'Zon','B17':'Afval','B18':'Wind op zee','B19':'Wind op land','B20':'Overig','B25':'Opslag'}
OUT=Path('data/live.json')
ENTSO_TOKEN=os.getenv('ENTSO_E_TOKEN','').strip();NED_TOKEN=os.getenv('NED_TOKEN','').strip();TENNET_TOKEN=os.getenv('TENNET_TOKEN','').strip()
class ApiError(RuntimeError):pass

def get_json(url,params,headers=None):
    req=urllib.request.Request(url+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'live-grid-nl/1.0 (+https://github.com/koenvanwijk/live-grid-nl)',**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
    except urllib.error.HTTPError as e:
        try:body=e.read().decode('utf-8','replace').strip().replace('\n',' ')[:500]
        except Exception:body=''
        raise ApiError(f'HTTP {e.code} {e.reason}'+(f': {body}' if body else '')) from e

def parse_dt(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except ValueError:return None

def tennet_window(hours=23):
    now=datetime.now(timezone.utc);start=now-timedelta(hours=hours);fmt='%d-%m-%Y %H:%M:%S';return start.strftime(fmt),now.strftime(fmt)
def ned_records(point,type_id,activity=1,days=1):
    if not NED_TOKEN:return []
    today=datetime.now(timezone.utc).date();start=today-timedelta(days=days);end=today+timedelta(days=1)
    p={'point':point,'type':type_id,'granularity':4,'granularitytimezone':0,'classification':2,'activity':activity,'validfrom[after]':start.isoformat(),'validfrom[strictly_before]':end.isoformat(),'itemsPerPage':1,'order[validfrom]':'desc'}
    d=get_json(NED_API,p,{'X-AUTH-TOKEN':NED_TOKEN,'Accept':'application/ld+json'});return d if isinstance(d,list) else d.get('hydra:member') or d.get('member') or d.get('data') or []
def latest_ned(point,type_id,activity=1):
    rows=[r for r in ned_records(point,type_id,activity) if r.get('capacity') is not None and r.get('validfrom')]
    if not rows:return None
    r=max(rows,key=lambda x:x['validfrom']);return {'mw':float(r['capacity'])/1000.0,'validfrom':r['validfrom'],'validto':r.get('validto'),'lastupdate':r.get('lastupdate')}
def tennet_json(url,hours=None):
    if not TENNET_TOKEN:return None
    params={}
    if hours is not None:
        a,b=tennet_window(hours);params={'date_from':a,'date_to':b}
    return get_json(url,params,{'apikey':TENNET_TOKEN,'Accept':'application/json'})
def response_points(data):
    result=[]
    for series in (data or {}).get('Response',{}).get('TimeSeries',[]):
        periods=series.get('Period',[]);periods=[periods] if isinstance(periods,dict) else periods
        for period in periods:result.extend(period.get('points') or period.get('Points') or [])
    return result
def number(value):
    try:return float(value)
    except (TypeError,ValueError):return 0.0
def latest_tennet_metered():
    rows=response_points(tennet_json(TENNET_METERED,23))
    if not rows:return None
    row=max(rows,key=lambda x:x.get('timeInterval_start',''));mwh=number(row.get('measured_infeed'))-number(row.get('scheduled_export'))+number(row.get('scheduled_import'))
    return {'mw':mwh*4,'measured_at':row.get('timeInterval_start'),'interval_end':row.get('timeInterval_end'),'measured_infeed_mwh':number(row.get('measured_infeed')),'scheduled_export_mwh':number(row.get('scheduled_export')),'scheduled_import_mwh':number(row.get('scheduled_import'))}
def latest_tennet_balance():
    rows=response_points(tennet_json(TENNET_BALANCE))
    if not rows:return None
    row=max(rows,key=lambda x:x.get('timeInterval_start',''));names=('power_afrr_in','power_afrr_out','power_igcc_in','power_igcc_out','power_mfrrda_in','power_mfrrda_out','power_picasso_in','power_picasso_out','power_mari_in','power_mari_out');fields={n:number(row.get(n)) for n in names};up=sum(v for k,v in fields.items() if k.endswith('_in'));down=sum(v for k,v in fields.items() if k.endswith('_out'));return {'measured_at':row.get('timeInterval_start'),'up_mw':round(up,1),'down_mw':round(down,1),'delta_mw':round(up-down,1),**fields}
def entso_query_hint(params):
    keys=('documentType','processType','in_Domain','out_Domain','outBiddingZone_Domain','inBiddingZone_Domain')
    return ' '.join(f'{k}={params[k]}' for k in keys if k in params)
def entso_error_body(err):
    try:body=err.read().decode('utf-8','replace')
    except Exception:return ''
    if body.strip().startswith('<'):
        try:
            texts=[(m.text or '').strip() for m in ET.fromstring(body).iter() if local_name(m.tag) in ('text','Text','Reason') and (m.text or '').strip()]
            if texts:return ' | '.join(texts)[:300]
        except Exception:pass
    return body.strip().replace('\n',' ')[:300]
def entso_request(params,retries=3,backoff=2.0):
    url=ENTSO_API+'?'+urllib.parse.urlencode({'securityToken':ENTSO_TOKEN,**params})
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return r.read()
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUS and attempt<retries-1:time.sleep(backoff*2**attempt);continue
            body=entso_error_body(e)
            raise ApiError(f'HTTP {e.code} {e.reason} [{entso_query_hint(params)}]'+(f': {body}' if body else '')) from e
        except OSError:  # URLError, TimeoutError and other socket errors
            if attempt<retries-1:time.sleep(backoff*2**attempt);continue
            raise
def entso_window():
    now=datetime.now(timezone.utc);start=now-timedelta(hours=8);end=now+timedelta(hours=1);fmt='%Y%m%d%H%M';return start.strftime(fmt),end.strftime(fmt)
def local_name(tag):return tag.rsplit('}',1)[-1]
def child_text(node,*names):
    wanted=set(names)
    for el in node.iter():
        if local_name(el.tag) in wanted and el.text:return el.text.strip()
    return None

def resolution_seconds(value):
    return {'PT15M':900,'PT30M':1800,'PT60M':3600,'PT1H':3600}.get(value,900)
def series_points(series):
    out={}
    for period in series.iter():
        if local_name(period.tag)!='Period':continue
        start_el=child_text(period,'start');seconds=resolution_seconds(child_text(period,'resolution') or 'PT15M')
        start=parse_dt(start_el)
        if not start:continue
        for point in period:
            if local_name(point.tag)!='Point':continue
            pos=child_text(point,'position');qty=child_text(point,'quantity')
            try:ts=start+timedelta(seconds=seconds*(int(pos or '1')-1));value=float(qty)
            except (TypeError,ValueError):continue
            out[ts.replace(microsecond=0).isoformat()]=value
    return out

def entso_load_series(start,end):
    root=ET.fromstring(entso_request({'documentType':'A65','processType':'A16','outBiddingZone_Domain':NL,'periodStart':start,'periodEnd':end}));out={}
    for series in root.iter():
        if local_name(series.tag)!='TimeSeries':continue
        for ts,val in series_points(series).items():out[ts]=out.get(ts,0.0)+val
    return out

def entso_generation_series(start,end):
    root=ET.fromstring(entso_request({'documentType':'A75','processType':'A16','in_Domain':NL,'periodStart':start,'periodEnd':end}));out={}
    for series in root.iter():
        if local_name(series.tag)!='TimeSeries':continue
        psr=child_text(series,'psrType')
        if not psr:continue
        has_in=any(local_name(el.tag)=='inBiddingZone_Domain.mRID' for el in series.iter());has_out=any(local_name(el.tag)=='outBiddingZone_Domain.mRID' for el in series.iter())
        if has_out and not has_in:continue
        for ts,val in series_points(series).items():out.setdefault(ts,{})[psr]=out.setdefault(ts,{}).get(psr,0.0)+val
    return out

def entso_direction_series(in_domain,out_domain,start,end):
    root=ET.fromstring(entso_request({'documentType':'A11','in_Domain':in_domain,'out_Domain':out_domain,'periodStart':start,'periodEnd':end}));out={}
    for series in root.iter():
        if local_name(series.tag)!='TimeSeries':continue
        for ts,val in series_points(series).items():out[ts]=out.get(ts,0.0)+val
    return out

def entso_border_series(other,start,end):
    # ENTSO-E physical-flow convention: in_Domain receives, out_Domain sends.
    inbound=entso_direction_series(NL,other,start,end)
    outbound=entso_direction_series(other,NL,start,end)
    stamps=set(inbound)|set(outbound)
    return {ts:inbound.get(ts,0.0)-outbound.get(ts,0.0) for ts in stamps}

def latest_common_timestamp(load,gen,borders):
    common=set(load)&set(gen)
    for label in CORE_BORDERS:
        if borders.get(label):common &= set(borders[label])
    if not common:return None
    # Avoid selecting an interval that starts in the future relative to collector time.
    now=datetime.now(timezone.utc)
    valid=[ts for ts in common if (parse_dt(ts) or now)<=now]
    return max(valid or common)

def aligned_entso_balance(start,end):
    load=entso_load_series(start,end);gen=entso_generation_series(start,end);borders={}
    for label,domain in BORDERS.items():borders[label]=entso_border_series(domain,start,end)
    ts=latest_common_timestamp(load,gen,borders)
    if not ts:raise ApiError('ENTSO-E: no common timestamp for load, generation and DE/BE border flows')
    mix=[{'code':code,'name':PSR_NAMES.get(code,code),'mw':round(mw,1)} for code,mw in gen[ts].items() if abs(mw)>=.05]
    mix.sort(key=lambda r:r['mw'],reverse=True)
    flows={label:round(series[ts],1) for label,series in borders.items() if ts in series}
    generation=round(sum(r['mw'] for r in mix),1);net_import=round(sum(flows.values()),1)
    residual=round(load[ts]-generation-net_import,1)
    return {'timestamp':ts,'load_mw':round(load[ts],1),'generation_mw':generation,'generation_mix':mix,'border_flows':flows,'net_import_mw':net_import,'balance_residual_mw':residual}

def entso_installed_capacity():
    now=datetime.now(timezone.utc);y=now.year;start=f'{y}01010000';end=f'{y+1}01010000'
    root=ET.fromstring(entso_request({'documentType':'A68','processType':'A33','in_Domain':NL,'periodStart':start,'periodEnd':end}));caps={}
    for series in root.iter():
        if local_name(series.tag)!='TimeSeries':continue
        psr=child_text(series,'psrType')
        if not psr:continue
        vals=[]
        for el in series.iter():
            if local_name(el.tag)=='quantity':
                try:vals.append(float(el.text))
                except (TypeError,ValueError):pass
        if vals:caps[psr]=caps.get(psr,0.0)+max(vals)
    return {k:round(v,1) for k,v in caps.items() if v>0}

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True);now=datetime.now(timezone.utc)
    data={'status':'no-data','generated_at':now.isoformat(),'measured_at':None,'balance_timestamp':None,'national_balance_source':None,'load_mw':None,'generation_mw':None,'generation_mix':[],'installed_capacity_by_type':{},'net_import_mw':None,'border_flows':{},'generation_by_province':{},'offshore_wind_mw':{},'tennet':{},'sources':[],'warnings':[]}
    if TENNET_TOKEN:
        try:
            m=latest_tennet_metered()
            if m:data['tennet']['metered_injections']=m
        except Exception as e:data['warnings'].append('TenneT metered injections: '+str(e))
        try:
            b=latest_tennet_balance()
            if b:data['tennet']['balance_delta']=b
        except Exception as e:data['warnings'].append('TenneT balance delta: '+str(e))
        data['sources'].append('TenneT')
    if NED_TOKEN:
        try:
            load=latest_ned(0,59,2)
            if load:data['ned_load_mw']=round(load['mw'],1);data['ned_load_measured_at']=load['validfrom']
        except Exception as e:data['warnings'].append('NED load: '+str(e))
        try:
            prod=latest_ned(0,27,1)
            if prod:data['ned_generation_mw']=round(prod['mw'],1);data['ned_generation_measured_at']=prod['validfrom']
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
        try:
            b=aligned_entso_balance(start,end)
            data.update({k:b[k] for k in ('load_mw','generation_mw','generation_mix','border_flows','net_import_mw','balance_residual_mw')})
            data['balance_timestamp']=b['timestamp'];data['measured_at']=b['timestamp'];data['national_balance_source']='ENTSO-E aligned';data['balance_equation']='vraag = opwek + netto import + restverschil'
        except Exception as e:data['warnings'].append('ENTSO-E aligned balance: '+str(e))
        try:data['installed_capacity_by_type']=entso_installed_capacity()
        except Exception as e:data['warnings'].append('ENTSO-E installed capacity: '+str(e))
        data['sources'].append('ENTSO-E')
    # Fallback only when a complete aligned ENTSO-E national balance is unavailable.
    if data['national_balance_source'] is None:
        if data.get('ned_load_mw') is not None:data['load_mw']=data['ned_load_mw'];data['measured_at']=data.get('ned_load_measured_at');data['national_balance_source']='NED partial fallback'
        if data.get('ned_generation_mw') is not None:data['generation_mw']=data['ned_generation_mw'];data['measured_at']=max(filter(None,[data.get('measured_at'),data.get('ned_generation_measured_at')]))
    if data['load_mw'] is not None or data['generation_mw'] is not None or data['tennet'] or data['generation_by_province'] or data['offshore_wind_mw'] or data['border_flows']:data['status']='ok'
    elif not NED_TOKEN and not TENNET_TOKEN and not ENTSO_TOKEN:data['status']='token-missing';data['warnings'].append('Configure NED_TOKEN, TENNET_TOKEN and ENTSO_E_TOKEN in GitHub Actions secrets.')
    else:data['status']='error'
    if not data['measured_at'] and data['status']=='ok':data['measured_at']=now.replace(minute=(now.minute//15)*15,second=0,microsecond=0).isoformat()
    OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');print(json.dumps(data,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
