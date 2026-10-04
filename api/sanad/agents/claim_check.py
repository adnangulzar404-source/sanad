"""Claim-check pipeline agents.

Two Claude calls to check English Islamic claims against the corpus:
1. extract_and_plan  — identify claims + Arabic search terms (effort=low)
2. assess_claims     — compare each claim against retrieved records (effort=medium)
"""
from __future__ import annotations

from ..corpus.models import Record
from . import claude_client

# ── Extract: identify claims and search terms ───────────────────────────────

_EXTRACT_SYSTEM = (
    "You read English text and identify discrete Islamic claims — statements "
    "that a hadith says X, that Islam teaches Y, or that a Qur'anic verse "
    "asserts Z. For each claim emit: (a) the claim as a concise English "
    "sentence, and (b) Arabic search terms to find it in a lexical index "
    "that does NOT stem Arabic and does NOT strip definite articles or "
    "prepositional prefixes (ب/ل/و fuse onto the next token). Emit SEVERAL "
    "surface forms per concept: bare root, definite form (ال), common "
    "inflections, and prepositional-prefix forms (بالـ, للـ). "
    "Example — claim 'actions judged by intentions' → terms: "
    "['نية', 'النية', 'نيات', 'النيات', 'بالنية', 'بالنيات', 'الاعمال', 'اعمال', 'نوى']. "
    "Skip claims that are not Islamic in nature. "
    "Return ONLY the structured object."
)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "search_terms": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claim", "search_terms"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}


def extract_and_plan(text: str, *, key: str, client=None) -> list[dict]:
    """Return [{claim: str, search_terms: list[str]}] for each Islamic claim found."""
    data = claude_client.call_structured(
        system_blocks=[{"type": "text", "text": _EXTRACT_SYSTEM}],
        user_text=text, schema=EXTRACT_SCHEMA,
        key=key, effort="low", max_tokens=2000, client=client)
    try:
        return data["claims"]
    except (KeyError, TypeError) as exc:
        raise claude_client.ClaudeError(f"extract response missing claims key: {exc}") from exc


# ── Assess: verdict for each claim vs retrieved records ─────────────────────

def _assess_system(corpus_scope: str) -> str:
    return (
        "You are given a list of Islamic claims paired with candidate passages "
        f"retrieved from this corpus. {corpus_scope} "
        "For each claim return ONE verdict:\n"
        "  supported          — a candidate directly and explicitly states the claim\n"
        "  partially_supported — a candidate is closely related but does not fully "
        "state the claim, or states it in a different context\n"
        "  not_found          — no candidate meaningfully supports the claim\n"
        "  unverifiable       — the claim is an interpretive or theological gloss "
        "that no corpus passage can confirm or deny as a direct quotation\n"
        "Also write a note (at most 30 words) explaining the verdict and list the "
        "record_ids of any supporting candidates (empty list if none). "
        "Return assessments in the SAME ORDER as the claims. "
        "Return ONLY the structured object."
    )


ASSESS_SCHEMA = {
    "type": "object",
    "properties": {
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string"},
                    "note": {"type": "string"},
                    "record_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["verdict", "note", "record_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["assessments"],
    "additionalProperties": False,
}


def _build_evidence_block(claims_with_candidates: list[dict]) -> str:
    lines = []
    for i, item in enumerate(claims_with_candidates, 1):
        lines.append(f"Claim {i}: {item['claim']}")
        recs: list[Record] = item["records"]
        if recs:
            for rec in recs:
                lines.append(f"  [{rec.id}] {rec.reference_display}: {rec.text_ar}")
        else:
            lines.append("  (no candidates retrieved)")
        lines.append("")
    return "\n".join(lines)


def assess_claims(claims_with_candidates: list[dict], *, key: str,
                  corpus_scope: str, client=None) -> list[dict]:
    """Return [{verdict, note, record_ids}] in same order as claims_with_candidates."""
    if not claims_with_candidates:
        return []
    evidence = _build_evidence_block(claims_with_candidates)
    data = claude_client.call_structured(
        system_blocks=[
            {"type": "text", "text": _assess_system(corpus_scope)},
            {"type": "text", "text": evidence},
        ],
        user_text="Assess each claim against its candidates.",
        schema=ASSESS_SCHEMA,
        key=key, effort="low", max_tokens=3000, client=client)
    try:
        return data["assessments"]
    except (KeyError, TypeError) as exc:
        raise claude_client.ClaudeError(f"assess response missing assessments key: {exc}") from exc
