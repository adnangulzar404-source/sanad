"""Shared Claude Messages API client for the Ask pipeline.

This is the single place any model-backed stage (query expansion,
select&frame, audit) talks to Anthropic. It uses raw httpx (already a core
dependency) rather than the anthropic SDK, and returns schema-validated JSON
extracted from the response's first text block.

Callers must import this module qualified (``from . import claude_client``)
and call ``claude_client.call_structured(...)`` rather than importing
``call_structured`` by name, so the eval runner (Task 12) can monkeypatch it.

A refusal comes back as HTTP 200 with ``stop_reason == "refusal"`` — this is
detected and raised as ``ClaudeError`` before any attempt to parse content.
Every model-stage failure (HTTP error, refusal, malformed JSON) raises
``ClaudeError`` so callers can turn it into abstention, never a 500.
"""
from __future__ import annotations

import json
import os

import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
CLAUDE_MODEL = "claude-opus-5"
_TIMEOUT = 120.0
_MAX_TOKENS = 16000


class ClaudeError(Exception):
    pass


def resolve_anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None


def call_structured(*, system_blocks: list[dict], user_text: str, schema: dict,
                    key: str, effort: str = "high",
                    client: httpx.Client | None = None) -> dict:
    owns = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": _MAX_TOKENS,
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        },
        "system": system_blocks,
        "messages": [{"role": "user", "content": user_text}],
    }
    try:
        resp = client.post(ANTHROPIC_URL, headers={
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }, json=body)
    except httpx.HTTPError as exc:
        raise ClaudeError(f"transport: {exc}") from exc
    finally:
        if owns:
            client.close()

    if resp.status_code != 200:
        raise ClaudeError(f"anthropic {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise ClaudeError(f"malformed response body: {exc}") from exc
    if not isinstance(data, dict):
        raise ClaudeError(f"response body is not a JSON object: {type(data).__name__}")
    if data.get("stop_reason") == "refusal":
        cat = (data.get("stop_details") or {}).get("category")
        raise ClaudeError(f"model refused (category={cat})")
    try:
        text = next(b["text"] for b in data["content"] if b.get("type") == "text")
        return json.loads(text)
    except (StopIteration, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ClaudeError(f"no valid JSON in response: {exc}") from exc
