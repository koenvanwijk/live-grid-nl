#!/usr/bin/env python3
"""Add a canonical observation model to data/live.json.

Two independent axes are encoded for every value:
- provenance: measured | derived | modelled | static
- temporal: actual | forecast | none

Legacy fields remain for backwards compatibility, but UI code can consume `observations`
without guessing whether a value is measured, derived, historical/current, or forecast.
"""
import json
from pathlib import Path

PATH = Path('data/live.json')
PROVENANCE = {'measured', 'derived', 'modelled', 'static'}
TEMPORAL = {'actual', 'forecast', 'none'}


def obs(value, unit='MW', provenance='measured', temporal='actual', source=None,
        measured_at=None, interval_start=None, interval_end=None, published_at=None,
        derivation=None):
    assert provenance in PROVENANCE
    assert temporal in TEMPORAL
    out = {'value': value, 'unit': unit, 'provenance': provenance, 'temporal': temporal}
    if source: out['source'] = source
    if measured_at: out['measured_at'] = measured_at
    if interval_start: out['interval_start'] = interval_start
    if interval_end: out['interval_end'] = interval_end
    if published_at: out['published_at'] = published_at
    if derivation: out['derivation'] = derivation
    return out


def legacy_meta(provenance, source, temporal='actual', measured_at=None, interval_end=None, derivation=None):
    out = {'provenance': provenance, 'temporal': temporal, 'source': source}
    if measured_at:
        out['measured_at'] = measured_at
        out['interval_start'] = measured_at
    if interval_end: out['interval_end'] = interval_end
    if derivation: out['derivation'] = derivation
    return out


def main():
    data = json.loads(PATH.read_text())
    generated = data.get('generated_at')
    measured_at = data.get('measured_at') or generated
    provenance = {}
    observations = {
        'system': {}, 'generation_mix': {}, 'border_flows': {},
        'generation_by_province': {}, 'offshore_wind': {},
        'model': {}, 'static': {}
    }

    metered = data.get('tennet', {}).get('metered_injections') or {}
    if data.get('load_mw') is not None:
        if metered:
            ts = metered.get('measured_at') or measured_at
            end = metered.get('interval_end')
            provenance['load_mw'] = legacy_meta('measured', 'TenneT', 'actual', ts, end)
            observations['system']['load'] = obs(data['load_mw'], provenance='measured', temporal='actual', source='TenneT', measured_at=ts, interval_start=ts, interval_end=end, published_at=generated)
        elif data.get('ned_load_mw') is not None:
            provenance['load_mw'] = legacy_meta('measured', 'NED', 'actual', measured_at)
            observations['system']['load'] = obs(data['load_mw'], provenance='measured', temporal='actual', source='NED', measured_at=measured_at, interval_start=measured_at, published_at=generated)

    mix = data.get('generation_mix') or []
    generation_by_type = {}
    for row in mix:
        row['provenance'] = 'measured'; row['temporal'] = 'actual'; row['source'] = 'ENTSO-E'; row['measured_at'] = measured_at
        code = row.get('code') or row.get('name')
        generation_by_type[code] = row.get('mw')
        observations['generation_mix'][code] = obs(row.get('mw'), provenance='measured', temporal='actual', source='ENTSO-E', measured_at=measured_at, interval_start=measured_at, published_at=generated)
    data['generation_by_type'] = generation_by_type
    if mix:
        provenance['generation_mw'] = legacy_meta('measured', 'ENTSO-E', 'actual', measured_at)
        provenance['generation_mix'] = legacy_meta('measured', 'ENTSO-E', 'actual', measured_at)
        observations['system']['generation'] = obs(data.get('generation_mw'), provenance='measured', temporal='actual', source='ENTSO-E', measured_at=measured_at, interval_start=measured_at, published_at=generated)

    if data.get('border_flows'):
        provenance['border_flows'] = legacy_meta('measured', 'ENTSO-E', 'actual', measured_at)
        for country, value in data['border_flows'].items():
            observations['border_flows'][country] = obs(value, provenance='measured', temporal='actual', source='ENTSO-E', measured_at=measured_at, interval_start=measured_at, published_at=generated)
        provenance['net_import_mw'] = legacy_meta('derived', 'ENTSO-E', 'actual', measured_at, derivation='Som van actuele fysieke grensstromen per gekoppeld land.')
        observations['system']['net_import'] = obs(data.get('net_import_mw'), provenance='derived', temporal='actual', source='ENTSO-E', measured_at=measured_at, interval_start=measured_at, published_at=generated, derivation='Som van actuele fysieke grensstromen per gekoppeld land.')

    for province, bucket in (data.get('generation_by_province') or {}).items():
        ts = bucket.get('measured_at') or measured_at
        bucket.update({'provenance':'measured','temporal':'actual','source':'NED'})
        observations['generation_by_province'][province] = {
            key: obs(value, provenance='measured', temporal='actual', source='NED', measured_at=ts, interval_start=ts, published_at=generated)
            for key, value in bucket.items() if key.endswith('_mw')
        }

    for park, value in (data.get('offshore_wind_mw') or {}).items():
        ts = value.get('measured_at') or measured_at
        value.update({'provenance':'measured','temporal':'actual','source':'NED'})
        observations['offshore_wind'][park] = obs(value.get('mw'), provenance='measured', temporal='actual', source='NED', measured_at=ts, interval_start=ts, published_at=generated)

    provenance['topology'] = legacy_meta('static', 'TenneT ArcGIS', 'none')
    provenance['country_boundaries'] = legacy_meta('static', 'PDOK/Kadaster', 'none')
    provenance['plant_capacity'] = legacy_meta('static', 'curated registry', 'none')
    provenance['internal_line_utilization'] = legacy_meta('derived', 'live-grid-nl model', 'actual', measured_at, derivation='Modelindicatie uit nettopologie en actuele grensstromen; geen TenneT SCADA-lijnmeting.')
    provenance['plant_generation'] = legacy_meta('derived', 'ENTSO-E', 'actual', measured_at, derivation='Landelijke productie per brandstoftype pro-rata verdeeld over bekende centrales van dat type.')
    provenance['regional_station_injections'] = legacy_meta('derived', 'NED + TenneT', 'actual', measured_at, derivation='NED regionale productie verdeeld over nabijgelegen 110/150-kV TenneT-stations.')

    observations['model']['internal_line_utilization'] = obs(None, provenance='derived', temporal='actual', source='live-grid-nl model', measured_at=measured_at, derivation=provenance['internal_line_utilization']['derivation'])
    observations['model']['plant_generation'] = obs(None, provenance='derived', temporal='actual', source='ENTSO-E', measured_at=measured_at, derivation=provenance['plant_generation']['derivation'])
    observations['model']['regional_station_injections'] = obs(None, provenance='derived', temporal='actual', source='NED + TenneT', measured_at=measured_at, derivation=provenance['regional_station_injections']['derivation'])
    observations['static']['topology'] = obs(None, unit=None, provenance='static', temporal='none', source='TenneT ArcGIS')
    observations['static']['country_boundaries'] = obs(None, unit=None, provenance='static', temporal='none', source='PDOK/Kadaster')
    observations['static']['plant_capacity'] = obs(None, unit='MW', provenance='static', temporal='none', source='curated registry')

    data['schema_version'] = 2
    data['provenance'] = provenance
    data['observations'] = observations
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
