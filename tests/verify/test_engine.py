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


def test_nearby_hadith_citation_does_not_crash_a_verse_match(conn):
    """`parse_references` also yields `HadithReference`s (Task 5). A hadith
    citation sitting near a verse quotation reaches the surah:ayah conflict
    check, which must recognise it as a citation of the wrong KIND and say so,
    rather than reading `.surah` off it. Regression test for AttributeError:
    'HadithReference' object has no attribute 'surah'.

    The verdict was EXACT while Task 5's stopgap filtered hadith citations out
    of the verse path entirely. It is WRONG_REFERENCE now that the citation is
    no longer discarded: attributing Al-Ikhlas to Sahih al-Bukhari is an error
    worth reporting, not one worth hiding. See Task 6."""
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "quran:112:1"


def test_correct_text_wrong_ayah_is_wrong_reference(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (112:4)"))
    assert m.verdict is Verdict.WRONG_REFERENCE


def test_a_bare_surah_name_cites_the_whole_surah_not_a_particular_ayah(conn):
    """`Reference.ayah` is None for a bare surah name ("Al-Ikhlas", with no
    verse number), and `_reference_conflicts` must then compare the surah only.
    Dropping the `ayah is not None` guard turns every bare-name citation into a
    WRONG_REFERENCE -- the citation is right, it is simply less specific.

    Added because mutation testing found the guard unobservable: every other
    test in this file that cites by name also gives a verse number, or cites
    across kinds, so `ayah is None` never reached the comparison with a
    matching surah. An unobservable guard is one no test can see fail.
    """
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Al-Ikhlas)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"
    assert m.given_reference.ayah is None

    # ...and it is still a real comparison: the wrong surah, named just as
    # loosely, is still wrong.
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Al-Baqarah)"))
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


