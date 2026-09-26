from types import SimpleNamespace

import pytest

from sanad.pipeline import orchestrate
from sanad.pipeline.guards import contains_arabic
from sanad.pipeline.types import (Expansion, RetrievalResult, RetrievalHit,
                                   Selection, SelectedItem, AuditVerdict, GuardResult)


def _walk_strings(obj):
    """Yield every string leaf inside a StageEvent payload (dict/list/tuple
    of arbitrary depth), so a leak check doesn't have to know each payload's
    exact shape."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_strings(v)


def _assert_no_leak(events, secret=None):
    """The unifying guarantee under final review: no streamed StageEvent may
    carry model-originated Arabic PROSE (a framing, a summary, an audit
    flag, a guard detail), and no streamed StageEvent may carry a
    provider's raw error text. Checks every string in every event's
    payload -- not just the one field a given ruling named -- so this
    catches a leak in a field nobody thought to look at.

    Deliberate exception: the `expand` stage's `search_terms` are Arabic BY
    DESIGN (spec stage 1 -- multiple Arabic surface forms for the lexical
    index) and are explicitly part of the brief's `expand` StageEvent
    schema, untouched by and unrelated to this review's C1/I1/M2 findings
    (which are about prose presented as evidence, audit flags, and error
    text -- never about the search keys used to retrieve candidates). Any
    OTHER stage carrying Arabic is exactly the bug this review found.
    """
    for e in events:
        if e.stage == "expand":
            continue
        for s in _walk_strings(e.payload):
            assert not contains_arabic(s), (
                f"Arabic leaked into a streamed '{e.stage}' event: {s!r}")
            if secret is not None:
                assert secret not in s, (
                    f"secret leaked into a streamed '{e.stage}' event: {s!r}")


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


# =====================================================================
# Final-review fix -- Critical C1 (select emitted before guards.check ran),
# Important I1 (raw provider error text in an `error` StageEvent), Medium
# M2 (unscrubbed Arabic in an `audit` StageEvent's `flags`). The unifying
# guarantee: no streamed StageEvent may carry model-originated Arabic, and
# no streamed StageEvent may carry a provider's raw error text. Each test
# below drives a DIFFERENT overall outcome (happy publish, guard-fail then
# retry, persistent-failure abstain, each of the three error paths) and
# scans EVERY event's payload with `_assert_no_leak`, not just the one
# field a given ruling named.
# =====================================================================

def test_arabic_in_framing_never_streamed_across_guard_fail_then_retry_publish():
    """Ruling C1. Uses the REAL guards.check (not a fake) so
    no_arabic_in_prose actually fires on attempt 0's Arabic framing; a clean
    attempt 1 then publishes -- proving the leak check holds across both the
    guard-fail/retry step and the eventual happy-publish outcome of the same
    run, and that the redacted attempt-0 `select` event carried no prose."""
    from sanad.pipeline.guards import check as real_check

    calls = {"n": 0}

    def flaky_select(cc, q, hits, *, key, client=None, feedback=None):
        calls["n"] += 1
        framing = "It reads كتب عليكم." if calls["n"] == 1 else "Clean framing."
        return Selection("Summary.", [SelectedItem("quran:2:183", framing)])

    events = _run("q", _deps(select=flaky_select, guards=real_check))
    assert calls["n"] == 2  # the Arabic framing drove exactly one retry
    assert events[-1].payload["status"] == "published"

    select_events = [e for e in events if e.stage == "select"]
    assert len(select_events) == 2
    assert select_events[0].payload == {"status": "rejected"}  # attempt 0: redacted
    assert "framing" not in str(select_events[0].payload)
    _assert_no_leak(events)


def test_arabic_in_framing_never_streamed_when_persistent_abstains():
    """Ruling C1, the abstain outcome: Arabic in the framing on BOTH
    attempts (the real guards.check fails it every time) must still never
    reach any streamed event, all the way to the final abstain."""
    from sanad.pipeline.guards import check as real_check

    def always_arabic_select(cc, q, hits, *, key, client=None, feedback=None):
        return Selection("Summary.", [SelectedItem("quran:2:183", "It reads كتب عليكم.")])

    events = _run("q", _deps(select=always_arabic_select, guards=real_check))
    assert events[-1].payload["status"] == "abstained"
    select_events = [e for e in events if e.stage == "select"]
    assert len(select_events) == 2
    assert all(e.payload == {"status": "rejected"} for e in select_events)
    _assert_no_leak(events)


def test_arabic_in_audit_flag_never_streamed_on_publish():
    """Ruling M2, the happy-publish outcome: a clean (non-overreaching)
    audit verdict can still carry an Arabic-script flag -- nothing about
    `overreach=False` guarantees the model wrote its flags in English."""
    def audit_with_arabic_flag(cc, sel, *, key, client=None):
        return AuditVerdict(False, ["فحص جيد", "looks fine overall"])

    events = _run("q", _deps(audit=audit_with_arabic_flag))
    assert events[-1].payload["status"] == "published"
    audit_events = [e for e in events if e.stage == "audit"]
    assert len(audit_events) == 1
    assert "فحص جيد" not in audit_events[0].payload["flags"]
    assert "looks fine overall" in audit_events[0].payload["flags"]  # non-Arabic flag preserved
    _assert_no_leak(events)


def test_arabic_in_audit_flag_never_streamed_across_retry_then_abstain():
    """Ruling M2, the retry-then-abstain outcome: a persistently
    overreaching audit verdict (driving RETRY then ABSTAIN) with an
    Arabic-script flag on every attempt must never leak it."""
    def always_overreaching_audit(cc, sel, *, key, client=None):
        return AuditVerdict(True, ["تجاوز واضح", "overreach detected"])

    events = _run("q", _deps(audit=always_overreaching_audit))
    assert events[-1].payload["status"] == "abstained"
    audit_events = [e for e in events if e.stage == "audit"]
    assert len(audit_events) == 2
    for e in audit_events:
        assert "تجاوز واضح" not in e.payload["flags"]
    _assert_no_leak(events)


def test_provider_secret_never_streamed_on_expand_failure():
    """Ruling I1, expand_failed. A ClaudeError's message can carry a
    provider's raw response text; the streamed `error` event must carry
    only the fixed generic message, and the SECRET must not appear anywhere
    in the stream, though it's fine (expected) that `code` stays informative."""
    from sanad.agents.claude_client import ClaudeError

    SECRET = "sk-ant-super-secret-leak-marker-should-never-stream"

    def boom(q, *, key, client=None):
        raise ClaudeError(f"transport failed, response body: {SECRET}")

    events = _run("q", _deps(expand=boom))
    assert events[-1].payload["status"] == "abstained"
    error_events = [e for e in events if e.stage == "error"]
    assert len(error_events) == 1
    assert error_events[0].payload["code"] == "expand_failed"
    assert error_events[0].payload["message"] == orchestrate._CLIENT_STAGE_ERROR_MESSAGE
    _assert_no_leak(events, secret=SECRET)


