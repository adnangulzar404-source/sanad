from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..agents.claude_client import ClaudeError, resolve_anthropic_key
from ..arabic.normalize import normalize
from ..corpus import db
from ..corpus.models import Record
from ..corpus.scope import CORPUS_SCOPE
from ..pipeline.orchestrate import run_ask
from ..retrieve.voyage import VoyageError, resolve_voyage_key
from ..verify.claims import detect_claims, requires_handoff, route_risk
from ..verify.engine import Verdict, verify_spans
from .schemas import (
    AskFinalOut,  # noqa: F401 -- documents the `final` event's payload shape
    AskRequest,
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

# `CORPUS_SCOPE` is imported from `corpus.scope` and re-exported here under its
# original name: it is a fact about the corpus, not about the HTTP layer, and
# the evaluation harness asserts it without importing FastAPI. Named in
# `__all__` so the re-export is deliberate rather than an unused import.
__all__ = ["CORPUS_SCOPE", "router"]

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
        isnad_ar=rec.isnad_ar, collection=rec.collection, hadith_no=rec.hadith_no,
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


# The client-facing text for a mid-stream `ClaudeError`/`VoyageError` catch
# (see `ask()` below). The route is a trust boundary: `str(exc)` can carry
# arbitrary upstream text (a provider's error body, a transport message that
# happens to echo a header) and must never be forwarded to the client
# verbatim -- only this fixed, generic string goes out over the wire. The
# real exception text is still recorded, but only in the server-side audit
# row (`_write_ask_audit`'s `error_detail`), which the client never reads.
_GENERIC_MIDSTREAM_ERROR_MESSAGE = "An internal error occurred while processing the request."


def _abstain_payload(*, risk: str, abstain_reason: str) -> dict:
    """The shared shape of an abstained `final` event's payload.

    Both the missing-key path and the mid-stream-error path in `ask()` need
    this exact dict, differing only in `risk` and `abstain_reason` --
    factored out so the two copies (previously separate ~10-line literals)
    cannot silently drift apart.
    """
    return {
        "status": "abstained", "question_language": None,
        "summary": None, "items": [],
        "reached": {"quran": False, "hadith": False},
        "unreached_reason": None, "risk": risk,
        "requires_handoff": False,
        "abstain_reason": abstain_reason,
        "corpus_scope": CORPUS_SCOPE,
    }


def _write_ask_audit(request: Request, status: str, risk: str,
                     record_ids: list[str], reached: dict,
                     error_detail: str | None = None) -> None:
    """One `audit_log` row per `/api/ask` call (spec §9) -- never the question
    text or the search terms, same rule `verify()` follows above. Reuses
    `app.state.audit_lock` for the same reason `verify()` does: see
    `app.py`'s `_open_audit_conn` docstring for why the write and its commit
    must be one atomic unit under that lock.

    `error_detail`, when given, is the full `str(exc)` from a mid-stream
    `ClaudeError`/`VoyageError` -- recorded here, server-side only, because
    the client-facing `error` event carries a generic message instead (see
    `_GENERIC_MIDSTREAM_ERROR_MESSAGE`). Omitted from `detail_json` on the
    (overwhelmingly common) no-error path rather than always present as
    `None`, so the row's shape matches the brief's documented
    `{risk, record_ids, abstained, reached}` exactly whenever there was
    nothing to add.
    """
    detail = {"risk": risk, "record_ids": record_ids,
              "abstained": status == "abstained", "reached": reached}
    if error_detail is not None:
        detail["error"] = error_detail
    audit_conn = _audit_conn(request)
    with request.app.state.audit_lock:
        audit_conn.execute(
            "INSERT INTO audit_log (ts, request_id, stage, verdict, detail_json) "
            "VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), str(uuid.uuid4()), "ask",
             status, json.dumps(detail)))
        audit_conn.commit()


