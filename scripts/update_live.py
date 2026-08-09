#!/usr/bin/env python3
import json, os, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

API='https://web-api.tp.entsoe.eu/api'
NL='10YNL----------L'
BORDERS={
    'DE':'10Y1001A1001A82H',
    'BE':'10YBE----------2',
    'GB':'10YGB-0000A-000',
    'NO2':'10YNO-2--------T',
    'DK1':'10YDK-1--------W',
}
OUT=Path('data/live.json')
TOKEN=os.getenv('ENTSO_E_TOKEN','').strip()


def request(params):
    q={'securityToken':TOKEN,**params}
    url=API+'?'+urllib.parse.urlencode(q)
    with urllib.request.urlopen(url,timeout=30) as r:
        return r.read()


def points(xml_bytes):
    root=ET.fromstring(xml_bytes)
    vals=[]
    for el in root.iter():
        if el.tag.endswith('quantity'):
            try: vals.append(float(el.text))
            except (TypeError,ValueError): pass
    return vals


def last_value(params):
    vals=points(request(params))
    return vals[-1] if vals else None


def time_window():
    now=datetime.now(timezone.utc)
    start=now-timedelta(hours=3)
    end=now+timedelta(hours=1)
    fmt='%Y%m%d%H%M'
    return start.strftime(fmt),end.strftime(fmt)


def border_flow(other,start,end):
    # Positive means import into NL. ENTSO-E publishes directional series,
    # so read both directions and net them.
    inbound=last_value({'documentType':'A11','in_Domain':other,'out_Domain':NL,'periodStart':start,'periodEnd':end}) or 0.0
    outbound=last_value({'documentType':'A11','in_Domain':NL,'out_Domain':other,'periodStart':start,'periodEnd':end}) or 0.0
    return inbound-outbound


def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc)
    data={'status':'token-missing','generated_at':now.isoformat(),'measured_at':None,'load_mw':None,'generation_mw':None,'net_import_mw':None,'border_flows':{},'source':'ENTSO-E Transparency Platform'}
    if not TOKEN:
        OUT.write_text(json.dumps(data,indent=2)+'\n')
        print('ENTSO_E_TOKEN not set; wrote topology-only snapshot')
        return
    start,end=time_window()
    errors=[]
    try:
        data['load_mw']=last_value({'documentType':'A65','processType':'A16','outBiddingZone_Domain':NL,'periodStart':start,'periodEnd':end})
    except Exception as e: errors.append('load: '+str(e))
    try:
        # A75 returns one series per production type. Sum latest point from each TimeSeries.
        raw=request({'documentType':'A75','processType':'A16','in_Domain':NL,'periodStart':start,'periodEnd':end})
        root=ET.fromstring(raw); latest=[]
        for ts in [x for x in root.iter() if x.tag.endswith('TimeSeries')]:
            vals=[]
            for el in ts.iter():
                if el.tag.endswith('quantity'):
                    try: vals.append(float(el.text))
                    except (TypeError,ValueError): pass
            if vals: latest.append(vals[-1])
        data['generation_mw']=sum(latest) if latest else None
    except Exception as e: errors.append('generation: '+str(e))
    for label,domain in BORDERS.items():
        try: data['border_flows'][label]=round(border_flow(domain,start,end),1)
        except Exception as e: errors.append(f'{label}: {e}')
    if data['border_flows']:
        data['net_import_mw']=round(sum(data['border_flows'].values()),1)
    data['status']='ok' if (data['load_mw'] is not None or data['border_flows']) else 'error'
    data['measured_at']=now.replace(minute=(now.minute//15)*15,second=0,microsecond=0).isoformat()
    if errors: data['warnings']=errors
    OUT.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))

if __name__=='__main__': main()
