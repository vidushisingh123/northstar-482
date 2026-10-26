# UK Wind Power Forecast Dashboard

A web dashboard for a UK electricity utility team that buys power in the day-ahead market. It compares
**national wind-generation forecasts** (Elexon BMRS `WINDFOR`) with **actual wind generation** (Elexon BMRS
`FUELHH`, wind only) for **January 2026**, and reports forecast accuracy (MAE, RMSE, bias).

- Live demo: **[TODO: public URL]**
- Demo video (unlisted, ≤ 10 min): **[TODO: YouTube URL]**

## Architecture

```
React (Vite) ──► FastAPI (Python) ──► Elexon BMRS API (FUELHH, WINDFOR)
```

- `backend/app/elexon.py` – HTTP client (documented parameters only, timeouts, retries on 429/5xx, 1-hour cache).
- `backend/app/analysis.py` – pure functions: interval alignment, day-ahead forecast selection, metrics. No network.
- `backend/app/service.py` – decides what to fetch, calls the analysis code.
- `backend/app/main.py` – `GET /api/health`, `GET /api/dashboard?start=YYYY-MM-DD&end=YYYY-MM-DD` (both inclusive).
- `frontend/` – React dashboard (Recharts). No database, authentication or ML.

## Data sources (Elexon BMRS only; no API key needed)

| Purpose | Endpoint | Parameters used |
|---|---|---|
| Actual | `GET /datasets/FUELHH/stream` | `settlementDateFrom/To`, `fuelType=WIND` (also re-filtered locally) |
| Forecast | `GET /datasets/WINDFOR/stream` | `publishDateTimeFrom/To` |

Fields used: `startTime`, `publishTime`, `generation` (MW).

## Methodology

1. **Intervals.** The grid is every 30-minute settlement interval from UK-local midnight of the start date to
   UK-local midnight after the end date (end date inclusive). Everything is matched on exact `startTime` in UTC.
2. **Day-ahead cutoff (an assumption – see Limitations).** For delivery day *D*, only forecasts with
   `publishTime` at or before **12:00 UK time on day *D−1*** are eligible. For each interval the latest eligible
   forecast is used. Forecasts published later are excluded; actual generation is never used to choose a forecast.
   Configurable with `FORECAST_CUTOFF_DAYS_BEFORE` and `FORECAST_CUTOFF_LOCAL_TIME`.
3. **Resolution.** `FUELHH` is half-hourly. `WINDFOR` appears to be **hourly** (start times on the hour), detected
   from the data. Forecast and actual are compared only where start times match exactly, so the half-hours starting
   at :30 are **not compared** and nothing is interpolated. These intervals are reported as "no forecast by design",
   not as missing data.
4. **Errors and metrics.** `error = forecast − actual` (positive = over-forecast). MAE, RMSE and mean error (bias)
   are computed only from intervals that have both values. With no matched intervals they are `null`, not 0.
5. **Duplicates and missing values.** Repeated actuals for one `startTime` keep the latest valid value. Repeated
   forecast rows (same `startTime` and `publishTime`) are counted once. Different `publishTime`s for one `startTime`
   are forecast revisions, not duplicates. Missing values stay missing and appear as gaps.
6. **Failures.** If Elexon cannot be reached the API returns HTTP 502/504 with a message and the page shows it.
   There is no fallback to sample data (sample data exists only behind `VITE_USE_MOCK=true`, with a visible banner).

## Findings and data validity

**[TODO – fill in after running `python scripts/verify_dashboard.py` and `python scripts/inspect_api.py` on the real data:
the forecast resolution seen, the publication times of day, lead time at the cutoff, how many January intervals
had an eligible forecast, and the headline MAE / RMSE / bias.]**

## Limitations

- The **12:00 D−1 cutoff is my assumption**, not a figure taken from Elexon. Change it if the brief says otherwise.
- Only publications that still exist in the API can be replayed; this is a reconstruction of what was published, not a record of what a desk saw.
- Hourly forecast vs half-hourly actual: only half-hours starting on the hour are compared. Whether an hourly WINDFOR
  value should instead be compared with the average of both half-hours is not specified in the documentation I reviewed.
- `WINDFOR` covers wind farms visible to the ESO with operational metering; `FUELHH` is a broader GB outturn.
  A persistent bias may partly reflect that definition gap, curtailment, or true forecast error – this tool cannot separate them.
- One winter month only; results may not generalise to other seasons.

## Run locally (Git Bash on Windows)

```bash
# backend
cd backend
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements-dev.txt
python -m pytest
uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
cp .env.example .env.local        # VITE_API_BASE_URL=http://127.0.0.1:8000
npm test
npm run dev                       # http://localhost:5173
```

Audit the real data path (backend running):

```bash
cd backend
python scripts/inspect_api.py --start 2026-01-15 --end 2026-01-15
python scripts/verify_dashboard.py --start 2026-01-01 --end 2026-01-07
```

## Docker

```bash
docker build -t wind-dashboard .
docker run --rm -p 8000:8000 wind-dashboard      # open http://localhost:8000
```

One image builds the React app and serves it together with the API on one origin.

## Deployment

**[TODO: platform (Vercel or Heroku as specified by the assignment), steps used, and the public URL.]**
Heroku container deploy uses the included `heroku.yml`.

## Testing

Backend (`pytest`): cutoff selection, hourly/half-hourly alignment, metrics, duplicates, date validation, API failures,
CORS, Elexon client retries/timeouts. Frontend (`vitest`): chart rendering, date presets, KPI updates, error/empty/gap states.

## AI use disclosure

**[TODO – edit so it is accurate for what YOU did.]** Draft: *This project was built with substantial assistance from
Claude (Anthropic) through the Claude web app: it proposed the architecture and generated most of the initial code,
tests and documentation. I ran, tested and reviewed the code locally, checked the Elexon documentation, and I am
responsible for the submission. Time spent: [N] hours.*
