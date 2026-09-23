from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..arabic.normalize import normalize
from ..corpus import db
from ..corpus.models import Record
from ..verify.claims import detect_claims, requires_handoff, route_risk
from ..verify.engine import Verdict, verify_spans
from .schemas import (
    ClaimOut,
    CorpusResponse,
    CorpusSourceOut,
    CorpusStatsOut,
    QuotationOut,
    RecordDetailOut,
    RecordOut,
    VerifyRequest,
    VerifyResponse,
)

router = APIRouter(prefix="/api")

CORPUS_SCOPE = (
    "This corpus contains the Qur'an only. Absence of a quotation from this "
    "corpus does not establish that it is fabricated."
)

# Tanzil's own accuracy disclaimer for en.pickthall, per the spec sec 5.2 item 4:
# it must accompany every rendered translation, not live only in a licence file.
TANZIL_TRANSLATION_DISCLAIMER = (
    "No translation of Quran can be a hundred percent accurate, nor can it be "
    "used as a replacement of the Quran text."
)

# Arabic block (matches `arabic.normalize._NON_ARABIC`'s complement), used
# only to decide which cleanup a search query needs -- see `_normalize_query`.
_ARABIC_CHAR = re.compile(r"[؀-ۿ]")


def _normalize_query(q: str) -> str:
    """Script-aware query normalization for `/api/search`.

    `normalize(q, "aggressive")` strips everything outside the Arabic block,
    so an English query like "mercy" was silently reduced to the empty
    string and `search()` returned zero results unconditionally -- even
    though `db.rebuild_fts` indexes the Pickthall `translation` column for
    every one of the corpus's 6,236 records. Half the corpus was
    unsearchable. Fix: normalize the Arabic portion of the query (if any) at
    the aggressive tier as before, and separately lowercase/clean the
    non-Arabic portion so it can still match `translation`. A query mixing
    both scripts searches both -- `db.fts_candidates`'s token-OR match
    doesn't care which half of this string a given token came from.
    """
    parts = []
    if _ARABIC_CHAR.search(q):
        ar = normalize(q, "aggressive")
        if ar:
            parts.append(ar)
    # Non-Arabic cleanup: drop any Arabic characters already handled above,
    # lowercase (FTS5's unicode61 tokenizer case-folds ASCII on both sides
    # anyway, but this keeps the two normalized halves visually consistent),
    # and collapse whitespace. `db.fts_candidates` still does its own
    # metacharacter stripping downstream; this only needs to not hand it an
    # empty string for ordinary English text.
    non_arabic = _ARABIC_CHAR.sub(" ", q)
    en = " ".join(non_arabic.lower().split())
    if en:
        parts.append(en)
    return " ".join(parts)


def _conn(request: Request) -> sqlite3.Connection:
    """The read-only corpus connection. Never written to -- see app.py."""
    return request.app.state.conn


def _audit_conn(request: Request) -> sqlite3.Connection:
    """The writable audit-log connection, a separate database from the corpus."""
    return request.app.state.audit_conn


def _fetch_translation(conn: sqlite3.Connection, record_id: str) -> tuple[str | None, str | None]:
    """The record's English translation and Tanzil's accuracy disclaimer.

    Returns `(None, None)` when no translation is stored -- the disclaimer is
    only meaningful (and only emitted) alongside actual translated text.
    """
    row = conn.execute(
        "SELECT text FROM translations WHERE record_id = ? AND lang = 'en' LIMIT 1",
        (record_id,)).fetchone()
    if row is None:
        return None, None
    return row["text"], TANZIL_TRANSLATION_DISCLAIMER


def _record_out(conn: sqlite3.Connection, rec: Record) -> RecordOut:
    translation_en, disclaimer = _fetch_translation(conn, rec.id)
    return RecordOut(
        id=rec.id, reference_display=rec.reference_display, text_ar=rec.text_ar,
        text_ar_sha256=rec.text_ar_sha256, surah=rec.surah, ayah=rec.ayah,
        translation_en=translation_en, translation_disclaimer=disclaimer,
        addenda_ar=rec.addenda_ar, unscorable_reason=rec.unscorable_reason,
    )


def _overall(quotations: list[QuotationOut], claims: list[ClaimOut], handoff: bool) -> str:
    if handoff:
        return "handoff"
    if not quotations and not claims:
        return "insufficient_span"
    bad = {Verdict.NOT_FOUND.value, Verdict.WRONG_REFERENCE.value, Verdict.NEAR_MATCH.value}
    if any(q.verdict in bad for q in quotations) or claims:
        return "needs_review"
    return "grounded"


