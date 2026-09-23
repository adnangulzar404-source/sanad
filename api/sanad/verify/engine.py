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
from .references import (
    AnyReference,
    HadithReference,
    Reference,
    nearest_reference,
    parse_references,
)

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
    # The citation the reader gave FOR THIS QUOTATION, or None. Where a record
    # was matched this is always a citation of that record's own kind -- a
    # verse citation is never reported as the reference "given" for a hadith,
    # or the reverse; see `_NearbyReferences`. Where nothing matched there is
    # no kind to align to, and this is simply the nearest citation of either
    # kind, for display: no attachment is being claimed.
    given_reference: AnyReference | None = None
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

    Both halves of the UNION are needed, and an index-only change would have
    covered neither: this tier reads the tables DIRECTLY, and it is the tier
    that did the damage the last time a filter was missing from it. The first
    half is the primary representation, in `records`; the second is every
    additional representation, in `record_variants` -- so a quotation of a
    hadith as the edition prints it matches at the same tier, and with the
    same verdict, as a quotation of its primary matn alone. `UNION` (not
    `UNION ALL`) collapses a record that ties on both of its representations
    to one row, so it can never be reported twice in `also_at`.

    `unscorable_reason IS NULL` excludes the records whose stored text is the
    edition's editorial apparatus rather than a narration -- see
    `Record.unscorable_reason` -- and is applied to both halves: "bi-hadha"
    normalizes to itself and tied four records exactly, verdict EXACT, score
    1.0.
    """
    needle = normalize(text, tier)
    if not needle:
        return []
    column = _NORM_COLUMN[tier]
    rows = conn.execute(
        f"SELECT r.id AS id, r.surah AS surah, r.ayah AS ayah FROM records r"
        f" WHERE r.{column} = ? AND r.unscorable_reason IS NULL"
        " UNION "
        "SELECT r.id, r.surah, r.ayah FROM record_variants v"
        " JOIN records r ON r.id = v.record_id"
        f" WHERE v.{column} = ? AND r.unscorable_reason IS NULL"
        " ORDER BY surah, ayah, id",
        (needle, needle)).fetchall()
    return [db.get_record(conn, row["id"]) for row in rows]


def _best_fuzzy(
    conn: sqlite3.Connection, text: str
) -> tuple[list[Record], float, dict[str, str]]:
    """Every fts candidate tied for the highest aggressive-tier score.

    Same duplicate-text concern as `_exact_at_tier`: a repeated verse can tie
    for the top fuzzy score across several of its own occurrences, and the
    caller needs all of them to prefer a reference-agreeing one.

    A record may be indexed under more than one representation (primary matn
    and full printed text -- see `corpus.models.RecordVariant`). Each is
    scored against the text that was actually indexed, and then the record
    keeps only its BEST-scoring representation, so one record cannot occupy
    two places in the tie set and cannot appear in its own `also_at`.

    The third return value maps record id to the representation's text that
    scored, for `_build_diff`: diffing a full-text hit against the record's
    primary matn would show the addendum as "corpus-only" text the quoter
    omitted, when they quoted it exactly.
    """
    needle = normalize(text, "aggressive")
    if not needle:
        return [], 0.0, {}
    best_per_record: dict[str, tuple[float, Record, str]] = {}
    for cand in db.fts_candidates(conn, needle, CANDIDATE_LIMIT):
        score = ratio(needle, cand.norm_aggressive)
        previous = best_per_record.get(cand.record.id)
        if previous is None or score > previous[0]:
            best_per_record[cand.record.id] = (score, cand.record, cand.text_ar)
    if not best_per_record:
        return [], 0.0, {}
    best_score = max(score for score, _, _ in best_per_record.values())
    if best_score == 0.0:
        return [], 0.0, {}
    best = [rec for score, rec, _ in best_per_record.values() if score == best_score]
    best.sort(key=lambda r: (r.surah or 0, r.ayah or 0, r.id))
    texts = {rec.id: matched for score, rec, matched in best_per_record.values()
             if score == best_score}
    return best, best_score, texts


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


def _reference_conflicts(given: AnyReference, rec: Record) -> bool:
    """Does the citation the reader gave disagree with where the text is?

    Only ever called with a citation of `rec`'s OWN kind -- `_NearbyReferences`
    is what guarantees that, and the `isinstance` below is dispatch, not a
    guard. A cross-kind pair never reaches here to be judged either way.

    For a hadith the comparison is on the PRINTED number, not the record id:
    `hadith_no` is not unique (7,124 distinct numbers over 7,129 records --
    the repeats carry an occurrence ordinal in the id and the display string,
    never in the printed number). A citation of a repeated number agrees with
    ANY record printed under it, which is why `_select_by_reference` walks
    every tied candidate rather than judging the first.
    """
    if isinstance(given, HadithReference):
        return given.collection != rec.collection or given.hadith_no != rec.hadith_no
    if given.surah != rec.surah:
        return True
    return given.ayah is not None and given.ayah != rec.ayah


@dataclass(frozen=True)
class _NearbyReferences:
    """The citations near one span, kept apart BY THE KIND THEY CAN ADDRESS.

    This shape is the fix for the Task 6 findings' D1, and the reason it is a
    shape rather than a check. Previously a single "nearest reference" was
    resolved for a span and then compared against whatever record the text
    matched: a Qur'anic `112:1` at the far end of a sentence was handed to a
    hadith quotation and reported as its given reference, so Sanad told a
    reader who had cited Sahih al-Bukhari 2866 perfectly that their citation
    was wrong. A false accusation of misattribution is in the same severity
    class as a false EXACT.

    There is no field here that can carry a `Reference` to a hadith record or
    a `HadithReference` to an ayah: `for_kind` is the only way out, and it
    reads the field named for the record's own kind. A kind that nothing
    cites gets `None`, never a fallback to "whatever was nearest". The
    property therefore holds by construction, for every present and future
    call site, instead of resting on three separate guards that each have to
    be remembered.

    `nearest` is the nearest citation of EITHER kind and exists for exactly
    one purpose: a span that matched NO record has no kind to align to, and
    showing the reader the citation they wrote next to unfindable text is
    information, not an attachment -- no comparison is ever made against it.
    It is deliberately not reachable through `for_kind`.
    """

    ayah: Reference | None
    hadith: HadithReference | None
    nearest: AnyReference | None

    def for_kind(self, kind: str) -> AnyReference | None:
        if kind == "ayah":
            return self.ayah
        if kind == "hadith":
            return self.hadith
        return None

    def for_record(self, rec: Record) -> AnyReference | None:
        return self.for_kind(rec.kind)


def _select_by_reference(
    candidates: list[Record], nearby: _NearbyReferences
) -> tuple[Record, bool]:
    """Which tied candidate a citation is naming, among records sharing text.

    Returns `(selected, agreed)`. When the citation given for a candidate's
    own kind names something that candidate actually is, that candidate is
    selected and `agreed` is True -- the quotation is genuine text, correctly
    attributed, even though other records happen to share its exact wording.

    When nothing agrees, the fallback prefers a candidate the reader actually
    cited something FOR, so that a wrong citation is reported against a record
    of the kind that was cited. Tie sets are usually all one kind, in which
    case this is the old behaviour exactly (the lowest-surah:ayah candidate);
    it only differs where an ayah and a hadith share wording, where reporting
    the wrong hadith number against the ayah -- or silently dropping it --
    would both be worse. The final fallback is the first candidate: stable and
    deterministic, and `agreed` is False, so no citation is endorsed.
    """
    for cand in candidates:
        given = nearby.for_record(cand)
        if given is not None and not _reference_conflicts(given, cand):
            return cand, True
    for cand in candidates:
        if nearby.for_record(cand) is not None:
            return cand, False
    return candidates[0], False


def _nearest_reference_to_span(
    refs: list[AnyReference], span: Span
) -> _NearbyReferences:
    """The citations "given" for a span, resolved per kind, from both edges.

    `nearest_reference` measures its window from a single point. A citation
    conventionally follows the closing quote ("«verse» (2:255)"), so for a
    span longer than the window (e.g. a full long verse like Ayat al-Kursi,
    quoted verbatim) a trailing citation can sit outside the window when
    measured only from span.start -- silently skipping the reference-conflict
    check and letting a wrong citation on a long verse read as EXACT. Some
    citations instead precede the quote, so span.start must still be tried.

    Each kind is resolved independently and on its own merits: a nearer
    citation of one kind never displaces, shadows or stands in for one of the
    other. That matters for text carrying both ("«matn» (112:1) (Bukhari 1)"),
    where a "nearest, then check its kind" rule would drop the hadith citation
    and let a genuinely wrong one pass unflagged.
    """
    def of_kind(kind: str) -> AnyReference | None:
        near_start = nearest_reference(refs, span.start, kind=kind)
        near_end = nearest_reference(refs, span.end, kind=kind)
        if near_start and near_end:
            return (near_start
                    if abs(near_start.start - span.start) <= abs(near_end.start - span.end)
                    else near_end)
        return near_start or near_end

    ayah = of_kind("ayah")
    hadith = of_kind("hadith")
    both = [r for r in (ayah, hadith) if r is not None]
    nearest = min(
        both,
        key=lambda r: min(abs(r.start - span.start), abs(r.start - span.end)),
    ) if both else None
    return _NearbyReferences(ayah=ayah, hadith=hadith, nearest=nearest)


_MatchCore = tuple[Verdict, Record | None, Tier | None, float,
                    list[tuple[str, str]] | None, list[str]]


def _match_text(
    conn: sqlite3.Connection, text: str, nearby: _NearbyReferences,
    *, include_fuzzy: bool = True
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
        selected, agreed = _select_by_reference(candidates, nearby)
        also_at = [c.id for c in candidates if c.id != selected.id]
        # Only a citation of the SELECTED record's own kind can make this a
        # wrong reference. Where none was given, the verdict is decided on the
        # text alone -- the correct answer for a quotation nobody cited.
        given = nearby.for_record(selected)
        verdict = Verdict.WRONG_REFERENCE if (given and not agreed) else _TIER_VERDICT[tier]
        return verdict, selected, tier, 1.0, None, also_at

    if not include_fuzzy:
        return Verdict.NOT_FOUND, None, None, 0.0, None, []

    candidates, score, matched_text = _best_fuzzy(conn, text)
    if candidates and score >= NEAR_THRESHOLD:
        tier: Tier = "aggressive"
        selected, _agreed = _select_by_reference(candidates, nearby)
        also_at = [c.id for c in candidates if c.id != selected.id]
        diff = _build_diff(text, matched_text[selected.id])
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


def _accept_bismillah_retry(
    conn: sqlite3.Connection, stripped: str, nearby: _NearbyReferences
) -> _MatchCore | None:
    """Run the full pipeline on a Bismillah-stripped remainder, but only
    accept the result when at least one record tied on that remainder is
    itself a legitimate Bismillah-bearing first ayah. Returns `None` when
    the retry must be discarded (the caller then falls through to whatever
    the unstripped text produces on its own).

    A stripped-prefix retry is only a legitimate "Bismillah + its own
    surah's opening ayah" quotation when SOME record tied on the stripped
    text is a surah's first ayah that carries a Bismillah -- not necessarily
    the one `_match_text` happened to select. Some Qur'anic wording repeats
    verbatim across otherwise unrelated ayat -- e.g. 39:1, 45:2, and 46:2 all
    read "تَنزِيلُ ٱلْكِتَٰبِ مِنَ ٱللَّهِ ٱلْعَزِيزِ ٱلْحَكِيمِ" -- so a
    stripped remainder can tie between a genuine Bismillah-bearing opener
    (39:1) and non-opening ayat with no Bismillah of their own (45:2, 46:2).
    Requiring *every* tied candidate to qualify (an earlier, over-corrected
    version of this check) rejected genuine mushaf pastes of 39:1 outright,
    because 45:2 and 46:2 -- which merely share its wording -- vetoed it.

    The correct rule is: when a non-qualifying record's text happens to be
    byte-identical to a qualifying record's, the input is genuinely
    ambiguous -- "Bismillah + <text>" is indistinguishable from a legitimate
    paste of the qualifying ayah -- so attributing it to that ayah (and
    disclosing the others through `also_at`) is the honest reading, not a
    guess and not a false verification: the text really is that ayah's
    text, and that ayah really does carry that Bismillah. Only when NO tied
    candidate qualifies (e.g. Al-Ikhlas's Bismillah stitched onto Ayat
    al-Kursi, or onto any ayah of At-Tawbah -- the one surah with no
    Bismillah at all, `bismillah IS NULL` for the whole surah) is the retry
    discarded.
    """
    _retry_verdict, retry_record, retry_tier, retry_score, _retry_diff, retry_also_at = (
        _match_text(conn, stripped, nearby))
    if retry_record is None:
        return None

    tied_ids = [retry_record.id] + retry_also_at
    tied = [db.get_record(conn, cid) for cid in tied_ids]
    tied = [c for c in tied if c is not None]
    tied.sort(key=lambda c: (c.surah or 0, c.ayah or 0, c.id))

    qualifying = [c for c in tied if c.ayah == 1 and c.bismillah is not None]
    if not qualifying:
        return None

    selected, agreed = _select_by_reference(qualifying, nearby)
    also_at = [c.id for c in tied if c.id != selected.id]
    given = nearby.for_record(selected)

    if retry_tier == "aggressive":
        # Aggressive-tier matches may never assert WRONG_REFERENCE (see
        # `_match_text`'s docstring) and need their diff rebuilt against
        # whichever candidate was actually selected here.
        verdict = _TIER_VERDICT["aggressive"]
        diff = _build_diff(stripped, selected.text_ar)
    else:
        verdict = Verdict.WRONG_REFERENCE if (given and not agreed) else _TIER_VERDICT[retry_tier]
        diff = None

    return verdict, selected, retry_tier, retry_score, diff, also_at


def _classify(conn: sqlite3.Connection, span: Span,
              refs: list[AnyReference]) -> Match:
    nearby = _nearest_reference_to_span(refs, span)

    # 1. Exact tiers on the text as quoted (no fuzzy fallback yet -- see
    #    `_match_text`'s docstring for why the fuzzy layer must not see the
    #    un-stripped text before the Bismillah retry gets a chance).
    verdict, record, tier, score, diff, also_at = _match_text(
        conn, span.text, nearby, include_fuzzy=False)

    # 2. A leading Bismillah, stripped, run through the full pipeline.
    if verdict is Verdict.NOT_FOUND:
        stripped = _strip_bismillah_prefix(conn, span.text)
        if stripped is not None:
            retry = _accept_bismillah_retry(conn, stripped, nearby)
            if retry is not None:
                verdict, record, tier, score, diff, also_at = retry

    # 3. Last resort: fuzzy match on the text exactly as quoted.
    if verdict is Verdict.NOT_FOUND:
        verdict, record, tier, score, diff, also_at = _match_text(conn, span.text, nearby)

    # Report the citation given FOR THE RECORD THAT MATCHED -- necessarily one
    # of that record's own kind. With nothing matched there is no kind to
    # align to, so the nearest of either kind is shown as-is; nothing was
    # compared against it and no attachment is claimed.
    given = nearby.for_record(record) if record is not None else nearby.nearest
    return Match(span, verdict, record, tier, score, given, diff, also_at)


def _is_only_a_citation(span: Span, refs: list[AnyReference]) -> bool:
    """Is this "quotation" nothing but a citation the reader wrote?

    The Task 6 findings, D2: an Arabic-script citation is itself a run of
    Arabic, so the extractor offered "صحيح البخاري ٣٠٣٠" up as a quotation and
    the verifier duly answered "not in this corpus". A citation is not a
    quotation, and only people who cite in Arabic ever saw this -- exactly the
    readers most likely to.

    The test is on what is LEFT after the characters covered by parsed
    citations are set aside: a span survives only if the remainder would still
    have qualified as a span on its own, by `extract_spans`' own measure and
    its own per-kind minimum. So a citation standing alone is dropped, while a
    quotation that merely sits next to one is untouched -- an over-broad
    filter here would silently delete real quotations, which is worse than the
    defect it fixes.

    Nothing is trimmed, re-spelled or handed on: the remainder is measured and
    discarded. Spans that survive are verified as the reader wrote them, byte
    for byte. On today's corpus no record's own text contains anything
    `parse_references` reads as a citation (swept in the tests), so this can
    only ever remove a citation, never a quotation of a real record.
    """
    covered = [(r.start, r.start + len(r.raw)) for r in refs]
    if not covered:
        return False
    remainder = "".join(
        ch for i, ch in enumerate(span.text, start=span.start)
        if not any(s <= i < e for s, e in covered)
    )
    floor = 2 if span.kind == "wrapped" else 6  # extract_spans' own minimums
    return len(normalize(remainder, "aggressive").replace(" ", "")) < floor


def verify_spans(conn: sqlite3.Connection, text: str) -> list[Match]:
    # `parse_references` yields both families -- `Reference` (surah:ayah) and
    # `HadithReference` (Task 5 of the hadith corpus plan) -- and both are
    # passed through. The Task 5 stopgap that filtered `HadithReference` out
    # here is gone: it existed only because the conflict check would have read
    # `.surah` off one and crashed, and `_NearbyReferences` now routes each
    # family to the record kind it can actually address, so a hadith citation
    # reaches a hadith quotation and nothing else. Keeping both mechanisms
    # would have left the filter quietly suppressing the feature.
    refs = parse_references(text)
    return [_classify(conn, span, refs) for span in extract_spans(text)
            if not _is_only_a_citation(span, refs)]
