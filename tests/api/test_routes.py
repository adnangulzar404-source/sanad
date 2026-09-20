import hashlib
import os
import pathlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from sanad.api.app import create_app

# Al-Ikhlas 1 (quran:112:1), written as explicit \\uXXXX escapes, one per
# codepoint, rather than as a literal glyph run. `text_ar` is Tanzil's
# verbatim byte sequence and is NEVER passed through NFC (the licence
# forbids changing the text; `arabic.normalize.normalize()` is applied only
# to the separate norm_* columns) -- so this constant's combining-mark order
# must match Tanzil's raw encoding exactly, including the non-canonical
# SHADDA-before-FATHA on the doubled lam of "Allah". A hand-typed literal
# glyph here is exactly the failure mode this project has hit nine times
# before: visually identical, silently wrong. This exact sequence was
# generated from -- and checked byte-for-byte equal to -- `records.text_ar`
# for quran:112:1 in the shipped corpus; see task-11-report.md.
IKHLAS_1 = "\u0642\u064f\u0644\u0652 \u0647\u064f\u0648\u064e \u0671\u0644\u0644\u0651\u064e\u0647\u064f \u0623\u064e\u062d\u064e\u062f\u064c"

# Ar-Rahman's refrain (quran:55:13 and 30 identical siblings), repeated
# verbatim 31 times -- the corpus-wide worked example for `Match.also_at`.
# Built and verified the same way as IKHLAS_1 above.
RAHMAN_REFRAIN = "\u0641\u064e\u0628\u0650\u0623\u064e\u0649\u0651\u0650 \u0621\u064e\u0627\u0644\u064e\u0627\u0653\u0621\u0650 \u0631\u064e\u0628\u0651\u0650\u0643\u064f\u0645\u064e\u0627 \u062a\u064f\u0643\u064e\u0630\u0651\u0650\u0628\u064e\u0627\u0646\u0650"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # `tmp_path_factory` is a real, built-in pytest fixture (session-scoped,
    # so it is legal for a module-scoped fixture to depend on it) -- this is
    # not the invalid `monkeypatch_module=None` parameter the brief had,
    # which pytest would try and fail to resolve as a fixture request.
    #
    # The audit log now lives in its own database (see
    # `settings.resolve_audit_db_path`), separate from the corpus, so that
    # serving requests never touches the corpus file's bytes. Point it at a
    # throwaway path for the whole module so the test suite never
    # accumulates rows in -- or has to `git checkout` -- a real file.
    audit_db = tmp_path_factory.mktemp("audit") / "sanad-audit-test.db"
    os.environ["SANAD_AUDIT_DB"] = str(audit_db)
    try:
        yield TestClient(create_app())
    finally:
        os.environ.pop("SANAD_AUDIT_DB", None)


def test_health_reports_corpus_loaded(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["records"] == 6236


def test_corpus_manifest_exposes_license_and_attribution(client):
    body = client.get("/api/corpus").json()
    src = body["sources"][0]
    assert src["license_id"] == "CC-BY-3.0"
    assert "PLEASE DO NOT REMOVE" in src["attribution"]
    assert len(body["db_sha256"]) == 64


def test_verify_exact_quote(client):
    r = client.post("/api/verify", json={"text": f"«{IKHLAS_1}»"})
    assert r.status_code == 200
    body = r.json()
    assert body["quotations"][0]["verdict"] == "EXACT"
    assert body["quotations"][0]["record"]["reference_display"] == "Al-Ikhlas 112:1"


def test_verify_wrong_reference(client):
    r = client.post("/api/verify",
                    json={"text": f"«{IKHLAS_1}» (Al-Baqarah 2:255)"})
    assert r.json()["quotations"][0]["verdict"] == "WRONG_REFERENCE"


def test_verify_reports_claims_and_risk(client):
    r = client.post("/api/verify",
                    json={"text": "All scholars agree. Can I marry my cousin?"})
    body = r.json()
    assert "unanimity" in {c["kind"] for c in body["claims"]}
    assert body["risk"] == "PERSONAL_RULING"
    assert body["requires_handoff"] is True


def test_verify_empty_text_is_rejected(client):
    assert client.post("/api/verify", json={"text": "   "}).status_code == 422


def test_verify_oversized_text_is_rejected(client):
    assert client.post("/api/verify",
                       json={"text": "x" * 60_000}).status_code == 422


def test_verify_english_only_prose_returns_empty_quotations(client):
    r = client.post("/api/verify", json={"text": "This is plain English prose."})
    assert r.status_code == 200
    assert r.json()["quotations"] == []


def test_verify_response_carries_corpus_scope_disclaimer(client):
    r = client.post("/api/verify", json={"text": "This is plain English prose."})
    scope = r.json()["corpus_scope"]
    assert "Qur'an only" in scope
    assert "does not establish" in scope


def test_get_record_returns_provenance(client):
    body = client.get("/api/records/quran:112:1").json()
    assert body["text_ar"] == IKHLAS_1
    assert len(body["text_ar_sha256"]) == 64
    assert body["source"]["license_id"] == "CC-BY-3.0"


def test_get_missing_record_404(client):
    assert client.get("/api/records/quran:999:1").status_code == 404


def test_search_finds_by_arabic_token(client):
    body = client.get("/api/search", params={"q": "الصمد"}).json()
    assert "quran:112:2" in {r["id"] for r in body["results"]}


def test_search_blank_query_is_rejected(client):
    assert client.get("/api/search", params={"q": "  "}).status_code == 422


def test_search_respects_limit(client):
    body = client.get("/api/search", params={"q": "الله", "limit": 3}).json()
    assert len(body["results"]) <= 3


def test_also_at_populated_for_duplicated_verse(client):
    # Ar-Rahman's refrain repeats verbatim 31 times; a bare, uncited quote of
    # it must not silently pin the match to one arbitrary ayah -- the other
    # 30 identical-text ids must be surfaced via `also_at`.
    r = client.post("/api/verify", json={"text": f"«{RAHMAN_REFRAIN}»"})
    body = r.json()
    q = body["quotations"][0]
    assert q["record"]["id"] == "quran:55:13"
    assert len(q["also_at"]) == 30
    assert "quran:55:16" in q["also_at"]


def test_also_at_empty_for_unique_verse(client):
    r = client.post("/api/verify", json={"text": f"«{IKHLAS_1}»"})
    body = r.json()
    assert body["quotations"][0]["also_at"] == []


def test_verify_does_not_echo_text_into_audit_log(client):
    # the spec forbids storing user text. Re-verified against the audit
    # database (a separate file from the corpus as of this task's fix for
    # the corpus-mutation defect below) -- `_conn_for_tests()` now returns
    # the audit connection specifically.
    client.post("/api/verify", json={"text": f"«{IKHLAS_1}» secret phrase"})
    from sanad.api.app import _conn_for_tests
    rows = _conn_for_tests().execute("SELECT detail_json FROM audit_log").fetchall()
    assert rows, "audit log should have at least one row after several verify calls"
    assert all("secret phrase" not in r[0] for r in rows)
    assert all(IKHLAS_1 not in r[0] for r in rows)


# --- Corpus immutability -----------------------------------------------
#
# Sanad's provenance story is "here is the corpus's SHA-256, here is the
# recipe that reproduces it, rebuild it and check." That claim is false if
# serving a request changes the file. `audit_log` used to live inside the
# same SQLite file as the corpus data; the fix is a second, separate,
# writable database for the audit log, and a corpus connection that is
# read-only at the SQLite level, not just by convention. See
# `api/sanad/api/app.py` (`_open_corpus_conn`, `_open_audit_conn`) and
# `api/sanad/corpus/schema.py` (`AUDIT_SCHEMA_SQL`).

_CORPUS_PATH = pathlib.Path("data/sanad-quran.db")


def test_serving_a_request_does_not_modify_the_corpus_file(client, tmp_path):
    before = hashlib.sha256(_CORPUS_PATH.read_bytes()).hexdigest()
    client.post("/api/verify", json={"text": f"«{IKHLAS_1}»"})
    client.post("/api/verify", json={"text": "Can I marry my cousin?"})
    after = hashlib.sha256(_CORPUS_PATH.read_bytes()).hexdigest()
    assert before == after, "serving traffic must not mutate the corpus"


def test_corpus_connection_is_read_only(client):
    conn = client.app.state.conn
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("CREATE TABLE nope (x)")


def test_reported_corpus_hash_matches_the_file_after_requests(client):
    client.post("/api/verify", json={"text": f"«{IKHLAS_1}»"})
    reported = client.get("/api/corpus").json()["db_sha256"]
    actual = hashlib.sha256(_CORPUS_PATH.read_bytes()).hexdigest()
    assert reported == actual


def test_audit_rows_are_written_to_the_audit_database(client):
    client.post("/api/verify", json={"text": f"«{IKHLAS_1}»"})
    n = client.app.state.audit_conn.execute("SELECT count(*) FROM audit_log").fetchone()[0]
    assert n > 0
