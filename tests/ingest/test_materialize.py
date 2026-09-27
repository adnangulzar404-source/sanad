"""materialize() derives everything a source-only DB is missing, no network.

`COMMITTED` is still the FULL, current corpus DB at this point in the Stage
A3 plan -- Task 4 is what will strip it down for real. These tests never
touch it: `_strip_to_source` works on a copy made in `tmp_path`.

`reference_display` is deliberately never nulled here and never asserted on
as an output of `materialize()` -- see Stage A3 ruling R-A3-3 and the
`sanad_ingest.materialize` module docstring. It depends on
`HadithUnit.is_repeat` and a build-time occurrence counter that are not
columns, so a source-only DB keeps it as a committed source column instead.
"""
import sqlite3

import pytest
from sanad.corpus import db
from sanad.corpus.schema import SOURCE_SCHEMA_SQL
from sanad_ingest.materialize import MaterializeError, materialize

COMMITTED = "data/sanad-quran.db"  # still full at this point in the plan


def _strip_to_source(full_path, src_path):
    """Copy only source columns/tables into a fresh file (simulates Task 4 output).

    `reference_display` is left populated -- it is NOT a derived column (see
    the module docstring above): a source-only DB still carries it.

    `data/sanad-quran.db`'s own `records` table still carries the OLD, pre-
    Stage-A3 `NOT NULL` constraints on the derived columns -- it is a file on
    disk, so the relaxed `SOURCE_SCHEMA_SQL` this task shipped cannot retro-
    actively loosen a table that already exists. A real Task-4 pipeline would
    build the source-only DB fresh from `SOURCE_SCHEMA_SQL`, so this helper
    rebuilds `records` under that schema before nulling the derived columns,
    rather than trying to null a column the copied file still forbids that on.
    """
    import shutil
    shutil.copy(full_path, src_path)
    conn = sqlite3.connect(src_path)
    conn.executescript("""
        DROP TABLE IF EXISTS records_fts;
        DROP TABLE IF EXISTS record_variants;
    """)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()]
    conn.execute("ALTER TABLE records RENAME TO records_old")
    conn.executescript(SOURCE_SCHEMA_SQL)  # recreates `records` with relaxed columns
    conn.execute(f"INSERT INTO records ({','.join(cols)}) "
                 f"SELECT {','.join(cols)} FROM records_old")
    conn.execute("DROP TABLE records_old")
    conn.execute("""
        UPDATE records SET norm_light=NULL, norm_standard=NULL,
                           norm_aggressive=NULL, text_ar_sha256=NULL
    """)
    conn.commit()
    conn.close()


def test_materialize_reproduces_derived_content(tmp_path):
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)
    a = sqlite3.connect(COMMITTED)
    b = sqlite3.connect(out)
    # Every scorable record's norms match the committed original, BYTE EXACT.
    rows_a = dict(a.execute("SELECT id, norm_standard FROM records").fetchall())
    rows_b = dict(b.execute("SELECT id, norm_standard FROM records").fetchall())
    assert rows_a == rows_b
    # Same check at the other two tiers -- a bug that only shows up in one
    # tier's derivation must not hide behind the other two passing.
    rows_a_light = dict(a.execute("SELECT id, norm_light FROM records").fetchall())
    rows_b_light = dict(b.execute("SELECT id, norm_light FROM records").fetchall())
    assert rows_a_light == rows_b_light
    rows_a_agg = dict(a.execute("SELECT id, norm_aggressive FROM records").fetchall())
    rows_b_agg = dict(b.execute("SELECT id, norm_aggressive FROM records").fetchall())
    assert rows_a_agg == rows_b_agg
    # And the hash column.
    rows_a_sha = dict(a.execute("SELECT id, text_ar_sha256 FROM records").fetchall())
    rows_b_sha = dict(b.execute("SELECT id, text_ar_sha256 FROM records").fetchall())
    assert rows_a_sha == rows_b_sha
    a.close()
    b.close()


def test_materialize_reproduces_record_variants(tmp_path):
    """The `full` variant rows -- and their norms -- match the committed DB."""
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)
    a = sqlite3.connect(COMMITTED)
    b = sqlite3.connect(out)
    cols = "record_id, variant, text_ar, norm_light, norm_standard, norm_aggressive"
    rows_a = sorted(a.execute(f"SELECT {cols} FROM record_variants").fetchall())
    rows_b = sorted(b.execute(f"SELECT {cols} FROM record_variants").fetchall())
    assert rows_a == rows_b
    assert len(rows_a) > 0  # the fixture must actually exercise this path
    a.close()
    b.close()


def test_materialize_reproduces_fingerprint(tmp_path):
    """The full corpus fingerprint -- covering records_fts too -- matches."""
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)
    a = sqlite3.connect(COMMITTED)
    b = sqlite3.connect(out)
    assert db.corpus_fingerprint(a) == db.corpus_fingerprint(b)
    a.close()
    b.close()


def test_materialize_is_deterministic(tmp_path):
    src = str(tmp_path / "src.db")
    _strip_to_source(COMMITTED, src)
    o1 = str(tmp_path / "o1.db")
    o2 = str(tmp_path / "o2.db")
    materialize(src, o1)
    materialize(src, o2)
    f1 = db.corpus_fingerprint(sqlite3.connect(o1))
    f2 = db.corpus_fingerprint(sqlite3.connect(o2))
    assert f1 == f2


def test_materialize_rejects_incomplete(tmp_path):
    """A genuinely un-derivable row (blank text_ar) must fail loudly.

    `text_ar` is `NOT NULL` in the schema -- it is the canonical Arabic matn,
    a source column that is never stripped -- so a NULL can never reach this
    code in the first place. An empty string is the real gap: it is legal
    under `NOT NULL`, normalises to '' (still non-NULL, so the norm_standard
    completeness check alone would not catch it), and is exactly the "live
    verification hazard" `build.py`'s own empty-scored-text guard rejects at
    build time. Forced onto one scorable row here so the test can actually
    fail if the blank-text_ar guard in `_assert_complete` is ever weakened
    or removed.
    """
    src = str(tmp_path / "src.db")
    _strip_to_source(COMMITTED, src)
    c = sqlite3.connect(src)
    (victim,) = c.execute(
        "SELECT id FROM records WHERE unscorable_reason IS NULL LIMIT 1"
    ).fetchone()
    c.execute("UPDATE records SET text_ar='' WHERE id=?", (victim,))
    c.commit()
    c.close()

    out = str(tmp_path / "out.db")
    with pytest.raises(MaterializeError):
        materialize(src, out)


def test_materialize_returns_corpus_stats(tmp_path):
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    stats = materialize(src, out)
    conn = sqlite3.connect(COMMITTED)
    expected_records = conn.execute("SELECT count(*) FROM records").fetchone()[0]
    conn.close()
    assert stats["records"] == expected_records


def test_materialize_never_mutates_source_db(tmp_path):
    """`materialize` must copy, never write through, the source file."""
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    before = sqlite3.connect(src).execute(
        "SELECT id, norm_standard FROM records ORDER BY id"
    ).fetchall()
    materialize(src, out)
    after = sqlite3.connect(src).execute(
        "SELECT id, norm_standard FROM records ORDER BY id"
    ).fetchall()
    assert before == after  # still all-NULL norms: src was never touched
