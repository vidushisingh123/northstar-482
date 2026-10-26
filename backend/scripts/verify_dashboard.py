"""Independently audit a /api/dashboard response (live URL or saved JSON file).

It re-derives everything from the returned series with separate code from the backend:
timestamps, signed error, matched pairs, MAE / RMSE / bias, missing counts, and the day-ahead cutoff.

Run from the backend/ folder (backend must be running for --url):
    python scripts/verify_dashboard.py --start 2026-01-01 --end 2026-01-07
    python scripts/verify_dashboard.py --file dash.json
Exit code 0 = every check passed, 1 = at least one check failed.
"""
import argparse
import json
import math
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402  (only for the cutoff settings, not for any logic)

LONDON = ZoneInfo("Europe/London")
failures = []


def check(ok, message):
    print(("  PASS  " if ok else "  FAIL  ") + message)
    if not ok:
        failures.append(message)


def parse(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def mean(values):
    return sum(values) / len(values) if values else None


def close(a, b, tol=0.02):
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= tol)


def audit(data):
    meta, metrics, series = data["meta"], data["metrics"], data["series"]
    print(f"\nRange {meta['start']} .. {meta['end']} (inclusive), unit {meta['unit']}, "
          f"forecast resolution {meta['forecast_resolution_minutes']} min")

    print("\nTimestamps / intervals")
    times = [parse(p["start_time"]) for p in series]
    check(times == sorted(times) and len(set(times)) == len(times), "series is sorted with no duplicate timestamps")
    check(all((b - a) == timedelta(minutes=30) for a, b in zip(times, times[1:])), "every step is exactly 30 minutes (no gaps in the grid)")
    first = datetime.combine(datetime.fromisoformat(meta["start"]).date(), time.min, tzinfo=LONDON).astimezone(timezone.utc)
    last = datetime.combine(datetime.fromisoformat(meta["end"]).date() + timedelta(days=1), time.min, tzinfo=LONDON).astimezone(timezone.utc)
    check(times[0] == first, f"first interval is UK-local midnight of the start date ({first:%Y-%m-%d %H:%M}Z)")
    check(times[-1] == last - timedelta(minutes=30), "last interval is 23:30 of the END date (end date is inclusive)")
    check(len(series) == meta["intervals_total"] == int((last - first) / timedelta(minutes=30)), f"interval count is {len(series)}")

    print("\nSigned error and matched pairs")
    pairs, bad_error = [], 0
    for p in series:
        f, a, e = p["forecast_mw"], p["actual_mw"], p["error_mw"]
        if f is not None and a is not None:
            pairs.append((f, a))
            bad_error += not close(e, f - a, 0.01)
        else:
            bad_error += e is not None
    check(bad_error == 0, "error_mw == forecast_mw - actual_mw for every matched pair, and null otherwise")
    check(len(pairs) == metrics["matched_intervals"], f"matched_intervals ({metrics['matched_intervals']}) equals pairs with both values ({len(pairs)})")

    print("\nMetrics recomputed from exactly those pairs")
    errors = [f - a for f, a in pairs]
    expected = {
        "mean_forecast_mw": mean([f for f, _ in pairs]), "mean_actual_mw": mean([a for _, a in pairs]),
        "mae_mw": mean([abs(e) for e in errors]),
        "rmse_mw": math.sqrt(mean([e * e for e in errors])) if errors else None,
        "bias_mw": mean(errors),
    }
    for key, value in expected.items():
        check(close(metrics[key], value), f"{key}: reported {metrics[key]} vs recomputed {None if value is None else round(value, 3)}")
    if errors:
        check(close(metrics["mean_forecast_mw"] - metrics["mean_actual_mw"], metrics["bias_mw"]), "mean forecast - mean actual == bias (positive = over-forecast)")
        check(metrics["mae_mw"] <= metrics["rmse_mw"] + 0.01 and abs(metrics["bias_mw"]) <= metrics["mae_mw"] + 0.01, "ordering |bias| <= MAE <= RMSE holds")

    print("\nCoverage counters")
    exp_total = sum(1 for p in series if p["forecast_expected"])
    miss_f = sum(1 for p in series if p["forecast_expected"] and p["forecast_mw"] is None)
    miss_a = sum(1 for p in series if p["actual_mw"] is None)
    check(exp_total == meta["intervals_forecastable"], f"intervals_forecastable = {exp_total}")
    check(miss_f == meta["intervals_missing_forecast"], f"intervals_missing_forecast = {miss_f} (only where a forecast can exist)")
    check(miss_a == meta["intervals_missing_actual"], f"intervals_missing_actual = {miss_a}")
    check(all(p["forecast_mw"] is None for p in series if not p["forecast_expected"]), "no forecast value is shown where the dataset has none by design")
    if meta["forecast_resolution_minutes"] == 60:
        check(all((parse(p["start_time"]).minute == 0) == p["forecast_expected"] for p in series), "hourly forecast: expected exactly on the hour")
    check(all(p["actual_mw"] is None or p["actual_mw"] >= 0 for p in series), "no negative actuals")

    print("\nDay-ahead cutoff (separate re-implementation)")
    late, not_before, horizons, publishes = 0, 0, [], set()
    for p in series:
        if p["forecast_publish_time"] is None:
            continue
        start, published = parse(p["start_time"]), parse(p["forecast_publish_time"])
        delivery_day = start.astimezone(LONDON).date()
        cutoff = datetime.combine(delivery_day - timedelta(days=config.CUTOFF_DAYS_BEFORE), config.CUTOFF_LOCAL_TIME, tzinfo=LONDON).astimezone(timezone.utc)
        late += published > cutoff
        not_before += published >= start
        horizons.append((start - published).total_seconds() / 3600)
        publishes.add(published)
    check(late == 0, f"no forecast was published after its cutoff ({config.CUTOFF_DAYS_BEFORE} day(s) before, {config.CUTOFF_LOCAL_TIME:%H:%M} UK time)")
    check(not_before == 0, "every forecast was published before the interval it predicts")
    check(all(p["forecast_publish_time"] is not None for p in series if p["forecast_mw"] is not None), "every shown forecast carries its publish time")
    if horizons:
        print(f"  INFO  forecast lead time at the cutoff: min {min(horizons):.1f} h, max {max(horizons):.1f} h; "
              f"{len(publishes)} distinct publications used")
        print(f"  INFO  publish times used (UTC): {sorted(t.strftime('%m-%d %H:%M') for t in publishes)[:12]}")
    print(f"  INFO  coverage: {metrics['matched_intervals']} compared of {meta['intervals_forecastable']} forecastable "
          f"({meta['intervals_total']} half-hours in range)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-01-07")
    parser.add_argument("--file", help="audit a saved JSON response instead of calling the API")
    args = parser.parse_args()
    if args.file:
        data = json.loads(Path(args.file).read_text())
    else:
        response = httpx.get(f"{args.url}/api/dashboard", params={"start": args.start, "end": args.end}, timeout=120)
        print(f"GET {response.request.url} -> HTTP {response.status_code}")
        if response.status_code != 200:
            print(response.text[:500])
            sys.exit(1)
        data = response.json()
    audit(data)
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
