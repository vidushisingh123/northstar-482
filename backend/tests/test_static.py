from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_frontend


def make_app(dist_dir):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app, mount_frontend(app, str(dist_dir))


def test_serves_built_frontend_without_shadowing_api(tmp_path):
    (tmp_path / "index.html").write_text("<html>dashboard</html>")
    app, mounted = make_app(tmp_path)
    client = TestClient(app)
    assert mounted
    assert "dashboard" in client.get("/").text
    assert client.get("/api/health").json() == {"status": "ok"}


def test_does_not_mount_when_folder_is_missing_or_unset(tmp_path):
    assert make_app(tmp_path / "nope")[1] is False
    assert make_app("")[1] is False
