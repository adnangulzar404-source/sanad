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
        # Halting integrity gate: no scorable hadith representation may be, in
        # its entirety, a Qur'anic quotation. Runs AFTER the norms and variants
        # it reads have been derived, alongside the completeness assertion.
        _reject_wholly_quranic_representations(conn)
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


# The whole of the invariant: nothing scorable as a hadith may be nothing but
# the Qur'an. The separator is a newline, which `normalize` never produces, so
# the surahs cannot be read across -- a string matches only if it sits inside
# ONE surah, which is what "is a Qur'anic quotation" means. Both sides are
# padded with spaces so a match has to fall on token boundaries rather than
# mid-word.
_SURAH_JOIN = "\n"


def _quran_blob(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT surah, norm_standard FROM records WHERE kind = 'ayah'"
        " ORDER BY surah, ayah").fetchall()
    by_surah: dict[int, list[str]] = {}
    for surah, norm_standard in rows:
        by_surah.setdefault(surah, []).append(norm_standard or "")
    return _SURAH_JOIN.join(f" {' '.join(v)} " for v in by_surah.values())


def _reject_wholly_quranic_representations(conn: sqlite3.Connection) -> None:
    """A hadith representation may not be, in its entirety, Qur'anic text.

    Record 4575's cut left a primary matn that was verbatim Qur'an 53:9-10, so
    quoting those two verses returned EXACT / Sahih al-Bukhari 4575, and
    quoting them with the correct "(53:9)" returned WRONG_REFERENCE. Both
    directions at once: scripture attributed to a hadith collection, and a
    reader told their correct citation was a misattribution.

    This is an assertion about the corpus, not a heuristic with a knob. The
    containment scan over all 7,504 scorable representations finds exactly one
    hit, and it is the record the audit now leaves uncut, so the check is
    expected to pass silently forever. If it ever fires, a cut has produced
    another one and materialisation stops rather than ship it -- which is the
    point: `_NEVER_CUT` fixes the record it names, and only this closes the
    class for the editions still to come, where tafsir-shaped units are far
    more common.

    It moved here from `build` with the derivation it depends on: it reads the
    `norm_standard` of every scorable hadith primary and every record_variant
    straight from the DB, so it must run after `_derive_records`,
    `_derive_variants` and `rebuild_fts`. Comparison is at the STANDARD tier,
    not `light`: that is the coarser of the two tiers that can return a verified
    verdict, so a match here is exactly the set of texts that could be answered
    EXACT or EXACT_ORTHOGRAPHY. Nothing is normalized in transit -- the stored
    norms are compared as they were derived.
    """
    blob = _quran_blob(conn)
    if not blob.strip():
        raise MaterializeError(
            "no Qur'anic records are in the corpus, so the wholly-Qur'anic "
            "check would pass vacuously. The Qur'an must be present before "
            "this gate can mean anything.")
    scorable = conn.execute(
        "SELECT id, 'primary', norm_standard FROM records"
        " WHERE kind = 'hadith' AND unscorable_reason IS NULL"
        " UNION ALL "
        "SELECT record_id, variant, norm_standard FROM record_variants"
    ).fetchall()
    offenders = [(rid, variant) for rid, variant, norm in scorable
                 if norm and norm.strip() and f" {norm} " in blob]
    if offenders:
        raise MaterializeError(
            f"{', '.join(f'{r} ({v})' for r, v in offenders)} "
            "is scorable as a hadith and is wholly a quotation of the Qur'an. "
            "Sanad would answer a reader who quotes those verses with a "
            "Bukhari citation, and would tell a reader who cites them "
            "correctly that their reference is wrong. The remedy is a "
            "judgement about the record -- almost always that the cut is in "
            "the wrong place and the unit should be left uncut, as "
            "openiti._NEVER_CUT does for 4575 -- read in the source, not a "
            "filter applied here.")


def _assert_complete(conn: sqlite3.Connection) -> None:
    # Mirrors build.py:112's BuildError: an empty (or all-whitespace) scored
    # text is a live verification hazard on its own, independent of whether
    # normalization later produced a value for it. `text_ar` is `NOT NULL` in
    # the schema, so this cannot fire on a NULL -- only on a blank string,
    # which the constraint permits and this check exists to catch.
    blank = conn.execute(
        "SELECT COUNT(*) FROM records WHERE unscorable_reason IS NULL "
        "AND TRIM(text_ar) = ''"
    ).fetchone()[0]
    if blank:
        raise MaterializeError(
            f"{blank} scorable record(s) have an empty or blank text_ar; "
            "an empty scored text is a live verification hazard")

    n = conn.execute(
        "SELECT COUNT(*) FROM records WHERE unscorable_reason IS NULL "
        "AND norm_standard IS NULL"
    ).fetchone()[0]
    if n:
        raise MaterializeError(f"{n} scorable records left un-derived")
