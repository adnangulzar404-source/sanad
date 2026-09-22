import hashlib
from pathlib import Path

import pytest
from sanad_ingest.tanzil import TanzilParseError, parse_tanzil, parse_tanzil_xml, parser_for

FIXTURE = Path("tests/fixtures/tanzil_excerpt.txt")
XML_FIXTURE = Path("tests/fixtures/tanzil_excerpt.xml")


@pytest.fixture()
def parsed():
    return parse_tanzil(FIXTURE.read_text(encoding="utf-8"))


def test_extracts_every_verse(parsed):
    assert len(parsed.verses) == 4


def test_verse_tuple_shape(parsed):
    surah, ayah, text = parsed.verses[0]
    assert (surah, ayah) == (1, 1)
    assert text.startswith("بِسْمِ")


def test_pipe_inside_text_is_not_a_delimiter():
    p = parse_tanzil("2|1|alpha|beta\n")
    assert p.verses == [(2, 1, "alpha|beta")]


def test_attribution_captures_the_copyright_block(parsed):
    assert "PLEASE DO NOT REMOVE" in parsed.attribution
    assert "Creative Commons Attribution 3.0" in parsed.attribution


def test_attribution_excludes_verse_lines(parsed):
    assert "بِسْمِ" not in parsed.attribution


def test_content_hash_covers_verses_only(parsed):
    payload = "\n".join(f"{s}|{a}|{t}" for s, a, t in parsed.verses)
    assert parsed.content_sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_content_hash_is_stable_across_copyright_year_change():
    base = "1|1|نص\n\n# Copyright (C) 2007-2026 Tanzil Project\n"
    later = "1|1|نص\n\n# Copyright (C) 2007-2031 Tanzil Project\n"
    assert parse_tanzil(base).content_sha256 == parse_tanzil(later).content_sha256


def test_empty_input_raises():
    with pytest.raises(TanzilParseError, match="no verse"):
        parse_tanzil("# only a comment\n")


def test_malformed_verse_line_raises():
    with pytest.raises(TanzilParseError, match="line 2"):
        parse_tanzil("1|1|ok\nnot-a-verse-line\n")


def test_attribution_is_byte_verbatim_including_trailing_whitespace():
    raw = "1|1|نص\n\n# line with trailing space   \n#\tline with a tab\n"
    p = parse_tanzil(raw)
    assert p.attribution == "# line with trailing space   \n#\tline with a tab"


def test_content_hash_changes_when_a_verse_changes():
    base = parse_tanzil("1|1|نص\n\n# Copyright (C) 2007-2026 Tanzil Project\n")
    edited = parse_tanzil("1|1|نصا\n\n# Copyright (C) 2007-2026 Tanzil Project\n")
    assert base.content_sha256 != edited.content_sha256


# --- parse_tanzil_xml --------------------------------------------------------
#
# The XML export is the correct source for the Arabic text: txt-2 prepends
# the Bismillah to ayah 1's text for every surah except At-Tawbah, silently
# corrupting text_ar. The XML export instead carries the Bismillah as a
# separate `bismillah` attribute. These tests guard that distinction using a
# small fixture, independent of the committed database.

@pytest.fixture()
def parsed_xml():
    return parse_tanzil_xml(XML_FIXTURE.read_text(encoding="utf-8"))


def _by_ref(parsed):
    return {(s, a): (t, b) for s, a, t, b in parsed.ayat}


def test_xml_extracts_every_aya(parsed_xml):
    assert len(parsed_xml.ayat) == 4


def test_xml_aya_tuple_shape(parsed_xml):
    surah, ayah, text, bismillah = parsed_xml.ayat[0]
    assert (surah, ayah) == (1, 1)
    assert text.startswith("بِسْمِ")
    assert bismillah is None  # Al-Fatiha 1:1 IS the Bismillah, not prefixed by it


