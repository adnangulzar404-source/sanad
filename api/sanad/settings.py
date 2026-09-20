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


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
