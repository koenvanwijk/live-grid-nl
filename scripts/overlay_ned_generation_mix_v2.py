#!/usr/bin/env python3
"""Run the NED overlay with the API's required validfrom window."""
from __future__ import annotations

import importlib.util
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).with_name('overlay_ned_generation_mix.py')
SPEC = importlib.util.spec_from_file_location('ned_mix_base', SCRIPT)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def request_latest(type_id, activity=1):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).date().isoformat()
    end = (now + timedelta(days=1)).date().isoformat()
    params = {
        'point': 0,
        'type': type_id,
        'granularity': 4,
        'granularitytimezone': 1,
        'classification': 2,
        'activity': activity,
        'validfrom[after]': start,
        'validfrom[strictly_before]': end,
        'itemsPerPage': 1,
        'order[validfrom]': 'desc',
    }
    req = urllib.request.Request(
        base.NED_API + '?' + urllib.parse.urlencode(params),
        headers={
            'X-AUTH-TOKEN': base.TOKEN,
            'Accept': 'application/ld+json',
            'User-Agent': 'live-grid-nl/1.0 (+https://github.com/koenvanwijk/live-grid-nl)',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')[:500]
        raise RuntimeError(f'NED HTTP {exc.code}: {body}') from exc
    rows = data if isinstance(data, list) else data.get('hydra:member') or data.get('member') or data.get('data') or []
    return rows[0] if rows else None


base.request_latest = request_latest

if __name__ == '__main__':
    base.main()
