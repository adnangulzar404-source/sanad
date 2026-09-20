from __future__ import annotations

import hashlib
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


def _cache_filename(src: LockedSource) -> str:
    """Cache filename keyed on id, format, AND a short hash of the url.

    Keying on `src.id` alone leaves a stale cache file behind when a source's
    export format changes while its id stays the same -- exactly what
    happened during ruling R13, when the pinned Arabic source moved from
    Tanzil's txt-2 export to its xml export. A cached txt-2 payload sitting
    under the same id would then be handed to the xml parser (or a cached
    xml payload to the txt-2 parser): not just stale content, a shape
    mismatch. Folding `format` into the filename gives a format change its
    own cache slot; the short url hash additionally covers a URL change at
    the same id/format (e.g. a new edition hosted at a different path).
    """
    url_hash = hashlib.sha256(src.url.encode("utf-8")).hexdigest()[:8]
    return f"{src.id}-{src.format}-{url_hash}.txt"


def _verse_count_and_hash(src: LockedSource, raw: str) -> tuple[int, str]:
    """Dispatch on the lockfile's declared format (via parser_for) so each
    export is hash-verified with the parser that matches its actual shape."""
    parsed = parser_for(src.format)(raw)
    return len(parsed), parsed.content_sha256


def fetch_source(src: LockedSource, cache_dir: Path) -> str:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / _cache_filename(src)

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
