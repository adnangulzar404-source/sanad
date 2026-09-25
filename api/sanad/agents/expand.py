"""Stage 1 of the Ask pipeline: query expansion.

Takes the user's question (any language) and asks Claude to (a) detect the
question's language and (b) produce Arabic search terms for retrieval. The
corpus FTS5 index has no Arabic stemmer and never strips the definite article
``ال`` (measured: ``صابرين`` returns 0 hits while ``الصبر``/``صبر`` return
different, non-overlapping sets) — so the prompt asks for SEVERAL surface
forms per concept, not one.
"""
from __future__ import annotations

from . import claude_client
from ..pipeline.types import Expansion

EXPAND_SYSTEM = (
    "You expand a user's question into Arabic search terms for a lexical index "
    "over the Qur'an and Sahih al-Bukhari. The index does NOT stem Arabic and "
    "does NOT strip the definite article. So for each concept in the question, "
    "emit SEVERAL surface forms, not one: the bare root-word, the form with "
    "the definite article ال, and common inflections (verb, active participle, "
    "plural). Example — concept 'patience' -> ['صبر', 'الصبر', 'صابرين', "
    "'يصبر', 'اصبروا']. Detect the question's language as an ISO 639-1 code. "
    "Return ONLY the structured object. Do not answer the question."
)

EXPAND_SCHEMA = {
    "type": "object",
    "properties": {
        "question_language": {"type": "string"},
        "search_terms": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["question_language", "search_terms"],
    "additionalProperties": False,
}


def expand_query(question: str, *, key: str, client=None) -> Expansion:
    data = claude_client.call_structured(
        system_blocks=[{"type": "text", "text": EXPAND_SYSTEM}],
        user_text=question, schema=EXPAND_SCHEMA, key=key, client=client)
    return Expansion(question_language=data["question_language"],
                     search_terms=list(data["search_terms"]))
