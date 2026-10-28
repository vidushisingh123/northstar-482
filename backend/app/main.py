from datetime import date
from pathlib import Path
from app.config import CORS_ORIGINS

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .elexon import ElexonClient, UpstreamError
from .schemas import DashboardResponse
from .service import get_dashboard

app = FastAPI(title="UK Wind Forecast API")

# Local development: the Vite dev server runs on a different port, so the browser needs CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_client = ElexonClient()


def get_client() -> ElexonClient:
    """FastAPI dependency; tests replace it with a fake client."""
    return _client


@app.get("/api/health")
def health():
    """Simple liveness check used by tests, Docker and the deployment platform."""
    return {"status": "ok"}


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(start: date, end: date, client: ElexonClient = Depends(get_client)):
    if start > end:
        raise HTTPException(status_code=400, detail="start must be on or before end")
    if start < config.ALLOWED_START or end > config.ALLOWED_END:
        raise HTTPException(
            status_code=400,
            detail=f"dates must be within {config.ALLOWED_START.isoformat()} and {config.ALLOWED_END.isoformat()}",
        )
    try:
        return get_dashboard(client, start, end)
    except UpstreamError as error:
        # Never fall back to made-up data: report the failure.
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


def mount_frontend(target: FastAPI, dist_dir: str) -> bool:
    """Serve the built React app from `dist_dir` (after all API routes, so /api/* still wins)."""
    path = Path(dist_dir)
    if dist_dir and (path / "index.html").is_file():
        target.mount("/", StaticFiles(directory=path, html=True), name="frontend")
        return True
    return False


mount_frontend(app, config.FRONTEND_DIST_DIR)