@router.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest, request: Request) -> VerifyResponse:
    conn = _conn(request)
    matches = verify_spans(conn, payload.text)

    quotations = [
        QuotationOut(
            quoted_text=m.span.text, start=m.span.start, end=m.span.end,
            verdict=m.verdict.value, tier=m.tier, score=round(m.score, 4),
            record=_record_out(conn, m.record) if m.record else None,
            also_at=list(m.also_at),
            given_reference=m.given_reference.raw if m.given_reference else None,
            diff=m.diff,
        )
        for m in matches
    ]
    claims = [ClaimOut(kind=c.kind, label=c.label, note=c.note)
              for c in detect_claims(payload.text)]
    risk = route_risk(payload.text)
    handoff = requires_handoff(risk)

    # Audit: verdicts, record ids, and claim kinds only. The submitted text
    # and any extracted quotation text are NEVER written here -- the spec
    # forbids retaining user conversation data. Written to the SEPARATE
    # audit database, never the (read-only) corpus connection -- see app.py.
    #
    # The write and its commit are one atomic unit under `audit_lock`.
    # `check_same_thread=False` (see app.py) only disables SQLite's thread
    # affinity check -- it does not make a single shared connection safe for
    # concurrent execute/commit from Starlette's threadpool. Without the
    # lock, two interleaved requests can each start a transaction and then
    # have one thread's `commit()` find the other thread already closed it,
    # raising `sqlite3.OperationalError: cannot commit - no transaction is
    # active`, or worse, silently attributing one request's row to another's
    # commit. Locking only `execute()` would not fix this -- the commit must
    # be inside the same critical section as the write it is committing.
    audit_conn = _audit_conn(request)
    with request.app.state.audit_lock:
        audit_conn.execute(
            "INSERT INTO audit_log (ts, request_id, stage, verdict, detail_json) "
            "VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), str(uuid.uuid4()), "verify",
             risk.value,
             json.dumps({"verdicts": [q.verdict for q in quotations],
                         "record_ids": [q.record.id for q in quotations if q.record],
                         "claim_kinds": [c.kind for c in claims]})),
        )
        audit_conn.commit()

    return VerifyResponse(
        quotations=quotations, claims=claims, risk=risk.value,
        requires_handoff=handoff,
        overall=_overall(quotations, claims, handoff),
        corpus_scope=CORPUS_SCOPE,
    )


@router.get("/records/{record_id}", response_model=RecordDetailOut)
def get_record(record_id: str, request: Request) -> RecordDetailOut:
    conn = _conn(request)
    rec = db.get_record(conn, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no record {record_id!r}")
    src = conn.execute("SELECT * FROM sources WHERE id = ?", (rec.source_id,)).fetchone()
    translation_en, disclaimer = _fetch_translation(conn, rec.id)
    return RecordDetailOut(
        id=rec.id, reference_display=rec.reference_display,
        text_ar=rec.text_ar, text_ar_sha256=rec.text_ar_sha256,
        surah=rec.surah, ayah=rec.ayah,
        surah_name_ar=rec.surah_name_ar, surah_name_en=rec.surah_name_en,
        translation_en=translation_en, translation_disclaimer=disclaimer,
        addenda_ar=rec.addenda_ar, unscorable_reason=rec.unscorable_reason,
        source=CorpusSourceOut(**dict(src)) if src else None,
    )


@router.get("/search")
def search(q: str, request: Request, limit: int = 20) -> dict:
    """Corpus browse. Spec section 9. Lexical only -- no embeddings in Stage A.

    Searches both the Arabic text and the (also indexed) English Pickthall
    translation -- see `_normalize_query` for why a purely-Arabic
    normalization used to make English queries return nothing.
    """
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank")
    limit = max(1, min(limit, 100))
    conn = _conn(request)
    # `fts_records`, not `fts_candidates`: a hadith indexed under both its
    # primary matn and its full printed text matches twice and is still one
    # result. See `corpus.db.fts_records`.
    hits = db.fts_records(conn, _normalize_query(q), limit)
    return {
        "query": q,
        "count": len(hits),
        "results": [
            {
                "id": r.id, "reference_display": r.reference_display,
                "text_ar": r.text_ar, "surah": r.surah, "ayah": r.ayah,
                # English is now findable (see _normalize_query), so a user
                # searching in English needs to see what actually matched.
                "translation_en": _fetch_translation(conn, r.id)[0],
            }
            for r in hits
        ],
    }


@router.get("/corpus", response_model=CorpusResponse)
def corpus(request: Request) -> CorpusResponse:
    conn = _conn(request)
    return CorpusResponse(
        db_sha256=request.app.state.db_sha256,
        db_path=str(request.app.state.db_path),
        stats=CorpusStatsOut(**db.corpus_stats(conn)),
        scope=CORPUS_SCOPE,
        sources=[CorpusSourceOut(**dict(r)) for r in conn.execute("SELECT * FROM sources")],
    )


@router.get("/health")
def health(request: Request) -> dict:
    stats = db.corpus_stats(_conn(request))
    return {"status": "ok", "records": stats["records"], "sources": stats["sources"]}
