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
from .extract import Span, extract_spans, minimum_chars
from .references import (
    AnyReference,
    HadithReference,
    nearest_reference,
    parse_citations,
)

NEAR_THRESHOLD = 0.86
CANDIDATE_LIMIT = 50

# "Is this quotation inside an ayah?" is asked at two tiers, because it is
# asked for two purposes whose errors cost opposite things.
#
# WITHHOLDING a hadith verdict (R40) is asked at the AGGRESSIVE tier -- the
# widest comparison this engine ever makes. Withholding needs no evidentiary
# standard: being wrong here costs recall on a hadith, which R40 accepts
# explicitly, while being wrong the other way tells a reader who cited
# scripture correctly that their reference is wrong.
#
# DISCLOSING where the words are is asked at the STANDARD tier -- the coarser
# of the two tiers that can carry a verified verdict, and the tier
# `build._reject_wholly_quranic_representations` uses for the same judgement.
# That is a statement made to the reader, and this module's founding rule is
# that an aggressive-tier fold (alef maksura/yeh, teh marbuta/heh) can
# manufacture an agreement that is not in the letters, so it may never be
# reported as verified. An ayah that contains the quotation only after those
# folds is enough to stay silent about the hadith and not enough to assert
# where the words are.
_WITHHOLDING_TIER: Tier = "aggressive"
_DISCLOSURE_TIER: Tier = "standard"


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
    # The citation the reader gave for this quotation, or None: whichever
    # parsed citation sits nearest the span, of either family. It may well be
    # a citation of the wrong KIND for the record that matched -- an ayah
    # attributed to Sahih al-Bukhari -- and that is precisely the case worth
    # surfacing rather than hiding, so it arrives here alongside a
    # WRONG_REFERENCE verdict. See `_reference_conflicts`.
    given_reference: AnyReference | None = None
    diff: list[tuple[str, str]] | None = None
    # Where else in this corpus these words are, beyond the record reported.
    #
    # Two things reach this list, and the shared meaning is "these words are
    # also at X" rather than "X is an equally good answer":
    #
    # 1. Other records carrying IDENTICAL normalized text at the matched tier
    #    (e.g. Ar-Rahman's refrain, repeated 31 times). Empty for the
    #    overwhelming majority of verses, which are unique.
    # 2. Any ayah whose own text CONTAINS this quotation, when the record
    #    reported is a hadith -- see `_ayat_containing`. One pair in the
    #    shipped corpus does this: Sahih al-Bukhari 3658's whole matn sits
    #    inside Qur'an 54:1. Saying only "Sahih al-Bukhari 3658" about words
    #    that are also scripture is true and incomplete.
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

    `unscorable_reason IS NULL` excludes the records whose stored PRIMARY is
    the edition's editorial apparatus rather than a narration -- see
    `Record.unscorable_reason`. "bi-hadha" normalizes to itself and tied four
    records exactly, verdict EXACT, score 1.0.

    It is applied to the FIRST half only. The reason is a judgement about one
    string, and the second half reads a different one: record 237's primary
    is a chain-transfer fragment and its full printed text is an ordinary
    869-character narration, the longest in the edition. Filtering both
    halves on the primary's judgement made the printed hadith unfindable.
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
        f" WHERE v.{column} = ?"
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


def _cited_kind(given: AnyReference) -> str:
    """The kind of record this citation claims to be addressing."""
    return "hadith" if isinstance(given, HadithReference) else "ayah"


def _reference_conflicts(given: AnyReference, rec: Record) -> bool:
    """Does the citation the reader gave disagree with where the text is?

    KIND IS COMPARED FIRST, and a mismatch is a conflict. "«qul huwa llahu
    ahad» (Bukhari 12)" attributes a Qur'anic verse to a hadith collection:
    the citation is real, it is the nearest thing to the quotation, and it is
    wrong about what kind of text this is. That is a category error about
    scripture and a graver misattribution than any wrong number, so it is
    reported, not passed over. An earlier version of this task refused to
    attach a cross-kind citation at all, which turned every instance of this
    into a silent EXACT.

    Comparing kind first is also what keeps the field comparisons honest: the
    branches below read `.surah`/`.ayah` and `.collection`/`.hadith_no`, and
    on a record of the other kind those are all `None`, so two mismatched
    things could otherwise agree by both being nothing.

    For a hadith the comparison is on the PRINTED number, not the record id:
    `hadith_no` is not unique (7,124 distinct numbers over 7,129 records --
    the repeats carry an occurrence ordinal in the id and the display string,
    never in the printed number). A citation of a repeated number agrees with
    ANY record printed under it, which is why `_select_by_reference` walks
    every tied candidate rather than judging the first.
    """
    if _cited_kind(given) != rec.kind:
        return True
    if isinstance(given, HadithReference):
        return given.collection != rec.collection or given.hadith_no != rec.hadith_no
    if given.surah != rec.surah:
        return True
    return given.ayah is not None and given.ayah != rec.ayah


