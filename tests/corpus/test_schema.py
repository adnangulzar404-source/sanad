import sqlite3
from sanad.corpus.schema import SCHEMA_SQL


def test_schema_executes_cleanly():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sources", "records", "translations", "gradings",
            "embeddings", "audit_log"} <= names


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
