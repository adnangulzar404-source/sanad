from __future__ import annotations

import logging
from pathlib import Path

import httpx

from .lockfile import LockedSource
from .tanzil import parse_tanzil

log = logging.getLogger(__name__)


class HashMismatch(Exception):
    pass


def _download(url: str) -> str:
    resp = httpx.get(url, follow_redirects=True, timeout=120.0)
    resp.raise_for_status()
    return resp.text


def fetch_source(src: LockedSource, cache_dir: Path) -> str:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{src.id}.txt"

    raw = cached.read_text(encoding="utf-8") if cached.is_file() else _download(src.url)

    parsed = parse_tanzil(raw)
    if len(parsed.verses) != src.expected_lines:
        raise HashMismatch(
            f"{src.id}: expected {src.expected_lines} verse lines, "
            f"got {len(parsed.verses)}")
    if parsed.content_sha256 != src.content_sha256:
        raise HashMismatch(
            f"{src.id}: content sha256 mismatch\n"
            f"  lockfile: {src.content_sha256}\n"
            f"  download: {parsed.content_sha256}\n"
            "Upstream changed, or the download is corrupt. Do not update the "
            "lockfile without reviewing the diff.")

    if not cached.is_file():
        cached.write_text(raw, encoding="utf-8")
    log.info("verified %s (%d verses)", src.id, len(parsed.verses))
    return raw
