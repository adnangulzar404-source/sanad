from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import httpx

from .lockfile import COUNT_FIELD_BY_FORMAT, LockedSource
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


def _count_and_hash(src: LockedSource, raw: str) -> tuple[int, str]:
    """Dispatch on the lockfile's declared format (via parser_for) so each
    export is hash-verified with the parser that matches its actual shape.

    The count is "records the parser found", whatever a record is for that
    format: a verse line for Tanzil, a numbered narration for OpenITI. Every
    parsed result defines __len__ so this function does not have to know.
    """
    parsed = parser_for(src.format)(raw)
    return len(parsed), parsed.content_sha256


def _expected_count(src: LockedSource) -> tuple[str, int]:
    """The count field this source's own format declares, and its value.

    Each format counts a different thing -- Tanzil's exports are one verse
    per line (`expected_lines`), OpenITI's markdown is one narration across
    many lines (`expected_records`) -- so there is no single field to read.
    fetch_source used to compare against `expected_lines` unconditionally,
    which for an OpenITI source (where it is None) mismatched every integer
    count and made the build impossible to run.

    A missing value raises rather than skipping the check. load_lockfile
    already requires the field, but "no count declared, so do not verify"
    is precisely how a truncated download would pass silently -- the one
    failure this whole function exists to catch.
    """
    field = COUNT_FIELD_BY_FORMAT[src.format]
    value = getattr(src, field)
    if value is None:
        raise HashMismatch(
            f"{src.id}: format {src.format!r} requires {field}, but it is unset; "
            "refusing to skip the count check")
    return field, value


def fetch_source(src: LockedSource, cache_dir: Path) -> str:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / _cache_filename(src)

    raw = cached.read_text(encoding="utf-8") if cached.is_file() else _download(src.url)

    count, content_sha256 = _count_and_hash(src, raw)
    count_field, expected = _expected_count(src)
    if count != expected:
        raise HashMismatch(
            f"{src.id}: expected {expected} ({count_field}), got {count}")
    if content_sha256 != src.content_sha256:
        raise HashMismatch(
            f"{src.id}: content sha256 mismatch\n"
            f"  lockfile: {src.content_sha256}\n"
            f"  download: {content_sha256}\n"
            "Upstream changed, or the download is corrupt. Do not update the "
            "lockfile without reviewing the diff.")

    if not cached.is_file():
        cached.write_text(raw, encoding="utf-8")
    log.info("verified %s (%d records)", src.id, count)
    return raw
