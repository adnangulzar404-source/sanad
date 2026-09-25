from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# Content-addressed embeddings, in their OWN database file, never the corpus DB.
# build_corpus() unlinks the corpus file on every run; keeping vectors here means
# a rebuild does not destroy them and re-embedding is idempotent by text_sha256.
VECTORS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS embeddings (
  record_id    TEXT PRIMARY KEY,
  model        TEXT NOT NULL,
  dim          INTEGER NOT NULL,
  dtype        TEXT NOT NULL,
  text_sha256  TEXT NOT NULL,
  vec          BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class EmbeddingRow:
    record_id: str
    model: str
    dim: int
    dtype: str
    text_sha256: str
    vec: bytes


_COLS = ("record_id", "model", "dim", "dtype", "text_sha256", "vec")


def connect_vectors(path: str | Path, *, read_only: bool = True) -> sqlite3.Connection:
    path = Path(path)
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(VECTORS_SCHEMA_SQL)
    conn.row_factory = sqlite3.Row
    return conn


def upsert_embeddings(conn: sqlite3.Connection, rows: Iterable[EmbeddingRow]) -> int:
    data = [tuple(getattr(r, c) for c in _COLS) for r in rows]
    conn.executemany(
        f"INSERT OR REPLACE INTO embeddings ({','.join(_COLS)}) "
        f"VALUES ({','.join('?' * len(_COLS))})", data)
    conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('count', ?)",
                 (str(conn.execute("SELECT count(*) FROM embeddings").fetchone()[0]),))
    if data:
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('model', ?)", (data[0][1],))
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('dim', ?)", (str(data[0][2]),))
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('dtype', ?)", (data[0][3],))
    conn.commit()
    return len(data)


def _to_row(r: sqlite3.Row) -> EmbeddingRow:
    return EmbeddingRow(**{c: r[c] for c in _COLS})


def get_embedding(conn: sqlite3.Connection, record_id: str) -> EmbeddingRow | None:
    r = conn.execute(
        f"SELECT {','.join(_COLS)} FROM embeddings WHERE record_id = ?",
        (record_id,)).fetchone()
    return _to_row(r) if r else None


def iter_embeddings(conn: sqlite3.Connection) -> Iterator[EmbeddingRow]:
    for r in conn.execute(f"SELECT {','.join(_COLS)} FROM embeddings ORDER BY record_id"):
        yield _to_row(r)


def vectors_meta(conn: sqlite3.Connection) -> dict:
    rows = {r["k"]: r["v"] for r in conn.execute("SELECT k, v FROM meta")}
    return {
        "model": rows.get("model"),
        "dim": int(rows["dim"]) if "dim" in rows else None,
        "dtype": rows.get("dtype"),
        "count": int(rows.get("count", 0)),
        "generated_at": rows.get("generated_at"),
    }
