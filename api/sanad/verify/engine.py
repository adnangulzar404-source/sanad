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


def _classify(conn: sqlite3.Connection, span: Span,
              refs: list[Reference]) -> Match:
    given = _nearest_reference_to_span(refs, span)

    for tier in ("light", "standard"):
        candidates = _exact_at_tier(conn, span.text, tier)
        if not candidates:
            continue
        verdict = _TIER_VERDICT[tier]
        selected, agreed = _select_by_reference(candidates, given)
        also_at = [c.id for c in candidates if c.id != selected.id]
        if given and not agreed:
            return Match(span, Verdict.WRONG_REFERENCE, selected, tier, 1.0, given,
                         also_at=also_at)
        return Match(span, verdict, selected, tier, 1.0, given, also_at=also_at)

    candidates, score = _best_fuzzy(conn, span.text)
    if candidates:
        selected, agreed = _select_by_reference(candidates, given)
        also_at = [c.id for c in candidates if c.id != selected.id]
        diff = _build_diff(span.text, selected.text_ar)
        if score >= 1.0:
            # matches only after lossy folding -> never "verified"
            if given and not agreed:
                return Match(span, Verdict.WRONG_REFERENCE, selected, "aggressive", score,
                             given, diff, also_at)
            return Match(span, Verdict.NEAR_MATCH, selected, "aggressive", score, given,
                         diff, also_at)
        if score >= NEAR_THRESHOLD:
            return Match(span, Verdict.NEAR_MATCH, selected, "aggressive", score, given,
                         diff, also_at)

    return Match(span, Verdict.NOT_FOUND, None, None, score, given)


def verify_spans(conn: sqlite3.Connection, text: str) -> list[Match]:
    refs = parse_references(text)
    return [_classify(conn, span, refs) for span in extract_spans(text)]
