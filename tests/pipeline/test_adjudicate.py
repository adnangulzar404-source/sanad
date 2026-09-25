from sanad.pipeline.adjudicate import adjudicate, Decision
from sanad.pipeline.types import GuardResult, AuditVerdict

def _guards(passed): return [GuardResult("g", passed, "")]

def test_guard_block_retries_then_abstains():
    assert adjudicate(guard_results=_guards(False), audit=None,
                      risk_label="GENERAL", attempt=0) is Decision.RETRY
    assert adjudicate(guard_results=_guards(False), audit=None,
                      risk_label="GENERAL", attempt=1) is Decision.ABSTAIN

def test_audit_overreach_retries_then_abstains():
    ov = AuditVerdict(overreach=True, flags=["x"])
    assert adjudicate(guard_results=_guards(True), audit=ov,
                      risk_label="GENERAL", attempt=0) is Decision.RETRY
    assert adjudicate(guard_results=_guards(True), audit=ov,
                      risk_label="GENERAL", attempt=1) is Decision.ABSTAIN

def test_clean_general_publishes():
    clean = AuditVerdict(overreach=False, flags=[])
    assert adjudicate(guard_results=_guards(True), audit=clean,
                      risk_label="GENERAL", attempt=0) is Decision.PUBLISH

def test_clean_disputed_relabels():
    clean = AuditVerdict(overreach=False, flags=[])
    assert adjudicate(guard_results=_guards(True), audit=clean,
                      risk_label="DISPUTED", attempt=0) is Decision.RELABEL_INTERPRETATION
