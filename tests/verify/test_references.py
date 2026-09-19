import pytest

from sanad.verify.references import Reference, nearest_reference, parse_references


def test_parses_numeric_reference():
    refs = parse_references("see 2:255 for this")
    assert (refs[0].surah, refs[0].ayah) == (2, 255)


def test_parses_named_surah_with_numbers():
    refs = parse_references("Al-Baqarah 2:255")
    assert (refs[0].surah, refs[0].ayah) == (2, 255)


def test_parses_bare_surah_name():
    refs = parse_references("as stated in Al-Ikhlas")
    assert refs[0].surah == 112
    assert refs[0].ayah is None


def test_surah_name_spelling_variants():
    for spelling in ("Al-Fatihah", "al fatiha", "AL-FATIHA"):
        assert parse_references(spelling)[0].surah == 1


def test_records_position_in_text():
    text = "aaaa 112:1 bbbb"
    assert parse_references(text)[0].start == text.index("112:1")


def test_ignores_out_of_range_surah():
    assert parse_references("999:1") == []


def test_ignores_out_of_range_ayah():
    # Al-Fatihah has 7 verses; 300 is impossible
    assert parse_references("1:300") == []


def test_no_reference_returns_empty():
    assert parse_references("no citation here") == []


def test_nearest_reference_picks_closest():
    refs = [Reference(2, 255, "2:255", 0), Reference(112, 1, "112:1", 500)]
    assert nearest_reference(refs, 480).surah == 112


def test_nearest_reference_respects_window():
    refs = [Reference(2, 255, "2:255", 0)]
    assert nearest_reference(refs, 5000, window=180) is None


def test_nearest_reference_on_empty_list():
    assert nearest_reference([], 0) is None


@pytest.mark.parametrize("text", [
    "Maryam told me she had finished reading it.",
    "My colleague Yusuf sent the draft yesterday.",
    "Ibrahim and Muhammad will both attend.",
    "Yunus is presenting after lunch.",
])
def test_ordinary_personal_names_are_not_references(text):
    assert parse_references(text) == []


@pytest.mark.parametrize("text,expected", [
    ("as stated in Al-Ikhlas", 112),
    ("see Surah Maryam", 19),
    ("chapter Yusuf describes this", 12),
    ("Al-Baqarah discusses it", 2),
])
def test_qualified_or_prefixed_names_still_resolve(text, expected):
    assert parse_references(text)[0].surah == expected


def test_arabic_indic_digits_parse_correctly():
    r = parse_references("٢:٢٥٥")[0]
    assert (r.surah, r.ayah) == (2, 255)
