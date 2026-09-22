from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

from .models import Record, Source
from .schema import SCHEMA_SQL

_RECORD_COLS = (
    "id", "source_id", "kind", "surah", "ayah", "surah_name_ar", "surah_name_en",
    "collection", "book_no", "chapter_ar", "hadith_no", "numbering_scheme",
    "text_ar", "text_ar_sha256", "bismillah", "isnad_ar", "addenda_ar", "norm_light",
    "norm_standard", "norm_aggressive", "reference_display",
)

# FTS5 treats these as syntax; a user's quote must never be parsed as a query.
_FTS_UNSAFE = re.compile(r'[^\w؀-ۿ ]', re.UNICODE)


def connect(path: str | Path, *, read_only: bool = True) -> sqlite3.Connection:
    path = Path(path)
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA_SQL)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_record(row: sqlite3.Row) -> Record:
    return Record(**{c: row[c] for c in _RECORD_COLS})


def insert_source(conn: sqlite3.Connection, source: Source) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sources (id, kind, title, publisher, edition, url,"
        " license_id, license_url, attribution, retrieved_at, upstream_sha256,"
        " modifications) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (source.id, source.kind, source.title, source.publisher, source.edition,
         source.url, source.license_id, source.license_url, source.attribution,
         source.retrieved_at, source.upstream_sha256, source.modifications),
    )
    conn.commit()


def insert_records(conn: sqlite3.Connection, records: Iterable[Record]) -> int:
    rows = [tuple(getattr(r, c) for c in _RECORD_COLS) for r in records]
    placeholders = ",".join("?" * len(_RECORD_COLS))
    conn.executemany(
        f"INSERT OR REPLACE INTO records ({','.join(_RECORD_COLS)}) "
        f"VALUES ({placeholders})", rows)
    conn.commit()
    return len(rows)


_TRANSLATION_COLS = ("record_id", "source_id", "lang", "text")


def insert_translations(conn: sqlite3.Connection,
                        rows: Iterable[tuple[str, str, str, str]]) -> int:
    rows = list(rows)
    placeholders = ",".join("?" * len(_TRANSLATION_COLS))
    conn.executemany(
        f"INSERT OR REPLACE INTO translations ({','.join(_TRANSLATION_COLS)}) "
        f"VALUES ({placeholders})", rows)
    conn.commit()
    return len(rows)


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM records_fts")
    conn.execute(
        "INSERT INTO records_fts (record_id, norm_standard, norm_aggressive, translation) "
        "SELECT r.id, r.norm_standard, r.norm_aggressive,"
        "       COALESCE((SELECT group_concat(t.text, ' ') FROM translations t"
        "                 WHERE t.record_id = r.id), '')"
        " FROM records r")
    conn.commit()


def iter_records(conn: sqlite3.Connection) -> Iterator[Record]:
    for row in conn.execute(f"SELECT {','.join(_RECORD_COLS)} FROM records"):
        yield _row_to_record(row)


def get_record(conn: sqlite3.Connection, record_id: str) -> Record | None:
    row = conn.execute(
        f"SELECT {','.join(_RECORD_COLS)} FROM records WHERE id = ?",
        (record_id,)).fetchone()
    return _row_to_record(row) if row else None


def fts_candidates(conn: sqlite3.Connection, query_norm: str,
                   limit: int = 50) -> list[Record]:
    """Token-OR search. Input is sanitized: a quotation is data, never a query."""
    tokens = [t for t in _FTS_UNSAFE.sub(" ", query_norm).split() if len(t) > 1]
    if not tokens:
        return []
    match = " OR ".join(f'"{t}"' for t in tokens)
    rows = conn.execute(
        f"SELECT r.{', r.'.join(_RECORD_COLS)} FROM records_fts f"
        " JOIN records r ON r.id = f.record_id"
        " WHERE records_fts MATCH ? ORDER BY bm25(records_fts) LIMIT ?",
        (match, limit)).fetchall()
    return [_row_to_record(r) for r in rows]


def corpus_stats(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "records": conn.execute("SELECT count(*) FROM records").fetchone()[0],
        "sources": conn.execute("SELECT count(*) FROM sources").fetchone()[0],
        "translations": conn.execute("SELECT count(*) FROM translations").fetchone()[0],
    }
