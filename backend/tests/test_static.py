"""Single-service deployment: the API serves the built frontend safely."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static import mount_frontend


def _app(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Rsafe</title>INDEX")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)")
    (dist / "shots").mkdir()
    (dist / "shots" / "manifest.json").write_text('{"files": []}')
    (tmp_path / "secret.txt").write_text("outside dist")
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    assert mount_frontend(app, dist)
    return TestClient(app)


def test_files_deep_links_and_api_404s(tmp_path):
    c = _app(tmp_path)
    assert c.get("/api/health").json() == {"status": "ok"}  # API routes registered first still win
    assert "INDEX" in c.get("/").text
    assert "INDEX" in c.get("/app/dashboard").text  # client-side routes get the app
    js = c.get("/assets/app-abc123.js")
    assert js.text == "console.log(1)" and "immutable" in js.headers["cache-control"]
    assert c.get("/shots/manifest.json").json() == {"files": []}
    r = c.get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_cannot_escape_the_dist_folder(tmp_path):
    c = _app(tmp_path)
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        assert "outside dist" not in c.get(path).text, path


def test_missing_dist_adds_nothing(tmp_path):
    app = FastAPI()
    assert mount_frontend(app, tmp_path / "missing") is False
    assert TestClient(app).get("/").status_code == 404