def _select_by_reference(
    candidates: list[Record], given: AnyReference | None
) -> tuple[Record, bool]:
    """Which tied candidate a citation is naming, among records sharing text.

    Returns `(selected, agreed)`. When `given` names something one of the tied
    `candidates` actually is, that candidate is selected and `agreed` is True
    -- the quotation is genuine text, correctly attributed, even though
    several other records happen to share its exact wording.

    When nothing agrees, the fallback prefers a candidate of the kind the
    citation addresses, so the mismatch is reported against a record the
    reader could plausibly have meant. Tie sets are all one kind on today's
    corpus, where this changes nothing; it matters only if an ayah and a
    hadith ever share wording, and reporting "Bukhari 9 is wrong" against an
    ayah would be a confusing way to be right. The final fallback is the first
    candidate: stable, deterministic, and `agreed` is False, so no citation is
    endorsed either way.
    """
    if given is not None:
        for cand in candidates:
            if not _reference_conflicts(given, cand):
                return cand, True
        for cand in candidates:
            if _cited_kind(given) == cand.kind:
                return cand, False
    return candidates[0], False


def _nearest_reference_to_span(
    refs: list[AnyReference], span: Span
) -> AnyReference | None:
    """The citation "given" for a span, checked from both of its edges.

    `nearest_reference` measures its window from a single point. A citation
    conventionally follows the closing quote ("«verse» (2:255)"), so for a
    span longer than the window (e.g. a full long verse like Ayat al-Kursi,
    quoted verbatim) a trailing citation can sit outside the window when
    measured only from span.start -- silently skipping the reference-conflict
    check and letting a wrong citation on a long verse read as EXACT. Some
    citations instead precede the quote, so span.start must still be tried.

    Kind plays no part here. Attachment is decided by distance across every
    citation in the text, and the Task 6 findings' D1 -- a hadith quotation
    picking up a Qur'anic citation from the far end of a sentence -- is a
    distance bug, fixed by measuring distance properly. The adjacent
    "(Bukhari 2866)" wins over the distant "(112:1)" because it is nearer,
    not because of what it cites. Whether the winner is the RIGHT kind of
    citation is a question about the verdict, answered in
    `_reference_conflicts`, and filtering it out here would only hide it.
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
    conn: sqlite3.Connection, text: str, given: AnyReference | None,
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
        selected, agreed = _select_by_reference(candidates, given)
        also_at = [c.id for c in candidates if c.id != selected.id]
        verdict = Verdict.WRONG_REFERENCE if (given and not agreed) else _TIER_VERDICT[tier]
        return verdict, selected, tier, 1.0, None, also_at

    if not include_fuzzy:
        return Verdict.NOT_FOUND, None, None, 0.0, None, []

    candidates, score, matched_text = _best_fuzzy(conn, text)
    if candidates and score >= NEAR_THRESHOLD:
        tier: Tier = "aggressive"
        selected, _agreed = _select_by_reference(candidates, given)
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
    conn: sqlite3.Connection, stripped: str, given: AnyReference | None
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
        _match_text(conn, stripped, given))
    if retry_record is None:
        return None

    tied_ids = [retry_record.id] + retry_also_at
    tied = [db.get_record(conn, cid) for cid in tied_ids]
    tied = [c for c in tied if c is not None]
    tied.sort(key=lambda c: (c.surah or 0, c.ayah or 0, c.id))

    qualifying = [c for c in tied if c.ayah == 1 and c.bismillah is not None]
    if not qualifying:
        return None

    selected, agreed = _select_by_reference(qualifying, given)
    also_at = [c.id for c in tied if c.id != selected.id]

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


def _ayat_containing(conn: sqlite3.Connection, text: str,
                     tier: Tier) -> list[Record]:
    """Every ayah whose own text contains this quotation, lowest surah:ayah first.

    Substring containment, not equality and not token alignment. The attached
    conjunction is the whole point: `hadith:bukhari:3658`'s entire matn is "the
    moon split" and Qur'an 54:1 ends with the same two words carrying a
    prefixed waw, so a token-aligned test -- which is what the build's
    `_reject_wholly_quranic_representations` runs, and rightly -- sees nothing.

    The record is legitimate. It is a Companion's report whose matn really is
    that short, so there is nothing to reject at build time and a build that
    refused it would be refusing an ordinary hadith. What the corpus needs is
    for the VERIFIER to know that these words have two addresses.

    A plain substring test could in principle fire mid-word, which would be a
    false statement about where a reader's words are. That is measured rather
    than assumed: swept over all 7,504 scorable hadith representations against
    all 6,236 ayat, substring containment yields exactly ONE hit -- 3658 in
    54:1 -- at the standard tier and the same one hit at the aggressive tier,
    and it is a clitic boundary, not a mid-word accident. The same sweep under
    a token-aligned test yields zero, which is the build invariant's own
    measurement, and under a clitic-relaxed test yields the same one. So the
    simplest rule and the carefully boundary-aware one agree on this corpus,
    and the simple one has no knob to tune wrong.

    The ayah rows are read whole rather than by id so the caller can re-ask
    the same question at a stricter tier without a second query -- see
    `_WITHHOLDING_TIER` and `_DISCLOSURE_TIER`.
    """
    needle = normalize(text, tier)
    if not needle:
        return []
    rows = conn.execute(
        "SELECT id FROM records WHERE kind = 'ayah'"
        f" AND instr({_NORM_COLUMN[tier]}, ?) > 0", (needle,)).fetchall()
    found = (db.get_record(conn, row["id"]) for row in rows)
    ayat = [rec for rec in found if rec is not None]
    ayat.sort(key=lambda r: (r.surah or 0, r.ayah or 0, r.id))
    return ayat


def _contains_at(ayah: Record, text: str, tier: Tier) -> bool:
    """Does `ayah` still contain `text` under a stricter comparison?

    Asked in Python, on the handful of rows the withholding-tier query already
    returned, rather than as a second scan of the Qur'an.
    """
    needle = normalize(text, tier)
    return bool(needle) and needle in getattr(ayah, _NORM_COLUMN[tier])


def _classify(conn: sqlite3.Connection, span: Span,
              refs: list[AnyReference]) -> Match:
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
            retry = _accept_bismillah_retry(conn, stripped, given)
            if retry is not None:
                verdict, record, tier, score, diff, also_at = retry

    # 3. Last resort: fuzzy match on the text exactly as quoted.
    if verdict is Verdict.NOT_FOUND:
        verdict, record, tier, score, diff, also_at = _match_text(conn, span.text, given)

    # 4. A hadith answer is withdrawn when the reader named an ayah their words
    #    are inside of, and disclosed alongside otherwise. R40:
    #
    #      when a reader supplies a Qur'anic reference and the quoted text is
    #      contained in that ayah, Sanad must not answer with a hadith verdict
    #      of any kind.
    #
    #    "Of any kind" includes NEAR_MATCH and, above all, WRONG_REFERENCE:
    #    telling someone who quoted two words of 54:1 and cited 54:1 that their
    #    reference is wrong is the same error as answering scripture with a
    #    hadith, said out loud. `_reference_conflicts` is reused rather than
    #    re-implemented so "does this citation name that ayah" has one answer
    #    in one place -- it compares kind first, so a HADITH citation next to a
    #    quotation of the same words withholds nothing: that reader asked about
    #    the hadith and gets it.
    #
    #    The withheld verdict is NOT_FOUND with no record. A fragment of an
    #    ayah has never been verifiable here -- Sanad's unit is the whole ayah,
    #    and C1's two-verse quotation is NOT_FOUND today for the same reason --
    #    so this is the existing limitation, not a new verdict invented for one
    #    record. What is new is that the fragment's address is disclosed, so
    #    NOT_FOUND cannot be read as "these words are in neither book".
    if record is not None and record.kind == "hadith":
        containing = _ayat_containing(conn, span.text, _WITHHOLDING_TIER)
        disclosed = [ayah.id for ayah in containing
                     if _contains_at(ayah, span.text, _DISCLOSURE_TIER)]
        if given is not None and any(not _reference_conflicts(given, ayah)
                                     for ayah in containing):
            return Match(span, Verdict.NOT_FOUND, None, None, 0.0, given, None,
                         disclosed)
        also_at = also_at + [i for i in disclosed if i not in also_at]

    return Match(span, verdict, record, tier, score, given, diff, also_at)


def _is_only_a_citation(span: Span, citation_spans: list[tuple[int, int]]) -> bool:
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

    The ranges come from `ParsedCitations.spans`, not from the resolved
    references, so a citation whose number is out of range ("sahih al-bukhari
    99999") is covered too. It resolves to nothing and is still obviously a
    citation; keying this off the resolved list left exactly that case being
    reported NOT_FOUND.

    Nothing is trimmed, re-spelled or handed on: the remainder is measured and
    discarded. Spans that survive are verified as the reader wrote them, byte
    for byte. On today's corpus no record's own text contains anything
    `parse_citations` reads as a citation (swept in the tests), so this can
    only ever remove a citation, never a quotation of a real record.
    """
    covered = citation_spans
    if not covered:
        return False
    remainder = "".join(
        ch for i, ch in enumerate(span.text, start=span.start)
        if not any(s <= i < e for s, e in covered)
    )
    floor = minimum_chars(span.kind)  # extract_spans' own minimum, not a copy
    return len(normalize(remainder, "aggressive").replace(" ", "")) < floor


def verify_spans(conn: sqlite3.Connection, text: str) -> list[Match]:
    # `parse_citations` yields both families -- `Reference` (surah:ayah) and
    # `HadithReference` (Task 5 of the hadith corpus plan) -- and both are
    # passed through, unfiltered. The Task 5 stopgap that dropped every
    # `HadithReference` here is gone rather than layered under this: it existed
    # only because the conflict check would have read `.surah` off one and
    # crashed, and `_reference_conflicts` now compares kind first and answers
    # the question properly. Keeping both mechanisms would have left the filter
    # quietly suppressing the feature.
    #
    # Nothing here selects which citations a span may see. Attachment is by
    # distance alone (`_nearest_reference_to_span`) and a citation of the wrong
    # kind is a verdict, not an omission.
    parsed = parse_citations(text)
    return [_classify(conn, span, parsed.references) for span in extract_spans(text)
            if not _is_only_a_citation(span, parsed.spans)]
