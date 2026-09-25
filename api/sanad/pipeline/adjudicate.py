"""Stage 6 of the Ask pipeline: deterministic adjudication (spec §2, §6).

Purely a function of its inputs -- no I/O, no Claude call. Combines the
guard results (stage 4, deterministic) and the audit verdict (stage 5,
fresh-context Claude) into one of four outcomes. The table is exhaustive:
every reachable combination of (guards blocked?, audit overreach?,
risk_label, attempt) maps to exactly one Decision, with no implicit
fall-through.

Decision table:
  guards blocked                          -> RETRY (attempt 0) / ABSTAIN (attempt 1)
  guards pass, audit overreach            -> RETRY (attempt 0) / ABSTAIN (attempt 1)
  guards pass, audit clean, DISPUTED risk -> RELABEL_INTERPRETATION
  guards pass, audit clean, otherwise     -> PUBLISH
"""
from __future__ import annotations

from enum import Enum

from .types import AuditVerdict, GuardResult


class Decision(str, Enum):
    PUBLISH = "PUBLISH"
    RELABEL_INTERPRETATION = "RELABEL_INTERPRETATION"
    RETRY = "RETRY"
    ABSTAIN = "ABSTAIN"


def adjudicate(*, guard_results: list[GuardResult], audit: AuditVerdict | None,
               risk_label: str, attempt: int) -> Decision:
    guards_blocked = not all(g.passed for g in guard_results)
    overreached = audit is not None and audit.overreach
    if guards_blocked or overreached:
        return Decision.RETRY if attempt == 0 else Decision.ABSTAIN
    if risk_label == "DISPUTED":
        return Decision.RELABEL_INTERPRETATION
    return Decision.PUBLISH
