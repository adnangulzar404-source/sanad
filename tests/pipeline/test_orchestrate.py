from types import SimpleNamespace

import pytest

from sanad.pipeline import orchestrate
from sanad.pipeline.types import (Expansion, RetrievalResult, RetrievalHit,
                                   Selection, SelectedItem, AuditVerdict, GuardResult)


def _deps(**over):
    base = dict(
        expand=lambda q, *, key, client=None: Expansion("en", ["صبر"]),
        retrieve=lambda cc, vc, *, arabic_terms, question, voyage_key, embed_fn=None:
            RetrievalResult([RetrievalHit("quran:2:183", 0.5, True, False)],
                            {"quran": True, "hadith": False}, None, 1),
        select=lambda cc, q, hits, *, key, client=None, feedback=None:
            Selection("Summary.", [SelectedItem("quran:2:183", "Framing.")]),
        guards=lambda sel, cands: [GuardResult("g", True, "")],
        audit=lambda cc, sel, *, key, client=None: AuditVerdict(False, []),
    )
    base.update(over)
    return SimpleNamespace(**base)


def _run(question, deps, risk="GENERAL"):
    import sanad.pipeline.orchestrate as o
    orig_route_risk = o.route_risk
    o.route_risk = lambda t: __import__("sanad.verify.claims", fromlist=["RiskCode"]).RiskCode(risk)
    try:
        return list(orchestrate.run_ask(object(), object(), question,
                                        anthropic_key="a", voyage_key=None, deps=deps))
    finally:
        o.route_risk = orig_route_risk


def test_happy_path_publishes():
    events = _run("How to be patient?", _deps())
    stages = [e.stage for e in events]
    assert stages[0] == "router" and stages[-1] == "final"
    final = events[-1].payload
    assert final["status"] == "published"
    assert final["items"][0]["record_id"] == "quran:2:183"


def test_personal_ruling_stops_after_router():
    events = _run("Can I divorce my wife?", _deps(), risk="PERSONAL_RULING")
    assert [e.stage for e in events] == ["router"]
    assert events[0].payload["requires_handoff"] is True


def test_guard_block_then_clean_retry_publishes():
    calls = {"n": 0}
    def flaky_guards(sel, cands):
        calls["n"] += 1
        return [GuardResult("g", calls["n"] > 1, "bad" if calls["n"] == 1 else "")]
    events = _run("q", _deps(guards=flaky_guards))
    assert events[-1].payload["status"] == "published"
    assert calls["n"] == 2  # retried once

def test_second_failure_abstains():
    events = _run("q", _deps(guards=lambda s, c: [GuardResult("g", False, "bad")]))
    assert events[-1].payload["status"] == "abstained"
    assert events[-1].payload["abstain_reason"]

def test_no_candidates_abstains_with_scope():
    from sanad.corpus.scope import CORPUS_SCOPE
    empty = lambda cc, vc, *, arabic_terms, question, voyage_key, embed_fn=None: \
        RetrievalResult([], {"quran": False, "hadith": False}, "nada", 0)
    events = _run("q", _deps(retrieve=empty))
    p = events[-1].payload
    assert p["status"] == "abstained" and "Sahih al-Bukhari" in p["abstain_reason"]

def test_claude_error_in_expand_abstains_not_raises():
    from sanad.agents.claude_client import ClaudeError
    def boom(q, *, key, client=None): raise ClaudeError("refused")
    events = _run("q", _deps(expand=boom))
    assert events[-1].stage in ("error", "final")
    assert events[-1].payload.get("status") == "abstained" or events[-1].stage == "error"


def test_attempt_zero_on_first_select_call():
    """The retry contract: attempt=0 on the first pass. Captured via adjudicate
    monkeypatch since select's fake deps don't see the attempt number directly."""
    seen_attempts = []
    real_adjudicate = orchestrate.adjudicate

    def spy_adjudicate(*, guard_results, audit, risk_label, attempt):
        seen_attempts.append(attempt)
        return real_adjudicate(guard_results=guard_results, audit=audit,
                                risk_label=risk_label, attempt=attempt)

    orchestrate.adjudicate = spy_adjudicate
    try:
        _run("q", _deps())
    finally:
        orchestrate.adjudicate = real_adjudicate
    assert seen_attempts[0] == 0


