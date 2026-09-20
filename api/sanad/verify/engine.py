"""Deterministic quotation verification.

The tier at which a span matches determines its verdict. This coupling is the
point: an aggressive-tier fold can turn a genuine misquote into a string that
equals a real verse, so an aggressive-tier hit may never be reported as
verified. See the spec, section 6.
"""
from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass, field
from enum import Enum

from ..arabic.normalize import Tier, normalize
from ..arabic.similarity import ratio
from ..corpus import db
from ..corpus.models import Record
from .extract import Span, extract_spans
from .references import Reference, nearest_reference, parse_references

NEAR_THRESHOLD = 0.86
CANDIDATE_LIMIT = 50


class Verdict(str, Enum):
    EXACT = "EXACT"
    EXACT_ORTHOGRAPHY = "EXACT_ORTHOGRAPHY"
    NEAR_MATCH = "NEAR_MATCH"
    WRONG_REFERENCE = "WRONG_REFERENCE"
    NOT_FOUND = "NOT_FOUND"


_TIER_VERDICT: dict[Tier, Verdict] = {
    "light": Verdict.EXACT,
    "standard": Verdict.EXACT_ORTHOGRAPHY,
    "aggressive": Verdict.NEAR_MATCH,
}

_NORM_COLUMN: dict[Tier, str] = {
    "light": "norm_light",
    "standard": "norm_standard",
    "aggressive": "norm_aggressive",
}


@dataclass(frozen=True)
class Match:
    span: Span
    verdict: Verdict
    record: Record | None
    tier: Tier | None
    score: float
    given_reference: Reference | None = None
    diff: list[tuple[str, str]] | None = None
    # Other record ids carrying identical normalized text at the matched tier
    # (e.g. Ar-Rahman's refrain, repeated 31 times). Empty for the
    # overwhelming majority of verses, which are unique.
    also_at: list[str] = field(default_factory=list)


def _exact_at_tier(conn: sqlite3.Connection, text: str, tier: Tier) -> list[Record]:
    """Every record tying on normalized text at this tier, lowest surah:ayah first.

    Some Qur'anic text repeats verbatim across multiple ayat (refrains such as
    Ar-Rahman 55 or Al-Mursalat 77). Returning only one such tied record (the
    old `LIMIT 1` behaviour) meant a correctly-cited quotation of a repeated
    verse could be compared against the WRONG sibling and reported as
    WRONG_REFERENCE even though the citation was exactly right. Callers must
    consider every tied candidate and prefer whichever agrees with a nearby
    reference; see `_select_by_reference`.
    """
    needle = normalize(text, tier)
    if not needle:
        return []
    rows = conn.execute(
        f"SELECT id FROM records WHERE {_NORM_COLUMN[tier]} = ? ORDER BY surah, ayah, id",
        (needle,)).fetchall()
    return [db.get_record(conn, row["id"]) for row in rows]


def _best_fuzzy(conn: sqlite3.Connection, text: str) -> tuple[list[Record], float]:
    """Every fts candidate tied for the highest aggressive-tier score.

    Same duplicate-text concern as `_exact_at_tier`: a repeated verse can tie
    for the top fuzzy score across several of its own occurrences, and the
    caller needs all of them to prefer a reference-agreeing one.
    """
    needle = normalize(text, "aggressive")
    if not needle:
        return [], 0.0
    best: list[Record] = []
    best_score = 0.0
    for cand in db.fts_candidates(conn, needle, CANDIDATE_LIMIT):
        score = ratio(needle, cand.norm_aggressive)
        if score > best_score:
            best, best_score = [cand], score
        elif score == best_score and best_score > 0.0:
            best.append(cand)
    best.sort(key=lambda r: (r.surah or 0, r.ayah or 0, r.id))
    return best, best_score


def _build_diff(quoted: str, canonical: str) -> list[tuple[str, str]]:
    """Character-level opcodes over the standard-tier forms, for display."""
    a, b = normalize(quoted, "standard"), normalize(canonical, "standard")
    out: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            out.append(("equal", a[i1:i2]))
        elif tag == "delete":
            out.append(("quoted-only", a[i1:i2]))
        elif tag == "insert":
            out.append(("corpus-only", b[j1:j2]))
        else:
            out.append(("quoted-only", a[i1:i2]))
            out.append(("corpus-only", b[j1:j2]))
    return out


def _reference_conflicts(given: Reference, rec: Record) -> bool:
    if given.surah != rec.surah:
        return True
    return given.ayah is not None and given.ayah != rec.ayah


