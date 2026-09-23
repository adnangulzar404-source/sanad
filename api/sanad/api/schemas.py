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


class QuotationOut(BaseModel):
    quoted_text: str
    start: int
    end: int
    verdict: str
    tier: str | None
    score: float
    record: RecordOut | None
    # Other record ids carrying identical text at the matched tier (e.g.
    # Ar-Rahman's refrain, repeated 31 times). Empty for the overwhelming
    # majority of verses, which are unique. See `verify.engine.Match.also_at`.
    also_at: list[str] = Field(default_factory=list)
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
    # This corpus contains the Qur'an only. Carried on every response so a
    # NOT_FOUND verdict is never read as "this quotation is fabricated" --
    # absence from a Qur'an-only corpus proves nothing about a quotation that
    # might be genuine Hadith, tafsir, or scholarly text Stage A does not hold.
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
    source: CorpusSourceOut | None = None
