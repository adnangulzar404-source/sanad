from sanad.agents import select
from sanad.pipeline.types import RetrievalHit, Selection

class _Rec:
    def __init__(self, rid, ref, text): self.id, self.reference_display, self.text_ar = rid, ref, text

def _conn_with(records):
    class C:
        def __init__(self, m): self.m = m
    import sanad.agents.select as s
    return records  # helper replaced via monkeypatch below

def test_select_builds_cached_evidence_and_parses(monkeypatch):
    recs = {"quran:2:183": _Rec("quran:2:183", "Al-Baqarah 2:183", "كتب عليكم الصيام")}
    monkeypatch.setattr(select.db, "get_record", lambda c, rid: recs.get(rid))
    captured = {}
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        captured["blocks"] = system_blocks
        return {"summary": "These verses address fasting.",
                "items": [{"record_id": "quran:2:183",
                           "framing": "Fasting is prescribed, as it was for those before."}]}
    monkeypatch.setattr(select.claude_client, "call_structured", fake)
    hits = [RetrievalHit("quran:2:183", 0.5, True, False)]
    out = select.select_and_frame(object(), "fasting?", hits, key="k")
    assert isinstance(out, Selection)
    assert out.items[0].record_id == "quran:2:183"
    # evidence block is a cached system block
    assert any(b.get("cache_control") for b in captured["blocks"])
    assert "quran:2:183" in captured["blocks"][-1]["text"]

def test_retry_feedback_reaches_the_prompt(monkeypatch):
    recs = {"quran:2:183": _Rec("quran:2:183", "Al-Baqarah 2:183", "x")}
    monkeypatch.setattr(select.db, "get_record", lambda c, rid: recs.get(rid))
    seen = {}
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        seen["user"] = user_text
        return {"summary": "s", "items": []}
    monkeypatch.setattr(select.claude_client, "call_structured", fake)
    select.select_and_frame(object(), "q", [RetrievalHit("quran:2:183",0.1,True,False)],
                            key="k", feedback="Do not cite IDs outside the candidate set.")
    assert "candidate set" in seen["user"]

def test_select_propagates_claude_error(monkeypatch):
    from sanad.agents.claude_client import ClaudeError
    recs = {"quran:2:183": _Rec("quran:2:183", "Al-Baqarah 2:183", "x")}
    monkeypatch.setattr(select.db, "get_record", lambda c, rid: recs.get(rid))
    def boom(**kw): raise ClaudeError("refused")
    monkeypatch.setattr(select.claude_client, "call_structured", boom)
    try:
        select.select_and_frame(object(), "q", [RetrievalHit("quran:2:183", 0.1, True, False)],
                                key="k")
        assert False
    except ClaudeError:
        pass
