from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..arabic.normalize import normalize
from ..corpus import db
from ..corpus.models import Record
from ..verify.claims import detect_claims, requires_handoff, route_risk
from ..verify.engine import Verdict, verify_spans
from .schemas import ClaimOut, QuotationOut, RecordOut, VerifyRequest, VerifyResponse

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
    audit_conn = _audit_conn(request)
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


@router.get("/records/{record_id}")
def get_record(record_id: str, request: Request) -> dict:
    conn = _conn(request)
    rec = db.get_record(conn, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no record {record_id!r}")
    src = conn.execute("SELECT * FROM sources WHERE id = ?", (rec.source_id,)).fetchone()
    translation_en, disclaimer = _fetch_translation(conn, rec.id)
    return {
        "id": rec.id, "reference_display": rec.reference_display,
        "text_ar": rec.text_ar, "text_ar_sha256": rec.text_ar_sha256,
        "surah": rec.surah, "ayah": rec.ayah,
        "surah_name_ar": rec.surah_name_ar, "surah_name_en": rec.surah_name_en,
        "translation_en": translation_en, "translation_disclaimer": disclaimer,
        "source": dict(src) if src else None,
    }


@router.get("/search")
def search(q: str, request: Request, limit: int = 20) -> dict:
    """Corpus browse. Spec section 9. Lexical only -- no embeddings in Stage A."""
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank")
    limit = max(1, min(limit, 100))
    hits = db.fts_candidates(_conn(request), normalize(q, "aggressive"), limit)
    return {
        "query": q,
        "count": len(hits),
        "results": [
            {"id": r.id, "reference_display": r.reference_display,
             "text_ar": r.text_ar, "surah": r.surah, "ayah": r.ayah}
            for r in hits
        ],
    }


@router.get("/corpus")
def corpus(request: Request) -> dict:
    conn = _conn(request)
    return {
        "db_sha256": request.app.state.db_sha256,
        "db_path": str(request.app.state.db_path),
        "stats": db.corpus_stats(conn),
        "scope": CORPUS_SCOPE,
        "sources": [dict(r) for r in conn.execute("SELECT * FROM sources")],
    }


@router.get("/health")
def health(request: Request) -> dict:
    stats = db.corpus_stats(_conn(request))
    return {"status": "ok", "records": stats["records"], "sources": stats["sources"]}
