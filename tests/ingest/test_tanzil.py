import hashlib
from pathlib import Path

import pytest
from sanad_ingest.tanzil import TanzilParseError, parse_tanzil

FIXTURE = Path("tests/fixtures/tanzil_excerpt.txt")


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