def _select_by_reference(
    candidates: list[Record], given: Reference | None
) -> tuple[Record, bool]:
    """Which tied candidate a citation is naming, among records sharing text.

    Returns `(selected, agreed)`. When `given` names a surah (and, if given,
    an ayah) that one of the tied `candidates` actually has, that candidate is
    selected and `agreed` is True -- the quotation is genuine text, correctly
    attributed, even though several other records happen to share its exact
    wording. Otherwise the lowest-surah:ayah candidate is selected (a stable,
    deterministic default) and `agreed` is False: either there was no nearby
    reference, or every candidate disagreed with the one given (a genuine
    WRONG_REFERENCE, reported against that default candidate).
    """
    if given is not None:
        for cand in candidates:
            if not _reference_conflicts(given, cand):
                return cand, True
    return candidates[0], False


def _nearest_reference_to_span(refs: list[Reference], span: Span) -> Reference | None:
    """The reference "given" for a span, checked from both of its edges.

    `nearest_reference` measures its window from a single point. A citation
    conventionally follows the closing quote ("«verse» (2:255)"), so for a
    span longer than the window (e.g. a full long verse like Ayat al-Kursi,
    quoted verbatim) a trailing citation can sit outside the window when
    measured only from span.start -- silently skipping the reference-conflict
    check and letting a wrong citation on a long verse read as EXACT. Some
    citations instead precede the quote, so span.start must still be tried.
    """
    near_start = nearest_reference(refs, span.start)
    near_end = nearest_reference(refs, span.end)
    if near_start and near_end:
        return (near_start if abs(near_start.start - span.start) <= abs(near_end.start - span.end)
                else near_end)
    return near_start or near_end


_MatchCore = tuple[Verdict, Record | None, Tier | None, float,
                    list[tuple[str, str]] | None, list[str]]


def _match_text(
    conn: sqlite3.Connection, text: str, given: Reference | None, *, include_fuzzy: bool = True
) -> _MatchCore:
    """Core three-tier-then-fuzzy lookup, independent of any particular `Span`.

    Returns `(verdict, record, tier, score, diff, also_at)`. Split out of
    `_classify` so the Bismillah-retry path can run this exact pipeline a
    second time, on a second candidate string, without duplicating -- and
    risking drifting from -- the tier logic.

    `_TIER_VERDICT[tier]` is the single source of truth for what a tier's
    match means; every return path derives its verdict from it rather than
    a hardcoded literal, EXCEPT the `WRONG_REFERENCE` override below, which
    is a separate, orthogonal signal (correct text, wrong citation) and
    applies only at `light`/`standard` tier. An `aggressive`-tier match may
    NEVER become `WRONG_REFERENCE`: the fold that produced it (ى/ي, ة/ه) can
    itself have manufactured the agreement OR the disagreement, so the only
    honest claim about the citation is silence -- `given_reference` is still
    populated for the caller to display, but the verdict stays `NEAR_MATCH`
    regardless of whether a citation is present or conflicts.

    `include_fuzzy=False` skips the aggressive/fuzzy fallback and reports
    `NOT_FOUND` on an exact-tier miss instead. `_classify` uses this to probe
    the un-stripped text without letting the fuzzy layer's global candidate
    search fire on it -- a long verse with a Bismillah stuck to the front is
    close enough (in edit-distance terms) to its own bare text to clear
    `NEAR_THRESHOLD` on its own, and a short one is close enough to the
    Bismillah-as-verse record (`quran:1:1`) to do the same, which would both
    report a misleading `NEAR_MATCH` for what is actually a clean, exact
    quotation once the Bismillah is accounted for.
    """
    for tier in ("light", "standard"):
        candidates = _exact_at_tier(conn, text, tier)
        if not candidates:
            continue
        selected, agreed = _select_by_reference(candidates, given)
        also_at = [c.id for c in candidates if c.id != selected.id]
        verdict = Verdict.WRONG_REFERENCE if (given and not agreed) else _TIER_VERDICT[tier]
        return verdict, selected, tier, 1.0, None, also_at

    if not include_fuzzy:
        return Verdict.NOT_FOUND, None, None, 0.0, None, []

    candidates, score = _best_fuzzy(conn, text)
    if candidates and score >= NEAR_THRESHOLD:
        tier: Tier = "aggressive"
        selected, _agreed = _select_by_reference(candidates, given)
        also_at = [c.id for c in candidates if c.id != selected.id]
        diff = _build_diff(text, selected.text_ar)
        return _TIER_VERDICT[tier], selected, tier, score, diff, also_at

    return Verdict.NOT_FOUND, None, None, score, None, []


