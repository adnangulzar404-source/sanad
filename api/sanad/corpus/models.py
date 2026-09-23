from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    title: str
    publisher: str | None
    edition: str | None
    url: str
    license_id: str
    license_url: str | None
    attribution: str
    retrieved_at: str
    upstream_sha256: str
    modifications: str


@dataclass(frozen=True)
class Record:
    id: str
    source_id: str
    kind: str
    text_ar: str
    text_ar_sha256: str
    norm_light: str
    norm_standard: str
    norm_aggressive: str
    reference_display: str
    surah: int | None = None
    ayah: int | None = None
    surah_name_ar: str | None = None
    surah_name_en: str | None = None
    collection: str | None = None
    book_no: int | None = None
    chapter_ar: str | None = None
    hadith_no: str | None = None
    numbering_scheme: str | None = None
    # The Bismillah, where Tanzil's XML export models it as verse metadata
    # rather than text prepended to the following ayah. A record must be
    # self-describing: the UI must not hardcode which surahs open with it.
    bismillah: str | None = None
    # The narrator chain, for hadith records. Stored but never scored: see the
    # Stage A2 spec §7. Scoring across isnad + matn puts a short, famous matn
    # near 0.13 against a 0.86 threshold.
    isnad_ar: str | None = None
    # Further narrations the edition appends after the primary matn, each with
    # its own chain and often its own variant wording. Never part of THIS
    # record's scored text -- leaving them in text_ar was a median 40% of the
    # stored string on the records that carry one, and dropped a quotation of
    # the Prophet's words alone out of reach of the 0.86 threshold.
    #
    # They are not out of the scored corpus, though: `text_ar + " " +
    # addenda_ar` is stored as this record's SECOND representation, in
    # `record_variants`, and is indexed and scored alongside the primary. See
    # `RecordVariant` for why. Also displayed -- `api.schemas.RecordOut`.
    addenda_ar: str | None = None
    # Why this record's PRIMARY text -- `text_ar`, and only `text_ar` -- is
    # not an independently quotable text, or None.
    # Where a narration repeats one already given in full, the al-Bugha
    # edition prints a pointer -- "bi-hadha", "mithlahu", "nahwahu" -- in
    # place of the matn. Those strings are everyday Arabic, and scoring them
    # made Sanad answer a commonplace with EXACT 1.0 and a Bukhari citation.
    # A record with a reason here keeps its id, its text and its citation and
    # stays reachable by reference lookup; its primary is simply never a
    # match candidate -- excluded from the FTS index (see `rebuild_fts`) and
    # from the exact-tier lookup (see `verify.engine._exact_at_tier`). The
    # list of 17 is an audit of the pinned edition; see
    # `openiti._UNSCORABLE`.
    #
    # THE SCOPE IS THE PRIMARY, NOT THE RECORD. The audit pins the sha256 of
    # one specific string and classifies that string; the full printed text
    # is a different string and was never judged. Applying the judgement to
    # both took hadith 237's 869-character narration -- the longest addendum
    # in this edition, and an ordinary quotable hadith -- out of the corpus
    # because of a ruling about the 40-character chain-transfer fragment
    # printed in front of it. See `RecordVariant`.
    unscorable_reason: str | None = None


# The name of the one representation that is NOT stored in `record_variants`:
# `records.text_ar` itself. Written into `records_fts.variant` so every index
# row says which representation it came from, and so a `record_variants` row
# can never collide with the primary.
PRIMARY_VARIANT = "primary"
# The primary matn with its appended addenda rejoined: the hadith exactly as
# the edition prints it, minus the isnad.
FULL_VARIANT = "full"


@dataclass(frozen=True)
class RecordVariant:
    """A second scorable form of a record's text, beyond `Record.text_ar`.

    The problem this exists for: the secondary-narration cut decides where a
    hadith's primary matn ends and the edition's further narrations begin, and
    that decision is a heuristic reading of an edition which marks the
    boundary inconsistently. Three rounds of work on that heuristic each left
    records cut in the wrong place -- 342 and 3164, the Isra'/Mi'raj, were cut
    in the middle of one continuous narration -- and every wrong cut cost a
    verification, because only one side of the cut was ever scored.

    Indexing BOTH sides removes the dependence on the cut being right. A
    record with an addendum is scored twice: once as its primary matn (so a
    quotation of just the Prophet's words verifies) and once as the full
    printed text (so a quotation of the hadith as the edition prints it
    verifies). An over-cut and an under-cut then both stop costing a
    verification, which is the only way this stops being a recurring defect.

    Only the ADDITIONAL representations live here; the primary stays in
    `records`, so there is exactly one copy of it and no second place for it
    to drift. A match on any representation yields the same record and the
    same `reference_display`, and a record is reported at most once no matter
    how many of its representations tie -- see `verify.engine._exact_at_tier`
    and `_best_fuzzy`.

    A record with an `unscorable_reason` still gets a row here. That reason
    is a judgement about its primary matn and carries no verdict on the full
    printed text -- 237 is the one record where the two differ, and the
    difference is 869 characters of narration.
    """

    record_id: str
    variant: str
    text_ar: str
    norm_light: str
    norm_standard: str
    norm_aggressive: str


@dataclass(frozen=True)
class Candidate:
    """One indexed representation, paired with the record that owns it.

    `db.fts_candidates` returns these rather than bare `Record`s because the
    fuzzy layer has to score the text that was actually indexed: scoring a
    full-text hit against the record's primary `norm_aggressive` would report
    a similarity the index never found.
    """

    record: Record
    variant: str
    text_ar: str
    norm_aggressive: str
