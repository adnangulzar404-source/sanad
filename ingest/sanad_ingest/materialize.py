"""Derive all recomputable corpus data from a source-only DB. No network.

Given a DB whose `records` rows carry only source columns -- everything
`build_corpus` currently writes MINUS the norm_*/text_ar_sha256 columns, and
minus the `record_variants`/`records_fts` tables entirely -- produce a full
DB: norm_light/norm_standard/norm_aggressive, text_ar_sha256, the `full`
record variant, records_fts, and the indexes over the derived columns.

`reference_display` is NOT derived here. It depends on `HadithUnit.is_repeat`
and a build-time occurrence counter, neither of which is a stored column, so
it cannot be recomputed from a source-only DB. It stays a committed source
column (see Stage A3 ruling R-A3-3) and this module never touches it.

Reuses the exact production derivation code -- `normalize`, `db.rebuild_fts`,
`openiti.full_text_from_parts` -- so the materialised DB is identical to what
`build` used to emit inline.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3

from sanad.arabic.normalize import normalize
from sanad.corpus import db
from sanad.corpus.models import FULL_VARIANT
from sanad.corpus.schema import DERIVED_SCHEMA_SQL

from .openiti import full_text_from_parts


class MaterializeError(Exception):
    pass


def materialize(src_path: str, out_path: str) -> dict:
    """Copy `src_path` to `out_path` and derive everything in place.

    `src_path` is never opened for writing and `out_path` is a fresh copy, so
    a source-only DB committed to the repo can never be mutated by this call.
    """
    shutil.copy(src_path, out_path)
    conn = sqlite3.connect(out_path)
    try:
        conn.executescript(DERIVED_SCHEMA_SQL)
        _derive_records(conn)
        _derive_variants(conn)
        db.rebuild_fts(conn)
        _assert_complete(conn)
        conn.commit()
        return db.corpus_stats(conn)
    finally:
        conn.close()


def _derive_records(conn: sqlite3.Connection) -> None:
    for rid, text_ar in conn.execute("SELECT id, text_ar FROM records").fetchall():
        if text_ar is None:
            # A source-only DB missing its canonical text for this row is not
            # this function's call to make. Leave the norm_* columns NULL and
            # let `_assert_complete` decide whether that row was allowed to
            # skip derivation (it never is, for a scorable record).
            continue
        conn.execute(
            "UPDATE records SET norm_light=?, norm_standard=?, norm_aggressive=?, "
            "text_ar_sha256=? WHERE id=?",
            (normalize(text_ar, "light"), normalize(text_ar, "standard"),
             normalize(text_ar, "aggressive"),
             hashlib.sha256(text_ar.encode("utf-8")).hexdigest(), rid),
        )


def _derive_variants(conn: sqlite3.Connection) -> None:
    for rid, text_ar, addenda in conn.execute(
        "SELECT id, text_ar, addenda_ar FROM records"
        " WHERE addenda_ar IS NOT NULL AND text_ar IS NOT NULL"
    ).fetchall():
        full = full_text_from_parts(text_ar, addenda)
        conn.execute(
            "INSERT INTO record_variants(record_id, variant, text_ar, "
            "norm_light, norm_standard, norm_aggressive) VALUES (?,?,?,?,?,?)",
            (rid, FULL_VARIANT, full, normalize(full, "light"),
             normalize(full, "standard"), normalize(full, "aggressive")),
        )


def _assert_complete(conn: sqlite3.Connection) -> None:
    n = conn.execute(
        "SELECT COUNT(*) FROM records WHERE unscorable_reason IS NULL "
        "AND norm_standard IS NULL"
    ).fetchone()[0]
    if n:
        raise MaterializeError(f"{n} scorable records left un-derived")
