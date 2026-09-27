from sanad.agents import expand
from sanad.pipeline.types import Expansion

_SCOPE = ("This corpus contains the Qur'an and Sahih al-Bukhari. It does not "
         "contain any other hadith collection. Absence from this corpus "
         "does not establish that a quotation is fabricated.")

def test_expand_returns_language_and_terms(monkeypatch):
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        assert "surface form" in system_blocks[0]["text"].lower()  # prompt asks for forms
        return {"question_language": "en",
                "search_terms": ["الصبر", "صبر", "صابرين", "يصبر"]}
    monkeypatch.setattr(expand.claude_client, "call_structured", fake)
    out = expand.expand_query("How should I be patient?", key="k", corpus_scope=_SCOPE)
    assert isinstance(out, Expansion)
    assert out.question_language == "en"
    assert "صبر" in out.search_terms and len(out.search_terms) >= 2

def test_expand_system_prompt_states_the_derived_scope_not_a_hardcoded_one(monkeypatch):
    # Stage A3 ruling R-A3-17: the prompt used to hardcode "the Qur'an and
    # Sahih al-Bukhari" -- false the moment a second hadith collection ships.
    # It must now say whatever `corpus_scope` the caller passed in.
    captured = {}
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        captured["text"] = system_blocks[0]["text"]
        return {"question_language": "en", "search_terms": ["صبر"]}
    monkeypatch.setattr(expand.claude_client, "call_structured", fake)
    six_collection_scope = (
        "This corpus contains the Qur'an, Sahih al-Bukhari, Sahih Muslim, "
        "Sunan Abi Dawud, Jami at-Tirmidhi, Sunan an-Nasai, and Sunan Ibn "
        "Majah. It does not contain any other hadith collection. Absence "
        "from this corpus does not establish that a quotation is fabricated.")
    expand.expand_query("q", key="k", corpus_scope=six_collection_scope)
    assert six_collection_scope in captured["text"]

def test_expand_propagates_claude_error(monkeypatch):
    from sanad.agents.claude_client import ClaudeError
    def boom(**kw): raise ClaudeError("refused")
    monkeypatch.setattr(expand.claude_client, "call_structured", boom)
    try:
        expand.expand_query("q", key="k", corpus_scope=_SCOPE); assert False
    except ClaudeError:
        pass
