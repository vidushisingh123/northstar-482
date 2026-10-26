"""Response models. These mirror the schema the React frontend was written against."""
from pydantic import BaseModel


class Meta(BaseModel):
    start: str
    end: str
    unit: str
    interval_minutes: int
    forecast_selection: str
    forecast_resolution_minutes: int
    intervals_total: int
    intervals_forecastable: int
    intervals_missing_forecast: int
    intervals_missing_actual: int
    duplicates_removed: int


class Metrics(BaseModel):
    matched_intervals: int
    mean_forecast_mw: float | None
    mean_actual_mw: float | None
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None


class SeriesPoint(BaseModel):
    start_time: str
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    forecast_publish_time: str | None
    forecast_expected: bool


class DashboardResponse(BaseModel):
    meta: Meta
    metrics: Metrics
    series: list[SeriesPoint]
