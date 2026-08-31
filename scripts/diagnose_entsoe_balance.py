#!/usr/bin/env python3
"""Capture the raw ENTSO-E series behind the national balance.

This is intentionally diagnostic: it does not change data/live.json. It records
all A65/A75/A11 TimeSeries metadata and the values at the newest comparable
interval so we can distinguish production, consumption, duplicates and missing
border series before changing the production collector.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://web-api.tp.entsoe.eu/api"
TOKEN = os.getenv("ENTSO_E_TOKEN", "").strip()
NL = "10YNL----------L"
BORDERS = {
    "DE": "10Y1001A1001A82H",
    "BE": "10YBE----------2",
    "GB": "10YGB-0000A-000",
    "NO2": "10YNO-2--------T",
    "DK1": "10YDK-1--------W",
}
OUT = Path("data/entsoe-diagnostics.json")


def lname(tag):
    return tag.rsplit("}", 1)[-1]


def direct_text(node, *names):
    wanted = set(names)
    for child in list(node):
        if lname(child.tag) in wanted and child.text:
            return child.text.strip()
    return None


def descendant_text(node, *names):
    wanted = set(names)
    for child in node.iter():
        if lname(child.tag) in wanted and child.text:
            return child.text.strip()
    return None


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def resolution_seconds(value):
    return {"PT15M": 900, "PT30M": 1800, "PT60M": 3600, "PT1H": 3600}.get(value, 900)


def request(params, retries=3, backoff=2.0):
    if not TOKEN:
        raise RuntimeError("ENTSO_E_TOKEN missing")
    url = API + "?" + urllib.parse.urlencode({"securityToken": TOKEN, **params})
    req = urllib.request.Request(url, headers={"User-Agent": "live-grid-nl/1.0 (+https://github.com/koenvanwijk/live-grid-nl)"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in {502, 503, 504} and attempt < retries - 1:
                time.sleep(backoff * 2 ** attempt)
                continue
            raise
        except OSError:  # URLError, TimeoutError and other socket errors
            if attempt < retries - 1:
                time.sleep(backoff * 2 ** attempt)
                continue
            raise


def point_map(series):
    result = {}
    for period in series.iter():
        if lname(period.tag) != "Period":
            continue
        start = parse_dt(descendant_text(period, "start"))
        resolution = descendant_text(period, "resolution") or "PT15M"
        if not start:
            continue
        step = resolution_seconds(resolution)
        for point in list(period):
            if lname(point.tag) != "Point":
                continue
            try:
                pos = int(descendant_text(point, "position") or "1")
                qty = float(descendant_text(point, "quantity"))
            except (TypeError, ValueError):
                continue
            ts = (start + timedelta(seconds=step * (pos - 1))).replace(microsecond=0).isoformat()
            result[ts] = qty
    return result


def domain_value(series, prefix):
    # ENTSO-E schemas use several tag spellings; retain the actual text only.
    for child in list(series):
        name = lname(child.tag)
        if name.startswith(prefix) and name.endswith("mRID") and child.text:
            return child.text.strip()
    return None


def series_metadata(series):
    return {
        "mRID": direct_text(series, "mRID"),
        "businessType": direct_text(series, "businessType"),
        "objectAggregation": direct_text(series, "objectAggregation"),
        "curveType": direct_text(series, "curveType"),
        "psrType": descendant_text(series, "psrType"),
        "in_domain": domain_value(series, "inBiddingZone_Domain") or domain_value(series, "in_Domain"),
        "out_domain": domain_value(series, "outBiddingZone_Domain") or domain_value(series, "out_Domain"),
    }


def parse_document(xml_bytes):
    root = ET.fromstring(xml_bytes)
    rows = []
    for series in root.iter():
        if lname(series.tag) != "TimeSeries":
            continue
        meta = series_metadata(series)
        meta["points"] = point_map(series)
        rows.append(meta)
    return rows


def values_at(rows, timestamp):
    out = []
    for row in rows:
        if timestamp not in row["points"]:
            continue
        item = {k: v for k, v in row.items() if k != "points"}
        item["mw"] = row["points"][timestamp]
        out.append(item)
    return out


def timestamps(rows):
    result = set()
    for row in rows:
        result.update(row["points"])
    return result


def directional_sum(rows, timestamp, receiver, sender):
    # Query itself fixes direction. Sum all returned series so diagnostics show
    # whether ENTSO-E provides multiple components for that direction.
    vals = [r["points"][timestamp] for r in rows if timestamp in r["points"]]
    return sum(vals) if vals else None


def classify_generation(row):
    inn, out = row.get("in_domain"), row.get("out_domain")
    if inn == NL and out != NL:
        return "production"
    if out == NL and inn != NL:
        return "consumption"
    if inn == NL and out == NL:
        return "both-domains"
    return "unclassified"


def main():
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(hours=8)
    end_dt = now + timedelta(hours=1)
    fmt = "%Y%m%d%H%M"
    start, end = start_dt.strftime(fmt), end_dt.strftime(fmt)

    load_rows = parse_document(request({
        "documentType": "A65", "processType": "A16",
        "outBiddingZone_Domain": NL, "periodStart": start, "periodEnd": end,
    }))
    gen_rows = parse_document(request({
        "documentType": "A75", "processType": "A16",
        "in_Domain": NL, "periodStart": start, "periodEnd": end,
    }))

    border_rows = {}
    for label, other in BORDERS.items():
        inbound = parse_document(request({
            "documentType": "A11", "in_Domain": NL, "out_Domain": other,
            "periodStart": start, "periodEnd": end,
        }))
        outbound = parse_document(request({
            "documentType": "A11", "in_Domain": other, "out_Domain": NL,
            "periodStart": start, "periodEnd": end,
        }))
        border_rows[label] = {"inbound": inbound, "outbound": outbound}

    common = timestamps(load_rows) & timestamps(gen_rows)
    # Require all five physical borders for a genuinely complete national flow sum.
    for pair in border_rows.values():
        common &= (timestamps(pair["inbound"]) | timestamps(pair["outbound"]))
    valid = [ts for ts in common if (parse_dt(ts) or now) <= now]
    target = max(valid) if valid else (max(common) if common else None)
    if not target:
        raise RuntimeError("No timestamp shared by A65, A75 and all configured borders")

    raw_gen = values_at(gen_rows, target)
    for row in raw_gen:
        row["classification"] = classify_generation(row)

    gen_by_class = {}
    gen_by_psr = {}
    for row in raw_gen:
        cls = row["classification"]
        gen_by_class[cls] = gen_by_class.get(cls, 0.0) + float(row["mw"])
        psr = row.get("psrType") or "unknown"
        # Consumption is negative in the net-generation reconciliation.
        sign = -1.0 if cls == "consumption" else 1.0
        gen_by_psr[psr] = gen_by_psr.get(psr, 0.0) + sign * float(row["mw"])

    load_values = values_at(load_rows, target)
    load_mw = sum(float(r["mw"]) for r in load_values)
    borders = {}
    for label, pair in border_rows.items():
        in_mw = directional_sum(pair["inbound"], target, NL, BORDERS[label]) or 0.0
        out_mw = directional_sum(pair["outbound"], target, BORDERS[label], NL) or 0.0
        borders[label] = {
            "import_mw": round(in_mw, 3),
            "export_mw": round(out_mw, 3),
            "net_import_mw": round(in_mw - out_mw, 3),
            "inbound_series": values_at(pair["inbound"], target),
            "outbound_series": values_at(pair["outbound"], target),
        }

    production = gen_by_class.get("production", 0.0) + gen_by_class.get("unclassified", 0.0) + gen_by_class.get("both-domains", 0.0)
    consumption = gen_by_class.get("consumption", 0.0)
    net_generation = production - consumption
    net_import = sum(v["net_import_mw"] for v in borders.values())
    residual = load_mw - net_generation - net_import

    output = {
        "generated_at": now.isoformat(),
        "target_timestamp": target,
        "query_window": {"start": start, "end": end},
        "equation": "load = net_generation + net_import + residual",
        "summary": {
            "load_mw": round(load_mw, 3),
            "production_mw": round(production, 3),
            "generation_consumption_mw": round(consumption, 3),
            "net_generation_mw": round(net_generation, 3),
            "net_import_mw": round(net_import, 3),
            "residual_mw": round(residual, 3),
        },
        "generation_by_class": {k: round(v, 3) for k, v in gen_by_class.items()},
        "generation_by_psr_net_mw": {k: round(v, 3) for k, v in sorted(gen_by_psr.items())},
        "a65_load_series_at_target": load_values,
        "a75_generation_series_at_target": raw_gen,
        "a11_borders_at_target": borders,
        "series_counts": {
            "A65": len(load_rows),
            "A75": len(gen_rows),
            **{f"A11_{label}_in": len(pair["inbound"]) for label, pair in border_rows.items()},
            **{f"A11_{label}_out": len(pair["outbound"]) for label, pair in border_rows.items()},
        },
    }
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output["summary"], indent=2))
    print("target:", target)
    print("A75 raw series:", len(raw_gen))
    for row in raw_gen:
        print("A75", row)
    for label, values in borders.items():
        print("A11", label, values["net_import_mw"], "MW net import")


def write_unavailable(reason):
    """Write a valid, empty diagnostics file so the workflow summary step and
    any consumer can still read the expected keys during a transient ENTSO-E
    outage, instead of failing the whole deploy."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_timestamp": None,
        "error": reason,
        "summary": {
            "load_mw": None,
            "production_mw": None,
            "generation_consumption_mw": None,
            "net_generation_mw": None,
            "net_import_mw": None,
            "residual_mw": None,
        },
        "a11_borders_at_target": {},
        "a75_generation_series_at_target": [],
    }
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"ENTSO-E diagnostics unavailable: {reason}")


if __name__ == "__main__":
    try:
        main()
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        write_unavailable(str(exc))