def test_feedback_flows_into_retry_select_call():
    """On retry, select_and_frame must receive non-empty feedback derived from
    the first attempt's failures."""
    feedback_seen = []
    calls = {"n": 0}

    def flaky_guards(sel, cands):
        calls["n"] += 1
        return [GuardResult("g", calls["n"] > 1, "specific failure detail"
                             if calls["n"] == 1 else "")]

    def recording_select(cc, q, hits, *, key, client=None, feedback=None):
        feedback_seen.append(feedback)
        return Selection("Summary.", [SelectedItem("quran:2:183", "Framing.")])

    _run("q", _deps(guards=flaky_guards, select=recording_select))
    assert feedback_seen[0] is None
    assert feedback_seen[1]
    assert "specific failure detail" in feedback_seen[1]


def test_persistent_failure_calls_select_at_most_twice():
    """One retry, never more: a persistently-failing selection ABSTAINs after
    exactly one retry — select_and_frame called at most twice."""
    calls = {"n": 0}

    def counting_select(cc, q, hits, *, key, client=None, feedback=None):
        calls["n"] += 1
        return Selection("Summary.", [SelectedItem("quran:2:183", "Framing.")])

    events = _run("q", _deps(select=counting_select,
                             guards=lambda s, c: [GuardResult("g", False, "bad")]))
    assert calls["n"] == 2
    assert events[-1].payload["status"] == "abstained"


def test_fabricated_id_drives_retry_then_abstain_via_real_guards():
    """candidate_ids passed to guards must be the actually-retrieved record_ids,
    so a fabricated (non-retrieved) id is caught by the real guard check."""
    from sanad.pipeline.guards import check as real_check

    events = _run("q", _deps(
        select=lambda cc, q, hits, *, key, client=None, feedback=None:
            Selection("Summary.", [SelectedItem("quran:99:99-fabricated", "Framing.")]),
        guards=real_check,
    ))
    assert events[-1].payload["status"] == "abstained"
    assert events[-1].payload["abstain_reason"]


def test_claude_error_in_select_abstains_and_skips_later_stages():
    """Modeled on test_claude_error_in_expand_abstains_not_raises: select's
    ClaudeError must be caught, mapped to an abstained final, and must NOT
    let guards/audit run on a selection that was never produced."""
    from sanad.agents.claude_client import ClaudeError

    def boom(cc, q, hits, *, key, client=None, feedback=None):
        raise ClaudeError("refused")

    guard_calls, audit_calls = [], []

    def spy_guards(sel, cands):
        guard_calls.append(1)
        return [GuardResult("g", True, "")]

    def spy_audit(cc, sel, *, key, client=None):
        audit_calls.append(1)
        return AuditVerdict(False, [])

    try:
        events = _run("q", _deps(select=boom, guards=spy_guards, audit=spy_audit))
    except ClaudeError:
        pytest.fail("ClaudeError from select escaped run_ask; it must be caught "
                    "and mapped to an abstained outcome, never raised")

    finals = [e for e in events if e.stage == "final"]
    assert finals, "no final event emitted"
    assert finals[-1].payload["status"] == "abstained"
    assert finals[-1].payload["abstain_reason"]
    assert guard_calls == [], "guards must not run after select's ClaudeError"
    assert audit_calls == [], "audit must not run after select's ClaudeError"


def test_claude_error_in_audit_abstains_and_no_exception_escapes():
    """Modeled on test_claude_error_in_expand_abstains_not_raises: audit's
    ClaudeError must be caught, mapped to an abstained final, and must NOT
    let adjudicate run on a verdict that was never produced."""
    from sanad.agents.claude_client import ClaudeError

    def boom(cc, sel, *, key, client=None):
        raise ClaudeError("refused")

    real_adjudicate = orchestrate.adjudicate
    adjudicate_calls = []

    def spy_adjudicate(**kw):
        adjudicate_calls.append(kw)
        return real_adjudicate(**kw)

    orchestrate.adjudicate = spy_adjudicate
    try:
        try:
            events = _run("q", _deps(audit=boom))
        except ClaudeError:
            pytest.fail("ClaudeError from audit escaped run_ask; it must be "
                        "caught and mapped to an abstained outcome, never raised")
    finally:
        orchestrate.adjudicate = real_adjudicate

    finals = [e for e in events if e.stage == "final"]
    assert finals, "no final event emitted"
    assert finals[-1].payload["status"] == "abstained"
    assert finals[-1].payload["abstain_reason"]
    assert adjudicate_calls == [], "adjudicate must not run after audit's ClaudeError"