def test_xml_bismillah_present_where_it_applies(parsed_xml):
    text, bismillah = _by_ref(parsed_xml)[(112, 1)]
    assert text == "قُلْ هُوَ ٱللَّهُ أَحَدٌ"  # not prefixed with the Bismillah
    assert bismillah == "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"


def test_xml_bismillah_absent_for_ordinary_verse(parsed_xml):
    _, bismillah = _by_ref(parsed_xml)[(112, 2)]
    assert bismillah is None


def test_xml_bismillah_not_contained_in_its_own_verse_text(parsed_xml):
    # text does not contain the Bismillah; the attribute does.
    text, bismillah = _by_ref(parsed_xml)[(112, 1)]
    assert bismillah not in text


def test_xml_bismillah_count_matches_expected(parsed_xml):
    # Of the fixture's 4 ayat (1:1, 9:1, 112:1, 112:2), exactly one --
    # 112:1 -- carries a bismillah attribute.
    count = sum(1 for _, _, _, b in parsed_xml.ayat if b is not None)
    assert count == 1


def test_xml_at_tawbah_has_no_bismillah(parsed_xml):
    _, bismillah = _by_ref(parsed_xml)[(9, 1)]
    assert bismillah is None


def test_xml_attribution_captures_the_comment_block(parsed_xml):
    assert "PLEASE DO NOT REMOVE" in parsed_xml.attribution
    assert "Creative Commons Attribution 3.0" in parsed_xml.attribution


def test_xml_attribution_excludes_aya_text(parsed_xml):
    assert "قُلْ" not in parsed_xml.attribution


def test_xml_content_hash_covers_ayat_only(parsed_xml):
    payload = "\n".join(f"{s}|{a}|{t}" for s, a, t, _ in parsed_xml.ayat)
    assert parsed_xml.content_sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _xml(comment: str, ayat: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8" ?>\n'
        f"<!-- {comment} -->\n"
        f"<quran>{ayat}</quran>\n"
    )


def test_xml_content_hash_is_stable_across_copyright_year_change():
    aya = '<sura index="1" name="s"><aya index="1" text="نص" /></sura>'
    base = parse_tanzil_xml(_xml("Copyright (C) 2007-2026 Tanzil Project", aya))
    later = parse_tanzil_xml(_xml("Copyright (C) 2007-2031 Tanzil Project", aya))
    assert base.content_sha256 == later.content_sha256


def test_xml_content_hash_changes_when_a_verse_changes():
    base = parse_tanzil_xml(
        _xml("c", '<sura index="1" name="s"><aya index="1" text="نص" /></sura>'))
    edited = parse_tanzil_xml(
        _xml("c", '<sura index="1" name="s"><aya index="1" text="نصا" /></sura>'))
    assert base.content_sha256 != edited.content_sha256


def test_xml_malformed_input_raises():
    with pytest.raises(TanzilParseError, match="malformed XML"):
        parse_tanzil_xml("<quran><sura>not closed")


def test_xml_empty_input_raises():
    with pytest.raises(TanzilParseError, match="no aya"):
        parse_tanzil_xml('<?xml version="1.0" encoding="utf-8" ?><quran></quran>')


# --- parser_for ---------------------------------------------------------
#
# The single place a lockfile format maps to a parser. fetch.py and both
# passes of build.py must all go through this rather than choosing a
# parser themselves -- that duplication is exactly how build_corpus's
# translation pass ended up ignoring format and always using parse_tanzil.

def test_parser_for_xml_returns_the_xml_parser():
    assert parser_for("xml") is parse_tanzil_xml


def test_parser_for_txt2_returns_the_pipe_parser():
    assert parser_for("txt-2") is parse_tanzil


def test_parser_for_rejects_unknown_format():
    with pytest.raises(ValueError, match="xlm"):
        parser_for("xlm")


def test_parser_for_openiti_returns_the_openiti_parser():
    from sanad_ingest.openiti import parse_openiti
    assert parser_for("openiti-markdown") is parse_openiti
