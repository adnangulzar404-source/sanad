"""Find Qur'an references in prose: "2:255", "Al-Baqarah 2:255", "Al-Ikhlas"."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..corpus.surahs import SURAH_NAMES

# Verses per surah. Generated from the built corpus by the step below -- never
# typed by hand, so it cannot disagree with the text we actually shipped.
from .ayah_counts import AYAH_COUNTS

# Separator between surah and ayah numbers. The fullwidth colon (U+FF1A) is
# written as an explicit backslash-u escape in the pattern text below, never
# as a literal glyph, so it cannot be silently dropped by adjacent-string-
# literal concatenation -- see the warning in the Stage A plan, Task 8. The
# `re` module interprets that escape when it compiles the pattern, so this
# works even though the surrounding Python string is itself a raw string.
#   U+003A  ASCII COLON      -- typed literally below, unambiguous
#   U+FF1A  FULLWIDTH COLON  -- typed as an escape, visually near-identical to ':'
_NUMERIC = re.compile(r"\b(\d{1,3})\s*[:\uFF1A]\s*(\d{1,3})\b")

# A bare English word is only treated as a surah name if it carries the "al-"
# article or is reasonably long. Without this, "Sad" (38), "Hud" (11), "Nuh"
# (71) and "Qaf" (50) would fire on ordinary English prose.
_MIN_BARE_NAME = 5

_NAME_CANDIDATE = re.compile(r"\b(?:al[-\s]?)?[A-Za-z]{3,}\b", re.IGNORECASE)


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def _spelling_variants(english_name: str) -> set[str]:
    """Accept Fatiha/Fatihah, Baqara/Baqarah, with or without the article."""
    base = _slug(english_name)
    out = {base}
    if base.endswith("h"):
        out.add(base[:-1])
    for prefix in ("al", "ad", "adh", "an", "ar", "as", "ash", "at", "az"):
        if base.startswith(prefix):
            stem = base[len(prefix):]
            if len(stem) >= 3:
                out.add(stem)
                if stem.endswith("h"):
                    out.add(stem[:-1])
    return out


_NAME_TO_SURAH: dict[str, int] = {}
for _num, (_ar, _en) in SURAH_NAMES.items():
    for _variant in _spelling_variants(_en):
        _NAME_TO_SURAH.setdefault(_variant, _num)


@dataclass(frozen=True)
class Reference:
    surah: int
    ayah: int | None
    raw: str
    start: int


def _valid(surah: int, ayah: int | None) -> bool:
    if surah not in AYAH_COUNTS:
        return False
    return ayah is None or 1 <= ayah <= AYAH_COUNTS[surah]


def parse_references(text: str) -> list[Reference]:
    refs: list[Reference] = []
    claimed: list[tuple[int, int]] = []

    for m in _NUMERIC.finditer(text):
        surah, ayah = int(m.group(1)), int(m.group(2))
        if _valid(surah, ayah):
            refs.append(Reference(surah, ayah, m.group(0), m.start()))
            claimed.append((m.start(), m.end()))

    for m in _NAME_CANDIDATE.finditer(text):
        slug = _slug(m.group(0))
        num = _NAME_TO_SURAH.get(slug)
        if num is None:
            continue
        if not slug.startswith("al") and len(slug) < _MIN_BARE_NAME:
            continue  # "sad", "hud", "nuh", "qaf" as ordinary English words
        # a named surah adjacent to a numeric ref we already captured is a duplicate
        if any(abs(m.start() - s) < 24 for s, _e in claimed):
            continue
        refs.append(Reference(num, None, m.group(0), m.start()))

    return sorted(refs, key=lambda r: r.start)


def nearest_reference(
    refs: list[Reference], position: int, window: int = 180
) -> Reference | None:
    candidates = [r for r in refs if abs(r.start - position) <= window]
    if not candidates:
        return None
    return min(candidates, key=lambda r: abs(r.start - position))
