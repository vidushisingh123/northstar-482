"""Endpoint tests. The Elexon client is replaced by a fake, so no network is used."""
import pytest
from fastapi.testclient import TestClient

from app.elexon import UpstreamError
from app.main import app, get_client


class FakeClient:
    def __init__(self, actual=None, forecast=None, error=None):
        self.actual, self.forecast, self.error = actual or [], forecast or [], error
        self.calls = []

    def fetch_fuelhh(self, settlement_from, settlement_to):
        self.calls.append(("fuelhh", settlement_from, settlement_to))
        if self.error:
            raise self.error
        return self.actual

    def fetch_windfor(self, publish_from, publish_to):
        self.calls.append(("windfor", publish_from, publish_to))
        if self.error:
            raise self.error
        return self.forecast


@pytest.fixture
def use_client():
    def install(fake):
        app.dependency_overrides[get_client] = lambda: fake
        return TestClient(app)

    yield install
    app.dependency_overrides.clear()


def test_response_matches_frontend_schema(use_client):
    fake = FakeClient(
        actual=[{"startTime": "2026-01-02T00:00:00Z", "publishTime": "2026-01-02T00:30:00Z", "fuelType": "WIND", "generation": 100}],
        forecast=[{"startTime": "2026-01-02T00:00:00Z", "publishTime": "2026-01-01T10:30:00Z", "generation": 120}],
    )
    response = use_client(fake).get("/api/dashboard", params={"start": "2026-01-02", "end": "2026-01-02"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"meta", "metrics", "series"}
    assert set(body["meta"]) == {"start", "end", "unit", "interval_minutes", "forecast_selection",
                                 "forecast_resolution_minutes", "intervals_total", "intervals_forecastable",
                                 "intervals_missing_forecast", "intervals_missing_actual", "duplicates_removed"}
    assert set(body["metrics"]) == {"matched_intervals", "mean_forecast_mw", "mean_actual_mw", "mae_mw", "rmse_mw", "bias_mw"}
    assert set(body["series"][0]) == {"start_time", "forecast_mw", "actual_mw", "error_mw",
                                      "forecast_publish_time", "forecast_expected"}
    assert len(body["series"]) == 48
    assert body["series"][0]["error_mw"] == 20.0
    assert body["metrics"]["mae_mw"] == 20.0 and body["metrics"]["bias_mw"] == 20.0


def test_forecast_after_cutoff_is_not_used(use_client):
    fake = FakeClient(forecast=[{"startTime": "2026-01-02T00:00:00Z", "publishTime": "2026-01-01T16:30:00Z", "generation": 120}])
    body = use_client(fake).get("/api/dashboard", params={"start": "2026-01-02", "end": "2026-01-02"}).json()
    assert body["series"][0]["forecast_mw"] is None
    # the only forecast record is on the hour, so the dataset is read as hourly: 24 forecastable intervals, all missing
    assert body["meta"]["forecast_resolution_minutes"] == 60
    assert body["meta"]["intervals_forecastable"] == 24
    assert body["meta"]["intervals_missing_forecast"] == 24


def test_no_data_is_reported_as_missing_never_invented(use_client):
    body = use_client(FakeClient()).get("/api/dashboard", params={"start": "2026-01-01", "end": "2026-01-01"}).json()
    assert body["metrics"]["matched_intervals"] == 0 and body["metrics"]["mae_mw"] is None
    assert all(p["actual_mw"] is None and p["forecast_mw"] is None for p in body["series"])


def test_fetch_windows_cover_the_request(use_client):
    fake = FakeClient()
    use_client(fake).get("/api/dashboard", params={"start": "2026-01-10", "end": "2026-01-12"})
    kinds = {call[0]: call for call in fake.calls}
    assert str(kinds["fuelhh"][1]) == "2026-01-10" and str(kinds["fuelhh"][2]) == "2026-01-13"
    # last delivery day is 12 Jan -> cutoff 12:00 on 11 Jan (+1h margin)
    assert kinds["windfor"][1].isoformat() == "2026-01-07T00:00:00+00:00"
    assert kinds["windfor"][2].isoformat() == "2026-01-11T13:00:00+00:00"


@pytest.mark.parametrize("params,text", [
    ({"start": "2026-01-10", "end": "2026-01-09"}, "start must be on or before end"),
    ({"start": "2025-12-31", "end": "2026-01-02"}, "within"),
    ({"start": "2026-01-30", "end": "2026-02-01"}, "within"),
])
def test_invalid_ranges_return_400(use_client, params, text):
    response = use_client(FakeClient()).get("/api/dashboard", params=params)
    assert response.status_code == 400 and text in response.json()["detail"]


@pytest.mark.parametrize("params", [{}, {"start": "2026-01-01"}, {"start": "nope", "end": "2026-01-02"}])
def test_missing_or_malformed_dates_return_422(use_client, params):
    assert use_client(FakeClient()).get("/api/dashboard", params=params).status_code == 422


@pytest.mark.parametrize("status", [502, 504])
def test_upstream_failures_are_reported_not_hidden(use_client, status):
    fake = FakeClient(error=UpstreamError("Elexon API timed out after 3 attempts", status))
    response = use_client(fake).get("/api/dashboard", params={"start": "2026-01-01", "end": "2026-01-01"})
    assert response.status_code == status
    assert "timed out" in response.json()["detail"]
    assert "series" not in response.json()


def test_cors_allows_vite_dev_origin_only(use_client):
    client = use_client(FakeClient())
    params = {"start": "2026-01-01", "end": "2026-01-01"}
    allowed = client.get("/api/dashboard", params=params, headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/api/dashboard", params=params, headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers
