import sqlite3
from sanad.corpus.schema import AUDIT_SCHEMA_SQL, SCHEMA_SQL


def test_schema_executes_cleanly():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sources", "records", "translations", "gradings", "embeddings"} <= names


def test_corpus_schema_does_not_include_audit_log():
    # audit_log is per-request, generated state; keeping it out of the corpus
    # schema is what makes the corpus file's SHA-256 a stable, reproducible
    # fact instead of one that drifts the moment the API is used. See
    # AUDIT_SCHEMA_SQL and api/sanad/settings.resolve_audit_db_path.
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "audit_log" not in names


def test_audit_schema_executes_cleanly_and_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.executescript(AUDIT_SCHEMA_SQL)
    conn.executescript(AUDIT_SCHEMA_SQL)  # IF NOT EXISTS
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "audit_log" in names
    conn.execute(
        "INSERT INTO audit_log (ts, request_id, stage, verdict, detail_json) "
        "VALUES ('t', 'r', 's', 'v', '{}')")
    assert conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1


def test_fts_table_exists_and_is_queryable():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.execute("INSERT INTO records_fts(record_id, norm_standard, norm_aggressive, translation) "
                 "VALUES ('x', 'قل هو الله احد', 'قل هو الله احد', '')")
    rows = conn.execute(
        "SELECT record_id FROM records_fts WHERE records_fts MATCH 'الله'").fetchall()
    assert rows == [("x",)]


def test_schema_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.executescript(SCHEMA_SQL)  # IF NOT EXISTS everywhere
