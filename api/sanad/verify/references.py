"""Find Qur'an and hadith references in prose: "2:255", "Al-Baqarah 2:255",
"Al-Ikhlas", "Bukhari 619"."""
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


@dataclass(frozen=True)
class HadithReference:
    collection: str
    hadith_no: str
    raw: str
    start: int


# A parsed citation like "Bukhari 619" only names a collection and a printed
# hadith number -- it is NOT a foreign key to exactly one corpus record.
# hadith_no is not unique in this edition (7,124 distinct numbers across
# 7,129 records; the repeats get occurrence-ordinal suffixes in the record
# id and reference_display, not in the printed number). Resolving a parsed
# citation to the record(s) it names is a later step's job, not this one's.
AnyReference = Reference | HadithReference


def _valid(surah: int, ayah: int | None) -> bool:
    if surah not in AYAH_COUNTS:
        return False
    return ayah is None or 1 <= ayah <= AYAH_COUNTS[surah]


# Collection names that mark a following number as a hadith citation. Bare
# names are rejected by requiring the number, mirroring the surah-name rule:
# a spurious reference produces an actively wrong WRONG_REFERENCE, whereas a
# missed one only downgrades to a correct plain match.
_COLLECTIONS = {
    "bukhari": "bukhari",
    "albukhari": "bukhari",
    "sahihbukhari": "bukhari",
    "sahihalbukhari": "bukhari",
}

# The optional second numeric group is the hadith number of a "kitab:hadith"
# pair (e.g. "Bukhari 1:1"). Same separator as `_NUMERIC` above -- the ASCII
# colon plus the fullwidth colon (U+FF1A) written as an explicit backslash-u
# escape, never as a literal glyph, per this module's character-safety rule.
_HADITH_CITE = re.compile(
    r"\b(?P<name>(?:sahih\s+)?(?:al[-\s]?)?bukhari)\b"
    r"(?:\s*,)?\s*"
    r"(?:(?:book|kitab)\s*\d{1,3}\s*,?\s*)?"
    r"(?:(?:hadith|hadeeth|no\.?|number|#)\s*)?"
    r"(\d{1,4})"
    r"(?:\s*[:\uFF1A]\s*(\d{1,4}))?",
    re.IGNORECASE,
)

# Arabic-script equivalent of `_HADITH_CITE` above, for citations written in
# Arabic rather than transliterated into Latin script: "sahih al-bukhari
# <n>", "al-bukhari <n>", "rawahu al-bukhari <n>" (Arabic for "Sahih
# al-Bukhari", "al-Bukhari", and "narrated by al-Bukhari", each followed by
# a hadith number). Every Arabic string below is written as an explicit backslash-u
# escape, never as a literal glyph, per this module's character-safety rule
# (see the note by `_NUMERIC` above): this is new code added on a project
# that has already shipped eleven defects from Arabic characters silently
# altered in transit, so these literals are generated from verified
# codepoints rather than typed by hand. In order: sahih (U+0635 U+062D
# U+064A U+062D), rawahu (U+0631 U+0648 U+0627 U+0647), the definite
# article al- (U+0627 U+0644), bukhari (U+0628 U+062E U+0627 U+0631
# U+064A), hadith (U+062D U+062F U+064A U+062B), raqam/"number" (U+0631
# U+0642 U+0645). The Arabic definite article is written attached to the
# noun (unlike English "al-", which needs a hyphen/space/absence
# alternation), so it is just an optional one-token prefix on the name
# itself rather than a separate alternation.
#
# The digit group is the exact same `\d{1,4}` character class as
# `_HADITH_CITE` and `_NUMERIC` above -- Python's `re` already treats
# Arabic-Indic (U+0660-0669) and Eastern Arabic (U+06F0-06F9) digits as
# `\d`, and `int()` already parses them (see
# `test_arabic_indic_digits_parse_correctly`, which exercises this on the
# Qur'an path) -- so no separate digit-normalizing routine is written here.
_COLLECTIONS_AR = {
    "\u0627\u0644\u0628\u062E\u0627\u0631\u064A": "bukhari",  # al-bukhari
    "\u0628\u062E\u0627\u0631\u064A": "bukhari",  # bukhari, no article
}
_HADITH_CITE_AR = re.compile(
    r"\b(?:\u0635\u062D\u064A\u062D\s+|\u0631\u0648\u0627\u0647\s+)?"
    r"(?P<name>(?:\u0627\u0644)?\u0628\u062E\u0627\u0631\u064A)\b"
    r"\s*"
    r"(?:(?:\u062D\u062F\u064A\u062B|\u0631\u0642\u0645)\s*)?"
    r"(\d{1,4})"
    r"(?:\s*[:\uFF1A]\s*(\d{1,4}))?"
)

MAX_HADITH_NO = 7124
# There is no hadith 0. The upper bound was enforced from the start and the
# lower one was not, so "Bukhari 0" parsed to hadith_no='0' -- a reference to
# a record that cannot exist, which downstream can only ever produce a
# spurious WRONG_REFERENCE. Same trade-off as bare surah names above: a missed
# citation costs a downgrade to a correct plain match, a spurious one costs a
# false accusation of misattribution.
MIN_HADITH_NO = 1


