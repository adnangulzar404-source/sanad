"""OpenITI mARkdown -> hadith units.

Pure function: text in, structure out. No network, no database, no file I/O.

The marker inventory below was measured against the pinned file on 2026-09-22,
not taken from OpenITI's documentation -- the file contains marker forms the
docs do not mention (ms####, backslash part markers), and a parser written from
the docs alone would have leaked them into stored text.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_HEADER_END = "#META#Header#End#"

# Structural markers, all stripped from stored text.
_CONTINUATION = "~~"
_PAGE = re.compile(r"PageV\d+P\d+")
_MILESTONE = re.compile(r"ms\d{4}")
_PART = re.compile(r"\\\s*\d+\s*\\")          # the "\ 1 \" part marker
_QURAN_MARK = re.compile(r"@QB@|@QE@")        # markers go, quoted words stay
_SECTION = re.compile(r"^###")                # ### | , ### || , ### |||
_KITAB = re.compile(r"^###\s*\|(?!\|)\s*(.*)$")
_BAB = re.compile(r"^###\s*\|\|+\s*(.*)$")
_UNIT_START = re.compile(r"^#\s")              # "^#\s" already can't match "###"
_NUMBERED = re.compile(r"^(\d+)\s+(م\s+)?(.*)$", re.DOTALL)
_LEADING_NUMBER = re.compile(r"^\d+\s+")

# A numbered unit whose text begins with "باب" is a chapter heading that the
# edition happens to number, not a narration. Six of them exist in the file.
_BAB_WORD = "باب"

# Everything outside these ranges is flagged (never corrected) as OCR noise.
_ALLOWED = re.compile(r"[؀-ۿ\s]")


@dataclass(frozen=True)
class HadithUnit:
    hadith_no: str
    record_id: str
    is_repeat: bool
    kitab_no: int
    kitab_ar: str
    bab_ar: str | None
    isnad_ar: str | None
    matn_ar: str


@dataclass(frozen=True)
class ParsedOpeniti:
    units: list[HadithUnit]
    attribution: str
    content_sha256: str
    noisy: list[tuple[str, str]]

    def __len__(self) -> int:
        """The record count fetch_source checks against `expected_records`.

        ParsedTanzil/ParsedTanzilXml define the same thing, so fetch_source
        can count any parsed source the same way instead of branching on
        which parser produced it.
        """
        return len(self.units)


def _clean(s: str) -> str:
    """Strip every structural marker; never touch letters.

    Order matters here: _MILESTONE must run before _PART. 15 occurrences in
    the pinned file look like "\\ 1 ms0007 \\" -- a milestone sitting inside
    a part marker's digits. If _PART ran first, its regex would not match
    across the embedded "ms0007" text, leaving the backslash-digit-backslash
    part marker unstripped once the milestone was removed afterward. A
    reviewer swapped the two lines during a check and the test suite caught
    the leak, so this ordering is load-bearing, not incidental.
    """
    s = _PAGE.sub(" ", s)
    s = _MILESTONE.sub(" ", s)
    s = _PART.sub(" ", s)
    s = _QURAN_MARK.sub(" ", s)
    return " ".join(s.split())


def _strip_heading_markup(s: str) -> str:
    """Drop the wrapping parens and leading printed number from a display
    heading -- "( 2 كتاب الإيمان )" -> "كتاب الإيمان". Cosmetic only: this
    never runs on isnad_ar/matn_ar, which carry the edition's words as-is.
    """
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    return _LEADING_NUMBER.sub("", s)


def parse_openiti(raw: str) -> ParsedOpeniti:
    end = raw.find(_HEADER_END)
    if end == -1:
        raise ValueError("no #META#Header#End# marker: not an OpenITI mARkdown file")
    attribution = raw[: end + len(_HEADER_END)]
    body = raw[end + len(_HEADER_END) :]

    units: list[HadithUnit] = []
    seen: dict[str, int] = {}
    kitab_no, kitab_ar, bab_ar = 0, "", None
    buf: list[str] | None = None

    # A "### ||" bab heading whose wrapping "(" isn't closed on its own line
    # spills the rest of its text onto following "#"-prefixed lines that look
    # exactly like anonymous narration fragments (774 of the file's 3,959 bab
    # headings do this). bab_parts/bab_balance track an in-progress heading
    # until its parens balance, a real numbered hadith starts, or a new
    # "###" section begins -- whichever comes first. The lookahead never
    # crosses into a real hadith: each candidate continuation chunk is
    # tested against _NUMBERED before being absorbed, so an actual narration
    # is never swallowed into a heading no matter how long the heading's
    # unresolved parenthesis run is.
    bab_parts: list[str] | None = None
    bab_balance = 0

    def start_bab(text: str) -> None:
        nonlocal bab_ar, bab_parts, bab_balance
        balance = text.count("(") - text.count(")")
        bab_ar = _strip_heading_markup(_clean(text)) or None
        if balance <= 0:
            bab_parts, bab_balance = None, 0
        else:
            bab_parts, bab_balance = [text], balance

    def flush() -> None:
        nonlocal buf, bab_ar, bab_parts, bab_balance
        if buf is None:
            return
        text, buf = " ".join(buf), None
        m = _NUMBERED.match(text)

        if bab_parts is not None:
            if m is None:
                # Heading continuation, not a narration -- absorb it.
                bab_parts.append(text)
                bab_balance += text.count("(") - text.count(")")
                bab_ar = _strip_heading_markup(_clean(" ".join(bab_parts))) or None
                if bab_balance <= 0:
                    bab_parts, bab_balance = None, 0
                return
            # A real numbered hadith starts here: the heading is done,
            # resolved or not (an unresolved case is a genuine missing
            # paren in the source -- roughly 25 of the 774 -- which no
            # amount of continuation-reading can close).
            bab_parts, bab_balance = None, 0

        if not m:
            return
        number, repeat, rest = m.group(1), bool(m.group(2)), m.group(3)
        rest_clean = _clean(rest)
        if rest_clean.startswith(_BAB_WORD):
            return  # numbered chapter heading, not a narration

        if "*" in rest:
            isnad_raw, matn_raw = rest.split("*", 1)
            isnad, matn = _clean(isnad_raw), _clean(matn_raw)
        else:
            isnad, matn = None, rest_clean
        if not matn:
            # Either the file marks no boundary at all (2795, 6964-6966) or it
            # puts the mark at the very end of the unit, where it separates
            # nothing (218, 1620, 5833). Same fact, same answer: keep
            # everything as matn rather than guessing where a chain ends.
            # Inventing an isnad is worse than admitting the source does not
            # mark one, and storing an empty scored text is worse than both --
            # 5833's matn is right there in the file, in front of the
            # misplaced mark.
            isnad, matn = None, _clean(rest.replace("*", " "))

        seen[number] = seen.get(number, 0) + 1
        suffix = "" if seen[number] == 1 else f"-{seen[number]}"
        units.append(
            HadithUnit(
                hadith_no=number,
                record_id=f"hadith:bukhari:{number}{suffix}",
                is_repeat=repeat,
                kitab_no=kitab_no,
                kitab_ar=kitab_ar,
                bab_ar=bab_ar,
                isnad_ar=isnad,
                matn_ar=matn,
            )
        )

    for line in body.splitlines():
        if line.startswith(_CONTINUATION):
            frag = line[len(_CONTINUATION) :]
            if buf is not None:
                buf.append(frag)
            elif bab_parts is not None:
                # A "~~" line can follow the "### ||" line directly, before
                # any "#"-prefixed chunk -- e.g. "( 1 باب ... صدقة الفطر" /
                # "~~فريضة )" is one heading, "فريضة" ("obligatory") being
                # the word that closes it. Dropping this line would lose
                # real words, not just markup.
                bab_parts.append(frag)
                bab_balance += frag.count("(") - frag.count(")")
                bab_ar = _strip_heading_markup(_clean(" ".join(bab_parts))) or None
                if bab_balance <= 0:
                    bab_parts, bab_balance = None, 0
            continue
        if _SECTION.match(line):
            flush()
            if bab_parts is not None:
                # A new section starts before the heading's paren closed --
                # no more continuation text is coming; keep what we have.
                bab_parts, bab_balance = None, 0
            if (k := _KITAB.match(line)) is not None:
                kitab_no += 1
                kitab_ar, bab_ar = _strip_heading_markup(_clean(k.group(1))), None
            elif (b := _BAB.match(line)) is not None:
                start_bab(b.group(1))
            continue
        if _UNIT_START.match(line):
            frag = line[2:]
            if (buf is not None and bab_parts is None
                    and _NUMBERED.match(" ".join(buf))
                    and not _NUMBERED.match(frag)):
                # A "#" line that carries no printed number is a CONTINUATION
                # of the numbered unit already open, not a new one. The
                # edition prints verse on its own "#" line -- "( la 'aysha
                # illa 'aysha l-akhira % ... )" -- and flushing here dropped
                # it on the floor, because the flushed chunk then failed
                # _NUMBERED and was discarded. That silently deleted the
                # entire matn of 3584, 4063 and 6050 and the closing verse of
                # 62 other records. Guarded three ways so no existing
                # behaviour moves: only when a numbered unit is open, only
                # when no bab heading is mid-assembly (that machinery reads
                # its own continuations through flush), and only when the
                # line is not itself a numbered unit.
                buf.append(frag)
                continue
            flush()
            buf = [frag]
            continue
        if buf is not None:
            buf.append(line)
    flush()

    noisy = []
    for u in units:
        bad = "".join(sorted({c for c in u.matn_ar if not _ALLOWED.match(c)}))
        if bad:
            noisy.append((u.record_id, bad))

    return ParsedOpeniti(
        units=units,
        attribution=attribution,
        content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        noisy=noisy,
    )
