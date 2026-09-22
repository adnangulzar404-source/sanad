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
    # its own chain and often its own variant wording. Stored and displayed,
    # never scored and never indexed -- for the same reason as isnad_ar, and
    # measured: leaving them in text_ar was a median 40% of the stored string
    # on the 155 records that carry one, and dropped them out of reach of the
    # 0.86 threshold.
    addenda_ar: str | None = None
