def test_root_entrypoint_exposes_an_asgi_app():
    """Vercel's Python runtime loads a top-level `app` from app.py."""
    import app as entrypoint
    assert hasattr(entrypoint, "app")
    from fastapi import FastAPI
    assert isinstance(entrypoint.app, FastAPI)


def test_root_entrypoint_serves_health(monkeypatch, tmp_path):
    monkeypatch.setenv("SANAD_AUDIT_DB", str(tmp_path / "audit.db"))
    from fastapi.testclient import TestClient
    import importlib
    import app as entrypoint
    importlib.reload(entrypoint)
    body = TestClient(entrypoint.app).get("/api/health").json()
    assert body["records"] == 6236
