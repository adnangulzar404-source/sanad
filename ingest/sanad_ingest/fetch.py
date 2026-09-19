from __future__ import annotations

import logging
from pathlib import Path

import httpx

from .lockfile import LockedSource
from .tanzil import parser_for

log = logging.getLogger(__name__)


class HashMismatch(Exception):
    pass


def _download(url: str) -> str:
    resp = httpx.get(url, follow_redirects=True, timeout=120.0)
    resp.raise_for_status()
    return resp.text


def _verse_count_and_hash(src: LockedSource, raw: str) -> tuple[int, str]:
    """Dispatch on the lockfile's declared format (via parser_for) so each
    export is hash-verified with the parser that matches its actual shape."""
    parsed = parser_for(src.format)(raw)
    return len(parsed), parsed.content_sha256


def fetch_source(src: LockedSource, cache_dir: Path) -> str:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{src.id}.txt"

    raw = cached.read_text(encoding="utf-8") if cached.is_file() else _download(src.url)

    verse_count, content_sha256 = _verse_count_and_hash(src, raw)
    if verse_count != src.expected_lines:
        raise HashMismatch(
            f"{src.id}: expected {src.expected_lines} verse lines, "
            f"got {verse_count}")
    if content_sha256 != src.content_sha256:
        raise HashMismatch(
            f"{src.id}: content sha256 mismatch\n"
            f"  lockfile: {src.content_sha256}\n"
            f"  download: {content_sha256}\n"
            "Upstream changed, or the download is corrupt. Do not update the "
            "lockfile without reviewing the diff.")

    if not cached.is_file():
        cached.write_text(raw, encoding="utf-8")
    log.info("verified %s (%d verses)", src.id, verse_count)
    return raw
