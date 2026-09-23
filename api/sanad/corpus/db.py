from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

from .models import PRIMARY_VARIANT, Candidate, Record, RecordVariant, Source
from .schema import SCHEMA_SQL

_RECORD_COLS = (
    "id", "source_id", "kind", "surah", "ayah", "surah_name_ar", "surah_name_en",
    "collection", "book_no", "chapter_ar", "hadith_no", "numbering_scheme",
    "text_ar", "text_ar_sha256", "bismillah", "isnad_ar", "addenda_ar",
    "unscorable_reason", "norm_light",
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


_VARIANT_COLS = ("record_id", "variant", "text_ar", "norm_light",
                 "norm_standard", "norm_aggressive")


def insert_record_variants(conn: sqlite3.Connection,
                           variants: Iterable[RecordVariant]) -> int:
    rows = [tuple(getattr(v, c) for c in _VARIANT_COLS) for v in variants]
    placeholders = ",".join("?" * len(_VARIANT_COLS))
    conn.executemany(
        f"INSERT OR REPLACE INTO record_variants ({','.join(_VARIANT_COLS)}) "
        f"VALUES ({placeholders})", rows)
    conn.commit()
    return len(rows)


def get_record_variants(conn: sqlite3.Connection,
                        record_id: str) -> list[RecordVariant]:
    rows = conn.execute(
        f"SELECT {','.join(_VARIANT_COLS)} FROM record_variants"
        " WHERE record_id = ? ORDER BY variant", (record_id,)).fetchall()
    return [RecordVariant(**{c: r[c] for c in _VARIANT_COLS}) for r in rows]


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
    """Rebuild the search index over every SCORABLE REPRESENTATION's own norms.

    Two inserts, one per source of a representation: `records` supplies the
    primary, `record_variants` supplies every additional one (today, the full
    printed text of a record whose matn was cut). A record with an addendum
    therefore has two index rows -- see `models.RecordVariant` for why both
    have to be searchable -- and `records_fts.variant` says which is which so
    a hit can be scored against the text that was actually indexed.

    `unscorable_reason IS NULL` filters the FIRST insert only, and that
    asymmetry is the point. The reason is a judgement about one string -- the
    primary matn, pinned by its sha256 in the ingest audit -- so it excludes
    the primary and says nothing about the full printed text, which is a
    different string. Record 237 is the case: its primary is a "bayna" clause
    ending at the chain-transfer mark and is rightly unscorable, while its
    869-character full narration is the longest in the edition and is an
    ordinary, quotable hadith. Excluding both put that narration out of reach
    of every tier.

    An excluded primary is still in `records`, still fetched by `get_record`,
    still displayed.
    """
    conn.execute("DELETE FROM records_fts")
    conn.execute(
        "INSERT INTO records_fts (record_id, variant, norm_standard,"
        "                         norm_aggressive, translation) "
        "SELECT r.id, ?, r.norm_standard, r.norm_aggressive,"
        "       COALESCE((SELECT group_concat(t.text, ' ') FROM translations t"
        "                 WHERE t.record_id = r.id), '')"
        " FROM records r WHERE r.unscorable_reason IS NULL", (PRIMARY_VARIANT,))
    conn.execute(
        "INSERT INTO records_fts (record_id, variant, norm_standard,"
        "                         norm_aggressive, translation) "
        "SELECT v.record_id, v.variant, v.norm_standard, v.norm_aggressive, ''"
        " FROM record_variants v")
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
                   limit: int = 50) -> list[Candidate]:
    """Token-OR search. Input is sanitized: a quotation is data, never a query.

    Returns one `Candidate` per matching REPRESENTATION, carrying that
    representation's own text and aggressive norm. A record with an addendum
    can appear twice, once per representation; callers that report records
    (rather than score text) must collapse them -- `fts_records` does, and
    `verify.engine._best_fuzzy` does.

    The `LEFT JOIN` resolves `f.variant` back to its row: NULL for the
    primary, whose text lives in `records`, so `COALESCE` picks the right
    side without a second query or a UNION.
    """
    tokens = [t for t in _FTS_UNSAFE.sub(" ", query_norm).split() if len(t) > 1]
    if not tokens:
        return []
    match = " OR ".join(f'"{t}"' for t in tokens)
    rows = conn.execute(
        f"SELECT r.{', r.'.join(_RECORD_COLS)}, f.variant AS _variant,"
        "        COALESCE(v.text_ar, r.text_ar) AS _match_text,"
        "        COALESCE(v.norm_aggressive, r.norm_aggressive) AS _match_norm"
        " FROM records_fts f"
        " JOIN records r ON r.id = f.record_id"
        " LEFT JOIN record_variants v"
        "        ON v.record_id = f.record_id AND v.variant = f.variant"
        " WHERE records_fts MATCH ? ORDER BY bm25(records_fts) LIMIT ?",
        (match, limit)).fetchall()
    return [Candidate(record=_row_to_record(r), variant=r["_variant"],
                      text_ar=r["_match_text"], norm_aggressive=r["_match_norm"])
            for r in rows]


def fts_records(conn: sqlite3.Connection, query_norm: str,
                limit: int = 50) -> list[Record]:
    """`fts_candidates` collapsed to distinct records, best rank first.

    For callers that list records -- `GET /api/search` -- where the same
    hadith matching on both its primary matn and its full printed text is one
    result, not two. Over-fetches so that collapsing cannot silently return
    fewer rows than asked for.
    """
    seen: dict[str, Record] = {}
    for cand in fts_candidates(conn, query_norm, limit * 2):
        seen.setdefault(cand.record.id, cand.record)
        if len(seen) == limit:
            break
    return list(seen.values())


def corpus_stats(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "records": conn.execute("SELECT count(*) FROM records").fetchone()[0],
        "sources": conn.execute("SELECT count(*) FROM sources").fetchone()[0],
        "translations": conn.execute("SELECT count(*) FROM translations").fetchone()[0],
    }
