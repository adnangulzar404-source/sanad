"""English claim-check pipeline.

Extracts Islamic claims from English text, retrieves corpus candidates for each,
then assesses whether the corpus supports each claim.
"""
from __future__ import annotations

from typing import Iterator

from ..agents.claim_check import assess_claims, extract_and_plan
from ..agents.claude_client import ClaudeError
from ..arabic.normalize import normalize
from ..corpus import db
from ..corpus.models import Record
from .types import StageEvent

_RETRIEVE_LIMIT = 20   # FTS records per search term
_CANDIDATES_PER_CLAIM = 10  # max candidates sent to assess

_CLIENT_ERROR_MSG = "Claim check encountered an error and could not complete."


def run_claim_check(
    corpus_conn, text: str, *, anthropic_key: str | None, corpus_scope: str
) -> Iterator[StageEvent]:
    """Yield StageEvent stream: extract → assess → final (or error)."""
    if not anthropic_key:
        yield StageEvent("error", {"message": _CLIENT_ERROR_MSG})
        return

    try:
        plans = extract_and_plan(text, key=anthropic_key)
    except ClaudeError:
        yield StageEvent("error", {"message": _CLIENT_ERROR_MSG})
        return

    if not plans:
        yield StageEvent("extract", {"claims": []})
        yield StageEvent("final", {"count": 0})
        return

    yield StageEvent("extract", {"claims": [p["claim"] for p in plans]})

    # FTS retrieve for each claim's search terms
    claims_with_candidates: list[dict] = []
    for plan in plans:
        seen: set[str] = set()
        records: list[Record] = []
        for term in plan["search_terms"]:
            norm = normalize(term, "standard")
            for rec in db.fts_records(corpus_conn, norm, _RETRIEVE_LIMIT):
                if rec.id not in seen:
                    seen.add(rec.id)
                    records.append(rec)
                    if len(records) >= _CANDIDATES_PER_CLAIM:
                        break
            if len(records) >= _CANDIDATES_PER_CLAIM:
                break
        claims_with_candidates.append({"claim": plan["claim"], "records": records})

    try:
        assessments = assess_claims(
            claims_with_candidates, key=anthropic_key, corpus_scope=corpus_scope)
    except ClaudeError:
        yield StageEvent("error", {"message": _CLIENT_ERROR_MSG})
        return

    # Pair assessments with their retrieved records (keep only cited ones)
    results = []
    for item, assessment in zip(claims_with_candidates, assessments):
        cited_ids = set(assessment.get("record_ids", []))
        cited_records = [r for r in item["records"] if r.id in cited_ids]
        results.append({
            "claim": item["claim"],
            "verdict": assessment["verdict"],
            "note": assessment["note"],
            "records": cited_records,
        })

    yield StageEvent("assess", {"results": results})
    yield StageEvent("final", {"count": len(results)})
