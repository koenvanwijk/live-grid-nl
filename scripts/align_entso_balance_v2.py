#!/usr/bin/env python3
"""Rebuild the national ENTSO-E balance from one complete timestamp.

This is deliberately a post-processing step over update_live.py.  It keeps the
raw collector small while making the balance rules explicit and diagnostic:
A65 load, A75 production/consumption and A11 flows for *all* NL borders must
exist at the selected timestamp.
"""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import update_live as u

OUT = Path('data/live.json')


def domain(series, prefix):
    return u.child_text(series, f'{prefix}BiddingZone_Domain.mRID', f'{prefix}_Domain.mRID')


def a75_series(start, end, direction):
    key = 'in_Domain' if direction == 'production' else 'out_Domain'
    root = ET.fromstring(u.entso_request({
        'documentType': 'A75', 'processType': 'A16', key: u.NL,
        'periodStart': start, 'periodEnd': end,
    }))
    rows = []
    values = {}
    for series in root.iter():
        if u.local_name(series.tag) != 'TimeSeries':
            continue
        psr = u.child_text(series, 'psrType')
        if not psr:
            continue
        business = u.child_text(series, 'businessType')
        in_domain = domain(series, 'in')
        out_domain = domain(series, 'out')
        points = u.series_points(series)
        rows.append({
            'direction': direction,
            'business_type': business,
            'psr_type': psr,
            'psr_name': u.PSR_NAMES.get(psr, psr),
            'in_domain': in_domain,
            'out_domain': out_domain,
            'points': points,
        })
        # A75 production is reported into the bidding zone; consumption
        # (notably pumped-storage charging) is reported out of the zone.
        sign = 1.0 if direction == 'production' else -1.0
        for ts, mw in points.items():
            bucket = values.setdefault(ts, {})
            bucket[psr] = bucket.get(psr, 0.0) + sign * mw
    return values, rows


def strict_timestamp(load, generation, borders):
    common = set(load) & set(generation)
    for label in u.BORDERS:
        series = borders.get(label) or {}
        common &= set(series)
    now = datetime.now(timezone.utc)
    valid = [ts for ts in common if (u.parse_dt(ts) or now) <= now]
    return max(valid) if valid else None


def main():
    if not u.ENTSO_TOKEN:
        print('ENTSO_E_TOKEN missing; keeping existing balance')
        return

    start, end = u.entso_window()
    load = u.entso_load_series(start, end)
    production, prod_rows = a75_series(start, end, 'production')
    consumption, cons_rows = a75_series(start, end, 'consumption')

    # Merge production and negative consumption.  Query overlap is made
    # visible in diagnostics rather than silently hidden.
    generation = {}
    for ts in set(production) | set(consumption):
        bucket = {}
        for source in (production.get(ts, {}), consumption.get(ts, {})):
            for psr, mw in source.items():
                bucket[psr] = bucket.get(psr, 0.0) + mw
        generation[ts] = bucket

    borders = {label: u.entso_border_series(domain_id, start, end)
               for label, domain_id in u.BORDERS.items()}
    ts = strict_timestamp(load, generation, borders)
    if not ts:
        raise u.ApiError('ENTSO-E v2: no timestamp shared by A65, A75 and all five NL borders')

    mix = [{'code': code, 'name': u.PSR_NAMES.get(code, code), 'mw': round(mw, 1)}
           for code, mw in generation[ts].items() if abs(mw) >= .05]
    mix.sort(key=lambda row: row['mw'], reverse=True)
    flows = {label: round(borders[label][ts], 1) for label in u.BORDERS}
    generation_mw = round(sum(row['mw'] for row in mix), 1)
    net_import_mw = round(sum(flows.values()), 1)
    residual_mw = round(load[ts] - generation_mw - net_import_mw, 1)

    def diag_row(row):
        value = row['points'].get(ts)
        if value is None:
            return None
        return {k: row[k] for k in ('direction','business_type','psr_type','psr_name','in_domain','out_domain')} | {'mw': round(value, 1)}

    diagnostics = {
        'timestamp': ts,
        'a65_load_mw': round(load[ts], 1),
        'a75_timeseries': [x for x in (diag_row(r) for r in prod_rows + cons_rows) if x],
        'a11_border_mw': flows,
        'all_borders_present': True,
        'equation': 'A65 load = A75 net generation + A11 net import + residual',
        'residual_mw': residual_mw,
    }

    data = json.loads(OUT.read_text())
    data.update({
        'load_mw': round(load[ts], 1),
        'generation_mw': generation_mw,
        'generation_mix': mix,
        'border_flows': flows,
        'net_import_mw': net_import_mw,
        'balance_residual_mw': residual_mw,
        'balance_timestamp': ts,
        'measured_at': ts,
        'national_balance_source': 'ENTSO-E aligned v2',
        'balance_equation': diagnostics['equation'],
        'entso_diagnostics': diagnostics,
    })
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
