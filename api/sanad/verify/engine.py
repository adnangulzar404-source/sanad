"""Deterministic quotation verification.

The tier at which a span matches determines its verdict. This coupling is the
point: an aggressive-tier fold can turn a genuine misquote into a string that
equals a real verse, so an aggressive-tier hit may never be reported as
verified. See the spec, section 6.
"""
from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass
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


def _exact_at_tier(conn: sqlite3.Connection, text: str, tier: Tier) -> Record | None:
    needle = normalize(text, tier)
    if not needle:
        return None
    row = conn.execute(
        f"SELECT id FROM records WHERE {_NORM_COLUMN[tier]} = ? LIMIT 1",
        (needle,)).fetchone()
    return db.get_record(conn, row["id"]) if row else None


def _best_fuzzy(conn: sqlite3.Connection, text: str) -> tuple[Record | None, float]:
    needle = normalize(text, "aggressive")
    if not needle:
        return None, 0.0
    best: Record | None = None
    best_score = 0.0
    for cand in db.fts_candidates(conn, needle, CANDIDATE_LIMIT):
        score = ratio(needle, cand.norm_aggressive)
        if score > best_score:
            best, best_score = cand, score
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
        rec = _exact_at_tier(conn, span.text, tier)
        if rec is None:
            continue
        verdict = _TIER_VERDICT[tier]
        if given and _reference_conflicts(given, rec):
            return Match(span, Verdict.WRONG_REFERENCE, rec, tier, 1.0, given)
        return Match(span, verdict, rec, tier, 1.0, given)

    rec, score = _best_fuzzy(conn, span.text)
    if rec is not None and score >= 1.0:
        # matches only after lossy folding -> never "verified"
        if given and _reference_conflicts(given, rec):
            return Match(span, Verdict.WRONG_REFERENCE, rec, "aggressive", score, given,
                         _build_diff(span.text, rec.text_ar))
        return Match(span, Verdict.NEAR_MATCH, rec, "aggressive", score, given,
                     _build_diff(span.text, rec.text_ar))

    if rec is not None and score >= NEAR_THRESHOLD:
        return Match(span, Verdict.NEAR_MATCH, rec, "aggressive", score, given,
                     _build_diff(span.text, rec.text_ar))

    return Match(span, Verdict.NOT_FOUND, None, None, score, given)


def verify_spans(conn: sqlite3.Connection, text: str) -> list[Match]:
    refs = parse_references(text)
    return [_classify(conn, span, refs) for span in extract_spans(text)]
