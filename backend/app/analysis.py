"""Pure functions: interval alignment, day-ahead forecast selection and accuracy metrics.

No network access happens here, so everything is easy to unit test.
All timestamps are handled as timezone-aware UTC datetimes.
"""
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import config

INTERVAL = timedelta(minutes=30)
UTC = timezone.utc


# ---------- parsing helpers ----------

def parse_utc(value) -> datetime | None:
    """'2026-01-01T00:00:00Z' -> aware UTC datetime. Returns None if missing or invalid."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:  # Elexon sends 'Z'; if a value ever has no zone, assume UTC
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def clean_generation(value) -> float | None:
    """Return a finite float, or None for missing / non-numeric values. Zero is a valid value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return float(value)


def iso_z(moment: datetime | None) -> str | None:
    return None if moment is None else moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def detect_forecast_resolution(records: list[dict]) -> int:
    """Resolution of the forecast dataset in minutes, read from the data itself.

    WINDFOR is reported as hourly (every startTime on the hour), while the 30-minute
    settlement grid has two intervals per hour. If no record starts at :30 and at least one
    record exists, we treat the forecast as hourly (60). Otherwise 30.
    """
    starts = [parse_utc(r.get("startTime")) for r in records]
    starts = [s for s in starts if s is not None]
    if starts and all(s.minute % 60 == 0 for s in starts):
        return 60
    return 30


