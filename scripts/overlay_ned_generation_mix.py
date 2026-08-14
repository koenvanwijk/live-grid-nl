#!/usr/bin/env python3
"""Overlay fresh NED generation data onto the live snapshot.

The detailed per-source NED queries are opportunistic. The fresh NED national
generation total is independent and remains authoritative for the headline even
when NED does not expose a compatible detailed mix for this query shape.
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


def request_latest(type_id):
    params = {
        'point': 0,
        'type': type_id,
        'granularity': 4,
        'granularitytimezone': 0,
        'classification': 2,
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
            else 'NED current/near-real-time nationale waarde; conservatief als afgeleid gemarkeerd.'
        ),
    }


def fresh_ned_total(warnings):
    try:
        row = request_latest(27)
        if row and row.get('capacity') is not None and fresh(row):
            return round(float(row['capacity']) / 1000.0, 1), row.get('validfrom')
        warnings.append('NED generation total: no fresh current value')
    except Exception as exc:
        warnings.append(f'NED generation total: {exc}')
    return None, None


def set_ned_headline(data, total, total_ts):
    if total is None:
        return
    data['generation_mw'] = total
    if total_ts:
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
            'code': 'UNSPLIT',
            'name': 'Niet uitgesplitst',
            'mw': gap,
            'source': 'NED totaal − ENTSO-E mix',
            'provenance': 'derived',
            'temporal': 'actual',
            'measured_at': data.get('measured_at'),
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
    total, total_ts = fresh_ned_total(warnings)
    set_ned_headline(data, total, total_ts)

    rows = []
    for type_id, code, name, provenance in NED_TYPES:
        try:
            row = to_mix_row(request_latest(type_id), code, name, provenance)
            if row:
                rows.append(row)
            else:
                warnings.append(f'NED generation mix {name}: no fresh current value')
        except Exception as exc:
            warnings.append(f'NED generation mix {name}: {exc}')

    if not any(r['code'] == 'B18' for r in rows):
        try:
            fallback = to_mix_row(request_latest(17), 'B18', 'Wind op zee', 'modelled')
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

    add_reconciliation_row(data, total)
    add_balance_check(data)
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print('NED generation total:', total, 'MW @', total_ts)
    print('balance residual:', data.get('balance_residual_mw'), 'MW')


if __name__ == '__main__':
    main()