def test_bismillah_retry_accepts_a_qualifying_tie_even_when_others_dont(conn):
    # 39:1, 45:2, and 46:2 share byte-identical wording, but only 39:1 is a
    # genuine Bismillah-bearing first ayah. Requiring EVERY tied candidate to
    # qualify (rather than ANY) would let 45:2 and 46:2 veto a real mushaf
    # paste of 39:1. The text really is 39:1's text, and 39:1 really does
    # carry that Bismillah, so this must verify EXACT, with the other two
    # disclosed via `also_at` rather than silently hidden or wrongly refused.
    r39 = db.get_record(conn, "quran:39:1")
    assert db.get_record(conn, "quran:45:2").text_ar == r39.text_ar
    assert db.get_record(conn, "quran:46:2").text_ar == r39.text_ar
    m = _only(verify_spans(conn, f"«{r39.bismillah} {r39.text_ar}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:39:1"
    assert set(m.also_at) == {"quran:45:2", "quran:46:2"}

    # An explicit, correct citation must not change the outcome.
    m2 = _only(verify_spans(conn, f"«{r39.bismillah} {r39.text_ar}» (39:1)"))
    assert m2.verdict is Verdict.EXACT
    assert m2.record.id == "quran:39:1"


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


# --- fix round 5: a record is scored under every representation it has -----
#
# Built on a throwaway database rather than the shipped corpus, so these pin
# the ENGINE's behaviour rather than today's data: the same assertions hold if
# a future edition cuts different records.


@pytest.fixture()
def two_representations(tmp_path):
    """One hadith, cut: primary matn "AAAA BBBB", addendum "CCCC DDDD"."""
    from sanad.corpus.models import Record, RecordVariant, Source
    primary, whole = "اااا بببب", "اااا بببب جججج دددد"
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, Source(
        id="s", kind="hadith-arabic", title="t", publisher=None, edition=None,
        url="https://example.invalid/", license_id="public-domain",
        license_url=None, attribution="a", retrieved_at="2026-09-23",
        upstream_sha256="0" * 64, modifications="none"))
    db.insert_records(conn, [Record(
        id="hadith:bukhari:1", source_id="s", kind="hadith", collection="bukhari",
        hadith_no="1", numbering_scheme="bugha-1987", text_ar=primary,
        addenda_ar="جججج دددد", text_ar_sha256="x" * 64,
        norm_light=primary, norm_standard=primary, norm_aggressive=primary,
        reference_display="Sahih al-Bukhari 1")])
    db.insert_record_variants(conn, [RecordVariant(
        record_id="hadith:bukhari:1", variant="full", text_ar=whole,
        norm_light=whole, norm_standard=whole, norm_aggressive=whole)])
    db.rebuild_fts(conn)
    return conn, primary, whole


def test_the_primary_matn_verifies(two_representations):
    conn, primary, _whole = two_representations
    m = _only(verify_spans(conn, f"«{primary}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "hadith:bukhari:1"


def test_the_full_printed_text_verifies_to_the_same_record(two_representations):
    """The point of the round: quoting the hadith as the edition prints it is
    the most natural thing a person can do with it, and before this it
    returned NOT_FOUND on any record the cut had split."""
    conn, _primary, whole = two_representations
    m = _only(verify_spans(conn, f"«{whole}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "hadith:bukhari:1"
    assert m.record.reference_display == "Sahih al-Bukhari 1"


def test_a_record_is_never_reported_twice_for_its_own_representations(
        two_representations):
    """`also_at` names OTHER records sharing the text. A record listing itself
    there would read as "this wording also appears at Sahih al-Bukhari 1" on a
    match to Sahih al-Bukhari 1."""
    conn, primary, whole = two_representations
    for quote in (primary, whole):
        m = _only(verify_spans(conn, f"«{quote}»"))
        assert m.also_at == [], quote


def test_a_near_miss_on_the_full_text_is_scored_against_the_full_text(
        two_representations):
    """One character added to the full quotation. Scored against the primary
    matn instead, the same string sits near 0.6 and reports NOT_FOUND; the
    diff would also show the whole addendum as text the quoter left out."""
    conn, _primary, whole = two_representations
    m = _only(verify_spans(conn, f"«{whole}ق»"))
    assert m.verdict is Verdict.NEAR_MATCH
    assert m.score > 0.9   # against the primary matn the same string is ~0.62
    assert m.record.id == "hadith:bukhari:1"
    joined = "".join(text for _tag, text in m.diff)
    assert "جججج" in joined and joined.count("جججج") == 1
    # The discriminating assertion: the ONE character the quoter added is the
    # only thing the diff marks. Built against the primary matn instead, the
    # diff marks the entire addendum as text the quoter invented -- the
    # quotation would be shown as wrong in the part it got exactly right.
    assert [text for tag, text in m.diff if tag != "equal"] == ["ق"]


@pytest.fixture()
def a_record_indexed_twice_under_one_text(tmp_path):
    """A record whose two representations carry IDENTICAL norms.

    The build never emits this -- the full text is strictly longer than the
    primary -- but the schema permits it, and the collapse is what guarantees
    a record is reported once regardless of what the build emits. Without a
    degenerate case the collapse is unobservable, and an unobservable guard
    is one no test can see fail.
    """
    from sanad.corpus.models import Record, RecordVariant, Source
    text = "اااا بببب جججج"
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, Source(
        id="s", kind="hadith-arabic", title="t", publisher=None, edition=None,
        url="https://example.invalid/", license_id="public-domain",
        license_url=None, attribution="a", retrieved_at="2026-09-23",
        upstream_sha256="0" * 64, modifications="none"))
    db.insert_records(conn, [Record(
        id="hadith:bukhari:1", source_id="s", kind="hadith", collection="bukhari",
        hadith_no="1", numbering_scheme="bugha-1987", text_ar=text,
        addenda_ar="جججج", text_ar_sha256="x" * 64, norm_light=text,
        norm_standard=text, norm_aggressive=text,
        reference_display="Sahih al-Bukhari 1")])
    db.insert_record_variants(conn, [RecordVariant(
        record_id="hadith:bukhari:1", variant="full", text_ar=text,
        norm_light=text, norm_standard=text, norm_aggressive=text)])
    db.rebuild_fts(conn)
    return conn, text


def test_the_exact_tier_returns_a_tied_record_once(a_record_indexed_twice_under_one_text):
    from sanad.verify.engine import _exact_at_tier
    conn, text = a_record_indexed_twice_under_one_text
    assert [r.id for r in _exact_at_tier(conn, text, "light")] == ["hadith:bukhari:1"]


def test_the_fuzzy_tier_returns_a_tied_record_once(a_record_indexed_twice_under_one_text):
    from sanad.verify.engine import _best_fuzzy
    conn, text = a_record_indexed_twice_under_one_text
    candidates, score, matched = _best_fuzzy(conn, text)
    assert [r.id for r in candidates] == ["hadith:bukhari:1"]
    assert score == 1.0
    assert matched == {"hadith:bukhari:1": text}


def test_a_tied_record_is_reported_once_end_to_end(a_record_indexed_twice_under_one_text):
    conn, text = a_record_indexed_twice_under_one_text
    m = _only(verify_spans(conn, f"«{text}»"))
    assert m.record.id == "hadith:bukhari:1"
    assert m.also_at == []


@pytest.fixture()
def an_unscorable_record_with_a_variant(tmp_path):
    """An excluded record that nonetheless HAS a second representation row.

    `build._hadith_records` refuses to emit this, so on today's corpus the
    filters downstream of it are unobservable -- and an unobservable filter is
    one no test can see fail. The exclusion is deliberately enforced in three
    independent places (build, `rebuild_fts`, `_exact_at_tier`) precisely so
    that no single mistake can put editorial apparatus behind a verdict, and
    that design is only real if each place is checked on its own.
    """
    from sanad.corpus.models import Record, RecordVariant, Source
    primary, whole = "اااا بببب", "اااا بببب جججج دددد"
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, Source(
        id="s", kind="hadith-arabic", title="t", publisher=None, edition=None,
        url="https://example.invalid/", license_id="public-domain",
        license_url=None, attribution="a", retrieved_at="2026-09-23",
        upstream_sha256="0" * 64, modifications="none"))
    db.insert_records(conn, [Record(
        id="hadith:bukhari:1", source_id="s", kind="hadith", collection="bukhari",
        hadith_no="1", numbering_scheme="bugha-1987", text_ar=primary,
        addenda_ar="جججج دددد", text_ar_sha256="x" * 64,
        unscorable_reason="chapter-heading",
        norm_light=primary, norm_standard=primary, norm_aggressive=primary,
        reference_display="Sahih al-Bukhari 1")])
    db.insert_record_variants(conn, [RecordVariant(
        record_id="hadith:bukhari:1", variant="full", text_ar=whole,
        norm_light=whole, norm_standard=whole, norm_aggressive=whole)])
    db.rebuild_fts(conn)
    return conn, primary, whole


def test_the_exact_tier_excludes_every_representation_of_an_excluded_record(
        an_unscorable_record_with_a_variant):
    from sanad.verify.engine import _exact_at_tier
    conn, primary, whole = an_unscorable_record_with_a_variant
    for tier in ("light", "standard", "aggressive"):
        assert _exact_at_tier(conn, primary, tier) == [], tier
        assert _exact_at_tier(conn, whole, tier) == [], tier


def test_an_excluded_record_never_verifies_under_either_representation(
        an_unscorable_record_with_a_variant):
    conn, primary, whole = an_unscorable_record_with_a_variant
    for quote in (primary, whole):
        m = _only(verify_spans(conn, f"«{quote}»"))
        assert m.verdict is Verdict.NOT_FOUND, quote
        assert m.record is None


# =========================================================================
# Task 6: a citation may only ever attach to a quotation of its OWN kind
# =========================================================================
#
# Every Arabic string in this section is either read out of the corpus at run
# time or written as explicit backslash-u escapes -- never typed as a literal
# glyph. This project has shipped eleven defects from Arabic altered silently
# in transit, two of them inside the test that was supposed to catch it, so a
# fixture that "looks right" is not evidence.
#
# "sahih al-bukhari": sahih U+0635 U+062D U+064A U+062D, then the definite
# article U+0627 U+0644 attached to bukhari U+0628 U+062E U+0627 U+0631 U+064A.
# "rawahu" (narrated by) is U+0631 U+0648 U+0627 U+0647.
_AL_BUKHARI_AR = "\u0627\u0644\u0628\u062e\u0627\u0631\u064a"
_SAHIH_AL_BUKHARI_AR = "\u0635\u062d\u064a\u062d" + " " + _AL_BUKHARI_AR
_RAWAHU_AL_BUKHARI_AR = "\u0631\u0648\u0627\u0647" + " " + _AL_BUKHARI_AR
# "qala al-nabiyyu" (the Prophet said): U+0642 U+0627 U+0644 + U+0627 U+0644
# U+0646 U+0628 U+064A. Prose, not a quotation -- see D2.
_QALA_AL_NABI_AR = "\u0642\u0627\u0644 \u0627\u0644\u0646\u0628\u064a"


def _arabic_indic(n: int) -> str:
    """Arabic-Indic digits (U+0660-U+0669), GENERATED from the integer.

    Typing "٣٠٣٠" by hand is exactly the transcription step that has gone
    wrong here before; deriving it from `n` means the fixture cannot disagree
    with the number the assertion is about.
    """
    return "".join(chr(0x0660 + int(d)) for d in str(n))


def test_arabic_indic_digit_helper_is_itself_correct():
    """The helper is a fixture generator; if it is wrong, every Arabic
    citation test below is testing the wrong number and still passing."""
    assert [ord(c) for c in _arabic_indic(3030)] == [0x0663, 0x0660, 0x0663, 0x0660]
    assert int(_arabic_indic(2866)) == 2866


# --- D1: the exact reproduction from the findings ---------------------------


def test_d1_a_correctly_cited_hadith_beside_a_quranic_citation(conn):
    """The defect this task exists for.

    `الحرب خدعة` really IS Sahih al-Bukhari 2866. Before the fix, the Qur'anic
    "112:1" from the far end of the sentence was handed to the hadith span as
    its "given reference", and Sanad told the user their correct citation was
    wrong -- a false accusation of misattribution, the same severity class as
    a false EXACT.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    text = (f"The Prophet said «{matn}» (Bukhari 2866), and the "
            f"Qur'an says «{IKHLAS_1}» (112:1).")
    hadith, ayah = verify_spans(conn, text)

    assert hadith.span.text == matn
    assert hadith.verdict is Verdict.EXACT
    assert hadith.record.id == "hadith:bukhari:2866"
    assert hadith.given_reference is not None
    assert hadith.given_reference.raw == "Bukhari 2866"

    assert ayah.verdict is Verdict.EXACT
    assert ayah.record.id == "quran:112:1"
    assert ayah.given_reference.raw == "112:1"


def test_a_hadith_quoted_and_correctly_cited_verifies(conn):
    matn = db.get_record(conn, "hadith:bukhari:1").text_ar
    m = _only(verify_spans(conn, f"«{matn}» (Bukhari 1)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "hadith:bukhari:1"


def test_the_famous_short_matn_verifies_on_its_own(conn):
    """The section-7 canary. Fails the moment anyone stores isnad+matn in
    text_ar: scoring across the chain puts a short famous matn near 0.13."""
    matn = db.get_record(conn, "hadith:bukhari:1").text_ar
    m = _only(verify_spans(conn, f"«{matn}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "hadith:bukhari:1"


def test_a_genuinely_wrong_hadith_citation_is_flagged_and_names_the_record(conn):
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    m = _only(verify_spans(conn, f"«{matn}» (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    # It must name where the text actually IS, not merely refuse the citation.
    assert m.record.id == "hadith:bukhari:2866"
    assert m.record.reference_display == "Sahih al-Bukhari 2866"
    assert m.given_reference.hadith_no == "1"


# --- D1 generalised: attachment by proximity, kind mismatch as a verdict -----
#
# Two rules, and they are easy to confuse:
#
#   1. A citation attaches to the quotation it is NEAREST to, across every
#      reference in the text regardless of the kind of record it addresses.
#   2. Once attached, a mismatch between the citation's kind and the kind of
#      record the text was actually found in is a WRONG_REFERENCE.
#
# An earlier attempt at D1 filtered by kind at step 1 instead. It fixed D1 and
# opened a worse hole: "«qul huwa llahu ahad» (Bukhari 12)" drew no citation
# at all and was reported EXACT, so attributing a Qur'anic verse to Sahih
# al-Bukhari passed silently. That is a category error about scripture and a
# graver misattribution than a wrong hadith number -- exactly what this tool
# exists to catch. D1 comes out right under rule 1 on its own, because the
# adjacent "(Bukhari 2866)" simply beats the distant "(112:1)" on distance.


def test_an_ayah_cited_as_bukhari_is_a_wrong_reference(conn):
    """Attributing scripture to a hadith collection. The citation is real, it
    is the nearest thing to the quotation, and it is wrong about what kind of
    text this is."""
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "quran:112:1"
    assert m.given_reference.hadith_no == "1"


def test_a_hadith_cited_as_a_verse_is_a_wrong_reference(conn):
    matn = db.get_record(conn, "hadith:bukhari:1").text_ar
    m = _only(verify_spans(conn, f"«{matn}» (Al-Baqarah 2:255)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "hadith:bukhari:1"
    assert m.given_reference.surah == 2


def test_a_cross_kind_citation_is_never_silently_dropped(conn):
    """The regression this fix round exists for, stated as a property.

    Whatever else happens, a citation of the wrong kind must reach the
    verdict. `given_reference is None` next to a verdict of EXACT is the
    failure mode: it reads to the user as "Verified, no citation given" when
    they did give one, and it was wrong.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    for text in (f"It says «{IKHLAS_1}» (Bukhari 12).",
                 f"It says «{matn}» (Quran 2:255)."):
        m = _only(verify_spans(conn, text))
        assert m.verdict is Verdict.WRONG_REFERENCE, text
        assert m.given_reference is not None, text


def test_the_nearer_citation_wins_regardless_of_kind(conn):
    """Rule 1, isolated. The same quotation, the same two citations, only the
    order changed -- and the verdict follows whichever is nearer, not whichever
    matches the record's kind."""
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    near_right = _only(verify_spans(conn, f"(112:1) ..... «{matn}» (Bukhari 2866)"))
    assert near_right.verdict is Verdict.EXACT
    assert near_right.given_reference.hadith_no == "2866"

    near_wrong = _only(verify_spans(conn, f"(Bukhari 2866) ..... «{matn}» (112:1)"))
    assert near_wrong.verdict is Verdict.WRONG_REFERENCE
    assert near_wrong.given_reference.surah == 112


def test_a_hadith_citation_cannot_rescue_a_wrong_verse_citation(conn):
    """Both kinds present and the NEARER one wrong, in each direction."""
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (2:4) (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.given_reference.surah == 2

    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    m = _only(verify_spans(conn, f"«{matn}» (Bukhari 1) (112:1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.given_reference.hadith_no == "1"


def test_kind_is_compared_before_the_numbers_are(conn):
    """A hadith citation whose NUMBER happens to match the ayah's number must
    still be wrong. Without an explicit kind comparison, a check that only
    read `hadith_no` off an ayah record would get None on both sides of some
    comparisons and could agree by accident."""
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Bukhari 112)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "quran:112:1"


def test_a_cross_kind_citation_is_a_verdict_not_an_exception(conn):
    """The Task 5 crash, restated. `_reference_conflicts` reads `.surah` off a
    `Reference` and `.hadith_no` off a `HadithReference`; handing it a record
    of the other kind must produce WRONG_REFERENCE, never AttributeError."""
    matn = db.get_record(conn, "hadith:bukhari:1").text_ar
    for text in (f"«{IKHLAS_1}» (Bukhari 1)", f"«{matn}» (2:255)",
                 f"«{matn}» (Al-Ikhlas)"):
        m = _only(verify_spans(conn, text))
        assert m.verdict is Verdict.WRONG_REFERENCE, text


# --- Arabic-script citations attach exactly as the Latin ones do -------------


def test_a_correctly_cited_hadith_in_arabic_script_verifies(conn):
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    for form in (_SAHIH_AL_BUKHARI_AR, _AL_BUKHARI_AR, _RAWAHU_AL_BUKHARI_AR):
        citation = f"{form} {_arabic_indic(2866)}"
        matches = [m for m in verify_spans(conn, f"«{matn}» ({citation})")
                   if m.span.text == matn]
        m = _only(matches)
        assert m.verdict is Verdict.EXACT, citation
        assert m.record.id == "hadith:bukhari:2866"
        assert m.given_reference is not None and m.given_reference.hadith_no == "2866"


def test_a_wrong_hadith_citation_in_arabic_script_is_still_flagged(conn):
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    citation = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(1)}"
    matches = [m for m in verify_spans(conn, f"«{matn}» ({citation})")
               if m.span.text == matn]
    m = _only(matches)
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "hadith:bukhari:2866"


def test_a_correctly_cited_hadith_survives_an_unrelated_quranic_citation(conn):
    """The findings' generalisation of D1, in both citation languages.

    "Unrelated ... elsewhere in the text" has to mean genuinely elsewhere now
    that proximity decides attachment: the verse citation is put a clear
    distance away, on the other side of a clause, with the hadith citation
    adjacent to its own quotation. That is the shape the original defect had,
    and the shape real prose has. Where the two citations are equidistant or
    the verse one is nearer, the reader has written something ambiguous and
    proximity is the honest tie-break -- see
    `test_the_nearer_citation_wins_regardless_of_kind`.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    filler = "and this clause is here only to put some distance between them"
    latin = "Bukhari 2866"
    arabic = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(2866)}"
    for citation in (latin, arabic):
        for text in (f"The Qur'an says (112:1), {filler}, «{matn}» ({citation})",
                     f"«{matn}» ({citation}), {filler}, and the Qur'an says (112:1)",
                     f"({citation}) «{matn}», {filler}, (112:1)"):
            m = _only([x for x in verify_spans(conn, text) if x.span.text == matn])
            assert m.verdict is Verdict.EXACT, text
            assert m.record.id == "hadith:bukhari:2866"
            assert m.given_reference.hadith_no == "2866", text


# --- D2: a citation is not a quotation ---------------------------------------


def test_d2_an_arabic_citation_is_not_offered_as_a_quotation(conn):
    """The reproduction from the findings.

    The citation is itself a run of Arabic script, so the extractor used to
    hand it to the verifier, which duly reported "صحيح البخاري ٣٠٣٠ -- not in
    this corpus". Only people who cite in Arabic ever saw this.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    citation = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(3030)}"
    out = verify_spans(conn, f"{_QALA_AL_NABI_AR} «{matn}» ({citation})")
    assert citation not in [m.span.text for m in out]
    quoted = _only([m for m in out if m.span.text == matn])
    # The findings' literal reproduction cites 3030 for a matn that is really
    # 2866, so the two fixes compose here: the citation stops being scored as
    # a quotation (D2) AND it now reaches the hadith it was written for (D1),
    # which is how it can be judged wrong at all. Before this task it was
    # ignored, and the matn read EXACT with a Qur'anic reference attached.
    assert quoted.verdict is Verdict.WRONG_REFERENCE
    assert quoted.record.id == "hadith:bukhari:2866"
    assert quoted.given_reference.hadith_no == "3030"
    # The same sentence with the RIGHT number verifies, citation still unscored.
    right = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(2866)}"
    out_right = verify_spans(conn, f"{_QALA_AL_NABI_AR} «{matn}» ({right})")
    assert right not in [m.span.text for m in out_right]
    assert _only([m for m in out_right if m.span.text == matn]).verdict is Verdict.EXACT
    # Out of scope, stated explicitly rather than changed quietly: the bare
    # prose run "قال النبي" is still extracted and still scores NOT_FOUND.
    # That is the Arabic-run extractor's problem, not the citation's; see the
    # findings, D2. Pinned here so a future change to it is visible, not
    # endorsed.
    assert [m.span.text for m in out] == [_QALA_AL_NABI_AR, matn]


def test_a_citation_standing_entirely_alone_yields_no_quotation(conn):
    for n in (1, 342, 3030, 7124):
        for form in (_SAHIH_AL_BUKHARI_AR, _AL_BUKHARI_AR, _RAWAHU_AL_BUKHARI_AR):
            text = f"{form} {_arabic_indic(n)}"
            assert verify_spans(conn, text) == [], text


def test_a_citation_whose_number_is_out_of_range_is_still_not_a_quotation(conn):
    """Concern 1 from the first round of this task, now fixed.

    "sahih al-bukhari 99999" resolves to no reference -- 99999 is past the end
    of the collection -- but it is still unmistakably a citation. While the
    filter keyed off the RESOLVED references, this survived as an Arabic run
    and the reader was told their citation was not in the corpus, which is the
    whole of D2 all over again in the one case D2's fix missed.
    """
    for n in (0, 9999, 99999):
        for form in (_SAHIH_AL_BUKHARI_AR, _AL_BUKHARI_AR, _RAWAHU_AL_BUKHARI_AR):
            text = f"{form} {_arabic_indic(n)}"
            assert verify_spans(conn, text) == [], text


def test_an_out_of_range_citation_beside_a_real_quotation(conn):
    """The same, in the shape it actually occurs: the quotation must still be
    verified on its own text, and the bad citation must not become a second,
    spurious NOT_FOUND beside it."""
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    citation = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(99999)}"
    out = verify_spans(conn, f"«{matn}» ({citation})")
    assert [m.span.text for m in out] == [matn]
    assert out[0].verdict is Verdict.EXACT
    assert out[0].record.id == "hadith:bukhari:2866"
    # No reference resolved, so nothing is claimed about the citation.
    assert out[0].given_reference is None


def test_a_quotation_is_not_dropped_merely_for_sitting_next_to_a_citation(conn):
    """The D2 filter removes spans a citation CONSUMES, not spans it neighbours.
    An over-broad filter would silently delete real quotations, which is worse
    than the defect it fixes."""
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    citation = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(2866)}"
    out = verify_spans(conn, f"«{matn}»{citation}")
    assert [m.span.text for m in out] == [matn]
    assert out[0].verdict is Verdict.EXACT


def test_no_corpus_record_is_swallowed_by_the_citation_filter(conn):
    """Sweep, not sample: every one of the 13,365 records, checked for text
    that `parse_references` would read as a citation covering it.

    If any record's own text contained something the citation patterns match,
    the D2 filter could delete a genuine quotation of it instead of a
    citation. Today none does -- and this test is what notices if a future
    edition, or a future citation pattern, changes that.
    """
    from sanad.verify.references import parse_references

    offenders = [r.id for r in db.iter_records(conn) if parse_references(r.text_ar)]
    assert offenders == [], f"{len(offenders)} records, e.g. {offenders[:5]}"


# --- hadith_no is not unique -------------------------------------------------


def test_a_repeated_hadith_number_is_satisfied_by_either_record(conn):
    """7,124 distinct printed numbers over 7,129 records. A citation of a
    repeated number is correct for ANY record carrying it; treating the first
    hit as the only one would flag one of the two as a wrong reference."""
    rows = conn.execute(
        "SELECT hadith_no FROM records WHERE kind='hadith'"
        " GROUP BY hadith_no HAVING count(*) > 1").fetchall()
    assert rows, "fixture assumes the edition repeats at least one number"
    checked = 0
    for (number,) in rows:
        siblings = conn.execute(
            "SELECT id FROM records WHERE kind='hadith' AND hadith_no = ?"
            " AND unscorable_reason IS NULL", (number,)).fetchall()
        for (rid,) in siblings:
            rec = db.get_record(conn, rid)
            m = _only(verify_spans(conn, f"«{rec.text_ar}» (Bukhari {number})"))
            assert m.verdict is not Verdict.WRONG_REFERENCE, rid
            assert m.record.hadith_no == number, rid
            checked += 1
    assert checked >= 2, "test exercised nothing"


# --- the two representations of one hadith are one record --------------------


def test_the_full_printed_text_with_a_correct_citation_verifies_once(conn):
    """A hadith is indexed under its primary matn AND its full printed text.
    Reference checking must see one record, not two: a record reported twice
    would read as "this also appears at Sahih al-Bukhari 10" on a match to
    Sahih al-Bukhari 10."""
    rec = db.get_record(conn, "hadith:bukhari:10")
    assert rec.addenda_ar, "fixture assumes this record was cut"
    whole = db.get_record_variants(conn, rec.id)[0].text_ar
    for quote in (rec.text_ar, whole):
        m = _only(verify_spans(conn, f"«{quote}» (Bukhari {rec.hadith_no})"))
        assert m.verdict is Verdict.EXACT
        assert m.record.id == rec.id
        assert m.also_at == []


def test_the_full_printed_text_with_a_wrong_citation_is_flagged_once(conn):
    rec = db.get_record(conn, "hadith:bukhari:10")
    whole = db.get_record_variants(conn, rec.id)[0].text_ar
    m = _only(verify_spans(conn, f"«{whole}» (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == rec.id
    assert m.also_at == []


# --- sweeps: the general property, not the examples --------------------------


def test_every_ayah_correctly_cited_still_verifies(conn):
    """The Qur'an path must not regress. Sweep, not sample: all 6,236 ayat,
    each quoted verbatim with its own address."""
    verified = {Verdict.EXACT, Verdict.EXACT_ORTHOGRAPHY}
    bad = []
    checked = 0
    for r in db.iter_records(conn):
        if r.kind != "ayah":
            continue
        m = _only(verify_spans(conn, f"«{r.text_ar}» ({r.surah}:{r.ayah})"))
        checked += 1
        if m.verdict not in verified or m.record.id != r.id:
            bad.append((r.id, m.verdict, m.record.id if m.record else None))
    assert checked == 6236, checked
    assert bad == [], f"{len(bad)} regressed, e.g. {bad[:5]}"


def test_every_ayah_wrongly_cited_is_still_flagged(conn):
    """The other half of the sweep. 2:255 is unique in the corpus (nothing
    ties with it), so citing it for any OTHER ayah is genuinely wrong."""
    bad = []
    checked = 0
    for r in db.iter_records(conn):
        if r.kind != "ayah" or r.id == "quran:2:255":
            continue
        m = _only(verify_spans(conn, f"«{r.text_ar}» (2:255)"))
        checked += 1
        if m.verdict is not Verdict.WRONG_REFERENCE:
            bad.append((r.id, m.verdict))
    assert checked == 6235, checked
    assert bad == [], f"{len(bad)} not flagged, e.g. {bad[:5]}"


def test_no_correctly_cited_hadith_is_ever_flagged_wrong_reference(conn):
    """Sweep of all 7,112 scorable hadith, each quoted verbatim and cited with
    its own printed number, in the Latin citation form."""
    bad = []
    checked = 0
    for r in db.iter_records(conn):
        if r.kind != "hadith" or r.unscorable_reason is not None:
            continue
        m = _only(verify_spans(conn, f"«{r.text_ar}» (Bukhari {r.hadith_no})"))
        checked += 1
        if m.verdict is Verdict.WRONG_REFERENCE or m.record is None \
                or m.record.hadith_no != r.hadith_no:
            bad.append((r.id, m.verdict, m.record.id if m.record else None))
    assert checked == 7112, checked
    assert bad == [], f"{len(bad)} regressed, e.g. {bad[:5]}"


def test_no_correctly_cited_hadith_is_flagged_in_the_arabic_citation_form(conn):
    """Same sweep, Arabic-script citation. The two forms must be
    interchangeable: an Arabic citation is not a second-class one."""
    bad = []
    checked = 0
    for r in db.iter_records(conn):
        if r.kind != "hadith" or r.unscorable_reason is not None:
            continue
        citation = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(int(r.hadith_no))}"
        m = _only([x for x in verify_spans(conn, f"«{r.text_ar}» ({citation})")
                   if x.span.text == r.text_ar])
        checked += 1
        if m.verdict is Verdict.WRONG_REFERENCE or m.record is None \
                or m.record.hadith_no != r.hadith_no:
            bad.append((r.id, m.verdict, m.record.id if m.record else None))
    assert checked == 7112, checked
    assert bad == [], f"{len(bad)} regressed, e.g. {bad[:5]}"


def test_every_wrongly_cited_hadith_is_flagged(conn):
    """hadith:bukhari:1's text is unique in the corpus, so citing Bukhari 1
    for any hadith not printed under number 1 is genuinely wrong."""
    bad = []
    checked = 0
    for r in db.iter_records(conn):
        if r.kind != "hadith" or r.unscorable_reason is not None or r.hadith_no == "1":
            continue
        m = _only(verify_spans(conn, f"«{r.text_ar}» (Bukhari 1)"))
        checked += 1
        if m.verdict is not Verdict.WRONG_REFERENCE:
            bad.append((r.id, m.verdict))
    assert checked == 7111, checked
    assert bad == [], f"{len(bad)} not flagged, e.g. {bad[:5]}"


def test_every_record_cited_as_the_other_kind_is_flagged(conn):
    """The D1 property swept across both corpora at once, in the direction the
    fix round corrected.

    Every scorable record, quoted verbatim with a citation of the WRONG kind
    adjacent to it, must be WRONG_REFERENCE -- and must carry the citation that
    made it so. The earlier, over-corrected rule returned EXACT with
    `given_reference is None` for all 13,348 of these: a silent pass on every
    possible misattribution across the two corpora.
    """
    bad = []
    checked = 0
    for r in db.iter_records(conn):
        if r.unscorable_reason is not None:
            continue
        wrong_kind = "(Bukhari 1)" if r.kind == "ayah" else "(2:255)"
        m = _only(verify_spans(conn, f"«{r.text_ar}» {wrong_kind}"))
        checked += 1
        if m.verdict is not Verdict.WRONG_REFERENCE or m.given_reference is None:
            bad.append((r.id, m.verdict))
    assert checked == 13348, checked
    assert bad == [], f"{len(bad)} not flagged, e.g. {bad[:5]}"


# --- paths no real-corpus input can reach ------------------------------------
#
# Two branches of the kind-aware reference check cannot be exercised by
# `data/sanad-quran.db` as it stands: no ayah shares text with any hadith
# (swept and confirmed), and every hadith record is in the one collection the
# citation patterns know. An unobservable branch is one no test can watch
# fail, so -- as elsewhere in this file -- they get throwaway databases built
# to reach them, which pins the ENGINE's behaviour rather than today's data.


@pytest.fixture()
def an_ayah_and_a_hadith_with_the_same_text(tmp_path):
    from sanad.corpus.models import Record, Source
    text = "اااا بببب جججج"
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, Source(
        id="s", kind="hadith-arabic", title="t", publisher=None, edition=None,
        url="https://example.invalid/", license_id="public-domain",
        license_url=None, attribution="a", retrieved_at="2026-09-23",
        upstream_sha256="0" * 64, modifications="none"))
    common = {"source_id": "s", "text_ar": text, "text_ar_sha256": "x" * 64,
              "norm_light": text, "norm_standard": text, "norm_aggressive": text}
    db.insert_records(conn, [
        Record(id="quran:2:1", kind="ayah", surah=2, ayah=1,
               reference_display="Al-Baqarah 2:1", **common),
        Record(id="hadith:bukhari:7", kind="hadith", collection="bukhari",
               hadith_no="7", numbering_scheme="bugha-1987",
               reference_display="Sahih al-Bukhari 7", **common),
    ])
    db.rebuild_fts(conn)
    return conn, text


def test_a_tie_across_kinds_is_resolved_by_the_citation_given(
        an_ayah_and_a_hadith_with_the_same_text):
    """One wording, two records of different kinds. The citation decides which
    one the reader meant -- and each kind of citation can only ever select a
    record of its own kind."""
    conn, text = an_ayah_and_a_hadith_with_the_same_text
    m = _only(verify_spans(conn, f"«{text}» (Bukhari 7)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "hadith:bukhari:7"
    m = _only(verify_spans(conn, f"«{text}» (2:1)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:2:1"


def test_a_wrong_citation_is_reported_against_the_kind_that_was_cited(
        an_ayah_and_a_hadith_with_the_same_text):
    """The fallback in `_select_by_reference`. With no candidate agreeing, the
    record reported must be one of the kind the reader actually cited: telling
    someone who wrote "Bukhari 9" that the text is at Al-Baqarah 2:1, with no
    citation shown and no flag raised, would bury the error they made."""
    conn, text = an_ayah_and_a_hadith_with_the_same_text
    m = _only(verify_spans(conn, f"«{text}» (Bukhari 9)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "hadith:bukhari:7"
    assert m.given_reference.hadith_no == "9"
    m = _only(verify_spans(conn, f"«{text}» (2:9)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "quran:2:1"
    assert m.given_reference.surah == 2


@pytest.fixture()
def a_hadith_in_another_collection(tmp_path):
    """A hadith record NOT in Bukhari. The corpus has only Bukhari today, so
    the collection half of the hadith conflict check is otherwise dead code --
    and dead code in a correctness check is indistinguishable from a bug."""
    from sanad.corpus.models import Record, Source
    text = "اااا بببب جججج"
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, Source(
        id="s", kind="hadith-arabic", title="t", publisher=None, edition=None,
        url="https://example.invalid/", license_id="public-domain",
        license_url=None, attribution="a", retrieved_at="2026-09-23",
        upstream_sha256="0" * 64, modifications="none"))
    db.insert_records(conn, [Record(
        id="hadith:muslim:1", source_id="s", kind="hadith", collection="muslim",
        hadith_no="1", numbering_scheme="x", text_ar=text,
        text_ar_sha256="x" * 64, norm_light=text, norm_standard=text,
        norm_aggressive=text, reference_display="Sahih Muslim 1")])
    db.rebuild_fts(conn)
    return conn, text


def test_the_right_number_in_the_wrong_collection_is_a_wrong_reference(
        a_hadith_in_another_collection):
    conn, text = a_hadith_in_another_collection
    m = _only(verify_spans(conn, f"«{text}» (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "hadith:muslim:1"


def test_the_bismillah_retry_applies_the_same_kind_rule(conn):
    """The Bismillah retry has its own reference comparison, reached only
    after the text as quoted has failed at every tier. It must reach the same
    verdicts as the main path -- a branch that compared citations differently
    would be a second place for this to go wrong."""
    rec = db.get_record(conn, "quran:112:1")
    quoted = f"{rec.bismillah} {rec.text_ar}"
    m = _only(verify_spans(conn, f"«{quoted}» (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "quran:112:1"
    assert m.given_reference.hadith_no == "1"
    # ... and a verse citation on that same path still works, right and wrong.
    assert _only(verify_spans(conn, f"«{quoted}» (112:1)")).verdict is Verdict.EXACT
    assert _only(verify_spans(
        conn, f"«{quoted}» (2:255)")).verdict is Verdict.WRONG_REFERENCE


@pytest.fixture()
def a_hadith_record_carrying_verse_columns(tmp_path):
    """A hadith record with `surah`/`ayah` populated.

    Nothing in the corpus looks like this, and that is the problem: on real
    data the kind comparison in `_reference_conflicts` is redundant, because a
    verse citation compared against a hadith record disagrees anyway -- the
    record's `surah` is NULL and the citation's is not. A check that only ever
    agrees with the check beside it is a check no test can watch fail, and
    this project has shipped defects behind exactly that.

    Populating the columns isolates the rule actually being asserted: what
    decides which family of citation may address a record is its KIND, not
    which columns happen to be filled in.
    """
    from sanad.corpus.models import Record, Source
    text = "اااا بببب جججج"
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, Source(
        id="s", kind="hadith-arabic", title="t", publisher=None, edition=None,
        url="https://example.invalid/", license_id="public-domain",
        license_url=None, attribution="a", retrieved_at="2026-09-23",
        upstream_sha256="0" * 64, modifications="none"))
    db.insert_records(conn, [Record(
        id="hadith:bukhari:1", source_id="s", kind="hadith", collection="bukhari",
        hadith_no="1", numbering_scheme="bugha-1987", surah=112, ayah=1,
        text_ar=text, text_ar_sha256="x" * 64, norm_light=text,
        norm_standard=text, norm_aggressive=text,
        reference_display="Sahih al-Bukhari 1")])
    db.rebuild_fts(conn)
    return conn, text


def test_kind_decides_which_citation_family_may_address_a_record(
        a_hadith_record_carrying_verse_columns):
    conn, text = a_hadith_record_carrying_verse_columns
    # A verse citation whose surah AND ayah both match the columns -- and
    # which is still wrong, because this is a hadith.
    m = _only(verify_spans(conn, f"«{text}» (112:1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "hadith:bukhari:1"
    # The hadith citation for the same record is right.
    assert _only(verify_spans(conn, f"«{text}» (Bukhari 1)")).verdict is Verdict.EXACT
