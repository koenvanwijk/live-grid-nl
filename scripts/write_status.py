#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

LIVE = Path('data/live.json')
STATUS = Path('data/status.json')


def age_minutes(value):
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0, round((datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 60, 1))
    except (TypeError, ValueError):
        return None


def source_status(data, source):
    warnings = [str(w) for w in data.get('warnings', [])]
    source_warnings = [w for w in warnings if w.lower().startswith(source.lower())]
    present = source in data.get('sources', [])

    if source == 'NED':
        observations = {
            'national_generation': data.get('generation_mw') is not None,
            'national_load_fallback': data.get('ned_load_mw') is not None,
            'provinces': len(data.get('generation_by_province') or {}),
            'offshore_parks': len(data.get('offshore_wind_mw') or {}),
        }
        useful = observations['national_generation'] or observations['national_load_fallback'] or observations['provinces'] > 0 or observations['offshore_parks'] > 0
    elif source == 'TenneT':
        tennet = data.get('tennet') or {}
        observations = {
            'metered_injections': 'metered_injections' in tennet,
            'balance_delta': 'balance_delta' in tennet,
        }
        useful = any(observations.values())
    else:
        observations = {
            'border_flows': len(data.get('border_flows') or {}),
            'generation_mix': len(data.get('generation_mix') or []),
        }
        useful = observations['border_flows'] > 0 or observations['generation_mix'] > 0

    return {
        'configured_or_reported': present,
        'ok': bool(useful),
        'observations': observations,
        'warnings': source_warnings,
    }


def main():
    data = json.loads(LIVE.read_text())
    measured = data.get('measured_at')
    status = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'snapshot_status': data.get('status'),
        'snapshot_generated_at': data.get('generated_at'),
        'measured_at': measured,
        'age_minutes': age_minutes(measured),
        'schema_version': data.get('schema_version'),
        'sources': {
            'NED': source_status(data, 'NED'),
            'TenneT': source_status(data, 'TenneT'),
            'ENTSO-E': source_status(data, 'ENTSO-E'),
        },
        'counts': {
            'provinces': len(data.get('generation_by_province') or {}),
            'offshore_parks': len(data.get('offshore_wind_mw') or {}),
            'border_flows': len(data.get('border_flows') or {}),
            'generation_types': len(data.get('generation_by_type') or data.get('generation_mix') or []),
            'observations': len(data.get('observations') or []),
        },
        'warnings': data.get('warnings', []),
    }
    STATUS.write_text(json.dumps(status, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
