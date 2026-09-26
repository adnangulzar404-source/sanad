# api/sanad/pipeline/types.py — the shared vocabulary across pipeline stages.
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievalHit:
    record_id: str
    rrf_score: float
    in_fts: bool
    in_vector: bool

@dataclass(frozen=True)
class RetrievalResult:
    hits: list[RetrievalHit]              # fused, truncated to RETRIEVAL_TOP_K, best first
    reached: dict[str, bool]              # {"quran": bool, "hadith": bool}
    unreached_reason: str | None
    candidate_count: int

@dataclass(frozen=True)
class Expansion:
    question_language: str                # ISO 639-1
    search_terms: list[str]               # Arabic surface forms, multiple per concept

@dataclass(frozen=True)
class SelectedItem:
    record_id: str
    framing: str

@dataclass(frozen=True)
class Selection:
    summary: str
    items: list[SelectedItem]

@dataclass(frozen=True)
class GuardResult:
    name: str
    passed: bool
    detail: str

@dataclass(frozen=True)
class AuditVerdict:
    overreach: bool
    flags: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class StageEvent:
    stage: str                            # "router"|"expand"|"retrieve"|"select"|"check"|"audit"|"final"|"error"
    payload: dict
