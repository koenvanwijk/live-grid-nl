#!/usr/bin/env python3
"""Add canonical provenance/observation metadata to data/live.json."""
import json
from pathlib import Path

PATH=Path('data/live.json')
PROVENANCE={'measured','derived','modelled','static'};TEMPORAL={'actual','forecast','none'}

def obs(value,unit='MW',provenance='measured',temporal='actual',source=None,measured_at=None,interval_start=None,interval_end=None,published_at=None,derivation=None):
    assert provenance in PROVENANCE and temporal in TEMPORAL
    out={'value':value,'unit':unit,'provenance':provenance,'temporal':temporal}
    if source:out['source']=source
    if measured_at:out['measured_at']=measured_at
    if interval_start:out['interval_start']=interval_start
    if interval_end:out['interval_end']=interval_end
    if published_at:out['published_at']=published_at
    if derivation:out['derivation']=derivation
    return out

def meta(provenance,source,temporal='actual',measured_at=None,derivation=None):
    out={'provenance':provenance,'temporal':temporal,'source':source}
    if measured_at:out['measured_at']=measured_at;out['interval_start']=measured_at
    if derivation:out['derivation']=derivation
    return out

def main():
    data=json.loads(PATH.read_text());generated=data.get('generated_at');aligned=data.get('national_balance_source')=='ENTSO-E aligned';balance_ts=data.get('balance_timestamp') or data.get('measured_at') or generated
    provenance={};observations={'system':{},'generation_mix':{},'border_flows':{},'generation_by_province':{},'offshore_wind':{},'comparison':{},'model':{},'static':{}}

    if aligned:
        if data.get('load_mw') is not None:
            provenance['load_mw']=meta('measured','ENTSO-E','actual',balance_ts)
            observations['system']['load']=obs(data['load_mw'],source='ENTSO-E',measured_at=balance_ts,interval_start=balance_ts,published_at=generated)
        if data.get('generation_mw') is not None:
            provenance['generation_mw']=meta('measured','ENTSO-E','actual',balance_ts)
            observations['system']['generation']=obs(data['generation_mw'],source='ENTSO-E',measured_at=balance_ts,interval_start=balance_ts,published_at=generated)
        if data.get('net_import_mw') is not None:
            provenance['net_import_mw']=meta('derived','ENTSO-E','actual',balance_ts,'Som van fysieke grensstromen op hetzelfde ENTSO-E balansmoment.')
            observations['system']['net_import']=obs(data['net_import_mw'],provenance='derived',source='ENTSO-E',measured_at=balance_ts,interval_start=balance_ts,published_at=generated,derivation='Som van fysieke grensstromen op hetzelfde ENTSO-E balansmoment.')
    else:
        if data.get('load_mw') is not None:
            source='NED' if data.get('ned_load_mw') is not None else 'TenneT';ts=data.get('ned_load_measured_at') or balance_ts
            provenance['load_mw']=meta('measured',source,'actual',ts);observations['system']['load']=obs(data['load_mw'],source=source,measured_at=ts,interval_start=ts,published_at=generated)
        if data.get('generation_mw') is not None:
            source='NED' if data.get('ned_generation_mw') is not None else 'ENTSO-E';ts=data.get('ned_generation_measured_at') or balance_ts
            provenance['generation_mw']=meta('derived' if source=='NED' else 'measured',source,'actual',ts);observations['system']['generation']=obs(data['generation_mw'],provenance='derived' if source=='NED' else 'measured',source=source,measured_at=ts,interval_start=ts,published_at=generated)

    mix=data.get('generation_mix') or [];generation_by_type={}
    for row in mix:
        source='ENTSO-E' if aligned else row.get('source','ENTSO-E');ts=balance_ts if aligned else row.get('measured_at') or balance_ts
        row.update({'provenance':'measured','temporal':'actual','source':source,'measured_at':ts});code=row.get('code') or row.get('name');generation_by_type[code]=row.get('mw');observations['generation_mix'][code]=obs(row.get('mw'),source=source,measured_at=ts,interval_start=ts,published_at=generated)
    data['generation_by_type']=generation_by_type
    if mix:provenance['generation_mix']=meta('measured','ENTSO-E' if aligned else 'mixed','actual',balance_ts)

    if data.get('border_flows'):
        provenance['border_flows']=meta('measured','ENTSO-E','actual',balance_ts)
        for country,value in data['border_flows'].items():observations['border_flows'][country]=obs(value,source='ENTSO-E',measured_at=balance_ts,interval_start=balance_ts,published_at=generated)

    if data.get('ned_load_mw') is not None:
        observations['comparison']['ned_load']=obs(data['ned_load_mw'],source='NED',measured_at=data.get('ned_load_measured_at'),interval_start=data.get('ned_load_measured_at'),published_at=generated,derivation='Onafhankelijke NED-controlewaarde; niet gemengd in de ENTSO-E balans.')
    if data.get('ned_generation_mw') is not None:
        observations['comparison']['ned_generation']=obs(data['ned_generation_mw'],provenance='derived',source='NED',measured_at=data.get('ned_generation_measured_at'),interval_start=data.get('ned_generation_measured_at'),published_at=generated,derivation='Onafhankelijke NED-controlewaarde; niet gemengd in de ENTSO-E balans.')
    metered=data.get('tennet',{}).get('metered_injections') or {}
    if metered.get('mw') is not None:observations['comparison']['tennet_transmission_load']=obs(metered['mw'],source='TenneT',measured_at=metered.get('measured_at'),interval_start=metered.get('measured_at'),interval_end=metered.get('interval_end'),published_at=generated,derivation='TenneT transmissienet-belasting; aparte systeemgrens.')

    for province,bucket in (data.get('generation_by_province') or {}).items():
        ts=bucket.get('measured_at') or balance_ts;bucket.update({'provenance':'measured','temporal':'actual','source':'NED'})
        observations['generation_by_province'][province]={key:obs(value,source='NED',measured_at=ts,interval_start=ts,published_at=generated) for key,value in bucket.items() if key.endswith('_mw')}
    for park,value in (data.get('offshore_wind_mw') or {}).items():
        ts=value.get('measured_at') or balance_ts;value.update({'provenance':'measured','temporal':'actual','source':'NED'});observations['offshore_wind'][park]=obs(value.get('mw'),source='NED',measured_at=ts,interval_start=ts,published_at=generated)

    provenance['topology']=meta('static','TenneT ArcGIS','none');provenance['country_boundaries']=meta('static','PDOK/Kadaster','none');provenance['plant_capacity']=meta('static','curated registry','none')
    provenance['internal_line_utilization']=meta('derived','live-grid-nl model','actual',balance_ts,'Modelindicatie; geen TenneT SCADA-lijnmeting.')
    observations['static']['topology']=obs(None,unit=None,provenance='static',temporal='none',source='TenneT ArcGIS');observations['static']['country_boundaries']=obs(None,unit=None,provenance='static',temporal='none',source='PDOK/Kadaster');observations['static']['plant_capacity']=obs(None,provenance='static',temporal='none',source='curated registry')
    data['schema_version']=2;data['provenance']=provenance;data['observations']=observations;PATH.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
