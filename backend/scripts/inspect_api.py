"""Inspect real Elexon BMRS responses. No secrets needed.

Run from the backend/ folder:
    python scripts/inspect_api.py
    python scripts/inspect_api.py --start 2026-01-15 --end 2026-01-15 --limit 3
    python scripts/inspect_api.py --start 2026-01-15 --end 2026-01-15 --lookback-days 5

It answers, from the REAL data: is WINDFOR hourly or half-hourly, when are forecasts published,
and does the publication history support the configured day-ahead cutoff?
"""
import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import config  # noqa: E402  (cutoff settings only)

BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
TIMEOUT = httpx.Timeout(60.0)
# The docs list text/plain as the default media type, so ask for JSON explicitly.
HEADERS = {"Accept": "application/json"}
# Diagnostic only: candidate "decision times" on the day BEFORE the target day (UTC).
CUTOFF_CANDIDATES = [time(0, 0), time(6, 0), time(9, 0), time(12, 0), time(18, 0)]


def parse_ts(value):
    """'2026-01-01T00:00:00Z' -> aware datetime (Python < 3.11 can't parse a trailing 'Z')."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_midnight(day):
    return day.strftime("%Y-%m-%dT00:00:00Z")


def fetch(path, params):
    """GET a stream endpoint, print what actually happened, return the list of records."""
    response = httpx.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=TIMEOUT)
    print(f"GET {response.request.url}")
    print(f"  HTTP status: {response.status_code}, content-type: {response.headers.get('content-type')}")
    if response.status_code == 429:
        print("  Rate limited (429). Wait a minute and retry.")
    response.raise_for_status()
    payload = response.json()
    print(f"  top-level JSON type: {type(payload).__name__}")
    if isinstance(payload, dict):
        print(f"  top-level keys: {list(payload.keys())}")
        payload = payload.get("data", [])
    return payload


def count_bad_generation(records):
    return sum(1 for r in records if not isinstance(r.get("generation"), (int, float)))


def inspect_actual(start, end, limit):
    print("\n=== ACTUAL: FUELHH stream, fuelType=WIND ===")
    records = fetch(
        "/datasets/FUELHH/stream",
        {
            "settlementDateFrom": start.isoformat(),
            "settlementDateTo": end.isoformat(),
            "fuelType": ["WIND"],
        },
    )
    print(f"  records returned: {len(records)}")
    if not records:
        return
    print(f"  fields in first record: {sorted(records[0])}")
    for record in records[:limit]:
        print(f"    {record}")
    print(f"  fuelType values: {dict(Counter(r.get('fuelType') for r in records))}")
    start_times = Counter(r["startTime"] for r in records if r.get("startTime"))
    print(f"  distinct startTime values: {len(start_times)}")
    print(f"  first / last startTime: {min(start_times)} / {max(start_times)}")
    print(f"  startTime values appearing more than once: {sum(1 for c in start_times.values() if c > 1)}")
    minutes = Counter(parse_ts(t).minute for t in start_times)
    print(f"  startTime minute-of-hour distribution: {dict(sorted(minutes.items()))}  (expect 0 and 30)")
    periods = sorted({r.get("settlementPeriod") for r in records if r.get("settlementPeriod") is not None})
    print(f"  settlementPeriod range: {periods[0] if periods else None} -> {periods[-1] if periods else None}")
    print(f"  records with missing/non-numeric generation: {count_bad_generation(records)}")


def inspect_forecast(start, end, limit, lookback_days):
    print("\n=== FORECAST: WINDFOR stream ===")
    # WINDFOR filters on PUBLISH time, so start the window before the target days.
    records = fetch(
        "/datasets/WINDFOR/stream",
        {
            "publishDateTimeFrom": utc_midnight(start - timedelta(days=lookback_days)),
            "publishDateTimeTo": utc_midnight(end + timedelta(days=1)),
        },
    )
    print(f"  records returned: {len(records)}")
    if not records:
        return records
    print(f"  fields in first record: {sorted(records[0])}")
    for record in records[:limit]:
        print(f"    {record}")
    publish_times = sorted({r["publishTime"] for r in records if r.get("publishTime")})
    print(f"  distinct publishTime values: {len(publish_times)}")
    print(f"  first 10 publishTimes: {publish_times[:10]}")
    start_times = sorted({r["startTime"] for r in records if r.get("startTime")})
    print(f"  startTime range: {start_times[0]} -> {start_times[-1]}")
    keys = Counter((r.get("startTime"), r.get("publishTime")) for r in records)
    print(f"  duplicate (startTime, publishTime) pairs: {sum(1 for c in keys.values() if c > 1)}")

    minutes = Counter(parse_ts(r["startTime"]).minute for r in records if r.get("startTime"))
    print(f"  startTime minute-of-hour distribution: {dict(sorted(minutes.items()))}")
    print(
        "  => forecast resolution looks "
        + ("HOURLY (every startTime on the hour; half-hours starting at :30 get no forecast)"
           if set(minutes) == {0} else "HALF-HOURLY or mixed")
    )
    schedule = Counter(parse_ts(p).strftime("%H:%M") for p in publish_times)
    print(f"  publication times of day (UTC) and number of runs at each: {dict(sorted(schedule.items()))}")
    per_run = Counter(r["publishTime"] for r in records if r.get("publishTime"))
    if per_run:
        print(f"  records per publication: min {min(per_run.values())}, max {max(per_run.values())}")
    horizons = [
        (parse_ts(r["startTime"]) - parse_ts(r["publishTime"])).total_seconds() / 3600
        for r in records
        if r.get("startTime") and r.get("publishTime")
    ]
    if horizons:
        print(f"  horizon (startTime - publishTime), hours: min {min(horizons):.1f}, max {max(horizons):.1f}")
    print(f"  records with missing/non-numeric generation: {count_bad_generation(records)}")
    return records


def day_ahead_report(records, target_day):
    """For one target day, show which forecasts existed and how cutoffs change coverage."""
    publishes = defaultdict(list)  # startTime -> [publishTime, ...]
    for r in records:
        if not r.get("startTime") or not r.get("publishTime"):
            continue
        start = parse_ts(r["startTime"])
        if start.date() == target_day:
            publishes[start].append(parse_ts(r["publishTime"]))

    print(f"\n=== DAY-AHEAD FEASIBILITY for target day {target_day} ===")
    print("  (UTC; in January GB local time equals UTC, so no clock-change effects)")
    hourly = all(s.minute == 0 for s in publishes)
    print(f"  forecast start times with at least one forecast: {len(publishes)} "
          f"({'24 expected if hourly' if hourly else '48 expected if half-hourly'})")
    if not publishes:
        return

    all_pubs = sorted({p for pubs in publishes.values() for p in pubs})
    print(f"  distinct publishTimes covering this day ({len(all_pubs)}): {[p.strftime('%m-%d %H:%M') for p in all_pubs]}")

    for label, key in (("first", min(publishes)), ("last", max(publishes))):
        pubs = sorted(set(publishes[key]))
        print(
            f"  {label} start time {key.isoformat()}: {len(pubs)} distinct publishTimes, "
            f"earliest {pubs[0].isoformat()}, latest {pubs[-1].isoformat()}"
        )

    cutoff_now = datetime.combine(
        target_day - timedelta(days=config.CUTOFF_DAYS_BEFORE), config.CUTOFF_LOCAL_TIME, tzinfo=config.MARKET_TZ
    ).astimezone(timezone.utc)
    usable = sum(1 for pubs in publishes.values() if any(p <= cutoff_now for p in pubs))
    print(f"  CONFIGURED cutoff {cutoff_now:%Y-%m-%d %H:%M}Z: {usable}/{len(publishes)} forecast start times have an eligible forecast")

    previous_day = target_day - timedelta(days=1)
    print(f"  forecast start times with a forecast published at or before a cutoff on {previous_day}:")
    for cutoff_time in CUTOFF_CANDIDATES:
        cutoff = datetime.combine(previous_day, cutoff_time, tzinfo=timezone.utc)
        covered = sum(1 for pubs in publishes.values() if any(p <= cutoff for p in pubs))
        print(f"    cutoff {cutoff_time:%H:%M}: {covered}/{len(publishes)}")


def main():
    parser = argparse.ArgumentParser(description="Inspect Elexon FUELHH and WINDFOR samples.")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--limit", type=int, default=3, help="sample rows to print per dataset")
    parser.add_argument("--lookback-days", type=int, default=3, help="days before --start to include in the publish window")
    args = parser.parse_args()
    print(f"Base URL: {BASE_URL}")
    try:
        inspect_actual(args.start, args.end, args.limit)
        forecasts = inspect_forecast(args.start, args.end, args.limit, args.lookback_days)
        day_ahead_report(forecasts, args.start)
    except httpx.HTTPError as error:
        print(f"\nRequest failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
