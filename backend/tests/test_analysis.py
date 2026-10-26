"""Unit tests for alignment, cutoff selection and metrics. All data here is synthetic test data."""
import math
from datetime import date, datetime, time, timezone

import pytest

from app.analysis import (
    build_actuals, build_dashboard, clean_generation, compute_metrics, day_bounds_utc,
    detect_forecast_resolution, forecast_cutoff, forecast_expected_at, interval_grid, select_forecasts,
)

UTC = timezone.utc
NOON = time(12, 0)


def dt(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def actual(start, value, publish=None, fuel="WIND"):
    return {"startTime": start, "publishTime": publish or start, "fuelType": fuel, "generation": value}


def forecast(start, publish, value):
    return {"startTime": start, "publishTime": publish, "generation": value}


# ---- helpers ----

@pytest.mark.parametrize("value,expected", [(0, 0.0), (12.5, 12.5), (None, None), ("5", None), (True, None),
                                            (float("nan"), None), (float("inf"), None)])
def test_clean_generation(value, expected):
    assert clean_generation(value) == expected


def test_cutoff_is_noon_previous_day_in_january():
    assert forecast_cutoff(dt("2026-01-02T00:00:00Z"), 1, NOON) == dt("2026-01-01T12:00:00Z")
    assert forecast_cutoff(dt("2026-01-02T23:30:00Z"), 1, NOON) == dt("2026-01-01T12:00:00Z")


def test_cutoff_respects_uk_summer_time():
    # 2026-07-02 00:00Z is 01:00 BST, delivery day 2 July; cutoff 12:00 BST on 1 July = 11:00Z
    assert forecast_cutoff(dt("2026-07-02T00:00:00Z"), 1, NOON) == dt("2026-07-01T11:00:00Z")


def test_grid_has_48_intervals_per_january_day():
    first, last = day_bounds_utc(date(2026, 1, 1), date(2026, 1, 2))
    grid = interval_grid(first, last)
    assert len(grid) == 96
    assert grid[0] == dt("2026-01-01T00:00:00Z") and grid[-1] == dt("2026-01-02T23:30:00Z")


def test_grid_handles_clock_change_days():
    first, last = day_bounds_utc(date(2026, 3, 29), date(2026, 3, 29))  # clocks go forward
    assert len(interval_grid(first, last)) == 46


# ---- actuals ----

def test_actuals_keep_only_wind_in_range_and_count_duplicates():
    first, last = day_bounds_utc(date(2026, 1, 1), date(2026, 1, 1))
    records = [
        actual("2026-01-01T00:00:00Z", 100, publish="2026-01-01T00:30:00Z"),
        actual("2026-01-01T00:00:00Z", 110, publish="2026-01-01T01:00:00Z"),   # duplicate, later publish wins
        actual("2026-01-01T00:30:00Z", 200, fuel="NUCLEAR"),                    # ignored fuel
        actual("2026-01-02T00:00:00Z", 300),                                    # outside range
        actual("2026-01-01T01:00:00Z", None),                                   # missing value
    ]
    actuals, duplicates = build_actuals(records, first, last)
    assert actuals == {dt("2026-01-01T00:00:00Z"): 110.0, dt("2026-01-01T01:00:00Z"): None}
    assert duplicates == 1


def test_actual_zero_is_kept_not_treated_as_missing():
    first, last = day_bounds_utc(date(2026, 1, 1), date(2026, 1, 1))
    actuals, _ = build_actuals([actual("2026-01-01T00:00:00Z", 0)], first, last)
    assert actuals[dt("2026-01-01T00:00:00Z")] == 0.0


# ---- forecast cutoff ----

TARGET = "2026-01-02T10:00:00Z"
RANGE = day_bounds_utc(date(2026, 1, 2), date(2026, 1, 2))


def test_latest_forecast_before_cutoff_is_used_and_later_ones_excluded():
    records = [
        forecast(TARGET, "2026-01-01T05:30:00Z", 100),
        forecast(TARGET, "2026-01-01T10:30:00Z", 150),   # latest allowed
        forecast(TARGET, "2026-01-01T12:00:00Z", 160),   # exactly at cutoff: allowed
        forecast(TARGET, "2026-01-01T12:30:00Z", 999),   # after cutoff: excluded
        forecast(TARGET, "2026-01-02T03:30:00Z", 888),   # same-day forecast: excluded
    ]
    chosen, duplicates = select_forecasts(records, *RANGE, 1, NOON)
    assert chosen == {dt(TARGET): (160.0, dt("2026-01-01T12:00:00Z"))}
    assert duplicates == 0


def test_only_late_forecasts_means_missing():
    records = [forecast(TARGET, "2026-01-01T16:30:00Z", 500), forecast(TARGET, "2026-01-02T03:30:00Z", 600)]
    chosen, _ = select_forecasts(records, *RANGE, 1, NOON)
    assert chosen == {}


def test_falls_back_to_earlier_valid_forecast_when_latest_is_null():
    records = [forecast(TARGET, "2026-01-01T08:30:00Z", 120), forecast(TARGET, "2026-01-01T10:30:00Z", None)]
    chosen, _ = select_forecasts(records, *RANGE, 1, NOON)
    assert chosen[dt(TARGET)] == (120.0, dt("2026-01-01T08:30:00Z"))


def test_duplicate_forecast_records_are_counted_and_revisions_are_not():
    records = [
        forecast(TARGET, "2026-01-01T08:30:00Z", 120),
        forecast(TARGET, "2026-01-01T08:30:00Z", 120),   # true duplicate
        forecast(TARGET, "2026-01-01T10:30:00Z", 130),   # a revision, not a duplicate
    ]
    chosen, duplicates = select_forecasts(records, *RANGE, 1, NOON)
    assert duplicates == 1
    assert chosen[dt(TARGET)][0] == 130.0


def test_different_cutoff_changes_selection():
    records = [forecast(TARGET, "2026-01-01T08:30:00Z", 120), forecast(TARGET, "2026-01-01T10:30:00Z", 130)]
    chosen, _ = select_forecasts(records, *RANGE, 1, time(9, 0))
    assert chosen[dt(TARGET)][0] == 120.0


# ---- metrics ----

def test_metrics_known_values():
    metrics = compute_metrics([(110.0, 100.0), (96.0, 100.0)])   # errors +10, -4
    assert metrics["matched_intervals"] == 2
    assert metrics["mae_mw"] == pytest.approx(7.0)
    assert metrics["rmse_mw"] == pytest.approx(math.sqrt((100 + 16) / 2))
    assert metrics["bias_mw"] == pytest.approx(3.0)
    assert metrics["mean_forecast_mw"] == pytest.approx(103.0)
    assert metrics["mean_actual_mw"] == pytest.approx(100.0)


def test_metrics_with_no_matches_are_null_not_zero():
    metrics = compute_metrics([])
    assert metrics["matched_intervals"] == 0
    assert all(metrics[k] is None for k in ("mae_mw", "rmse_mw", "bias_mw", "mean_forecast_mw", "mean_actual_mw"))


# ---- whole payload ----

def test_dashboard_aligns_intervals_and_uses_only_matched_pairs_for_metrics():
    day = date(2026, 1, 2)
    actual_records = [
        actual("2026-01-02T00:00:00Z", 100),
        actual("2026-01-02T00:30:00Z", 200),
        actual("2026-01-02T01:00:00Z", None),         # actual missing
    ]
    forecast_records = [
        forecast("2026-01-02T00:00:00Z", "2026-01-01T10:30:00Z", 110),
        forecast("2026-01-02T00:30:00Z", "2026-01-01T13:00:00Z", 999),  # published after cutoff
        forecast("2026-01-02T01:00:00Z", "2026-01-01T10:30:00Z", 50),
    ]
    result = build_dashboard(day, day, actual_records, forecast_records, 1, NOON)
    series = result["series"]
    assert len(series) == 48
    assert series[0] == {"start_time": "2026-01-02T00:00:00Z", "forecast_mw": 110.0, "actual_mw": 100.0,
                         "error_mw": 10.0, "forecast_publish_time": "2026-01-01T10:30:00Z",
                         "forecast_expected": True}
    assert series[1]["forecast_mw"] is None and series[1]["error_mw"] is None   # excluded by cutoff
    assert series[2]["actual_mw"] is None and series[2]["error_mw"] is None
    assert result["metrics"]["matched_intervals"] == 1
    assert result["metrics"]["mae_mw"] == 10.0 and result["metrics"]["bias_mw"] == 10.0
    assert result["meta"]["intervals_total"] == 48
    assert result["meta"]["intervals_missing_forecast"] == 46
    assert result["meta"]["intervals_missing_actual"] == 46
    assert "12:00" in result["meta"]["forecast_selection"]


def test_dashboard_with_no_data_reports_everything_missing():
    result = build_dashboard(date(2026, 1, 1), date(2026, 1, 1), [], [], 1, NOON)
    assert result["meta"]["intervals_missing_actual"] == 48
    assert result["meta"]["intervals_missing_forecast"] == 48
    assert result["metrics"]["matched_intervals"] == 0 and result["metrics"]["mae_mw"] is None


# ---- hourly forecast (WINDFOR) against half-hourly actuals (FUELHH) ----

def _hourly_week():
    """Synthetic: half-hourly actuals for 1-7 Jan, hourly forecasts published 10:30 on the previous day."""
    from datetime import timedelta
    z = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    actuals = [actual(z(t0 + timedelta(minutes=30 * i)), 1000 + i) for i in range(336)]
    forecasts = []
    for day in range(7):
        published = z(t0 + timedelta(days=day - 1, hours=10, minutes=30))
        for hour in range(24):
            forecasts.append(forecast(z(t0 + timedelta(days=day, hours=hour)), published, 1100 + hour))
    return actuals, forecasts


def test_detect_forecast_resolution():
    assert detect_forecast_resolution([forecast("2026-01-02T01:00:00Z", "2026-01-01T10:30:00Z", 1)]) == 60
    mixed = [forecast("2026-01-02T01:00:00Z", "2026-01-01T10:30:00Z", 1), forecast("2026-01-02T01:30:00Z", "2026-01-01T10:30:00Z", 1)]
    assert detect_forecast_resolution(mixed) == 30
    assert detect_forecast_resolution([]) == 30


def test_forecast_expected_at():
    assert forecast_expected_at(dt("2026-01-02T01:00:00Z"), 60) is True
    assert forecast_expected_at(dt("2026-01-02T01:30:00Z"), 60) is False
    assert forecast_expected_at(dt("2026-01-02T01:30:00Z"), 30) is True


def test_hourly_forecast_week_reproduces_336_168_and_reports_no_false_gaps():
    actuals, forecasts = _hourly_week()
    result = build_dashboard(date(2026, 1, 1), date(2026, 1, 7), actuals, forecasts, 1, NOON)
    meta, metrics = result["meta"], result["metrics"]
    assert meta["intervals_total"] == 336
    assert meta["forecast_resolution_minutes"] == 60
    assert meta["intervals_forecastable"] == 168
    assert meta["intervals_missing_forecast"] == 0          # the :30 half-hours are NOT "missing forecasts"
    assert meta["intervals_missing_actual"] == 0
    assert metrics["matched_intervals"] == 168
    assert "hourly" in meta["forecast_selection"]
    half_hours = [p for p in result["series"] if p["start_time"][14:16] == "30"]
    assert len(half_hours) == 168
    assert all(p["forecast_expected"] is False and p["forecast_mw"] is None and p["error_mw"] is None for p in half_hours)


def test_hourly_forecast_real_gap_is_still_counted_as_missing():
    actuals, forecasts = _hourly_week()
    forecasts = [f for f in forecasts if f["startTime"] != "2026-01-03T05:00:00Z"]   # remove one real hour
    result = build_dashboard(date(2026, 1, 1), date(2026, 1, 7), actuals, forecasts, 1, NOON)
    assert result["meta"]["intervals_missing_forecast"] == 1
    assert result["metrics"]["matched_intervals"] == 167
    gap = next(p for p in result["series"] if p["start_time"] == "2026-01-03T05:00:00Z")
    assert gap["forecast_expected"] is True and gap["forecast_mw"] is None


def test_hourly_metrics_use_exactly_the_matched_pairs_and_signed_error():
    actuals, forecasts = _hourly_week()
    result = build_dashboard(date(2026, 1, 1), date(2026, 1, 7), actuals, forecasts, 1, NOON)
    pairs = [(p["forecast_mw"], p["actual_mw"]) for p in result["series"] if p["error_mw"] is not None]
    assert len(pairs) == result["metrics"]["matched_intervals"] == 168
    errors = [f - a for f, a in pairs]
    assert all(p["error_mw"] == p["forecast_mw"] - p["actual_mw"] for p in result["series"] if p["error_mw"] is not None)
    assert result["metrics"]["bias_mw"] == pytest.approx(sum(errors) / 168, abs=1e-2)
    assert result["metrics"]["mae_mw"] == pytest.approx(sum(abs(e) for e in errors) / 168, abs=1e-2)
    assert result["metrics"]["rmse_mw"] == pytest.approx(math.sqrt(sum(e * e for e in errors) / 168), abs=1e-2)
    assert result["metrics"]["mean_forecast_mw"] - result["metrics"]["mean_actual_mw"] == pytest.approx(result["metrics"]["bias_mw"], abs=1e-2)
    assert max(p["forecast_publish_time"] for p in result["series"] if p["forecast_publish_time"]) <= "2026-01-06T12:00:00Z"