def test_disputed_risk_relabels_and_still_publishes():
    """Task 11's SSE contract depends on this path: DISPUTED risk with clean
    guards/audit must route through adjudicate's RELABEL_INTERPRETATION
    branch (not PUBLISH, not ABSTAIN) and still land on status="published",
    with risk="DISPUTED" carried through so the frontend can render the
    interpretation caveat off `risk` alone (no separate status string)."""
    from sanad.pipeline.adjudicate import Decision

    real_adjudicate = orchestrate.adjudicate
    decisions = []

    def spy_adjudicate(**kw):
        d = real_adjudicate(**kw)
        decisions.append(d)
        return d

    orchestrate.adjudicate = spy_adjudicate
    try:
        events = _run("Is qunut obligatory according to the four madhhabs?",
                      _deps(), risk="DISPUTED")
    finally:
        orchestrate.adjudicate = real_adjudicate

    assert decisions == [Decision.RELABEL_INTERPRETATION]
    assert events[0].stage == "router"
    assert events[0].payload["requires_handoff"] is False
    assert events[0].payload["risk"] == "DISPUTED"
    final = events[-1]
    assert final.stage == "final"
    assert final.payload["status"] == "published"
    assert final.payload["risk"] == "DISPUTED"


def test_run_helper_restores_route_risk_after_disputed_call():
    """Regression for the `_run` test-helper hazard: `_run` monkeypatches the
    module-level `route_risk` with NO teardown, so it only looked safe
    because every existing test happens to route through `_run` (which
    reassigns the patch fresh each call). Any caller that invokes
    `orchestrate.run_ask` directly — bypassing `_run` — after some other
    test's `_run(..., risk="DISPUTED")` call would silently inherit that
    leaked fake forever, an order-dependence landmine.

    This test manufactures exactly that sequence itself (a DISPUTED `_run`
    call, immediately followed by a DIRECT `run_ask` call) so it proves the
    fix regardless of file/collection order, then asserts the direct call
    sees the REAL router's classification of "Can I divorce my wife?"
    (PERSONAL_RULING, per verify.claims' real _PERSONAL_TOPICS pattern) --
    not a leaked "DISPUTED".

    Before `_run` was changed to restore `route_risk` in a `finally` block,
    this failed: the direct call below observed the leaked fake, saw
    risk="DISPUTED" (requires_handoff=False) instead of the real
    PERSONAL_RULING classification, and so ran straight past the router
    into the rest of the pipeline instead of stopping — `stages` was
    `["router", "expand", "retrieve", "select", "check", "audit", "final"]`
    with `risk == "DISPUTED"`, failing the `== ["router"]` assertion below.
    """
    _run("Some disputed question", _deps(), risk="DISPUTED")

    events = list(orchestrate.run_ask(object(), object(), "Can I divorce my wife?",
                                      anthropic_key="a", voyage_key=None,
                                      deps=_deps()))
    assert [e.stage for e in events] == ["router"], (
        "route_risk leaked from the prior DISPUTED _run() call instead of "
        "being restored -- the real router never got to classify this "
        "question")
    assert events[0].payload["risk"] == "PERSONAL_RULING"
    assert events[0].payload["requires_handoff"] is True


def test_deps_none_resolves_default_deps_without_error():
    """Smoke test for the production wiring path: run_ask(deps=None) must
    resolve to DEFAULT_DEPS, lazily binding the real `retrieve` function via
    _bind_retrieve, rather than crashing on a None dep. Routed through the
    PERSONAL_RULING handoff path (via _run's usual route_risk monkeypatch, so
    this is decoupled from the real claim-detection regexes) so it returns
    right after the router stage before any dep is actually called — hermetic
    (no network, no keys) while still exercising the deps=None -> DEFAULT_DEPS
    resolution line for real."""
    events = _run("q", None, risk="PERSONAL_RULING")
    assert [e.stage for e in events] == ["router"]
    assert events[0].payload["requires_handoff"] is True

    # The wiring shape: DEFAULT_DEPS now holds the real production stages.
    assert orchestrate.DEFAULT_DEPS.expand is orchestrate._expand.expand_query
    assert orchestrate.DEFAULT_DEPS.select is orchestrate._select.select_and_frame
    assert orchestrate.DEFAULT_DEPS.guards is orchestrate._guards.check
    assert orchestrate.DEFAULT_DEPS.audit is orchestrate._audit.audit_brief
    assert orchestrate.DEFAULT_DEPS.retrieve is not None


def test_auditor_not_given_expansion_or_selection_reasoning():
    """Auditor isolation: orchestrator must not pass expansion/selection
    reasoning objects into audit — only corpus_conn, selection, key, client."""
    audit_call_args = []

    def recording_audit(cc, sel, *, key, client=None):
        audit_call_args.append((cc, sel, key, client))
        return AuditVerdict(False, [])

    _run("q", _deps(audit=recording_audit))
    assert len(audit_call_args) == 1
    cc, sel, key, client = audit_call_args[0]
    assert isinstance(sel, Selection)
    assert key == "a"
