import httpx
from sanad.agents.claude_client import call_structured, ClaudeError

_SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}},
           "required": ["x"], "additionalProperties": False}

def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_returns_parsed_json_from_first_text_block():
    def h(req):
        return httpx.Response(200, json={
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": '{"x": "ok"}'}],
            "usage": {"cache_read_input_tokens": 0}})
    out = call_structured(system_blocks=[{"type": "text", "text": "sys"}],
                          user_text="q", schema=_SCHEMA, key="k", client=_client(h))
    assert out == {"x": "ok"}

def test_refusal_raises_claude_error():
    def h(req):
        return httpx.Response(200, json={"stop_reason": "refusal",
                                         "stop_details": {"category": "reasoning_extraction"},
                                         "content": []})
    try:
        call_structured(system_blocks=[{"type": "text", "text": "s"}], user_text="q",
                        schema=_SCHEMA, key="k", client=_client(h))
        assert False
    except ClaudeError:
        pass

def test_http_error_raises_claude_error():
    def h(req):
        return httpx.Response(429, json={"error": "rate"})
    try:
        call_structured(system_blocks=[{"type": "text", "text": "s"}], user_text="q",
                        schema=_SCHEMA, key="k", client=_client(h))
        assert False
    except ClaudeError:
        pass

def test_request_body_uses_adaptive_thinking_and_output_config():
    seen = {}
    def h(req):
        import json
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"stop_reason": "end_turn",
            "content": [{"type": "text", "text": '{"x":"1"}'}], "usage": {}})
    call_structured(system_blocks=[{"type": "text", "text": "s"}], user_text="q",
                    schema=_SCHEMA, key="k", client=_client(h))
    assert seen["model"] == "claude-opus-5"
    assert seen["thinking"] == {"type": "adaptive"}
    assert seen["output_config"]["format"]["type"] == "json_schema"
    assert seen["output_config"]["effort"] == "high"
    assert "budget_tokens" not in seen.get("thinking", {})
