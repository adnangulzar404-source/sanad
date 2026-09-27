"""materialize() derives everything a source-only DB is missing, no network.

As of Stage A3 Task 4 the committed `COMMITTED` DB IS source-only: no norms,
no `text_ar_sha256`, no `record_variants`, no `records_fts`. So these tests no
longer compare materialize's output against a "golden" full committed DB (there
is none); they verify the derivation is CORRECT against the normalizer, and
that it is deterministic. `_strip_to_source` still runs (idempotently) so the
tests are robust whether the committed file is source-only or, historically,
full. Every DB touched is a copy made in `tmp_path`.

`reference_display` is deliberately never nulled here and never asserted on
as an output of `materialize()` -- see Stage A3 ruling R-A3-6 and the
`sanad_ingest.materialize` module docstring. It depends on
`HadithUnit.is_repeat` and a build-time occurrence counter that are not
columns, so a source-only DB keeps it as a committed source column instead.
"""
import hashlib
import sqlite3

import pytest
from sanad.arabic.normalize import normalize
from sanad.corpus import db
from sanad.corpus.schema import SOURCE_SCHEMA_SQL
from sanad_ingest.materialize import (
    MaterializeError,
    _reject_wholly_quranic_representations,
    materialize,
)

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


def test_materialize_derives_correct_norms(tmp_path):
    """Every derived norm equals normalize(text_ar) at its tier, and the sha256
    is of the canonical text.

    The committed DB is source-only, so the reference is the normalizer itself
    -- computed here from the source column -- not a golden full DB. A bug in
    one tier's derivation cannot hide behind the other two, because all three
    are checked per record.
    """
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)
    b = sqlite3.connect(out)
    rows = b.execute(
        "SELECT id, text_ar, norm_light, norm_standard, norm_aggressive,"
        " text_ar_sha256 FROM records").fetchall()
    assert len(rows) > 0
    for rid, text_ar, nl, ns, na, sha in rows:
        assert nl == normalize(text_ar, "light"), rid
        assert ns == normalize(text_ar, "standard"), rid
        assert na == normalize(text_ar, "aggressive"), rid
        assert sha == hashlib.sha256(text_ar.encode("utf-8")).hexdigest(), rid
    b.close()


def test_materialize_derives_record_variants(tmp_path):
    """One `full` variant per record with an addendum: its text is the primary
    plus the addendum rejoined, and its norms derive from that exact string."""
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)
    b = sqlite3.connect(out)
    rows = b.execute(
        "SELECT v.record_id, v.variant, v.text_ar, v.norm_light, v.norm_standard,"
        "       v.norm_aggressive, r.text_ar, r.addenda_ar"
        " FROM record_variants v JOIN records r ON r.id = v.record_id").fetchall()
    assert len(rows) > 0  # the fixture must actually exercise this path
    for (rid, variant, vtext, vnl, vns, vna, rtext, addenda) in rows:
        assert variant == "full", rid
        assert vtext == rtext + " " + addenda, rid
        assert vnl == normalize(vtext, "light"), rid
        assert vns == normalize(vtext, "standard"), rid
        assert vna == normalize(vtext, "aggressive"), rid
    b.close()


def test_materialize_fingerprint_is_stable_and_source_preserving(tmp_path):
    """The full corpus fingerprint (covering records_fts and record_variants) is
    reproducible across two materialisations of the same source, and the SOURCE
    fingerprint of the materialised DB is unchanged from the committed source DB
    -- materialize adds derived data, it never alters source data."""
    src = str(tmp_path / "src.db")
    _strip_to_source(COMMITTED, src)
    o1 = str(tmp_path / "o1.db")
    o2 = str(tmp_path / "o2.db")
    materialize(src, o1)
    materialize(src, o2)
    a = sqlite3.connect(o1)
    b = sqlite3.connect(o2)
    assert db.corpus_fingerprint(a) == db.corpus_fingerprint(b)
    s = sqlite3.connect(src)
    assert db.corpus_source_fingerprint(s) == db.corpus_source_fingerprint(a)
    a.close()
    b.close()
    s.close()


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