def _strip_bismillah_prefix(conn: sqlite3.Connection, text: str) -> str | None:
    """If `text` opens with a Bismillah, return the remainder after it.

    Returns `None` when no leading Bismillah is detected (including when
    `text` is nothing but the Bismillah, so there is no remainder to match).
    Comparison is at the "standard" tier (diacritics stripped, alef forms
    folded): a quoted Bismillah's harakat may not match a stored ayah's
    styling exactly, and the phrase's skeleton is identical across surahs.

    This is a narrow fix for one common, real quotation shape -- a verse
    quoted as it appears in a mushaf, with its surah's opening Bismillah
    prepended -- not a general multi-span matcher. Callers must only invoke
    this after the FULL text has already failed to match at every tier: for
    `quran:1:1`, the Bismillah IS the verse, and a verbatim quote of it
    matches directly on the first attempt, so this path never runs for it.
    """
    row = conn.execute(
        "SELECT bismillah FROM records WHERE bismillah IS NOT NULL LIMIT 1").fetchone()
    if row is None:
        return None
    target = normalize(row["bismillah"], "standard")
    if not target:
        return None
    # Find the LARGEST raw prefix whose standard-tier form still equals the
    # canonical Bismillah, not the smallest. The smallest match lands right
    # after the last base letter but before any diacritic still attached to
    # it (e.g. the closing kasra on "الرحيم"); since normalize() strips
    # diacritics, a shorter and a longer prefix can normalize identically.
    # Stopping at the smallest leaves that diacritic as the first character
    # of the "remainder" -- a combining mark `.lstrip()` will not remove --
    # which then fails a light-tier (byte-exact) match on the retry even
    # though the actual verse text is untouched.
    limit = min(len(text), len(row["bismillah"]) + 15)
    best_k = None
    for k in range(1, limit + 1):
        if normalize(text[:k], "standard") == target:
            best_k = k
        elif best_k is not None:
            break  # prefix has grown past the Bismillah; stop extending
    if best_k is None:
        return None
    remainder = text[best_k:].lstrip()
    return remainder or None


def _classify(conn: sqlite3.Connection, span: Span,
              refs: list[Reference]) -> Match:
    given = _nearest_reference_to_span(refs, span)

    # 1. Exact tiers on the text as quoted (no fuzzy fallback yet -- see
    #    `_match_text`'s docstring for why the fuzzy layer must not see the
    #    un-stripped text before the Bismillah retry gets a chance).
    verdict, record, tier, score, diff, also_at = _match_text(
        conn, span.text, given, include_fuzzy=False)

    # 2. A leading Bismillah, stripped, run through the full pipeline.
    if verdict is Verdict.NOT_FOUND:
        stripped = _strip_bismillah_prefix(conn, span.text)
        if stripped is not None:
            retry = _match_text(conn, stripped, given)
            retry_record = retry[1]
            retry_also_at = retry[5]
            # A stripped-prefix retry is only a legitimate "Bismillah + its
            # own surah's opening ayah" quotation when EVERY record tied on
            # the stripped text is itself a surah's first ayah that carries
            # a Bismillah. Checking only the selected record is not enough:
            # some Qur'anic wording repeats verbatim across otherwise
            # unrelated ayat (e.g. 39:1, 45:2, and 46:2 all read "تَنزِيلُ
            # ٱلْكِتَٰبِ مِنَ ٱللَّهِ ٱلْعَزِيزِ ٱلْحَكِيمِ"), so a stripped
            # remainder can tie between a genuine Bismillah-bearing opener
            # (39:1) and non-opening ayat with no Bismillah of their own
            # (45:2, 46:2). Accepting the selected 39:1 alone would still
            # report "Bismillah + 45:2's text" as EXACT, which is exactly
            # the false verification this fix exists to prevent -- the
            # citation is genuinely ambiguous, and the honest response is
            # silence, not a guess. More generally: without this check, ANY
            # text sharing a light/standard-tier prefix-stripped form with
            # ANY record -- e.g. Al-Ikhlas's Bismillah stitched onto Ayat
            # al-Kursi, or onto any ayah of At-Tawbah, the one surah with no
            # Bismillah at all (`bismillah IS NULL` for the whole surah) --
            # would report a multi-ayah quotation, which is not a single
            # corpus record, as EXACT. Discard an illegitimate retry and
            # fall through to whatever the unstripped text produces on its
            # own (step 3); `verdict`/`record`/etc are simply left as step
            # 1's NOT_FOUND.
            candidate_ids = [retry_record.id] + retry_also_at if retry_record else []
            candidates = [db.get_record(conn, cid) for cid in candidate_ids]
            if candidates and all(
                    c is not None and c.ayah == 1 and c.bismillah is not None
                    for c in candidates):
                verdict, record, tier, score, diff, also_at = retry

    # 3. Last resort: fuzzy match on the text exactly as quoted.
    if verdict is Verdict.NOT_FOUND:
        verdict, record, tier, score, diff, also_at = _match_text(conn, span.text, given)

    return Match(span, verdict, record, tier, score, given, diff, also_at)


def verify_spans(conn: sqlite3.Connection, text: str) -> list[Match]:
    refs = parse_references(text)
    return [_classify(conn, span, refs) for span in extract_spans(text)]
