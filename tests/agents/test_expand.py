from sanad.agents import expand
from sanad.pipeline.types import Expansion

def test_expand_returns_language_and_terms(monkeypatch):
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        assert "surface form" in system_blocks[0]["text"].lower()  # prompt asks for forms
        return {"question_language": "en",
                "search_terms": ["الصبر", "صبر", "صابرين", "يصبر"]}
    monkeypatch.setattr(expand.claude_client, "call_structured", fake)
    out = expand.expand_query("How should I be patient?", key="k")
    assert isinstance(out, Expansion)
    assert out.question_language == "en"
    assert "صبر" in out.search_terms and len(out.search_terms) >= 2

def test_expand_propagates_claude_error(monkeypatch):
    from sanad.agents.claude_client import ClaudeError
    def boom(**kw): raise ClaudeError("refused")
    monkeypatch.setattr(expand.claude_client, "call_structured", boom)
    try:
        expand.expand_query("q", key="k"); assert False
    except ClaudeError:
        pass