# --- C1: a hadith representation may not be wholly Qur'anic -----------------
#
# The guard moved out of `build` into `materialize` in Stage A3 Task 4: it now
# reads norm_standard from the DB (records + record_variants), not from
# in-memory Record/RecordVariant lists, and raises MaterializeError.
#
# These unit tests use Latin placeholder "verses" on purpose. What is being
# tested is the containment rule -- token boundaries, one surah at a time,
# primaries and variants alike -- and that rule is script-agnostic, while an
# Arabic literal typed into a test file is the single most reliable source of
# defects on this project. The Arabic half is tested over every scorable
# representation of the shipped corpus, in tests/ingest/test_real_corpus.py.


def _guard_db(tmp_path, ayat, hadith=(), variants=(), name="g.db"):
    """A DB with the given ayat/hadith/variants, norms derived, ready for the guard.

    `ayat`:     (surah, ayah, text)
    `hadith`:   (record_id, text, unscorable_reason)
    `variants`: (record_id, text)   -- a `full` variant
    """
    from sanad.corpus.models import FULL_VARIANT, Record, RecordVariant
    conn = db.connect(tmp_path / name, read_only=False)  # full schema: needs variants
    db.insert_records(conn, [
        Record(id=f"quran:{s}:{a}", source_id="s", kind="ayah", surah=s, ayah=a,
               text_ar=t, text_ar_sha256="0" * 64,
               norm_light=normalize(t, "light"),
               norm_standard=normalize(t, "standard"),
               norm_aggressive=normalize(t, "aggressive"),
               reference_display=f"S {s}:{a}")
        for s, a, t in ayat])
    db.insert_records(conn, [
        Record(id=rid, source_id="s", kind="hadith", collection="bukhari",
               hadith_no="1", numbering_scheme="bugha-1987", text_ar=t,
               unscorable_reason=reason, text_ar_sha256="0" * 64,
               norm_light=normalize(t, "light"),
               norm_standard=normalize(t, "standard"),
               norm_aggressive=normalize(t, "aggressive"),
               reference_display=f"Sahih al-Bukhari {rid}")
        for rid, t, reason in hadith])
    db.insert_record_variants(conn, [
        RecordVariant(record_id=rid, variant=FULL_VARIANT, text_ar=t,
                      norm_light=normalize(t, "light"),
                      norm_standard=normalize(t, "standard"),
                      norm_aggressive=normalize(t, "aggressive"))
        for rid, t in variants])
    return conn


def test_a_wholly_quranic_primary_aborts_materialize(tmp_path):
    conn = _guard_db(tmp_path,
                     [(53, 9, "alpha beta gamma"), (53, 10, "delta epsilon")],
                     hadith=[("hadith:bukhari:1", "beta gamma delta", None)])
    with pytest.raises(MaterializeError, match="wholly a quotation of the Qur'an"):
        _reject_wholly_quranic_representations(conn)


def test_a_wholly_quranic_full_text_aborts_too(tmp_path):
    """The variant is checked, not just the primary.

    4575 was caught on its primary, but a cut can leave scripture on either
    side of itself, and a check that read only `records` would ship the other
    half.
    """
    conn = _guard_db(tmp_path, [(53, 9, "alpha beta gamma")],
                     hadith=[("hadith:bukhari:1", "a narration", None)],
                     variants=[("hadith:bukhari:1", "alpha beta")])
    with pytest.raises(MaterializeError, match=r"\(full\)"):
        _reject_wholly_quranic_representations(conn)


def test_a_hadith_that_merely_contains_an_ayah_is_not_rejected(tmp_path):
    """The invariant is WHOLLY, and it has to be: hundreds of narrations quote
    scripture. The defect is a matn that is nothing BUT an ayah."""
    conn = _guard_db(tmp_path, [(2, 201, "alpha beta gamma")],
                     hadith=[("hadith:bukhari:1",
                              "he said alpha beta gamma and departed", None)])
    _reject_wholly_quranic_representations(conn)  # must not raise


