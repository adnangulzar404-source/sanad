# api/sanad/pipeline/orchestrate.py — Task 10: pipeline orchestration.
#
# Wires the seven stages (router, expand, retrieve, select, check, audit,
# adjudicate) into one runnable generator with a single retry. Every stage
# body already exists and is tested elsewhere in this tree; this module only
# composes the calls, in the order and with the short-circuits spec §2 and
# the task-10 brief specify. It never talks to Claude/Voyage directly — all
# model-backed and network-backed work goes through `deps`, so tests inject
# fakes and production wiring binds the real functions via DEFAULT_DEPS.
from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

from ..agents import audit as _audit
from ..agents import expand as _expand
from ..agents import select as _select
from ..agents.claude_client import ClaudeError
from ..corpus.scope import CORPUS_SCOPE
from ..verify.claims import RiskCode, requires_handoff, route_risk
from . import guards as _guards
from .adjudicate import Decision, adjudicate
from .types import StageEvent

DEFAULT_DEPS = SimpleNamespace(
    expand=_expand.expand_query,
    retrieve=None,   # bound below to avoid an import cycle at module import
    select=_select.select_and_frame,
    guards=_guards.check,
    audit=_audit.audit_brief,
)


def _bind_retrieve():
    from ..retrieve.retrieve import retrieve
    DEFAULT_DEPS.retrieve = retrieve
    return DEFAULT_DEPS


def _feedback(guard_results, audit) -> str:
    parts = [g.detail for g in guard_results if not g.passed and g.detail]
    if audit is not None and audit.overreach:
        parts.extend(audit.flags)
    return "; ".join(parts) or "The brief was rejected; be more conservative."


def _final(*, status, question_language, summary, items, reached,
           unreached_reason, risk, abstain_reason=None):
    return StageEvent("final", {
        "status": status,
        "question_language": question_language,
        "summary": summary,
        "items": items,                 # [{record_id, framing}] — route renders records
        "reached": reached,
        "unreached_reason": unreached_reason,
        "risk": risk,
        "requires_handoff": False,
        "abstain_reason": abstain_reason,
    })


def run_ask(corpus_conn, vectors_conn, question, *, anthropic_key,
            voyage_key, deps=None) -> Iterator[StageEvent]:
    deps = deps or (DEFAULT_DEPS if DEFAULT_DEPS.retrieve else _bind_retrieve())

    risk = route_risk(question)
    if requires_handoff(risk):
        yield StageEvent("router", {"risk": risk.value, "requires_handoff": True,
                                    "corpus_scope": CORPUS_SCOPE})
        return
    yield StageEvent("router", {"risk": risk.value, "requires_handoff": False})

    try:
        expansion = deps.expand(question, key=anthropic_key)
    except ClaudeError as exc:
        yield StageEvent("error", {"code": "expand_failed", "message": str(exc)})
        yield _final(status="abstained", question_language=None, summary=None,
                     items=[], reached={"quran": False, "hadith": False},
                     unreached_reason=None, risk=risk.value,
                     abstain_reason="Query expansion was unavailable.")
        return
    yield StageEvent("expand", {"question_language": expansion.question_language,
                                "search_terms": expansion.search_terms})

    result = deps.retrieve(corpus_conn, vectors_conn,
                           arabic_terms=expansion.search_terms, question=question,
                           voyage_key=voyage_key)
    yield StageEvent("retrieve", {"candidate_count": result.candidate_count,
                                  "reached": result.reached,
                                  "unreached_reason": result.unreached_reason})
    if not result.hits:
        yield _final(status="abstained",
                     question_language=expansion.question_language, summary=None,
                     items=[], reached=result.reached,
                     unreached_reason=result.unreached_reason, risk=risk.value,
                     abstain_reason=CORPUS_SCOPE)
        return

    # candidate_ids is the set of record_ids actually retrieved (spec §5): this
    # is what guards.check uses to catch a fabricated/non-retrieved citation.
    candidate_ids = {h.record_id for h in result.hits}
    feedback = None
    for attempt in (0, 1):  # 0-indexed: 0 = first pass, 1 = the single retry.
        try:
            selection = deps.select(corpus_conn, question, result.hits,
                                    key=anthropic_key, feedback=feedback)
        except ClaudeError as exc:
            yield StageEvent("error", {"code": "select_failed", "message": str(exc)})
            yield _final(status="abstained",
                         question_language=expansion.question_language, summary=None,
                         items=[], reached=result.reached,
                         unreached_reason=result.unreached_reason, risk=risk.value,
                         abstain_reason="The brief could not be generated.")
            return
        yield StageEvent("select", {
            "summary": selection.summary,
            "items": [{"record_id": i.record_id, "framing": i.framing}
                      for i in selection.items]})

        guard_results = deps.guards(selection, candidate_ids)
        yield StageEvent("check", {"guards": [
            {"name": g.name, "pass": g.passed, "detail": g.detail}
            for g in guard_results]})

        audit = None
        if all(g.passed for g in guard_results):
            # Auditor isolation (spec §2 stage 5): only corpus_conn + the
            # drafted selection go in. Never expansion, never stage-3
            # reasoning/feedback — a fresh-context review is the point.
            try:
                audit = deps.audit(corpus_conn, selection, key=anthropic_key)
            except ClaudeError as exc:
                yield StageEvent("error", {"code": "audit_failed", "message": str(exc)})
                yield _final(status="abstained",
                             question_language=expansion.question_language,
                             summary=None, items=[], reached=result.reached,
                             unreached_reason=result.unreached_reason,
                             risk=risk.value,
                             abstain_reason="The brief could not be reviewed.")
                return
            yield StageEvent("audit", {"overreach": audit.overreach,
                                       "flags": audit.flags})

        # Contract: attempt is 0-indexed — 0 on the first pass, 1 on the
        # single retry. adjudicate() treats attempt==0 as first-try and any
        # non-zero attempt as already-retried, so a second RETRY verdict
        # resolves to ABSTAIN rather than looping. This loop MUST pass 0
        # then 1, in that order, exactly once each.
        decision = adjudicate(guard_results=guard_results, audit=audit,
                              risk_label=risk.value, attempt=attempt)
        if decision in (Decision.PUBLISH, Decision.RELABEL_INTERPRETATION):
            # RELABEL_INTERPRETATION still publishes; the DISPUTED label
            # already carried in `risk` is what tells the frontend to render
            # the interpretation caveat (see brief's note on this).
            status = "published"
            yield _final(status=status,
                         question_language=expansion.question_language,
                         summary=selection.summary,
                         items=[{"record_id": i.record_id, "framing": i.framing}
                                for i in selection.items],
                         reached=result.reached,
                         unreached_reason=result.unreached_reason, risk=risk.value)
            return
        if decision is Decision.ABSTAIN:
            break
        feedback = _feedback(guard_results, audit)  # RETRY: feeds attempt 1's select call

    yield _final(status="abstained", question_language=expansion.question_language,
                 summary=None, items=[], reached=result.reached,
                 unreached_reason=result.unreached_reason, risk=risk.value,
                 abstain_reason="The brief did not pass review after one retry.")
