#!/usr/bin/env python3
"""Overlay fresh NED generation and load data onto the live snapshot.

NED is used for the headline national generation and demand because those series
share the same near-real-time cadence. TenneT metered injections are preserved
as a separate transmission-grid metric and must not silently override a fresher
national demand value.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

NED_API = 'https://api.ned.nl/v1/utilizations'
PATH = Path('data/live.json')
TOKEN = os.getenv('NED_TOKEN', '').strip()
MAX_AGE_MINUTES = 90

NED_TYPES = [
    (19, 'B05', 'Steenkool', 'derived'),
    (18, 'B04', 'Gas', 'derived'),
    (20, 'B14', 'Kernenergie', 'derived'),
    (2, 'B16', 'Zon', 'modelled'),
    (51, 'B18', 'Wind op zee', 'modelled'),
    (21, 'B17', 'Afval', 'derived'),
    (25, 'B01', 'Biomassa', 'derived'),
    (26, 'B20', 'Overig', 'derived'),
    (1, 'B19', 'Wind op land', 'modelled'),
]


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        return None


def age_minutes(value, now=None):
    ts = parse_time(value)
    if ts is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 60.0)


def fresh(row, now=None):
    age = age_minutes(row.get('validfrom'), now)
    return age is not None and age <= MAX_AGE_MINUTES


def request_latest(type_id, activity=1):
    params = {
        'point': 0,
        'type': type_id,
        'granularity': 4,
        'granularitytimezone': 0,
        'classification': 2,
        'activity': activity,
        'itemsPerPage': 1,
        'order[validfrom]': 'desc',
    }
    req = urllib.request.Request(
        NED_API + '?' + urllib.parse.urlencode(params),
        headers={
            'X-AUTH-TOKEN': TOKEN,
            'Accept': 'application/ld+json',
            'User-Agent': 'live-grid-nl/1.0 (+https://github.com/koenvanwijk/live-grid-nl)',
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    rows = data if isinstance(data, list) else data.get('hydra:member') or data.get('member') or data.get('data') or []
    return rows[0] if rows else None


def to_mix_row(ned_row, code, name, provenance):
    if not ned_row or ned_row.get('capacity') is None or not fresh(ned_row):
        return None
    try:
        mw = float(ned_row['capacity']) / 1000.0
    except (TypeError, ValueError):
        return None
    if mw < 0:
        return None
    ts = ned_row.get('validfrom')
    return {
        'code': code,
        'name': name,
        'mw': round(mw, 1),
        'source': 'NED',
        'provenance': provenance,
        'temporal': 'actual',
        'measured_at': ts,
        'interval_start': ts,
        'interval_end': ned_row.get('validto'),
        'published_at': ned_row.get('lastupdate'),
        'derivation': (
            'NED current/near-real-time model value; geen directe lokale meterwaarde.'
            if provenance == 'modelled'
            else 'NED current/near-real-time nationale waarde; conservatief als afgeleid gemarkeerd.'
        ),
    }


def fresh_ned_value(type_id, activity, label, warnings):
    try:
        row = request_latest(type_id, activity)
        if row and row.get('capacity') is not None and fresh(row):
            return round(float(row['capacity']) / 1000.0, 1), row.get('validfrom'), row.get('validto'), row.get('lastupdate')
        warnings.append(f'NED {label}: no fresh current value')
    except Exception as exc:
        warnings.append(f'NED {label}: {exc}')
    return None, None, None, None


def preserve_tennet_transmission_load(data):
    metered = data.get('tennet', {}).get('metered_injections') or {}
    if not metered or metered.get('mw') is None:
        return
    data['tennet_transmission_load_mw'] = round(float(metered['mw']), 1)
    data['tennet_transmission_load_measured_at'] = metered.get('measured_at')
    data.setdefault('observations', {}).setdefault('system', {})['tennet_transmission_load'] = {
        'value': data['tennet_transmission_load_mw'], 'unit': 'MW', 'provenance': 'measured',
        'temporal': 'actual', 'source': 'TenneT', 'measured_at': metered.get('measured_at'),
        'interval_start': metered.get('measured_at'), 'interval_end': metered.get('interval_end'),
        'derivation': 'TenneT metered injections; apart gehouden van de nationale NED-vraag.',
    }


def set_ned_load_headline(data, load, ts, interval_end=None, published_at=None):
    if load is None:
        return
    data['ned_load_mw'] = load
    data['load_mw'] = load
    data['load_mw_measured_at'] = ts
    data.setdefault('provenance', {})['load_mw'] = {
        'provenance': 'measured', 'temporal': 'actual', 'source': 'NED', 'measured_at': ts,
    }
    data.setdefault('observations', {}).setdefault('system', {})['load'] = {
        'value': load, 'unit': 'MW', 'provenance': 'measured', 'temporal': 'actual',
        'source': 'NED', 'measured_at': ts, 'interval_start': ts, 'interval_end': interval_end,
        'published_at': published_at,
        'derivation': 'NED actuele landelijke elektriciteitsvraag (type 59, activity 2).',
    }


def set_ned_headline(data, total, total_ts):
    if total is None:
        return
    data['generation_mw'] = total
    data['generation_mw_measured_at'] = total_ts
    if total_ts:
        current = parse_time(data.get('measured_at'))
        incoming = parse_time(total_ts)
        if incoming and (current is None or incoming > current):
            data['measured_at'] = total_ts
    if 'NED' not in data.setdefault('sources', []):
        data['sources'].append('NED')
    data.setdefault('provenance', {})['generation_mw'] = {
        'provenance': 'derived', 'temporal': 'actual', 'source': 'NED', 'measured_at': total_ts,
    }
    data.setdefault('observations', {}).setdefault('system', {})['generation'] = {
        'value': total, 'unit': 'MW', 'provenance': 'derived', 'temporal': 'actual',
        'source': 'NED', 'measured_at': total_ts, 'interval_start': total_ts,
        'derivation': 'NED current/near-real-time nationale elektriciteitsproductie.',
    }


def add_reconciliation_row(data, total):
    if total is None:
        return
    mix = [r for r in (data.get('generation_mix') or []) if r.get('code') != 'UNSPLIT']
    known = sum(float(r.get('mw') or 0) for r in mix)
    gap = round(total - known, 1)
    data['generation_mix_accounted_mw'] = round(known, 1)
    data['generation_mix_gap_mw'] = gap
    if gap > 50:
        mix.append({
            'code': 'UNSPLIT', 'name': 'Niet uitgesplitst', 'mw': gap,
            'source': 'NED totaal − ENTSO-E mix', 'provenance': 'derived', 'temporal': 'actual',
            'measured_at': data.get('generation_mw_measured_at') or data.get('measured_at'),
            'derivation': 'Verschil tussen het actuele NED-productietotaal en de beschikbare ENTSO-E bronuitsplitsing.',
        })
        mix.sort(key=lambda r: float(r.get('mw') or 0), reverse=True)
        data['generation_mix'] = mix


def add_balance_check(data):
    load = data.get('load_mw'); generation = data.get('generation_mw'); net = data.get('net_import_mw')
    if all(v is not None for v in (load, generation, net)):
        residual = round(float(load) - float(generation) - float(net), 1)
        data['balance_residual_mw'] = residual
        data['balance_equation'] = 'vraag = opwek + netto import + restverschil'


def main():
    if not TOKEN:
        print('NED_TOKEN missing: keeping ENTSO-E fallback')
        return

    data = json.loads(PATH.read_text())
    warnings = data.setdefault('warnings', [])
    preserve_tennet_transmission_load(data)

    load, load_ts, load_end, load_published = fresh_ned_value(59, 2, 'load', warnings)
    set_ned_load_headline(data, load, load_ts, load_end, load_published)

    total, total_ts, _total_end, _total_published = fresh_ned_value(27, 1, 'generation total', warnings)
    set_ned_headline(data, total, total_ts)

    rows = []
    for type_id, code, name, provenance in NED_TYPES:
        try:
            row = to_mix_row(request_latest(type_id, 1), code, name, provenance)
            if row:
                rows.append(row)
            else:
                warnings.append(f'NED generation mix {name}: no fresh current value')
        except Exception as exc:
            warnings.append(f'NED generation mix {name}: {exc}')

    if not any(r['code'] == 'B18' for r in rows):
        try:
            fallback = to_mix_row(request_latest(17, 1), 'B18', 'Wind op zee', 'modelled')
            if fallback:
                rows.append(fallback)
        except Exception as exc:
            warnings.append(f'NED generation mix Wind op zee fallback: {exc}')

    core = {'B04', 'B05', 'B14', 'B16', 'B18', 'B19'}
    complete = len(rows) >= 6 and len(core & {r['code'] for r in rows}) >= 5
    if complete:
        rows.sort(key=lambda r: r['mw'], reverse=True)
        data['generation_mix'] = rows
        data['generation_by_type'] = {r['code']: r['mw'] for r in rows}
        data.setdefault('provenance', {})['generation_mix'] = {
            'provenance': 'derived', 'temporal': 'actual', 'source': 'NED', 'measured_at': total_ts,
            'note': 'Per bron kan provenance derived of modelled zijn.',
        }
    else:
        warnings.append(f'NED generation mix incomplete ({len(rows)} fresh rows); keeping ENTSO-E detail, NED total remains headline')

    system_obs = data.setdefault('observations', {}).setdefault('system', {})
    if data.get('net_import_mw') is not None:
        net_obs = system_obs.get('net_import') or {}
        data['net_import_mw_measured_at'] = net_obs.get('measured_at') or data.get('measured_at')

    add_reconciliation_row(data, total)
    add_balance_check(data)
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print('NED load:', load, 'MW @', load_ts)
    print('NED generation total:', total, 'MW @', total_ts)
    print('TenneT transmission load:', data.get('tennet_transmission_load_mw'), 'MW @', data.get('tennet_transmission_load_measured_at'))
    print('balance residual:', data.get('balance_residual_mw'), 'MW')


if __name__ == '__main__':
    main()
