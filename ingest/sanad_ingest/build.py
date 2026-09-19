from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import sqlite3
from pathlib import Path

from sanad.arabic.normalize import normalize
from sanad.corpus import db
from sanad.corpus.models import Record, Source
from sanad.corpus.surahs import surah_name

from .fetch import fetch_source
from .lockfile import LockedSource, load_lockfile
from .tanzil import ParsedTanzil, parse_tanzil

log = logging.getLogger(__name__)


def _register_source(conn: sqlite3.Connection, locked: LockedSource,
                     parsed: ParsedTanzil, today: str) -> None:
    db.insert_source(conn, Source(
        id=locked.id, kind=locked.kind, title=locked.title,
        publisher=locked.publisher, edition=locked.edition, url=locked.url,
        license_id=locked.license_id, license_url=locked.license_url,
        attribution=parsed.attribution, retrieved_at=today,
        upstream_sha256=parsed.content_sha256,
        modifications=locked.modifications,
    ))


def build_corpus(lockfile: Path, out_db: Path, cache_dir: Path) -> dict[str, int]:
    out_db = Path(out_db)
    if out_db.exists():
        out_db.unlink()

    conn = db.connect(out_db, read_only=False)
    today = _dt.datetime.now(tz=_dt.timezone.utc).date().isoformat()
    locked_sources = load_lockfile(lockfile)

    # Pass 1: quran-arabic sources. translations.record_id references
    # records.id, so every ayah record must exist before any translation row
    # referencing it is inserted -- we cannot rely on lockfile order for
    # that, so Arabic and translation sources are handled in separate
    # passes rather than a single loop.
    for locked in locked_sources:
        if locked.kind != "quran-arabic":
            continue

        raw = fetch_source(locked, cache_dir)
        parsed = parse_tanzil(raw)
        _register_source(conn, locked, parsed, today)

        records = []
        for surah, ayah, text in parsed.verses:
            name_ar, name_en = surah_name(surah)
            records.append(Record(
                id=f"quran:{surah}:{ayah}", source_id=locked.id, kind="ayah",
                surah=surah, ayah=ayah, surah_name_ar=name_ar, surah_name_en=name_en,
                text_ar=text,
                text_ar_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                norm_light=normalize(text, "light"),
                norm_standard=normalize(text, "standard"),
                norm_aggressive=normalize(text, "aggressive"),
                reference_display=f"{name_en} {surah}:{ayah}",
            ))
        db.insert_records(conn, records)
        log.info("inserted %d records from %s", len(records), locked.id)

    # Pass 2: quran-translation sources, now that every record they
    # reference exists.
    for locked in locked_sources:
        if locked.kind == "quran-arabic":
            continue
        if locked.kind != "quran-translation":
            log.warning("skipping %s: kind %r not handled in Stage A",
                        locked.id, locked.kind)
            continue

        raw = fetch_source(locked, cache_dir)
        parsed = parse_tanzil(raw)
        _register_source(conn, locked, parsed, today)

        translations = [
            (f"quran:{surah}:{ayah}", locked.id, "en", text)
            for surah, ayah, text in parsed.verses
        ]
        db.insert_translations(conn, translations)
        log.info("inserted %d translations from %s", len(translations), locked.id)

    db.rebuild_fts(conn)
    stats = db.corpus_stats(conn)
    conn.close()
    return stats