def _resolve_collection(name: str) -> str | None:
    """Collection lookup shared by the Latin and Arabic hadith-citation
    passes below. The Arabic name is looked up as a literal, exact string --
    never normalized or re-spelled. The Latin name is looked up via the same
    case/spelling-folding slug already used for surah names elsewhere in
    this module; slugging an Arabic string yields "" (ASCII-only filter),
    which simply misses `_COLLECTIONS`, so the two lookups cannot collide.
    """
    return _COLLECTIONS_AR.get(name) or _COLLECTIONS.get(_slug(name))


def _collect_hadith_citations(
    pattern: re.Pattern[str],
    text: str,
    refs: list[AnyReference],
    claimed: list[tuple[int, int]],
) -> None:
    """Run one hadith-citation pattern (Latin or Arabic) over `text`,
    appending any `HadithReference` it finds to `refs` and claiming its span
    in `claimed` regardless of whether it resolved -- so the verse-numeric
    pass below never re-reads text a hadith citation already consumed, valid
    or not (see `parse_references`).
    """
    for m in pattern.finditer(text):
        claimed.append((m.start(), m.end()))
        collection = _resolve_collection(m.group("name"))
        if collection is None:
            continue  # defensive: the regex only ever matches known spellings
        # A kitab:hadith pair's SECOND number is the hadith number; the first
        # is the book/kitab number and is discarded (Task 5 parses only).
        printed = m.group(3) if m.group(3) is not None else m.group(2)
        # `int()` already understands Arabic-Indic and Eastern Arabic digits
        # (same as `_NUMERIC`'s surah/ayah conversion below), so a citation
        # written with Arabic-Indic digits and one written with ASCII digits
        # resolve to the same `hadith_no` -- the numeral SCRIPT a citation
        # happens to use is not part of the text being verified, unlike the
        # matn/ayah wording itself, which this module never re-spells. `raw`
        # still preserves the untouched matched text for display/audit.
        value = int(printed)
        if not MIN_HADITH_NO <= value <= MAX_HADITH_NO:
            continue  # out of range -- never falls back to a verse reading
        refs.append(HadithReference(collection, str(value), m.group(0), m.start()))


@dataclass(frozen=True)
class ParsedCitations:
    """What a piece of prose says about where its quotations come from.

    Two different questions, which used to have one answer between them:

    `references` -- the citations that RESOLVED to something addressable. This
    is what `parse_references` returns and what the engine compares records
    against.

    `spans` -- every character range that READS as a citation, resolved or
    not. A citation whose number is out of range ("sahih al-bukhari 99999")
    resolves to nothing, but it is still unmistakably a citation, and the
    difference matters downstream: an Arabic-script citation is itself a run
    of Arabic script, so anything not recognised here is handed to the
    verifier as a quotation to look up, and the reader is told their citation
    is not in the corpus. Keying that filter off `references` alone left
    exactly the out-of-range case still doing it.

    Ranges are half-open and may overlap; callers should treat them as a set
    of covered positions rather than as a partition.
    """

    references: list[AnyReference]
    spans: list[tuple[int, int]]


def parse_references(text: str) -> list[AnyReference]:
    """Just the citations that resolved. See `parse_citations` for the rest."""
    return parse_citations(text).references


def parse_citations(text: str) -> ParsedCitations:
    refs: list[AnyReference] = []
    claimed: list[tuple[int, int]] = []

    # Hadith citations run FIRST and claim their span so the verse-numeric
    # pass below skips text they've already consumed -- that is what makes
    # "Bukhari 1:1" resolve as kitab 1, hadith 1, and never as surah 1, ayah 1.
    _collect_hadith_citations(_HADITH_CITE, text, refs, claimed)
    _collect_hadith_citations(_HADITH_CITE_AR, text, refs, claimed)

    for m in _NUMERIC.finditer(text):
        if any(m.start() < e and s < m.end() for s, e in claimed):
            continue  # already consumed by a hadith citation above
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
        # Deliberately NOT added to `claimed`, in either role. That list is
        # consulted by the dedup two lines above on every later iteration, so
        # adding to it would let one surah name suppress another within the
        # 24-character window; and a bare surah name is ASCII, so it can never
        # overlap a run of Arabic script and has nothing to contribute to
        # `spans` -- which exists to stop citations being read as quotations.
        refs.append(Reference(num, None, m.group(0), m.start()))

    return ParsedCitations(sorted(refs, key=lambda r: r.start), sorted(set(claimed)))


def nearest_reference(
    refs: list[AnyReference], position: int, window: int = 180
) -> AnyReference | None:
    """The nearest citation to `position`, of WHATEVER kind of record it names.

    Proximity decides attachment, and only proximity. This function must never
    filter by kind, and the temptation to make it do so is real enough to be
    worth writing down: filtering here fixes the Task 6 findings' D1 (a distant
    verse citation being attached to a hadith quotation) and opens a strictly
    worse hole behind it, because "«qul huwa llahu ahad» (Bukhari 12)" then
    draws no citation at all and reports EXACT. Attributing a Qur'anic verse to
    Sahih al-Bukhari would pass in silence -- a category error about scripture,
    and a graver misattribution than any wrong hadith number.

    A citation of the wrong kind is not absent. It is wrong, and it has to
    reach the engine to be called wrong: see `engine._reference_conflicts`.
    D1 is a proximity bug and is fixed by proximity -- the adjacent
    "(Bukhari 2866)" beats the distant "(112:1)" on distance alone.
    """
    candidates = [r for r in refs if abs(r.start - position) <= window]
    if not candidates:
        return None
    return min(candidates, key=lambda r: abs(r.start - position))