def test_the_containment_check_falls_on_token_boundaries(tmp_path):
    """"eta" inside "beta" is not a quotation of anything."""
    conn = _guard_db(tmp_path, [(1, 1, "alpha beta gamma")],
                     hadith=[("hadith:bukhari:1", "eta gamm", None)])
    _reject_wholly_quranic_representations(conn)  # must not raise


def test_text_spanning_two_surahs_is_not_a_quranic_quotation(tmp_path):
    """A string that only appears by reading the end of one surah into the start
    of the next is not a quotation the reader could have made."""
    within = _guard_db(tmp_path, [(1, 1, "alpha beta"), (2, 1, "gamma delta")],
                       hadith=[("hadith:bukhari:1", "alpha beta", None)],
                       name="within.db")
    with pytest.raises(MaterializeError, match="wholly a quotation"):
        _reject_wholly_quranic_representations(within)
    across = _guard_db(tmp_path, [(1, 1, "alpha beta"), (2, 1, "gamma delta")],
                       hadith=[("hadith:bukhari:1", "beta gamma", None)],
                       name="across.db")
    _reject_wholly_quranic_representations(across)  # must not raise


def test_an_unscorable_primary_is_not_subject_to_the_invariant(tmp_path):
    """A record that cannot be matched cannot make a false claim. The check
    follows scorability, so an unscorable primary is out of its scope."""
    conn = _guard_db(tmp_path, [(1, 1, "alpha beta")],
                     hadith=[("hadith:bukhari:1", "alpha beta", "editorial pointer")])
    _reject_wholly_quranic_representations(conn)  # must not raise


def test_the_invariant_refuses_to_pass_vacuously(tmp_path):
    """With no Qur'an in the DB there is nothing to compare against, and a silent
    pass would be a check that never ran."""
    conn = _guard_db(tmp_path, [], hadith=[("hadith:bukhari:1", "alpha beta", None)])
    with pytest.raises(MaterializeError, match="pass vacuously"):
        _reject_wholly_quranic_representations(conn)


# --- corpus_source_fingerprint: the committed source artifact's content hash --


def test_source_fingerprint_is_invariant_under_materialize(tmp_path):
    """materialize() only ADDS derived data, so the source fingerprint of a
    source-only DB equals that of its materialisation. If the source
    fingerprint accidentally covered record_variants or the norm columns (both
    populated by materialize), this would fail."""
    src = str(tmp_path / "src.db")
    out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)
    a = sqlite3.connect(src)
    b = sqlite3.connect(out)
    assert db.corpus_source_fingerprint(a) == db.corpus_source_fingerprint(b)
    a.close()
    b.close()


def test_source_fingerprint_ignores_derived_columns_but_full_does_not(tmp_path):
    """Writing a norm value must NOT move the source fingerprint -- it is a
    derived column -- while it MUST move the full fingerprint."""
    out = str(tmp_path / "out.db")
    src = str(tmp_path / "src.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)  # a full DB, so corpus_fingerprint is defined
    conn = sqlite3.connect(out)
    src_before = db.corpus_source_fingerprint(conn)
    full_before = db.corpus_fingerprint(conn)
    conn.execute("UPDATE records SET norm_standard='X' WHERE id='quran:112:1'")
    conn.commit()
    assert db.corpus_source_fingerprint(conn) == src_before
    assert db.corpus_fingerprint(conn) != full_before
    conn.close()


def test_source_fingerprint_changes_when_a_source_column_changes(tmp_path):
    """A change to a SOURCE column -- the canonical text -- must move the hash.
    reference_display is a source column too, so it is covered by the same
    guarantee."""
    src = str(tmp_path / "src.db")
    _strip_to_source(COMMITTED, src)
    conn = sqlite3.connect(src)
    before = db.corpus_source_fingerprint(conn)
    conn.execute("UPDATE records SET text_ar = text_ar || 'x' WHERE id='quran:112:1'")
    conn.commit()
    assert db.corpus_source_fingerprint(conn) != before
    ref_before = db.corpus_source_fingerprint(conn)
    conn.execute("UPDATE records SET reference_display = reference_display || 'y'"
                 " WHERE id='quran:112:1'")
    conn.commit()
    assert db.corpus_source_fingerprint(conn) != ref_before
    conn.close()
