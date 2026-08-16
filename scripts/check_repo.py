#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def main():
    solar = load('data/solar-parks.json')
    parks = solar.get('parks') or []
    assert solar.get('schema_version') == 3
    assert solar.get('overview_threshold_mwp') == 25.0
    assert len(parks) == solar.get('stats', {}).get('physical_parks')
    assert len(parks) >= 100
    assert any(0 < float(p.get('capacity_mwp', 0)) < 25 for p in parks)
    overview = [p for p in parks if float(p.get('capacity_mwp', 0)) >= 25]
    assert len(overview) == solar.get('stats', {}).get('overview_ge25mwp')
    assert all(p.get('status') == 'operationeel' for p in parks)
    assert all(float(p.get('capacity_mwp', 0)) > 0 for p in parks)
    assert all(p.get('source') == 'ROM3D Zon op Kaart' for p in parks)

    solar_js = (ROOT / 'data/solar-storage.js').read_text(encoding='utf-8')
    for fragment in ('solarThreshold','z<8?25','z<9.5?10','z<11?5','z<12.5?2','MAX_VISIBLE_SOLAR'):
        assert fragment in solar_js, fragment

    wind = load('data/onshore-wind-rivm.json')
    clusters = wind.get('clusters') or []
    turbines = wind.get('turbines') or []
    assert wind.get('source', {}).get('provider') == 'RIVM'
    assert wind.get('threshold_mw') == 25.0
    assert wind.get('turbine_count') == len(turbines)
    assert wind.get('clusters_ge_25mw') == len(clusters)
    assert len(turbines) > 1000
    assert len(clusters) > 10
    assert all(float(c.get('capacity_mw', 0)) >= 25 for c in clusters)

    storage = load('data/solar-storage.json')
    assert 'solar' not in storage
    assert storage.get('thresholds') == {'storage_mw': 25}
    assert all(float(p.get('power_mw', 0)) >= 25 for p in storage.get('storage', []))

    demand = load('data/province-demand-model.json')
    assert demand.get('schema_version') == 1
    assert demand.get('population_source', {}).get('provider') == 'CBS'
    assert demand.get('population_source', {}).get('table') == '71488NED'
    provinces = demand.get('provinces') or {}
    assert len(provinces) == 12
    pop_sum = sum(int(p.get('population', 0)) for p in provinces.values())
    assert pop_sum == int(demand.get('population_source', {}).get('population_total', 0))
    profiles = demand.get('profiles') or {}
    assert set(profiles) == {'urban', 'mixed', 'industrial'}
    for profile in profiles.values():
        assert len(profile.get('weekday') or []) == 24
        assert len(profile.get('weekend') or []) == 24
        assert all(float(x) > 0 for x in profile['weekday'] + profile['weekend'])
    assert all(p.get('profile') in profiles for p in provinces.values())
    assert len(demand.get('assumptions') or []) >= 5

    province_flow = (ROOT / 'data/province-flow.js').read_text(encoding='utf-8')
    for fragment in ('generation_by_province','wind_onshore_mw','solar_mw','province-demand-model.json','demandByProvince','load_mw','renewable balance'):
        assert fragment in province_flow, fragment
    assert 'gemeten fysieke' in province_flow.lower()
    assert 'sum' in province_flow.lower()
    assert 'avg=' not in province_flow and 'EDGES=' not in province_flow

    index = (ROOT / 'index.html').read_text(encoding='utf-8')
    assert 'Aannames provinciaal gebruik' in index
    assert 'provinciaal gebruik is een model' in index

    for path in ['data/capacity-scale.js','data/injections.js','data/solar-storage.js','data/interconnector-flags.js','data/capacity-overrides.js']:
        text = (ROOT / path).read_text(encoding='utf-8')
        assert 'capacityDiameter' in text, path

    print('repository consistency: OK')

if __name__ == '__main__':
    main()
