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

# A bare English word is only accepted as a surah name if it is MARKED as one
# (see _carries_article and _preceded_by_qualifier below): it carries the
# Arabic definite article, is preceded by a surah-indicating word, or sits
# next to a numeric reference.
# An unprefixed, unqualified name like "Maryam" or "Yusuf" -- also ordinary
# personal names -- is rejected even though it resolves to a real surah,
# because a spurious reference here causes the engine to report an actively
# wrong WRONG_REFERENCE verdict, whereas a missed reference only downgrades
# to a plain (correct) verified match. This is the opposite trade-off from
# extraction (Task 7), deliberately: a miss costs less than noise here.
#
# The length floor below is now a SECONDARY guard, not the primary one: it
# still keeps short, common English words -- "Sad" (38), "Hud" (11), "Nuh"
# (71), "Qaf" (50) -- from firing even if some future variant table entry
# made them look "marked".
_MIN_BARE_NAME = 5

# Longest-prefix-first, so "adh"/"ash" are tried before their substrings
# "ad"/"as" -- otherwise the shorter alternative would win and strand an
# "h" in front of the stem (e.g. "adh-Dhariyat" -> stray "h" + "Dhariyat").
_ARTICLES = ("adh", "ash", "al", "an", "ar", "as", "at", "az", "ad")
_ARTICLE_GROUP = "|".join(_ARTICLES)

_NAME_CANDIDATE = re.compile(
    rf"\b(?:(?:{_ARTICLE_GROUP})[-\s]?)?[A-Za-z]{{3,}}\b", re.IGNORECASE
)

# Words that mark the next name as a surah reference (rule 2). The
# alternative spelling with a macroned u (U+016B, LATIN SMALL LETTER U
# WITH MACRON) and the alternative apostrophe (U+2019, RIGHT SINGLE
# QUOTATION MARK) are both written as explicit backslash-u escapes in the
# tuple below, never as literal glyphs, per the character-safety rule for
# this module. The plain ASCII apostrophe in "qur'an" is left as a
# literal since it is visually unambiguous.
_QUALIFIER_WORDS = (
    "surahs", "surah", "suras", "sura", "surat", "s\u016brah",
    "chapters", "chapter",
    "qur'an", "qur\u2019an", "quran",
    "q",
)
_QUALIFIER_BEFORE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _QUALIFIER_WORDS) + r")\s*$",
    re.IGNORECASE,
)
_QUALIFIER_LOOKBEHIND = 24  # "a few tokens" of preceding text, in characters


def _carries_article(slug: str) -> bool:
    """Rule 1: does the matched surface text itself carry the definite article?"""
    return any(slug.startswith(a) and len(slug) > len(a) for a in _ARTICLES)


def _preceded_by_qualifier(text: str, start: int) -> bool:
    """Rule 2: is a surah-indicating word ("surah", "chapter", ...) just before it?"""
    window = text[max(0, start - _QUALIFIER_LOOKBEHIND):start]
    return _QUALIFIER_BEFORE.search(window) is not None


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
        if not _carries_article(slug) and len(slug) < _MIN_BARE_NAME:
            continue  # secondary guard: "sad", "hud", "nuh", "qaf" as English words
        # rule 3 is handled by this dedup: a name next to a numeric ref we already
        # captured (which independently resolved surah *and* ayah) is a duplicate
        if any(abs(m.start() - s) < 24 for s, _e in claimed):
            continue
        # rules 1 and 2: an unmarked bare name is an ordinary personal name
        # ("Maryam", "Yusuf", "Ibrahim", ...) far more often than a citation --
        # a spurious reference here yields an actively wrong WRONG_REFERENCE
        # verdict downstream, so require the article or an explicit qualifier.
        if not (_carries_article(slug) or _preceded_by_qualifier(text, m.start())):
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
