#!/usr/bin/env python3
"""Replace the national generation mix with fresh NED near-real-time values.

ENTSO-E remains the fallback in update_live.py, but when NED current data is
available this script makes it the primary source for the generation table.
Each row carries its own timestamp so stale values cannot masquerade as live.
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

# NED type -> ENTSO-E PSR-compatible code + UI label.
# Wind/solar values are explicitly model-based in NED; for the other NED
# near-real-time values we conservatively label provenance as derived rather
# than claiming a direct plant meter measurement.
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


def request_latest(type_id):
    params = {
        'point': 0,
        'type': type_id,
        'granularity': 4,
        'granularitytimezone': 0,
        'classification': 2,  # Current / near-real-time, never forecast.
        'activity': 1,
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
            else 'NED current/near-real-time nationale waarde; conservatief als afgeleid gemarkeerd, niet als directe centrale-metering.'
        ),
    }


def main():
    if not TOKEN:
        print('NED_TOKEN missing: keeping ENTSO-E generation mix fallback')
        return

    data = json.loads(PATH.read_text())
    rows = []
    warnings = data.setdefault('warnings', [])

    for type_id, code, name, provenance in NED_TYPES:
        try:
            source = request_latest(type_id)
            row = to_mix_row(source, code, name, provenance)
            if row:
                rows.append(row)
            else:
                warnings.append(f'NED generation mix {name}: no fresh current value')
        except Exception as exc:
            warnings.append(f'NED generation mix {name}: {exc}')

    # NED's preferred offshore series is type 51. Fall back to its older
    # current offshore series (17) only when type 51 is unavailable.
    if not any(r['code'] == 'B18' for r in rows):
        try:
            fallback = to_mix_row(request_latest(17), 'B18', 'Wind op zee', 'modelled')
            if fallback:
                rows.append(fallback)
        except Exception as exc:
            warnings.append(f'NED generation mix Wind op zee fallback: {exc}')

    # Do not replace a complete ENTSO-E table with a clearly broken NED pull.
    core = {'B04', 'B05', 'B14', 'B16', 'B18', 'B19'}
    if len(rows) < 6 or len(core & {r['code'] for r in rows}) < 5:
        warnings.append(f'NED generation mix incomplete ({len(rows)} fresh rows); keeping ENTSO-E fallback')
        PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        return

    rows.sort(key=lambda r: r['mw'], reverse=True)
    data['generation_mix'] = rows
    data['generation_by_type'] = {r['code']: r['mw'] for r in rows}

    # Prefer NED total generation when it is fresh; otherwise sum the fresh rows.
    total = None
    total_ts = None
    try:
        t = request_latest(27)
        if t and t.get('capacity') is not None and fresh(t):
            total = round(float(t['capacity']) / 1000.0, 1)
            total_ts = t.get('validfrom')
    except Exception as exc:
        warnings.append(f'NED generation total: {exc}')
    if total is None:
        total = round(sum(r['mw'] for r in rows), 1)
        total_ts = max((r.get('measured_at') for r in rows if r.get('measured_at')), default=data.get('measured_at'))

    data['generation_mw'] = total
    if total_ts:
        data['measured_at'] = total_ts
    if 'NED' not in data.setdefault('sources', []):
        data['sources'].append('NED')

    observations = data.setdefault('observations', {})
    observations['generation_mix'] = {
        r['code']: {
            'value': r['mw'],
            'unit': 'MW',
            'provenance': r['provenance'],
            'temporal': 'actual',
            'source': 'NED',
            'measured_at': r['measured_at'],
            'interval_start': r.get('interval_start'),
            'interval_end': r.get('interval_end'),
            'published_at': r.get('published_at'),
            'derivation': r.get('derivation'),
        }
        for r in rows
    }
    observations.setdefault('system', {})['generation'] = {
        'value': total,
        'unit': 'MW',
        'provenance': 'derived',
        'temporal': 'actual',
        'source': 'NED',
        'measured_at': total_ts,
        'interval_start': total_ts,
        'derivation': 'NED ElectricityMix current/near-real-time nationale elektriciteitsproductie.',
    }
    data.setdefault('provenance', {})['generation_mix'] = {
        'provenance': 'derived',
        'temporal': 'actual',
        'source': 'NED',
        'measured_at': total_ts,
        'note': 'Per bron kan provenance derived of modelled zijn; zie generation_mix rows / observations.',
    }
    data['provenance']['generation_mw'] = {
        'provenance': 'derived',
        'temporal': 'actual',
        'source': 'NED',
        'measured_at': total_ts,
    }

    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print('NED generation mix:', ', '.join(f"{r['name']}={r['mw']} MW" for r in rows))
    print('NED generation total:', total, 'MW @', total_ts)


if __name__ == '__main__':
    main()