def test_provider_secret_never_streamed_on_select_failure():
    """Ruling I1, select_failed."""
    from sanad.agents.claude_client import ClaudeError

    SECRET = "sk-ant-super-secret-leak-marker-should-never-stream"

    def boom(cc, q, hits, *, key, client=None, feedback=None):
        raise ClaudeError(f"transport failed, response body: {SECRET}")

    events = _run("q", _deps(select=boom))
    assert events[-1].payload["status"] == "abstained"
    error_events = [e for e in events if e.stage == "error"]
    assert len(error_events) == 1
    assert error_events[0].payload["code"] == "select_failed"
    assert error_events[0].payload["message"] == orchestrate._CLIENT_STAGE_ERROR_MESSAGE
    _assert_no_leak(events, secret=SECRET)


def test_provider_secret_never_streamed_on_audit_failure():
    """Ruling I1, audit_failed."""
    from sanad.agents.claude_client import ClaudeError

    SECRET = "sk-ant-super-secret-leak-marker-should-never-stream"

    def boom(cc, sel, *, key, client=None):
        raise ClaudeError(f"transport failed, response body: {SECRET}")

    events = _run("q", _deps(audit=boom))
    assert events[-1].payload["status"] == "abstained"
    error_events = [e for e in events if e.stage == "error"]
    assert len(error_events) == 1
    assert error_events[0].payload["code"] == "audit_failed"
    assert error_events[0].payload["message"] == orchestrate._CLIENT_STAGE_ERROR_MESSAGE
    _assert_no_leak(events, secret=SECRET)
