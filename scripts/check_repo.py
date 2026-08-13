#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    solar = load('data/solar-parks.json')
    parks = solar.get('parks') or []
    assert solar.get('schema_version') == 2
    assert solar.get('threshold_mwp') == 25.0
    assert len(parks) == solar.get('stats', {}).get('published_ge25mwp')
    assert len(parks) >= 20
    assert all(p.get('status') == 'operationeel' for p in parks)
    assert all(float(p.get('capacity_mwp', 0)) >= 25 for p in parks)
    assert all(p.get('source') == 'ROM3D Zon op Kaart' for p in parks)

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

    for path in ['data/capacity-scale.js','data/injections.js','data/solar-storage.js','data/interconnector-flags.js','data/capacity-overrides.js']:
        text = (ROOT / path).read_text(encoding='utf-8')
        assert 'capacityDiameter' in text, path

    print('repository consistency: OK')


if __name__ == '__main__':
    main()
