from sanad.agents import audit
from sanad.pipeline.types import Selection, SelectedItem, AuditVerdict

class _Rec:
    def __init__(self, rid, text): self.id, self.reference_display, self.text_ar = rid, rid, text

def test_audit_parses_verdict(monkeypatch):
    monkeypatch.setattr(audit.db, "get_record",
                        lambda c, rid: _Rec(rid, "arabic"))
    captured = {}
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        # auditor must NOT receive stage-3 reasoning; only brief + evidence
        captured["system_blocks"] = system_blocks
        captured["user_text"] = user_text
        return {"overreach": False, "flags": []}
    monkeypatch.setattr(audit.claude_client, "call_structured", fake)
    sel = Selection("summary", [SelectedItem("quran:2:183", "framing")])
    v = audit.audit_brief(object(), sel, key="k")
    assert isinstance(v, AuditVerdict) and v.overreach is False
    # Fresh-context isolation: only the auditor's own system prompt goes out
    # (no cached stage-3 evidence/reasoning block), and the user text carries
    # only the brief's summary/framings and the record text beneath them --
    # no expansion query, search terms, or select-stage prompt/rationale.
    assert captured["system_blocks"] == [{"type": "text", "text": audit.AUDIT_SYSTEM}]
    assert "summary" in captured["user_text"].lower()
    assert "framing" in captured["user_text"].lower()
    for leaked in ("search_terms", "question_language", "expansion", "candidate set"):
        assert leaked not in captured["user_text"].lower()

def test_audit_reports_overreach(monkeypatch):
    monkeypatch.setattr(audit.db, "get_record", lambda c, rid: _Rec(rid, "x"))
    monkeypatch.setattr(audit.claude_client, "call_structured",
        lambda **kw: {"overreach": True, "flags": ["framing misrepresents ayah"]})
    v = audit.audit_brief(object(), Selection("s", [SelectedItem("quran:2:183","f")]), key="k")
    assert v.overreach is True and v.flags