def forecast_expected_at(interval_start: datetime, resolution_minutes: int) -> bool:
    """True if the forecast dataset can have a value for an interval starting at this time."""
    return int(interval_start.timestamp() // 60) % resolution_minutes == 0


# ---------- intervals and cutoff ----------

def day_bounds_utc(start: date, end: date, tz: ZoneInfo = config.MARKET_TZ) -> tuple[datetime, datetime]:
    """UK-local midnight of `start` to UK-local midnight after `end`, as UTC (end exclusive)."""
    first = datetime.combine(start, time.min, tzinfo=tz).astimezone(UTC)
    last = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
    return first, last


def interval_grid(first: datetime, last: datetime) -> list[datetime]:
    """Every 30-minute interval start in [first, last). Stepping in UTC copes with clock changes."""
    grid, current = [], first
    while current < last:
        grid.append(current)
        current += INTERVAL
    return grid


def forecast_cutoff(
    interval_start: datetime,
    days_before: int = config.CUTOFF_DAYS_BEFORE,
    cutoff_time: time = config.CUTOFF_LOCAL_TIME,
    tz: ZoneInfo = config.MARKET_TZ,
) -> datetime:
    """Latest publishTime (UTC) a forecast may have to be usable for this interval."""
    delivery_day = interval_start.astimezone(tz).date()
    cutoff_day = delivery_day - timedelta(days=days_before)
    return datetime.combine(cutoff_day, cutoff_time, tzinfo=tz).astimezone(UTC)


def describe_selection(days_before: int, cutoff_time: time, resolution_minutes: int = 30) -> str:
    when = "the day before delivery" if days_before == 1 else f"{days_before} days before the delivery day"
    text = (
        f"For each forecast interval, the latest valid WINDFOR forecast published at or before "
        f"{cutoff_time:%H:%M} UK time on {when} (day-ahead cutoff). Forecasts published later "
        f"are excluded; intervals with no eligible forecast are counted as missing."
    )
    if resolution_minutes == 60:
        text += (
            " WINDFOR is hourly, so forecasts exist only for half-hours starting on the hour; "
            "forecast and actual are compared on those exactly matching start times only "
            "(the :30 half-hours are not compared, and no values are interpolated)."
        )
    return text


# ---------- building the two aligned datasets ----------

def build_actuals(records: list[dict], first: datetime, last: datetime) -> tuple[dict[datetime, float | None], int]:
    """FUELHH WIND records -> {interval_start: MW or None}, plus count of duplicate records dropped.

    Duplicates (same startTime) are resolved by keeping the valid value with the latest publishTime.
    """
    groups: dict[datetime, list[tuple[datetime, float | None]]] = defaultdict(list)
    for record in records:
        if record.get("fuelType") != "WIND":
            continue
        start = parse_utc(record.get("startTime"))
        if start is None or not (first <= start < last):
            continue
        published = parse_utc(record.get("publishTime")) or datetime.min.replace(tzinfo=UTC)
        groups[start].append((published, clean_generation(record.get("generation"))))

    actuals: dict[datetime, float | None] = {}
    duplicates = 0
    for start, items in groups.items():
        duplicates += len(items) - 1
        valid = [item for item in items if item[1] is not None]
        actuals[start] = max(valid, key=lambda item: item[0])[1] if valid else None
    return actuals, duplicates


def select_forecasts(
    records: list[dict],
    first: datetime,
    last: datetime,
    days_before: int = config.CUTOFF_DAYS_BEFORE,
    cutoff_time: time = config.CUTOFF_LOCAL_TIME,
) -> tuple[dict[datetime, tuple[float, datetime]], int]:
    """WINDFOR records -> {interval_start: (MW, publishTime)} using only forecasts available at the cutoff.

    Several publishTimes for one startTime are different forecast revisions, NOT duplicates.
    A duplicate is the same (startTime, publishTime) appearing more than once.
    """
    unique: dict[tuple[datetime, datetime], float | None] = {}
    duplicates = 0
    for record in records:
        start = parse_utc(record.get("startTime"))
        published = parse_utc(record.get("publishTime"))
        if start is None or published is None or not (first <= start < last):
            continue
        value = clean_generation(record.get("generation"))
        key = (start, published)
        if key in unique:
            duplicates += 1
            if unique[key] is None and value is not None:
                unique[key] = value
        else:
            unique[key] = value

    by_start: dict[datetime, list[tuple[datetime, float]]] = defaultdict(list)
    for (start, published), value in unique.items():
        if value is not None and published <= forecast_cutoff(start, days_before, cutoff_time):
            by_start[start].append((published, value))

    chosen = {}
    for start, items in by_start.items():
        published, value = max(items, key=lambda item: item[0])
        chosen[start] = (value, published)
    return chosen, duplicates


# ---------- metrics ----------

def compute_metrics(pairs: list[tuple[float, float]]) -> dict:
    """pairs = [(forecast, actual), ...] for matched intervals only. error = forecast - actual."""
    count = len(pairs)
    if count == 0:
        return {
            "matched_intervals": 0, "mean_forecast_mw": None, "mean_actual_mw": None,
            "mae_mw": None, "rmse_mw": None, "bias_mw": None,
        }
    errors = [forecast - actual for forecast, actual in pairs]
    return {
        "matched_intervals": count,
        "mean_forecast_mw": sum(f for f, _ in pairs) / count,
        "mean_actual_mw": sum(a for _, a in pairs) / count,
        "mae_mw": sum(abs(e) for e in errors) / count,
        "rmse_mw": math.sqrt(sum(e * e for e in errors) / count),
        "bias_mw": sum(errors) / count,
    }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


# ---------- the dashboard payload ----------

def build_dashboard(
    start: date,
    end: date,
    actual_records: list[dict],
    forecast_records: list[dict],
    days_before: int = config.CUTOFF_DAYS_BEFORE,
    cutoff_time: time = config.CUTOFF_LOCAL_TIME,
) -> dict:
    first, last = day_bounds_utc(start, end)
    actuals, actual_duplicates = build_actuals(actual_records, first, last)
    forecasts, forecast_duplicates = select_forecasts(forecast_records, first, last, days_before, cutoff_time)
    resolution = detect_forecast_resolution(forecast_records)

    series, pairs = [], []
    missing_forecast = missing_actual = forecastable = 0
    for interval_start in interval_grid(first, last):
        actual = actuals.get(interval_start)
        forecast, published = forecasts.get(interval_start, (None, None))
        expected = forecast_expected_at(interval_start, resolution)
        if expected:
            forecastable += 1
            if forecast is None:  # only a genuine gap: the dataset should have a value here
                missing_forecast += 1
        if actual is None:
            missing_actual += 1
        error = None
        if forecast is not None and actual is not None:
            error = forecast - actual
            pairs.append((forecast, actual))
        series.append({
            "start_time": iso_z(interval_start),
            "forecast_mw": _round(forecast),
            "actual_mw": _round(actual),
            "error_mw": _round(error),
            "forecast_publish_time": iso_z(published),
            "forecast_expected": expected,
        })

    metrics = {k: (v if k == "matched_intervals" else _round(v)) for k, v in compute_metrics(pairs).items()}
    return {
        "meta": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "unit": "MW",
            "interval_minutes": 30,
            "forecast_selection": describe_selection(days_before, cutoff_time, resolution),
            "forecast_resolution_minutes": resolution,
            "intervals_total": len(series),
            "intervals_forecastable": forecastable,
            "intervals_missing_forecast": missing_forecast,
            "intervals_missing_actual": missing_actual,
            "duplicates_removed": actual_duplicates + forecast_duplicates,
        },
        "metrics": metrics,
        "series": series,
    }
