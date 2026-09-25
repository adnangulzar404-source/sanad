from types import SimpleNamespace

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
    o.route_risk = lambda t: __import__("sanad.verify.claims", fromlist=["RiskCode"]).RiskCode(risk)
    return list(orchestrate.run_ask(object(), object(), question,
                                    anthropic_key="a", voyage_key=None, deps=deps))


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
