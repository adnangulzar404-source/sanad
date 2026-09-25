from __future__ import annotations

import sqlite3

from ..corpus import db
from ..pipeline.types import RetrievalHit, RetrievalResult
from . import voyage
from .fuse import rrf_fuse
from .vector_store import iter_embeddings

RETRIEVAL_K_PER_RETRIEVER = 50
RETRIEVAL_TOP_K = 24

_NO_REACH = ("Retrieval could not reach the corpus for this question: no Arabic "
             "search terms were available and vector search is unavailable "
             "(no Voyage key or no embeddings). Ask cannot answer without "
             "reaching the corpus, and does not guess.")


def _fts_ranked(conn: sqlite3.Connection, arabic_terms: list[str]) -> list[str]:
    """Union FTS results across every surface form, best-ranked first, deduped.

    FTS5 has no Arabic stemmer and the norms never strip `ال`, so one term is
    not enough (see plan §departures 2). Every term is queried; a record's best
    (earliest) appearance across terms sets its rank.
    """
    seen: dict[str, int] = {}
    order: list[str] = []
    for term in arabic_terms:
        for rec in db.fts_records(conn, term, RETRIEVAL_K_PER_RETRIEVER):
            if rec.id not in seen:
                seen[rec.id] = len(order)
                order.append(rec.id)
    return order


def _vector_ranked(cconn, vconn, *, question, key, embed_fn) -> list[str]:
    if vconn is None or not key:
        return []
    corpus = [(e.record_id, e.vec) for e in iter_embeddings(vconn)]
    if not corpus:
        return []
    qvec = embed_fn([question], input_type="query", key=key)[0]
    return [rid for rid, _dist in
            voyage.hamming_topk(qvec, corpus, RETRIEVAL_K_PER_RETRIEVER)]


def retrieve(corpus_conn, vectors_conn, *, arabic_terms, question,
             voyage_key, embed_fn=voyage.embed_texts) -> RetrievalResult:
    lexical = _fts_ranked(corpus_conn, arabic_terms)
    try:
        vector = _vector_ranked(corpus_conn, vectors_conn, question=question,
                                key=voyage_key, embed_fn=embed_fn)
    except voyage.VoyageError:
        vector = []  # degrade to lexical; never fail the whole request

    fused = rrf_fuse([lexical, vector])[:RETRIEVAL_TOP_K]
    lex_set, vec_set = set(lexical), set(vector)
    hits: list[RetrievalHit] = []
    reached = {"quran": False, "hadith": False}
    for rid, score in fused:
        rec = db.get_record(corpus_conn, rid)
        if rec is None:
            continue
        hits.append(RetrievalHit(record_id=rid, rrf_score=score,
                                 in_fts=rid in lex_set, in_vector=rid in vec_set))
        reached[rec.kind if rec.kind == "hadith" else "quran"] = True

    unreached = _NO_REACH if not hits and not vector and not lexical else None
    return RetrievalResult(hits=hits, reached=reached,
                           unreached_reason=unreached, candidate_count=len(hits))
