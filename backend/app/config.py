"""Central configuration. Everything can be overridden with environment variables.

There are no secrets: the Elexon Insights API is public and needs no key.
"""
import os
from datetime import date, time
from zoneinfo import ZoneInfo  # needs the `tzdata` package on Windows (see requirements.txt)

ELEXON_BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1").rstrip("/")
ELEXON_TIMEOUT_SECONDS = float(os.getenv("ELEXON_TIMEOUT_SECONDS", "60"))
ELEXON_MAX_RETRIES = int(os.getenv("ELEXON_MAX_RETRIES", "2"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# The assignment covers January 2026 only.
ALLOWED_START = date(2026, 1, 1)
ALLOWED_END = date(2026, 1, 31)

# --- Day-ahead purchasing cutoff (ASSUMPTION - confirm against the assignment text) ---
# For delivery day D, only forecasts published at or before CUTOFF_LOCAL_TIME (UK local
# time) on day D - CUTOFF_DAYS_BEFORE are used. Later publications are excluded.
MARKET_TZ = ZoneInfo("Europe/London")
CUTOFF_DAYS_BEFORE = int(os.getenv("FORECAST_CUTOFF_DAYS_BEFORE", "1"))
CUTOFF_LOCAL_TIME = time.fromisoformat(os.getenv("FORECAST_CUTOFF_LOCAL_TIME", "12:00"))

# How many days before the first delivery day we ask WINDFOR for publications.
FORECAST_LOOKBACK_DAYS = int(os.getenv("FORECAST_LOOKBACK_DAYS", "3"))

# Optional: folder with the built React app (frontend/dist). When set, the API also serves the page,
# so one container can be deployed on its own. Leave unset for local development (Vite serves the page).
FRONTEND_DIST_DIR = os.getenv("FRONTEND_DIST_DIR", "")

# Browser origins allowed to call this API (the Vite dev server).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
