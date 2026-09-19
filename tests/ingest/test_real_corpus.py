"""Regression guard for the committed corpus, data/sanad-quran.db.

Tanzil's txt-2 export prepends the Bismillah to the text of ayah 1 for every
surah except At-Tawbah -- e.g. it would store 112:1 with the Bismillah
prefixed onto "Say: He is Allah, the One" instead of just that verse,
corrupting similarity scoring for 112 of the corpus's 6,236 records --
disproportionately the short, heavily-quoted ones. The Arabic source is now
Tanzil's XML export, which models the Bismillah as separate metadata; these
tests assert that the shipped database reflects that.

See tests/ingest/test_tanzil.py and tests/ingest/test_build.py for the
equivalent checks against fixtures, independent of this committed database.
"""
from pathlib import Path

from sanad.corpus import db

DB_PATH = Path("data/sanad-quran.db")

# 112:1, "Say: He is Allah, the One" -- built from explicit codepoints,
# verified against the built database, rather than a literal in the source
# file. Tanzil's Uthmani text orders the combining marks on the word "Allah"
# here as SHADDA (U+0651) then FATHA (U+064E); a hand-typed or copy-pasted
# literal with the exact same visual rendering can silently end up in the
# opposite, equally-legible order (FATHA then SHADDA) depending on input
# method or editor/terminal normalization, and would then fail this
# exact-equality check for a reason that has nothing to do with the
# Bismillah bug this test exists to guard against.
_QURAN_112_1_CODEPOINTS = (
    0x0642, 0x064F, 0x0644, 0x0652, 0x0020,  # first word
    0x0647, 0x064F, 0x0648, 0x064E, 0x0020,  # second word
    0x0671, 0x0644, 0x0644, 0x0651, 0x064E, 0x0647, 0x064F, 0x0020,  # "Allah"
    0x0623, 0x064E, 0x062D, 0x064E, 0x062F, 0x064C,  # last word
)
_QURAN_112_1 = "".join(chr(cp) for cp in _QURAN_112_1_CODEPOINTS)


def test_bismillah_is_not_prepended_to_verse_text():
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "quran:112:1").text_ar == _QURAN_112_1


def test_bismillah_stored_separately_where_it_applies():
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "quran:112:1").bismillah is not None


def test_al_fatiha_1_1_is_the_bismillah_itself():
    conn = db.connect(DB_PATH)
    r = db.get_record(conn, "quran:1:1")
    assert r.text_ar.startswith(chr(0x0628) + chr(0x0650) + chr(0x0633) + chr(0x0652)
                                 + chr(0x0645) + chr(0x0650))  # "Bismi..."
    assert r.bismillah is None


def test_at_tawbah_has_no_bismillah():
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "quran:9:1").bismillah is None


def test_exactly_112_records_carry_a_bismillah():
    conn = db.connect(DB_PATH)
    n = conn.execute("SELECT count(*) FROM records WHERE bismillah IS NOT NULL").fetchone()[0]
    assert n == 112  # 114 surahs, minus Al-Fatiha where it is verse 1, minus At-Tawbah
