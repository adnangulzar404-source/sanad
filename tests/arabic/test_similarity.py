from sanad.arabic.similarity import levenshtein, ratio, ratio_at


def test_levenshtein_identical_is_zero():
    assert levenshtein("كتاب", "كتاب") == 0


def test_levenshtein_single_substitution():
    assert levenshtein("كتاب", "كتاف") == 1


def test_levenshtein_empty_operand():
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3


def test_levenshtein_is_symmetric():
    assert levenshtein("قل هو الله", "قل هو اللة") == levenshtein("قل هو اللة", "قل هو الله")


def test_ratio_identical_is_one():
    assert ratio("كتاب", "كتاب") == 1.0


def test_ratio_of_two_empties_is_zero_not_nan():
    assert ratio("", "") == 0.0


def test_ratio_bounds():
    assert 0.0 <= ratio("كتاب", "شمس") <= 1.0


def test_ratio_at_standard_ignores_diacritics():
    assert ratio_at("قُلْ هُوَ ٱللَّهُ أَحَدٌ", "قل هو الله احد", "standard") == 1.0


def test_ratio_at_light_does_not_ignore_diacritics():
    assert ratio_at("قُلْ هُوَ ٱللَّهُ أَحَدٌ", "قل هو الله احد", "light") < 1.0


def test_ratio_at_detects_single_letter_mutation():
    # a real misquote must not score 1.0 at any tier
    for tier in ("light", "standard", "aggressive"):
        assert ratio_at("قل هو الله أحد", "قل هو الله أحدق", tier) < 1.0
