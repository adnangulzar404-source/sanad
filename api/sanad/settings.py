"""Where the API finds its corpus database.

Kept separate from `api/` proper so it has no FastAPI dependency: the ingest
CLI and any future service can resolve the same path the same way.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


class CorpusNotFound(Exception):
    pass


def resolve_db_path() -> Path:
    """`SANAD_DB` env var if set, else `data/sanad.db`, else `data/sanad-quran.db`."""
    override = os.environ.get("SANAD_DB")
    if override:
        p = Path(override)
        if not p.is_file():
            raise CorpusNotFound(f"SANAD_DB points at a missing file: {p}")
        return p
    for candidate in (Path("data/sanad.db"), Path("data/sanad-quran.db")):
        if candidate.is_file():
            return candidate
    raise CorpusNotFound(
        "no corpus found. Run: sanad-ingest build --out data/sanad-quran.db")


def resolve_audit_db_path() -> Path:
    """`SANAD_AUDIT_DB` env var if set, else `data/sanad-audit.db`.

    Unlike `resolve_db_path()`, this path is generated state, not shipped
    data: the audit log records verdicts and record ids for every
    `/api/verify` call, so it is created on first use rather than required
    to already exist. Kept in a separate file from the corpus database on
    purpose -- see `corpus.schema.AUDIT_SCHEMA_SQL` for why.
    """
    override = os.environ.get("SANAD_AUDIT_DB")
    if override:
        return Path(override)
    return Path("data/sanad-audit.db")


def resolve_vectors_db_path() -> Path | None:
    """`SANAD_VECTORS_DB` env var if set and an existing file, else
    `data/sanad-vectors.db` if it exists, else `None`.

    Unlike `resolve_db_path`, absence is not an error: the vectors sidecar
    (`retrieve.vector_store`) is optional -- Ask degrades to lexical-only
    retrieval when it is missing (spec's Availability note), it does not
    fail to start.
    """
    override = os.environ.get("SANAD_VECTORS_DB")
    if override:
        p = Path(override)
        return p if p.is_file() else None
    p = Path("data/sanad-vectors.db")
    return p if p.is_file() else None


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
