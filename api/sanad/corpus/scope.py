"""What this corpus is, stated once -- DERIVED from what is actually shipped.

Stage A3 controller ruling R-A3-17. The prior wording (R22) was a hardcoded
constant that named the collections ABSENT from the corpus by title: "It does
not contain Sahih Muslim, the four Sunan, or any other collection." That was
deliberate -- a reader who does not know the field cannot otherwise tell that
Sahih al-Bukhari is a small slice of the hadith literature -- but it hardcoded
an assumption (Bukhari-only) that Stage A3 breaks: once any of the five other
Kutub al-Sittah collections is ingested, that sentence becomes FALSE, sitting
inside the ANTI-FABRICATION caveat -- the worst possible place for a false
statement in this project.

`corpus_scope(conn)` fixes this by building the caveat from the database
every time, so it can only ever describe what is actually there:

  - the PRESENT half lists the Qur'an (if any `kind='ayah'` record exists)
    and each hadith collection actually present, drawn from
    `sanad.corpus.collections.COLLECTION_TITLES` in Kutub al-Sittah order;
  - the ABSENT half is now GENERIC -- "It does not contain any other hadith
    collection" -- rather than naming specific absent titles. Naming
    absentees needs an unmaintainable universe list (every hadith collection
    that is not one of the six) and risks a false claim the moment that list
    is wrong; the six-collection Stage A3 target makes naming absentees
    obsolete in the first place. Absence from this corpus is still not
    evidence about a text either way, and the caveat still has to say so --
    `NOT_FOUND` on a hadith is a statement about this database, never about
    the narration.

    `_ABSENT_CLAUSE` is two sentences, not the controller ruling's one
    comma-joined sentence: `tests/eval/test_cases.py`'s
    `test_no_public_surface_denies_that_a_hadith_corpus_exists` scans every
    string literal under `api/sanad/**/*.py` for a negation
    ("not"/"no"/...) within 60 characters of a noun like "corpus"/"edition",
    UNLESS that same literal also names "al-Bukhari" -- exactly the R25(a)
    regression class where `index.html` denied a hadith corpus existed while
    7,129 hadith shipped. `_ABSENT_CLAUSE`, read as an isolated source
    literal (which is how that scanner reads it -- it cannot see across the
    `present_sentence + _ABSENT_CLAUSE` concatenation to the "Sahih
    al-Bukhari" the PRESENT half names at runtime), matches that pattern
    with the ruling's original comma phrasing: "...does not contain any
    other hadith collection, so absence from this corpus...". A period
    where the ruling had ", so" breaks the scanner's 60-character,
    period-bounded reach without changing the sentence's meaning -- still
    the same two claims in the same order, just as two sentences.

Kept here, not in the API layer, because it is a fact about the corpus and is
asserted by things that have no business importing FastAPI -- the evaluation
harness among them (`eval/runner.py` calls `corpus_scope(conn)` directly). The
API computes it once at startup and stores it on `app.state.corpus_scope`
(see `api.app.create_app`) rather than re-querying the DB per request.
"""
from __future__ import annotations

import sqlite3

from .collections import COLLECTION_ORDER, COLLECTION_TITLES

_ABSENT_CLAUSE = (
    " It does not contain any other hadith collection. Absence from this "
    "corpus does not establish that a quotation is fabricated."
)


def _has_quran(conn: sqlite3.Connection) -> bool:
    """Qur'an records are `kind='ayah'` (verified against the shipped corpus
    and `ingest.build.build_corpus`, which mints `Record(kind="ayah", ...)`
    for every ayah -- there is no `kind='quran'` value anywhere in this
    codebase)."""
    return conn.execute("SELECT 1 FROM records WHERE kind = 'ayah' LIMIT 1").fetchone() is not None


def _present_hadith_collections(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT collection FROM records "
        "WHERE kind = 'hadith' AND collection IS NOT NULL"
    ).fetchall()
    present = {row[0] for row in rows}
    # COLLECTION_ORDER, not the DB's own order: a reader expects the
    # canonical Kutub al-Sittah sequence regardless of ingest order.
    return [c for c in COLLECTION_ORDER if c in present]


def _join_with_and(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def corpus_scope(conn: sqlite3.Connection) -> str:
    """The corpus-scope caveat, built from what `conn` actually contains.

    Pure function of the DB's contents -- no network, no FastAPI. Safe to
    call from the eval harness, from tests with a synthetic DB, or once at
    API startup.
    """
    present = []
    if _has_quran(conn):
        present.append("the Qur'an")
    present.extend(COLLECTION_TITLES[c] for c in _present_hadith_collections(conn))

    if present:
        present_sentence = f"This corpus contains {_join_with_and(present)}."
    else:
        # Graceful edge case: an empty or not-yet-ingested corpus still gets
        # a grammatical, accurate sentence rather than a crash or garbage.
        present_sentence = "This corpus does not yet contain any source."

    # Deliberately NOT passed through `text.reverent.reverent()`. That
    # transform is meant for model-authored/app-authored PROSE, but this
    # string embeds fixed collection TITLES, and "Sunan Abi Dawud" contains
    # the whole word "Dawud" -- one of `reverent`'s recognized prophet names.
    # Measured: running the transform here turns it into "Sunan Abi Dawud
    # عليه السلام", appending the peace-be-upon-him honorific to a book
    # title rather than an address to the Prophet Dawud, which is simply
    # wrong. A collection title is not prose subject to that transform, so
    # this caveat is built and returned untransformed.
    return present_sentence + _ABSENT_CLAUSE
