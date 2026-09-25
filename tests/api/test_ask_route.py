"""Task 11: `POST /api/ask` — SSE route rendering records server-side.

`run_ask` (Task 10) is monkeypatched module-qualified on `sanad.api.routes`
so these tests need no network access and no real API keys. The shipped
corpus (`data/sanad-quran.db`, resolved via `SANAD_DB`'s fallback) provides
the real `quran:2:153` record so the "server renders the record" assertion
is against real data, not a fake.
"""
from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient
from sanad.agents.claude_client import ClaudeError


def _events_from(resp_text):
    return [json.loads(line[len("data: "):])
            for line in resp_text.splitlines() if line.startswith("data: ")]


def _make_client(tmp_path):
    """Fresh app per test, audit log isolated to a throwaway file -- mirrors
    the isolation `tests/api/test_routes.py`'s `client` fixture gives each
    test module, but as a plain helper since each test here needs its own
    `routes` monkeypatches applied before the app is exercised.
    """
    from sanad.api.app import create_app
    os.environ["SANAD_AUDIT_DB"] = str(tmp_path / "sanad-audit-test.db")
    return TestClient(create_app())


def test_ask_streams_events_and_renders_records(monkeypatch, tmp_path):
    from sanad.api import routes
    from sanad.pipeline.types import StageEvent

    def fake_run(cc, vc, q, *, anthropic_key, voyage_key, deps=None):
        yield StageEvent("router", {"risk": "GENERAL", "requires_handoff": False})
        yield StageEvent("final", {
            "status": "published", "question_language": "en",
            "summary": "Sources on patience.",
            "items": [{"record_id": "quran:2:153", "framing": "Seek help in patience."}],
            "reached": {"quran": True, "hadith": False}, "unreached_reason": None,
            "risk": "GENERAL", "requires_handoff": False, "abstain_reason": None})

    monkeypatch.setattr(routes, "run_ask", fake_run)
    monkeypatch.setattr(routes, "resolve_anthropic_key", lambda: "a")
    client = _make_client(tmp_path)
    r = client.post("/api/ask", json={"question": "patience?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _events_from(r.text)
    assert events[0]["stage"] == "router"
    final = events[-1]["payload"]
    assert final["items"][0]["record"]["id"] == "quran:2:153"   # server-rendered
    assert "text_ar" in final["items"][0]["record"]
    # exactly one terminal `final` event
    assert sum(1 for e in events if e["stage"] == "final") == 1

    # Audit row written; question text and search terms never in detail_json.
    from sanad.api.app import _conn_for_tests
    row = _conn_for_tests().execute(
        "SELECT stage, verdict, detail_json FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["stage"] == "ask"
    assert row["verdict"] == "published"
    detail = json.loads(row["detail_json"])
    assert detail["record_ids"] == ["quran:2:153"]
    assert "patience" not in json.dumps(detail)


def test_ask_without_key_abstains(monkeypatch, tmp_path):
    from sanad.api import routes
    monkeypatch.setattr(routes, "resolve_anthropic_key", lambda: None)
    client = _make_client(tmp_path)
    r = client.post("/api/ask", json={"question": "x"})
    assert r.status_code == 200
    events = _events_from(r.text)
    assert events[-1]["payload"]["status"] == "abstained"
    assert events[-1]["payload"]["reached"] == {"quran": False, "hadith": False}
    assert "key" in events[-1]["payload"]["abstain_reason"].lower()


def test_ask_rejects_blank_question(tmp_path):
    client = _make_client(tmp_path)
    assert client.post("/api/ask", json={"question": "  "}).status_code == 422


def test_ask_rejects_missing_question(tmp_path):
    client = _make_client(tmp_path)
    assert client.post("/api/ask", json={}).status_code == 422


def test_ask_route_is_mounted(tmp_path):
    # Any non-404 (422 here, for the empty body) proves the route exists.
    client = _make_client(tmp_path)
    r = client.post("/api/ask", json={})
    assert r.status_code != 404


def test_ask_midstream_claude_error_becomes_error_event(monkeypatch, tmp_path):
    from sanad.api import routes

    def fake_run(cc, vc, q, *, anthropic_key, voyage_key, deps=None):
        from sanad.pipeline.types import StageEvent
        yield StageEvent("router", {"risk": "GENERAL", "requires_handoff": False})
        raise ClaudeError("boom: transport failed")
        yield  # pragma: no cover -- unreachable, makes this a generator

    monkeypatch.setattr(routes, "run_ask", fake_run)
    monkeypatch.setattr(routes, "resolve_anthropic_key", lambda: "a")
    client = _make_client(tmp_path)
    r = client.post("/api/ask", json={"question": "patience?"})
    assert r.status_code == 200
    events = _events_from(r.text)
    assert events[0]["stage"] == "router"
    assert events[1]["stage"] == "error"
    final = events[-1]["payload"]
    assert final["status"] == "abstained"
    assert sum(1 for e in events if e["stage"] == "final") == 1

    from sanad.api.app import _conn_for_tests
    row = _conn_for_tests().execute(
        "SELECT stage, verdict FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["stage"] == "ask"
    assert row["verdict"] == "abstained"
