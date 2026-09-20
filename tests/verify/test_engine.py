import pytest
from sanad.corpus import db
from sanad.verify.engine import Verdict, verify_spans

IKHLAS_1 = "قُلْ هُوَ ٱللَّهُ أَحَدٌ"
# quran:108:1. The task brief's literal used a bare alef here; the corpus (and
# correct Uthmani orthography) has ALEF WITH MADDA ABOVE (U+0622), which the
# "light" tier does not fold. Kept verbatim from the corpus so this fixture is a
# real light-tier EXACT match, not an EXACT_ORTHOGRAPHY one.
KAWTHAR_1 = "إِنَّآ أَعْطَيْنَٰكَ ٱلْكَوْثَرَ"


@pytest.fixture(scope="module")
def conn():
    return db.connect("data/sanad-quran.db")


def _only(matches):
    assert len(matches) == 1, f"expected one span, got {len(matches)}"
    return matches[0]


def test_verbatim_quote_is_exact(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"
    assert m.tier == "light"


def test_undiacritized_quote_is_exact_orthography(conn):
    m = _only(verify_spans(conn, "«قل هو الله احد»"))
    assert m.verdict is Verdict.EXACT_ORTHOGRAPHY
    assert m.record.id == "quran:112:1"
    assert m.tier == "standard"


def test_plain_alef_instead_of_wasla_is_still_exact_orthography(conn):
    # the single most common real-world variation
    m = _only(verify_spans(conn, "«قُلْ هُوَ اللَّهُ أَحَدٌ»"))
    assert m.verdict is Verdict.EXACT_ORTHOGRAPHY


def test_single_letter_mutation_is_near_match_not_exact(conn):
    m = _only(verify_spans(conn, "«قل هو الله احدق»"))
    assert m.verdict is Verdict.NEAR_MATCH
    assert m.diff is not None


def test_near_match_never_reports_as_verified(conn):
    m = _only(verify_spans(conn, "«قل هو الله احدق»"))
    assert m.verdict not in (Verdict.EXACT, Verdict.EXACT_ORTHOGRAPHY)


def test_correct_text_wrong_surah_is_wrong_reference(conn):
    m = _only(verify_spans(conn, f"The Qur'an says «{IKHLAS_1}» (Al-Baqarah 2:255)."))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "quran:112:1"
    assert m.given_reference.surah == 2


def test_correct_text_correct_reference_is_exact(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Al-Ikhlas 112:1)"))
    assert m.verdict is Verdict.EXACT


def test_correct_text_wrong_ayah_is_wrong_reference(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (112:4)"))
    assert m.verdict is Verdict.WRONG_REFERENCE


def test_fabricated_arabic_is_not_found(conn):
    m = _only(verify_spans(conn, "«هذا كلام مخترع تماما وليس من القران الكريم»"))
    assert m.verdict is Verdict.NOT_FOUND
    assert m.record is None


def test_multiple_spans_are_all_classified(conn):
    matches = verify_spans(conn, f"«{IKHLAS_1}» and «{KAWTHAR_1}»")
    assert len(matches) == 2
    assert all(m.verdict is Verdict.EXACT for m in matches)


def test_no_arabic_returns_no_matches(conn):
    assert verify_spans(conn, "There is no Arabic in this sentence.") == []


def test_ayat_al_kursi_long_verse_matches(conn):
    kursi = db.get_record(conn, "quran:2:255").text_ar
    m = _only(verify_spans(conn, f"«{kursi}»"))
    assert m.verdict is Verdict.EXACT


def test_diff_is_populated_only_for_near_match(conn):
    assert _only(verify_spans(conn, f"«{IKHLAS_1}»")).diff is None
    assert _only(verify_spans(conn, "«قل هو الله احدق»")).diff is not None


def test_duplicate_verse_verifies_against_each_of_its_own_citations(conn):
    refrain = db.get_record(conn, "quran:55:16").text_ar
    for ayah in (13, 16, 18, 21, 25, 28):
        m = _only(verify_spans(conn, f"«{refrain}» (55:{ayah})"))
        assert m.verdict is Verdict.EXACT, f"55:{ayah} failed"
        assert m.record.id == f"quran:55:{ayah}"


def test_duplicate_verse_with_a_genuinely_wrong_citation_still_flags(conn):
    refrain = db.get_record(conn, "quran:55:16").text_ar
    m = _only(verify_spans(conn, f"«{refrain}» (2:255)"))
    assert m.verdict is Verdict.WRONG_REFERENCE


def test_duplicate_verse_reports_its_other_locations(conn):
    refrain = db.get_record(conn, "quran:55:16").text_ar
    m = _only(verify_spans(conn, f"«{refrain}»"))
    assert len(m.also_at) == 30  # 31 occurrences, minus the one reported


def test_unique_verse_has_no_also_at(conn):
    m = _only(verify_spans(conn, "«" + db.get_record(conn, "quran:2:255").text_ar + "»"))
    assert m.also_at == []


# --- Finding 1: an aggressive-tier match may never assert WRONG_REFERENCE ---
# ى ALEF MAKSURA -> ي YEH is exactly the lossy fold _LOSSY_FOLDS
# applies at the aggressive tier (see normalize.py); both letters are written
# as explicit escapes here rather than literal glyphs, since they are
# visually near-identical and this substitution is precisely what is under
# test.


def test_aggressive_match_with_conflicting_citation_is_near_match_not_wrong_reference(conn):
    rec = db.get_record(conn, "quran:2:2")
    assert "ى" in rec.text_ar
    variant = rec.text_ar.replace("ى", "ي")
    m = _only(verify_spans(conn, f"«{variant}» (2:255)"))
    assert m.verdict is Verdict.NEAR_MATCH
    assert m.tier == "aggressive"
    assert m.given_reference is not None
    assert m.given_reference.surah == 2
    assert m.diff is not None


# --- Finding 2: the tier -> verdict map must be load-bearing, not decorative ---


def test_aggressive_tier_can_never_produce_a_verified_verdict():
    from sanad.verify.engine import _TIER_VERDICT

    assert _TIER_VERDICT["aggressive"] is Verdict.NEAR_MATCH


def test_no_aggressive_match_is_ever_reported_as_verified(conn):
    verified = {Verdict.EXACT, Verdict.EXACT_ORTHOGRAPHY}
    checked = 0
    for r in list(db.iter_records(conn))[:300]:
        variant = r.text_ar.replace("ى", "ي")
        if variant == r.text_ar:
            continue
        for suffix in ("", " (2:255)"):
            for m in verify_spans(conn, f"«{variant}»{suffix}"):
                assert m.verdict not in verified, (r.id, suffix, m.verdict)
                checked += 1
    assert checked > 0, "test exercised nothing"


# --- Finding 3: pin the span-edge reference-window fix ---


def test_citation_after_a_long_verse_is_still_associated(conn):
    kursi = db.get_record(conn, "quran:2:255").text_ar
    assert len(kursi) > 300, "fixture must be long enough to exercise the window"
    m = _only(verify_spans(conn, f"«{kursi}» (Al-Fatiha 1:5)"))
    assert m.verdict is Verdict.WRONG_REFERENCE


def test_citation_before_a_long_verse_is_still_associated(conn):
    kursi = db.get_record(conn, "quran:2:255").text_ar
    m = _only(verify_spans(conn, f"(Al-Fatiha 1:5) «{kursi}»"))
    assert m.verdict is Verdict.WRONG_REFERENCE


# --- Bismillah retry: a common, real quotation shape (a mushaf-style verse) ---


def test_prepended_bismillah_still_verifies_the_ayah(conn):
    bismillah = db.get_record(conn, "quran:112:1").bismillah
    m = _only(verify_spans(conn, f"«{bismillah} {IKHLAS_1}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"


def test_al_fatiha_first_ayah_still_verifies_as_itself(conn):
    # quran:1:1 IS the Bismillah -- the retry must not swallow it and leave
    # nothing to match.
    fatiha_1 = db.get_record(conn, "quran:1:1").text_ar
    m = _only(verify_spans(conn, f"«{fatiha_1}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:1:1"


# --- Bismillah retry must not turn a multi-ayah quotation into a false EXACT ---


def test_bismillah_retry_rejects_a_non_first_ayah(conn):
    bism = db.get_record(conn, "quran:112:1").bismillah
    kursi = db.get_record(conn, "quran:2:255").text_ar
    m = _only(verify_spans(conn, f"«{bism} {kursi}»"))
    assert m.verdict is not Verdict.EXACT
    assert m.verdict is not Verdict.EXACT_ORTHOGRAPHY


def test_bismillah_retry_rejects_at_tawbah(conn):
    bism = db.get_record(conn, "quran:112:1").bismillah
    tawbah = db.get_record(conn, "quran:9:1").text_ar
    m = _only(verify_spans(conn, f"«{bism} {tawbah}»"))
    assert m.verdict not in (Verdict.EXACT, Verdict.EXACT_ORTHOGRAPHY)


def test_bismillah_retry_still_accepts_a_real_first_ayah(conn):
    r = db.get_record(conn, "quran:112:1")
    m = _only(verify_spans(conn, f"«{r.bismillah} {r.text_ar}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"


def test_no_non_first_ayah_verifies_with_a_bismillah_prepended(conn):
    bism = db.get_record(conn, "quran:112:1").bismillah
    verified = {Verdict.EXACT, Verdict.EXACT_ORTHOGRAPHY}
    leaked = []
    for r in list(db.iter_records(conn))[:400]:
        if r.ayah == 1 and r.bismillah is not None:
            continue
        for m in verify_spans(conn, f"«{bism} {r.text_ar}»"):
            if m.verdict in verified:
                leaked.append(r.id)
    assert leaked == [], f"{len(leaked)} leaked, e.g. {leaked[:5]}"
