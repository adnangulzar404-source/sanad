import pytest
from sanad.arabic.normalize import normalize, TIERS

BASMALA_UTHMANI = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"


def test_light_strips_tatweel_but_keeps_diacritics():
    assert normalize("بِسْـــمِ", "light") == "بِسْمِ"


def test_light_collapses_whitespace():
    assert normalize("  بِسْمِ   ٱللَّهِ  ", "light") == "بِسْمِ ٱللَّهِ"


def test_light_preserves_alef_wasla():
    assert "ٱ" in normalize(BASMALA_UTHMANI, "light")


def test_standard_strips_all_diacritics():
    out = normalize(BASMALA_UTHMANI, "standard")
    assert out == "بسم الله الرحمن الرحيم"


def test_standard_folds_alef_wasla_to_plain_alef():
    assert normalize("ٱللَّه", "standard") == "الله"


def test_standard_folds_every_alef_form():
    assert normalize("آ أ إ ٱ", "standard") == "ا ا ا ا"


def test_standard_keeps_ya_and_ta_marbuta_distinct():
    # these can change a word, so they must survive tier 2
    assert normalize("عَلَى", "standard") == "على"
    assert normalize("رَحْمَة", "standard").endswith("ة")


def test_aggressive_folds_alef_maqsura_and_ta_marbuta():
    assert normalize("عَلَى", "aggressive") == "علي"
    assert normalize("رَحْمَة", "aggressive") == "رحمه"


def test_aggressive_strips_latin_and_punctuation():
    assert normalize("قُلْ (Say) هُوَ", "aggressive") == "قل هو"


def test_strips_quranic_annotation_marks_at_standard():
    # U+06D6 small high ligature sad-lam-alef-ya
    assert normalize("ٱلرَّحِيمِۖ", "standard") == "الرحيم"


def test_superscript_alef_removed_at_standard():
    assert normalize("ٱلرَّحْمَٰن", "standard") == "الرحمن"


def test_normalization_is_idempotent():
    for tier in TIERS:
        once = normalize(BASMALA_UTHMANI, tier)
        assert normalize(once, tier) == once


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        normalize("x", "nonsense")


def test_standard_preserves_arabic_indic_digits():
    assert normalize("سورة ١١٢", "standard") == "سورة ١١٢"


def test_standard_preserves_dotless_letters():
    # U+066E and U+066F are letters, not diacritics
    assert normalize("ٮٯ", "standard") == "ٮٯ"
