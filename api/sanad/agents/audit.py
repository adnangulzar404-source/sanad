"""Stage 5 of the Ask pipeline: fresh-context adversarial audit.

This is a SEPARATE Claude call from stage 3 (select & frame). It receives
only the drafted brief (summary + framings) and the Arabic source records
each framing sits under -- never stage 3's prompt, its expansion, or its
reasoning. Context isolation is the point: an auditor that saw why stage 3
chose what it chose could rationalize the same overreach rather than judge
it independently.

Every framing is checked against ONLY the record beneath it. The auditor
flags overreach (a framing claiming more than the passage says), any claim
of unanimity/consensus, any flattening of madhhab disagreement into one
position, and any implied authenticity grading -- the same categories
guards.py polices lexically, caught here semantically for cases the guard's
pattern matching cannot see.
"""
from __future__ import annotations

from . import claude_client
from ..corpus import db
from ..pipeline.types import AuditVerdict, Selection

AUDIT_SYSTEM = (
    "You are an independent reviewer. You are shown an evidence brief (a summary "
    "and framing lines, each under a record) and the Arabic source records. You "
    "did NOT write the brief and must not assume its framings are correct. For "
    "each framing, judge ONLY whether it is fairly supported by the record it "
    "sits under. Flag: overreach (a framing claiming more than the passage "
    "says), any claim of unanimity/consensus, any flattening of madhhab "
    "disagreement into one position, and any implied authenticity grading. "
    "Set overreach true if ANY framing or the summary overreaches. Return ONLY "
    "the structured object."
)

AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "overreach": {"type": "boolean"},
        "flags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overreach", "flags"],
    "additionalProperties": False,
}


def audit_brief(corpus_conn, selection: Selection, *, key: str,
                client=None) -> AuditVerdict:
    lines = [f"SUMMARY: {selection.summary}", "", "BRIEF ITEMS AND SOURCES:"]
    for item in selection.items:
        rec = db.get_record(corpus_conn, item.record_id)
        lines.append(f"- framing: {item.framing}")
        lines.append(f"  record [{item.record_id}]: {rec.text_ar if rec else '(missing)'}")
    data = claude_client.call_structured(
        system_blocks=[{"type": "text", "text": AUDIT_SYSTEM}],
        user_text="\n".join(lines), schema=AUDIT_SCHEMA, key=key, client=client)
    return AuditVerdict(overreach=bool(data["overreach"]),
                        flags=list(data["flags"]))
