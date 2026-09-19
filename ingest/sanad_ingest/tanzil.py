"""Parsers for Tanzil's Qur'an exports.

`parse_tanzil` handles the "text with aya numbers" (txt-2) export.
Format, verified 2026-09-19: UTF-8, LF, one verse per line as
"surah|ayah|text", followed by a 28-line copyright block whose lines begin
with "#". The block embeds the current year, so it is excluded from the
content hash but captured verbatim for attribution.

`parse_tanzil_xml` handles the XML export. It is the correct source for the
Arabic text: txt-2 prepends the Bismillah to the text of ayah 1 for every
surah except At-Tawbah, which silently corrupts the first ayah of every
other surah (most visibly the short, heavily-quoted ones, e.g. 112:1). The
XML export instead models the Bismillah as a separate `bismillah` attribute
on the `<aya>` element, leaving `text` exactly equal to the ayah itself.
Format, verified 2026-09-19: UTF-8, `<quran><sura index="N" name="...">
<aya index="M" text="..." [bismillah="..."] /></sura></quran>`, preceded by
an XML comment holding the same copyright block as the txt-2 export. As
with the pipe format, the comment embeds the current year and is excluded
from the content hash but captured verbatim for attribution.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

_VERSE = re.compile(r"^(\d{1,3})\|(\d{1,3})\|(.*)$")
_XML_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)


class TanzilParseError(Exception):
    pass


@dataclass(frozen=True)
class ParsedTanzil:
    verses: list[tuple[int, int, str]]
    attribution: str
    content_sha256: str

    def __len__(self) -> int:
        return len(self.verses)


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


@dataclass(frozen=True)
class ParsedTanzilXml:
    # (surah, ayah, text, bismillah) -- bismillah is None where the aya
    # element carries no bismillah attribute.
    ayat: list[tuple[int, int, str, str | None]]
    attribution: str
    content_sha256: str

    def __len__(self) -> int:
        return len(self.ayat)


def parse_tanzil_xml(raw: str) -> ParsedTanzilXml:
    comment_match = _XML_COMMENT.search(raw)
    attribution = comment_match.group(1) if comment_match else ""

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise TanzilParseError(f"malformed XML: {exc}") from exc

    ayat: list[tuple[int, int, str, str | None]] = []
    for sura in root.findall("sura"):
        surah = int(sura.get("index"))
        for aya in sura.findall("aya"):
            ayat.append((
                surah,
                int(aya.get("index")),
                aya.get("text"),
                aya.get("bismillah"),
            ))

    if not ayat:
        raise TanzilParseError("no aya elements found in input")

    payload = "\n".join(f"{s}|{a}|{t}" for s, a, t, _ in ayat)
    return ParsedTanzilXml(
        ayat=ayat,
        attribution=attribution,
        content_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )


def parser_for(fmt: str):
    """Single source of truth mapping a lockfile format to its parser.

    fetch.fetch_source and both passes of build.build_corpus all call this
    instead of choosing a parser themselves, so the format-to-parser mapping
    lives in exactly one place and cannot drift between call sites the way
    it did when build_corpus's translation pass called parse_tanzil
    unconditionally instead of dispatching on the source's declared format.

    load_lockfile validates format against the same two values at load
    time, so a bad value should never reach this function in practice; the
    ValueError here is a belt-and-braces backstop, not the primary guard.
    """
    if fmt == "xml":
        return parse_tanzil_xml
    if fmt == "txt-2":
        return parse_tanzil
    raise ValueError(f"unsupported source format {fmt!r}; expected 'xml' or 'txt-2'")
