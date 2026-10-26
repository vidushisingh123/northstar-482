"""Tests for the Elexon HTTP client using a fake transport (no real network)."""
from datetime import date, datetime, timezone

import httpx
import pytest

from app.elexon import ElexonClient, UpstreamError


def make_client(handler, **kwargs):
    return ElexonClient(
        base_url="https://example.test/api", max_retries=2, cache_ttl=60,
        transport=httpx.MockTransport(handler), sleep=lambda seconds: None, **kwargs,
    )


def test_fuelhh_request_uses_documented_parameters_and_accepts_array():
    seen = {}

    def handler(request):
        seen["url"] = request.url
        seen["accept"] = request.headers["accept"]
        return httpx.Response(200, json=[{"startTime": "2026-01-01T00:00:00Z", "fuelType": "WIND", "generation": 1}])

    records = make_client(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    assert records == [{"startTime": "2026-01-01T00:00:00Z", "fuelType": "WIND", "generation": 1}]
    assert seen["url"].path == "/api/datasets/FUELHH/stream"
    assert seen["url"].params["settlementDateFrom"] == "2026-01-01"
    assert seen["url"].params["settlementDateTo"] == "2026-01-02"
    assert seen["url"].params["fuelType"] == "WIND"
    assert seen["accept"] == "application/json"


def test_windfor_request_and_data_wrapper_shape():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [{"startTime": "x"}, "not-a-dict"]})

    start = datetime(2025, 12, 29, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 13, tzinfo=timezone.utc)
    assert make_client(handler).fetch_windfor(start, end) == [{"startTime": "x"}]
    assert seen["params"] == {"publishDateTimeFrom": "2025-12-29T00:00:00Z", "publishDateTimeTo": "2026-01-01T13:00:00Z"}


def test_400_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, text="bad date")

    with pytest.raises(UpstreamError) as error:
        make_client(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    assert len(calls) == 1 and "400" in str(error.value) and error.value.status_code == 502


def test_temporary_failures_are_retried_then_succeed():
    responses = [httpx.Response(429), httpx.Response(500), httpx.Response(200, json=[])]

    def handler(request):
        return responses.pop(0)

    assert make_client(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2)) == []


def test_persistent_server_error_raises_after_retries():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(UpstreamError) as error:
        make_client(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    assert len(calls) == 3 and error.value.status_code == 502


def test_timeout_maps_to_504():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(UpstreamError) as error:
        make_client(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    assert error.value.status_code == 504 and "timed out" in str(error.value)


def test_connection_error_maps_to_502():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(UpstreamError) as error:
        make_client(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    assert error.value.status_code == 502


def test_invalid_json_and_unexpected_shape_raise():
    with pytest.raises(UpstreamError, match="not valid JSON"):
        make_client(lambda r: httpx.Response(200, text="<html>")).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    with pytest.raises(UpstreamError, match="unexpected response shape"):
        make_client(lambda r: httpx.Response(200, json={"oops": 1})).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))


def test_identical_requests_are_cached():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=[])

    client = make_client(handler)
    client.fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    client.fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 2))
    assert len(calls) == 1
