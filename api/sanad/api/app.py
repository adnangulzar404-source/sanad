from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..corpus.schema import AUDIT_SCHEMA_SQL
from ..settings import file_sha256, resolve_audit_db_path, resolve_db_path
from .routes import router

log = logging.getLogger(__name__)
_APP: FastAPI | None = None


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
    framework (see FastAPI's own SQL databases tutorial), not a hack, and
    audit-log writes are still safe: requests are handled one at a time per
    worker here, so there is no concurrent write to the same connection.
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
    app.state.db_path = corpus_path
    app.state.db_sha256 = file_sha256(corpus_path)
    log.info("corpus %s sha256=%s (read-only)", corpus_path, app.state.db_sha256)
    log.info("audit log %s", audit_path)

    app.include_router(router)
    _APP = app
    return app


def _conn_for_tests():
    """Test hook: the live audit connection, for asserting on audit_log contents."""
    assert _APP is not None, "create_app() has not run"
    return _APP.state.audit_conn
