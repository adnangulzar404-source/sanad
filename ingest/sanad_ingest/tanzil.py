"""Parser for Tanzil's "text with aya numbers" export.

Format, verified 2026-09-19: UTF-8, LF, one verse per line as
"surah|ayah|text", followed by a 28-line copyright block whose lines begin
with "#". The block embeds the current year, so it is excluded from the
content hash but captured verbatim for attribution.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_VERSE = re.compile(r"^(\d{1,3})\|(\d{1,3})\|(.*)$")


class TanzilParseError(Exception):
    pass


@dataclass(frozen=True)
class ParsedTanzil:
    verses: list[tuple[int, int, str]]
    attribution: str
    content_sha256: str


def parse_tanzil(raw: str) -> ParsedTanzil:
    verses: list[tuple[int, int, str]] = []
    notice: list[str] = []

    for lineno, line in enumerate(raw.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            # Preserve the line exactly as it appears, including trailing whitespace
            notice.append(line)
            continue
        m = _VERSE.match(line)
        if not m:
            raise TanzilParseError(f"unrecognized content at line {lineno}: {line[:40]!r}")
        # split on the first two pipes only; the text may legitimately contain one
        verses.append((int(m.group(1)), int(m.group(2)), m.group(3).strip()))

    if not verses:
        raise TanzilParseError("no verse lines found in input")

    payload = "\n".join(f"{s}|{a}|{t}" for s, a, t in verses)
    return ParsedTanzil(
        verses=verses,
        attribution="\n".join(notice),
        content_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )
