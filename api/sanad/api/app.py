from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from ..corpus.schema import AUDIT_SCHEMA_SQL
from ..retrieve.vector_store import connect_vectors
from ..settings import (
    file_sha256,
    resolve_audit_db_path,
    resolve_db_path,
    resolve_vectors_db_path,
)
from .routes import router

log = logging.getLogger(__name__)
_APP: FastAPI | None = None


class _SPAStaticFiles(StaticFiles):
    """`StaticFiles(html=True)` only serves `index.html` for the mount's own
    root and per-directory index files -- it has no notion of a single-page
    app's client-side routes (e.g. `/verify/quran:112:1`), so a request for
    one of those 404s instead of loading the app shell. This is the
    standard `try_files $uri /index.html;` fallback: any GET/HEAD that does
    not resolve to a real file on disk still gets `index.html`, so a
    hard refresh on a client-side route works.

    Never falls back for a path under `api/` -- this mount only ever sees
    those when no `/api/*` route matched (see `create_app`'s mount-order
    comment), and such a request must still 404 as JSON, not silently
    return the HTML shell.
    """

    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            is_api = path == "api" or path.startswith(("api/", "api\\"))
            if exc.status_code == 404 and not is_api:
                return await super().get_response("index.html", scope)
            raise


def _open_corpus_conn(path: Path) -> sqlite3.Connection:
    """A READ-ONLY connection to the shipped corpus, safe across FastAPI's
    per-request threadpool.

    Read-only is structural here, not a promise: SQLite's `mode=ro` URI flag
    makes any write attempt raise `sqlite3.OperationalError` regardless of
    what application code does. The corpus's SHA-256 is meant to be a
    stable, reproducible fact about a build from the lockfile (see
    `sanad-ingest build`); a connection able to write to it would make the
    API itself the thing that breaks that promise on first use -- which is
    exactly the defect this split (corpus file vs. audit file) fixes.
    `check_same_thread=False` for the same reason as `_open_audit_conn`
    below: a live server's synchronous route handlers run in Starlette's
    threadpool, a different thread than the one that opened the connection.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _open_audit_conn(path: Path) -> sqlite3.Connection:
    """A writable connection to the (generated, not shipped) audit database.

    Deliberately a separate file from the corpus: a table that every
    request writes to cannot live in a file whose hash is supposed to be a
    stable, reproducible fact. See `settings.resolve_audit_db_path` and
    `corpus.schema.AUDIT_SCHEMA_SQL`.

    `check_same_thread=False`: a live HTTP server's synchronous route
    handlers run in Starlette's threadpool -- a different worker thread per
    request than the one that opened the connection at startup -- so
    SQLite's default `check_same_thread=True` raises `ProgrammingError` on
    the very first request. This is the standard fix for SQLite behind a web
    framework (see FastAPI's own SQL databases tutorial), not a hack.

    IMPORTANT -- `check_same_thread=False` on its own is NOT enough. It only
    disables SQLite's thread-affinity *check*; it does nothing to make one
    shared connection safe for concurrent `execute`/`commit` calls from
    Starlette's threadpool, which really does run multiple worker threads at
    once. Under real concurrency, two threads' writes can interleave and one
    thread's `commit()` finds no transaction of its own left to commit,
    raising `sqlite3.OperationalError: cannot commit - no transaction is
    active` (or, worse, silently committing the wrong row). A prior revision
    of this comment claimed "requests are handled one at a time per worker,
    so there is no concurrent write" -- that was false; nothing here
    serialized anything. The actual safety net is `app.state.audit_lock`,
    held across the write AND its commit as one unit -- see `routes.verify()`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(AUDIT_SCHEMA_SQL)
    conn.row_factory = sqlite3.Row
    return conn


def create_app() -> FastAPI:
    global _APP
    app = FastAPI(
        title="Sanad", version="0.1.0",
        description="Evidence-first verification of Islamic textual claims.",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    corpus_path = resolve_db_path()
    audit_path = resolve_audit_db_path()

    # The corpus is shipped, read-only data; the audit log is generated,
    # writable state. Two files, two connections -- see the two _open_*
    # helpers above for why serving a request must never touch the corpus
    # file's bytes.
    app.state.conn = _open_corpus_conn(corpus_path)
    app.state.audit_conn = _open_audit_conn(audit_path)
    # Guards every audit write-and-commit as one atomic unit against
    # Starlette's threadpool. Locking only the `execute()` is not enough --
    # see `_open_audit_conn`'s docstring for why the commit must be inside
    # the same critical section.
    app.state.audit_lock = threading.Lock()
    app.state.db_path = corpus_path
    app.state.db_sha256 = file_sha256(corpus_path)
    log.info("corpus %s sha256=%s (read-only)", corpus_path, app.state.db_sha256)
    log.info("audit log %s", audit_path)

    # The vectors sidecar is optional (spec's Availability note): Ask degrades
    # to lexical-only retrieval when it is absent, rather than failing to
    # start. Read-only for the same reason the corpus connection is -- a
    # live server has no business writing to a build artifact.
    vectors_path = resolve_vectors_db_path()
    app.state.vectors_conn = (
        connect_vectors(vectors_path, read_only=True) if vectors_path else None)
    log.info("vectors %s", vectors_path or "(absent -- Ask runs lexical-only)")

    app.include_router(router)

    # Serve the built frontend when it is present. Mounted last so /api/*
    # always wins over the SPA catch-all. Guarded because the tests and a
    # bare `uvicorn` run have no build. Vercel's Python preset routes every
    # request to this app, so the app itself -- not vercel.json -- is
    # responsible for serving the static React build outside /api/*. See
    # the Stage C spec: "the frontend is a static build that can be served
    # by the API or by any CDN."
    _dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    if _dist.is_dir():
        app.mount("/", _SPAStaticFiles(directory=_dist, html=True), name="web")

    _APP = app
    return app


def _conn_for_tests():
    """Test hook: the live audit connection, for asserting on audit_log contents."""
    assert _APP is not None, "create_app() has not run"
    return _APP.state.audit_conn
