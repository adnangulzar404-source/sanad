"""Stage 3 of the Ask pipeline: select & frame.

Claude is shown the retrieved candidate records (id, reference, Arabic text)
and must (a) SELECT which record_ids are relevant to the question and (b)
write a short English (or question-language) summary plus a per-item framing.

Claude never writes Arabic here — the schema has no Arabic field, and the
server renders every Arabic quotation from the database by id later, so
fabrication is structurally impossible. Stage 4's guards police that the
selected ids and framings are honest; this stage only proposes them.

The evidence block (candidate id/reference/text) is placed in its own system
block carrying ``cache_control: {"type": "ephemeral"}`` so it is a stable,
cacheable prefix shared across the select and audit calls even though the
question (and any retry feedback) varies per request.
"""
from __future__ import annotations

from ..corpus import db
from ..pipeline.types import RetrievalHit, SelectedItem, Selection
from . import claude_client

SELECT_SYSTEM = (
    "You build an EVIDENCE BRIEF from a fixed candidate set of Qur'an verses "
    "and Sahih al-Bukhari hadith. Rules, all mandatory:\n"
    "1. You may ONLY cite record_ids that appear in the candidate set below.\n"
    "2. You write PROSE ONLY. Never output Arabic script — not a word, not a "
    "letter. The server renders the Arabic from the database by id.\n"
    "3. Choose only candidates genuinely relevant to the question. Omit the "
    "rest. Selecting nothing is a valid, honest outcome.\n"
    "4. For each chosen record write ONE framing line, at most 25 words, "
    "describing what the passage says. For a hadith this is your labelled "
    "explanation, NOT a translation.\n"
    "5. Write a neutral summary of at most 80 words of what the sources cover. "
    "Do not rule, do not grade authenticity, do not claim consensus.\n"
    "6. Write the summary and every framing in the question's own language.\n"
    "Return ONLY the structured object."
)

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {"record_id": {"type": "string"},
                           "framing": {"type": "string"}},
            "required": ["record_id", "framing"],
            "additionalProperties": False,
        }},
    },
    "required": ["summary", "items"],
    "additionalProperties": False,
}


def build_evidence_block(corpus_conn, hits: list[RetrievalHit]) -> str:
    lines = ["CANDIDATE SET (cite only these record_ids):", ""]
    for h in hits:
        rec = db.get_record(corpus_conn, h.record_id)
        if rec is None:
            continue
        lines.append(f"[{rec.id}] {rec.reference_display}")
        lines.append(rec.text_ar)
        lines.append("")
    return "\n".join(lines)


def select_and_frame(corpus_conn, question: str, hits: list[RetrievalHit], *,
                     key: str, client=None, feedback: str | None = None) -> Selection:
    evidence = build_evidence_block(corpus_conn, hits)
    system_blocks = [
        {"type": "text", "text": SELECT_SYSTEM},
        {"type": "text", "text": evidence, "cache_control": {"type": "ephemeral"}},
    ]
    user = f"Question: {question}"
    if feedback:
        user += ("\n\nYour previous attempt was rejected. Fix exactly this and "
                 f"try again:\n{feedback}")
    data = claude_client.call_structured(
        system_blocks=system_blocks, user_text=user, schema=SELECT_SCHEMA,
        key=key, client=client)
    return Selection(
        summary=data["summary"],
        items=[SelectedItem(record_id=i["record_id"], framing=i["framing"])
               for i in data["items"]])
