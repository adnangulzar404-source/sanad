"""Stage 1 of the Ask pipeline: query expansion.

Takes the user's question (any language) and asks Claude to (a) detect the
question's language and (b) produce Arabic search terms for retrieval. The
corpus FTS5 index has no Arabic stemmer and never strips the definite article
``ال`` (measured: ``صابرين`` returns 0 hits while ``الصبر``/``صبر`` return
different, non-overlapping sets) — so the prompt asks for SEVERAL surface
forms per concept, not one.
"""
from __future__ import annotations

from ..pipeline.types import Expansion
from . import claude_client


# The system prompt used to hardcode "over the Qur'an and Sahih al-Bukhari" --
# a description of the corpus that Stage A3 makes false the moment another
# hadith collection is ingested (Stage A3 ruling R-A3-17). `corpus_scope` is
# `corpus.scope.corpus_scope(conn)`'s output, carried in by the caller
# (`pipeline.orchestrate.run_ask`) rather than queried here, so this module
# stays free of any DB dependency.
def _expand_system(corpus_scope: str) -> str:
    return (
        "You expand a user's question into Arabic search terms for a lexical "
        f"index over this corpus. {corpus_scope} The index does NOT stem "
        "Arabic and does NOT strip the definite article or prepositional "
        "prefixes (ب، ل، و، ك fuse onto the next word as one token). "
        "For each concept in the question emit SEVERAL surface forms: the "
        "bare root, the form with ال, common inflections (verb, active "
        "participle, plural), AND forms with prepositional prefixes fused "
        "to the definite noun (بالـ, للـ, وال). "
        "Example — concept 'intention' -> "
        "['نية', 'النية', 'نيات', 'النيات', 'بالنية', 'بالنيات', 'نوى']. "
        "Example — concept 'patience' -> "
        "['صبر', 'الصبر', 'صابرين', 'يصبر', 'بالصبر']. "
        "Detect the question's language as an ISO 639-1 code. Return ONLY "
        "the structured object. Do not answer the question."
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


def _history_block(history: list[dict]) -> str:
    """Preceding-turns context for pronoun/ellipsis resolution.

    Each turn carries only its English question and summary (never Arabic) so
    "that hadith" or "in Muslim" in the new question can be resolved without
    handing the model any Arabic it could echo back as prose.
    """
    lines = []
    for i, t in enumerate(history, 1):
        lines.append(f"Turn {i} question: {t.get('question', '').strip()}")
        s = (t.get('summary') or "").strip()
        if s:
            lines.append(f"Turn {i} summary: {s}")
        ids = t.get("item_ids", [])
        if ids:
            lines.append(f"Turn {i} evidence IDs: {', '.join(ids)}")
    return "\n".join(lines)


def expand_query(question: str, *, key: str, corpus_scope: str,
                 history: list[dict] | None = None, client=None) -> Expansion:
    if history:
        user_text = (
            "Prior turns (English only — use for pronoun and ellipsis resolution):\n"
            + _history_block(history)
            + "\n\nNew question to expand: " + question
        )
    else:
        user_text = question
    data = claude_client.call_structured(
        system_blocks=[{"type": "text", "text": _expand_system(corpus_scope)}],
        user_text=user_text, schema=EXPAND_SCHEMA, key=key, effort="low",
        max_tokens=2000, client=client)
    return Expansion(question_language=data["question_language"],
                     search_terms=list(data["search_terms"]))