@router.post("/ask")
def ask(payload: AskRequest, request: Request) -> StreamingResponse:
    """Streams the Ask pipeline's `StageEvent`s as `text/event-stream`.

    The route owns key resolution (Task 10's carry-forward rule): it calls
    `resolve_anthropic_key`/`resolve_voyage_key` and passes the resolved
    values into `run_ask` as plain kwargs -- `run_ask` never reads the
    environment itself. A missing Anthropic key produces a clean `final`
    abstain event (spec §3.5: Verify must stay fully functional even when
    Ask cannot run), never a 500. The vectors sidecar is optional; its
    absence is the `voyage_key=None`, lexical-only path -- see `app.py`.

    The server renders records: `final.items` carry `record_id` + `framing`
    from `run_ask` only. This handler is the ONLY place that turns a
    `record_id` into Arabic text, via `db.get_record` + `_record_out` --
    exactly the same structural guarantee `verify()` relies on. Nothing here
    ever serializes Arabic that passed through the model.
    """
    conn = _conn(request)
    vectors_conn = getattr(request.app.state, "vectors_conn", None)
    anthropic_key = resolve_anthropic_key()
    voyage_key = resolve_voyage_key()

    def _sse():
        record_ids: list[str] = []
        status = "abstained"
        risk = "GENERAL"
        reached = {"quran": False, "hadith": False}
        error_detail: str | None = None

        if anthropic_key is None:
            final = {"stage": "final", "payload": _abstain_payload(
                risk="GENERAL",
                abstain_reason=("Ask needs an Anthropic API key, which is "
                                "not configured. Verification is unaffected."))}
            yield f"data: {json.dumps(final)}\n\n"
            _write_ask_audit(request, "abstained", "GENERAL", [], reached)
            return

        try:
            for event in run_ask(conn, vectors_conn, payload.question,
                                 anthropic_key=anthropic_key, voyage_key=voyage_key):
                payload_out = dict(event.payload)
                if event.stage == "router":
                    risk = payload_out.get("risk", risk)
                if event.stage == "final":
                    items = []
                    for it in payload_out.get("items", []):
                        rec = db.get_record(conn, it["record_id"])
                        items.append({
                            "record_id": it["record_id"], "framing": it["framing"],
                            "record": _record_out(conn, rec).model_dump() if rec else None})
                    payload_out["items"] = items
                    payload_out["corpus_scope"] = CORPUS_SCOPE
                    record_ids = [it["record_id"] for it in items]
                    status = payload_out.get("status", "abstained")
                    risk = payload_out.get("risk", risk)
                    reached = payload_out.get("reached", reached)
                yield f"data: {json.dumps({'stage': event.stage, 'payload': payload_out})}\n\n"
        except (ClaudeError, VoyageError) as exc:
            # `run_ask` already catches its own ClaudeError calls internally
            # and turns them into `error` + abstained-`final` StageEvents
            # (see `pipeline.orchestrate`) -- this is a second line of
            # defense so an exception that reaches the route (a bug, or a
            # future stage that forgets to catch) still surfaces as the
            # brief's error event and a clean stream close, never a bare 500
            # or a truncated response.
            #
            # Trust boundary: `str(exc)` is NEVER put in the client-facing
            # event -- an upstream provider's raw error text could carry
            # anything, including a fragment of a request that had a key in
            # it. Only the fixed, generic message crosses the wire; the real
            # detail is recorded server-side only, via `error_detail` below.
            error_detail = str(exc)
            error_event = {"stage": "error", "payload": {
                "code": "pipeline_error",
                "message": _GENERIC_MIDSTREAM_ERROR_MESSAGE}}
            yield f"data: {json.dumps(error_event)}\n\n"
            status = "abstained"
            final = {"stage": "final", "payload": _abstain_payload(
                risk=risk,
                abstain_reason="The Ask pipeline encountered an error and could not complete.")}
            yield f"data: {json.dumps(final)}\n\n"
            reached = {"quran": False, "hadith": False}

        _write_ask_audit(request, status, risk, record_ids, reached, error_detail=error_detail)

    return StreamingResponse(_sse(), media_type="text/event-stream")


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
        isnad_ar=rec.isnad_ar, collection=rec.collection, hadith_no=rec.hadith_no,
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
