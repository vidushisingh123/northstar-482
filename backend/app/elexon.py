"""Small client for the public Elexon Insights (BMRS) stream endpoints.

Documented parameters only:
  GET /datasets/FUELHH/stream  : settlementDateFrom, settlementDateTo (yyyy-MM-dd), fuelType[]
  GET /datasets/WINDFOR/stream : publishDateTimeFrom, publishDateTimeTo
"""
import threading
import time
from datetime import date, datetime, timezone

import httpx

from . import config


class UpstreamError(Exception):
    """Elexon could not give us usable data. `status_code` is what our API should return."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class ElexonClient:
    def __init__(
        self,
        base_url: str = config.ELEXON_BASE_URL,
        timeout: float = config.ELEXON_TIMEOUT_SECONDS,
        max_retries: int = config.ELEXON_MAX_RETRIES,
        cache_ttl: int = config.CACHE_TTL_SECONDS,
        transport: httpx.BaseTransport | None = None,  # tests pass a fake transport here
        sleep=time.sleep,
    ):
        self._http = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            headers={"Accept": "application/json"},  # docs list text/plain as the default media type
            transport=transport,
        )
        self._max_retries = max_retries
        self._cache_ttl = cache_ttl
        self._sleep = sleep
        self._cache: dict[tuple, tuple[float, list[dict]]] = {}
        self._lock = threading.Lock()

    # ----- public methods -----

    def fetch_fuelhh(self, settlement_from: date, settlement_to: date) -> list[dict]:
        """Half-hourly outturn, filtered to WIND on the server (we filter again locally)."""
        return self._get_list(
            "/datasets/FUELHH/stream",
            {
                "settlementDateFrom": settlement_from.isoformat(),
                "settlementDateTo": settlement_to.isoformat(),
                "fuelType": ["WIND"],
            },
        )

    def fetch_windfor(self, publish_from: datetime, publish_to: datetime) -> list[dict]:
        return self._get_list(
            "/datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": _iso_z(publish_from),
                "publishDateTimeTo": _iso_z(publish_to),
            },
        )

    # ----- internals -----

    def _get_list(self, path: str, params: dict) -> list[dict]:
        key = (path, tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in params.items())))
        with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < self._cache_ttl:
                return cached[1]
        records = self._request(path, params)
        with self._lock:
            self._cache[key] = (time.monotonic(), records)
        return records

    def _request(self, path: str, params: dict) -> list[dict]:
        last_problem = "unknown error"
        last_status = 502
        for attempt in range(self._max_retries + 1):
            if attempt:
                self._sleep(2 ** (attempt - 1))  # 1s, 2s, ...
            try:
                response = self._http.get(path, params=params)
            except httpx.TimeoutException:
                last_problem, last_status = "Elexon API timed out", 504
                continue
            except httpx.HTTPError as error:
                last_problem, last_status = f"Could not reach the Elexon API ({type(error).__name__})", 502
                continue

            if response.status_code == 429 or response.status_code >= 500:
                last_problem = f"Elexon API returned HTTP {response.status_code}"
                last_status = 502
                continue  # temporary problem: retry
            if response.status_code >= 400:
                snippet = response.text[:200].replace("\n", " ")
                raise UpstreamError(f"Elexon API rejected the request (HTTP {response.status_code}): {snippet}")

            return self._parse(response)

        raise UpstreamError(f"{last_problem} after {self._max_retries + 1} attempts", last_status)

    @staticmethod
    def _parse(response: httpx.Response) -> list[dict]:
        try:
            payload = response.json()
        except ValueError:
            raise UpstreamError("Elexon API returned a response that is not valid JSON") from None
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if not isinstance(payload, list):
            raise UpstreamError("Elexon API returned an unexpected response shape (expected a JSON array)")
        return [item for item in payload if isinstance(item, dict)]


def _iso_z(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
