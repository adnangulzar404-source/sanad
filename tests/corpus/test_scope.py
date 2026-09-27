"""Tests for `corpus.scope.corpus_scope` -- the corpus-scope caveat, DERIVED
from what the database actually contains rather than a hardcoded literal.

Stage A3 ingests five more hadith collections (Task 10 brief). The OLD
`CORPUS_SCOPE` constant said "It does not contain Sahih Muslim, the four
Sunan, or any other collection" -- wording that becomes FALSE the moment any
of those five lands, inside the ANTI-FABRICATION caveat, which is the worst
place for a false statement in this project. `corpus_scope(conn)` replaces
the constant so the caveat can never say something the database contradicts.

Each test here builds a real, throwaway SQLite DB from the schema, inserts
synthetic rows via the same `db.insert_source`/`db.insert_records` API the
real ingest pipeline uses, and queries `corpus_scope()`'s REAL output --
never a fixture literal standing in for it. A regression back to a
hardcoded string, or to code that reads a stale collection list, fails here.
"""
from __future__ import annotations

from pathlib import Path

from sanad.corpus import db
from sanad.corpus.models import Record, Source
from sanad.corpus.schema import SOURCE_SCHEMA_SQL
from sanad.corpus.scope import corpus_scope


def _source(id_: str, kind: str) -> Source:
    return Source(
        id=id_, kind=kind, title="t", publisher=None, edition=None,
        url="https://example.test", license_id="X", license_url=None,
        attribution="a", retrieved_at="2026-01-01", upstream_sha256="0" * 64,
        modifications="none",
    )


def _quran_record(n: int) -> Record:
    return Record(
        id=f"quran:1:{n}", source_id="quran-src", kind="ayah",
        text_ar="بسم الله", text_ar_sha256=None, norm_light=None,
        norm_standard=None, norm_aggressive=None,
        reference_display=f"Al-Fatihah 1:{n}", surah=1, ayah=n,
    )


def _hadith_record(collection: str, n: int) -> Record:
    return Record(
        id=f"hadith:{collection}:{n}", source_id=f"{collection}-src",
        kind="hadith", collection=collection, text_ar="متن",
        text_ar_sha256=None, norm_light=None, norm_standard=None,
        norm_aggressive=None, reference_display=f"{collection} {n}",
        hadith_no=str(n),
    )


def _conn(tmp_path: Path, *, quran: bool, collections: list[str]):
    conn = db.connect(tmp_path / "scope-test.db", read_only=False,
                      schema=SOURCE_SCHEMA_SQL)
    if quran:
        db.insert_source(conn, _source("quran-src", "quran-arabic"))
        db.insert_records(conn, [_quran_record(1)])
    for c in collections:
        db.insert_source(conn, _source(f"{c}-src", "hadith-arabic"))
        db.insert_records(conn, [_hadith_record(c, 1)])
    return conn


def test_bukhari_only_states_present_and_a_generic_absent_clause(tmp_path):
    conn = _conn(tmp_path, quran=True, collections=["bukhari"])
    scope = corpus_scope(conn)
    assert scope == (
        "This corpus contains the Qur'an and Sahih al-Bukhari. It does not "
        "contain any other hadith collection. Absence from this corpus "
        "does not establish that a quotation is fabricated."
    )


def test_adding_muslim_moves_it_from_absent_to_present(tmp_path):
    # The old mechanic ("with Muslim added it drops 'Muslim' from the
    # does-not-contain tail") no longer exists -- the absent clause is
    # generic and never names a collection. What must still be true: Muslim
    # appears in the PRESENT list, and it is nowhere in the absent half.
    conn = _conn(tmp_path, quran=True, collections=["bukhari", "muslim"])
    scope = corpus_scope(conn)
    assert "This corpus contains the Qur'an, Sahih al-Bukhari, and Sahih Muslim." in scope
    assert "does not contain any other hadith collection" in scope
    absent_half = scope.split("It does not contain", 1)[1]
    assert "Muslim" not in absent_half


def test_six_collections_render_in_kutub_al_sittah_order_regardless_of_insert_order(tmp_path):
    conn = _conn(tmp_path, quran=True,
                collections=["ibnmajah", "bukhari", "nasai", "muslim",
                             "tirmidhi", "abudawud"])
    scope = corpus_scope(conn)
    assert scope == (
        "This corpus contains the Qur'an, Sahih al-Bukhari, Sahih Muslim, "
        "Sunan Abi Dawud, Jami at-Tirmidhi, Sunan an-Nasai, and Sunan Ibn "
        "Majah. It does not contain any other hadith collection. Absence "
        "from this corpus does not establish that a quotation is fabricated."
    )


def test_quran_only_with_no_hadith_yet_is_still_grammatical_and_accurate(tmp_path):
    conn = _conn(tmp_path, quran=True, collections=[])
    scope = corpus_scope(conn)
    assert scope == (
        "This corpus contains the Qur'an. It does not contain any other "
        "hadith collection. Absence from this corpus does not establish "
        "that a quotation is fabricated."
    )


def test_empty_corpus_does_not_crash_and_stays_honest(tmp_path):
    conn = _conn(tmp_path, quran=False, collections=[])
    scope = corpus_scope(conn)
    assert scope  # a real sentence, not an empty string or a crash
    assert "does not establish that a quotation is fabricated" in scope
