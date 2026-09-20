from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..corpus.schema import SCHEMA_SQL
from ..settings import file_sha256, resolve_db_path
from .routes import router

log = logging.getLogger(__name__)
_APP: FastAPI | None = None


def _open_conn(path: Path) -> sqlite3.Connection:
    """A writable connection, safe across FastAPI's per-request threadpool.

    `corpus.db.connect()` is correct for the single-threaded ingest and test
    callers it was written for, where the connection is opened and used in
    the same thread. A live HTTP server's synchronous route handlers run in
    Starlette's threadpool -- a different worker thread per request than the
    one that opened the connection at startup -- so SQLite's default
    `check_same_thread=True` raises `ProgrammingError` on the very first
    request. `check_same_thread=False` is the standard fix for SQLite behind
    a web framework (see FastAPI's own SQL databases tutorial), not a hack,
    and audit-log writes are still safe: requests are handled one at a time
    per worker here, so there is no concurrent write to the same connection.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA_SQL)
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

    path = resolve_db_path()
    # audit_log is written, so the connection cannot be read-only.
    app.state.conn = _open_conn(path)
    app.state.db_path = path
    app.state.db_sha256 = file_sha256(path)
    log.info("corpus %s sha256=%s", path, app.state.db_sha256)

    app.include_router(router)
    _APP = app
    return app


def _conn_for_tests():
    """Test hook: the live connection, for asserting on audit_log contents."""
    assert _APP is not None, "create_app() has not run"
    return _APP.state.conn
