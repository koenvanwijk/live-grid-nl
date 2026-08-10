#!/usr/bin/env python3
"""Enrich data/live.json with explicit provenance metadata.

The collector intentionally keeps source acquisition separate from presentation metadata.
This post-processing step makes measured, derived and static values machine-readable so
the UI never has to infer reliability from field names.
"""
import json
from pathlib import Path

PATH = Path('data/live.json')


def meta(kind, source, measured_at=None, derivation=None):
    value = {'provenance': kind, 'source': source}
    if measured_at:
        value['measured_at'] = measured_at
    if derivation:
        value['derivation'] = derivation
    return value


def main():
    data = json.loads(PATH.read_text())
    measured_at = data.get('measured_at') or data.get('generated_at')
    provenance = {}

    if data.get('load_mw') is not None:
        if data.get('tennet', {}).get('metered_injections'):
            provenance['load_mw'] = meta('measured', 'TenneT', data['tennet']['metered_injections'].get('measured_at') or measured_at)
        elif data.get('ned_load_mw') is not None:
            provenance['load_mw'] = meta('measured', 'NED', measured_at)

    mix = data.get('generation_mix') or []
    generation_by_type = {}
    for row in mix:
        row['provenance'] = 'measured'
        row['source'] = 'ENTSO-E'
        row['measured_at'] = measured_at
        generation_by_type[row.get('code') or row.get('name')] = row.get('mw')
    data['generation_by_type'] = generation_by_type
    if mix:
        provenance['generation_mw'] = meta('measured', 'ENTSO-E', measured_at)
        provenance['generation_mix'] = meta('measured', 'ENTSO-E', measured_at)

    if data.get('border_flows'):
        provenance['border_flows'] = meta('measured', 'ENTSO-E', measured_at)
        provenance['net_import_mw'] = meta(
            'derived', 'ENTSO-E', measured_at,
            'Som van de actuele fysieke grensstromen per gekoppeld land.'
        )

    for province, bucket in (data.get('generation_by_province') or {}).items():
        bucket['provenance'] = 'measured'
        bucket['source'] = 'NED'
        bucket.setdefault('measured_at', measured_at)
        bucket['derivation'] = 'Regionale brondata; kaartallocatie naar individuele stations is afgeleid.'

    for park, value in (data.get('offshore_wind_mw') or {}).items():
        value['provenance'] = 'measured'
        value['source'] = 'NED'
        value.setdefault('measured_at', measured_at)

    provenance['topology'] = meta('static', 'TenneT ArcGIS')
    provenance['country_boundaries'] = meta('static', 'PDOK/Kadaster')
    provenance['plant_capacity'] = meta('static', 'curated registry')
    provenance['internal_line_utilization'] = meta(
        'derived', 'live-grid-nl model', measured_at,
        'Modelindicatie uit nettopologie en actuele grensstromen; geen TenneT SCADA-lijnmeting.'
    )
    provenance['plant_generation'] = meta(
        'derived', 'ENTSO-E', measured_at,
        'Landelijke productie per brandstoftype pro-rata verdeeld over bekende centrales van dat type totdat unitdata beschikbaar is.'
    )
    provenance['regional_station_injections'] = meta(
        'derived', 'NED + TenneT', measured_at,
        'NED regionale productie verdeeld over nabijgelegen echte 110/150-kV TenneT-stations.'
    )
    data['provenance'] = provenance

    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
