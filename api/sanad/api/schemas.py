from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class VerifyRequest(BaseModel):
    text: str = Field(..., max_length=50_000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class RecordOut(BaseModel):
    id: str
    reference_display: str
    text_ar: str
    text_ar_sha256: str
    surah: int | None = None
    ayah: int | None = None
    # Display-only English translation (Tanzil's en.pickthall, public domain).
    # Verification never reads this -- it is Arabic-against-Arabic only. When
    # present, `translation_disclaimer` is always populated alongside it: per
    # Tanzil's own terms, the accuracy disclaimer must accompany every
    # rendered translation, not live in a licence file no one reads.
    translation_en: str | None = None
    translation_disclaimer: str | None = None
    # The further narrations the edition appends after the primary matn, for
    # hadith records that carry them. `text_ar` is the primary matn alone, so
    # without this field the response silently holds back part of the printed
    # hadith -- and the corpus does score the two rejoined (see
    # `corpus.models.RecordVariant`), so a quotation can match text that had
    # no way of reaching the client. None for every Qur'anic record.
    addenda_ar: str | None = None
    # Why this record is never a match candidate, or None. A client showing a
    # record reached by reference lookup needs to be able to say why Sanad
    # will not verify a quotation of it; the explanation used to stop at the
    # database. None for all but 17 records.
    unscorable_reason: str | None = None
    # The narrator chain, for hadith records. Display-only, exactly like
    # `addenda_ar` above -- see `corpus.models.Record.isnad_ar` for why it is
    # stored but never scored. None for every Qur'anic record. Note what this
    # is NOT: an isnad names who transmitted a text, not whether anyone has
    # graded that transmission sound. Sanad ships no gradings, so a client
    # rendering this field must not present it as an authenticity verdict.
    isnad_ar: str | None = None
    # "bukhari" for every hadith record, None for every ayah. Lets a client
    # distinguish the two kinds of match without parsing `id` or
    # `reference_display` -- a fragile substitute for a field the record
    # already carries.
    collection: str | None = None
    # The edition's own hadith number, e.g. "1". None for ayat, which are
    # addressed by surah:ayah instead -- see `surah`/`ayah` above.
    hadith_no: str | None = None


class QuotationOut(BaseModel):
    quoted_text: str
    start: int
    end: int
    verdict: str
    tier: str | None
    score: float
    record: RecordOut | None
    # Other records carrying identical text at the matched tier (e.g.
    # Ar-Rahman's refrain, repeated 31 times), beyond `record`. See
    # `verify.engine.Match.also_at`.
    also_at: list[str] = Field(default_factory=list)
    # Ayat whose own text CONTAINS this quotation, when the quotation is
    # answered with a hadith, or withheld from being one. It is therefore
    # populated even when `record` is null: a client that prints nothing in
    # that case drops the only thing telling the reader their words are
    # scripture. Split out of `also_at` (R46) -- see
    # `verify.engine.Match.contained_in`.
    contained_in: list[str] = Field(default_factory=list)
    given_reference: str | None
    diff: list[tuple[str, str]] | None


class ClaimOut(BaseModel):
    kind: str
    label: str
    note: str


class VerifyResponse(BaseModel):
    quotations: list[QuotationOut]
    claims: list[ClaimOut]
    risk: str
    requires_handoff: bool
    overall: str
    # This corpus contains the Qur'an and Sahih al-Bukhari, and nothing else.
    # Carried on every response so a NOT_FOUND verdict is never read as "this
    # quotation is fabricated" -- absence from this corpus proves nothing
    # about a quotation that might be genuine Sahih Muslim, one of the four
    # Sunan, tafsir, or scholarly text this corpus does not hold.
    corpus_scope: str


class CorpusSourceOut(BaseModel):
    """One row of `sources` -- mirrors its columns exactly (see
    `corpus.schema.AUDIT_SCHEMA_SQL`'s sibling, the corpus schema's `sources`
    table). This is the provenance panel's data: license, attribution, and
    the verbatim Tanzil notice. A field added to the table but not here would
    be silently dropped from every API response that lists sources -- the
    same "two things meant to agree, quietly diverging" failure this project
    keeps hitting, just moved into the response layer instead of the client.
    """

    id: str
    kind: str
    title: str
    publisher: str | None = None
    edition: str | None = None
    url: str
    license_id: str
    license_url: str | None = None
    attribution: str
    retrieved_at: str
    upstream_sha256: str
    modifications: str


class CorpusStatsOut(BaseModel):
    records: int
    sources: int
    translations: int


class CorpusResponse(BaseModel):
    db_sha256: str
    db_path: str
    stats: CorpusStatsOut
    scope: str
    sources: list[CorpusSourceOut]


class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v


class ReachedOut(BaseModel):
    quran: bool
    hadith: bool


class AskItemOut(BaseModel):
    record_id: str
    framing: str
    record: RecordOut | None = None


class AskFinalOut(BaseModel):
    status: str                       # "published" | "abstained"
    question_language: str | None = None
    summary: str | None = None
    items: list[AskItemOut] = Field(default_factory=list)
    reached: ReachedOut
    unreached_reason: str | None = None
    risk: str
    requires_handoff: bool = False
    abstain_reason: str | None = None
    corpus_scope: str


class RecordDetailOut(BaseModel):
    """`GET /api/records/{id}`'s full response -- a superset of `RecordOut`
    (which is what `QuotationOut.record` embeds). This endpoint additionally
    surfaces the surah's bilingual name and the full source record, so it
    gets its own model rather than reusing `RecordOut`.
    """

    id: str
    reference_display: str
    text_ar: str
    text_ar_sha256: str
    surah: int | None = None
    ayah: int | None = None
    surah_name_ar: str | None = None
    surah_name_en: str | None = None
    translation_en: str | None = None
    translation_disclaimer: str | None = None
    # Present for the same reason as on `RecordOut`, and kept in step with it
    # deliberately: this model is documented as a superset, and a field that
    # exists on one and not the other is the "two things meant to agree,
    # quietly diverging" failure this project keeps hitting.
    addenda_ar: str | None = None
    unscorable_reason: str | None = None
    isnad_ar: str | None = None
    collection: str | None = None
    hadith_no: str | None = None
    source: CorpusSourceOut | None = None
