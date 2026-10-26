"""Orchestration: decide what to fetch from Elexon, then hand it to the pure analysis code."""
from datetime import date, time, timedelta

from . import config
from .analysis import INTERVAL, build_dashboard, day_bounds_utc, forecast_cutoff
from .elexon import ElexonClient


def get_dashboard(
    client: ElexonClient,
    start: date,
    end: date,
    days_before: int = config.CUTOFF_DAYS_BEFORE,
    cutoff_time: time = config.CUTOFF_LOCAL_TIME,
    lookback_days: int = config.FORECAST_LOOKBACK_DAYS,
) -> dict:
    first, last = day_bounds_utc(start, end)

    # Actuals: ask one day past `end` so the result is right whether or not
    # settlementDateTo is inclusive; build_actuals() trims to the requested range.
    actual_records = client.fetch_fuelhh(start, end + timedelta(days=1))

    # Forecasts: WINDFOR filters on PUBLISH time. We only need publications up to the
    # latest cutoff in the range (plus an hour of margin; the exact cutoff is re-applied locally).
    latest_cutoff = forecast_cutoff(last - INTERVAL, days_before, cutoff_time)
    forecast_records = client.fetch_windfor(
        first - timedelta(days=lookback_days), latest_cutoff + timedelta(hours=1)
    )
    return build_dashboard(start, end, actual_records, forecast_records, days_before, cutoff_time)
