import pytest
from sanad.corpus import db
from sanad.verify.engine import Verdict, verify_spans
from sanad.verify.references import HadithReference, Reference

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
    """`parse_references` now also yields `HadithReference`s (Task 5). A
    hadith citation sitting near a verse quotation must not be handed to the
    surah:ayah conflict check as if it were a `Reference` -- see
    `verify_spans`. Regression test for AttributeError: 'HadithReference'
    object has no attribute 'surah'."""
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Bukhari 1)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"


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


# --- D1 generalised: neither kind of citation may cross over -----------------


def test_a_quranic_citation_never_attaches_to_a_hadith_quotation(conn):
    """The findings' rule, and the point on which the brief's own Step 1 test
    was wrong: a verse citation beside a hadith quotation is NOT a wrong
    reference, it is NO reference. The brief expected WRONG_REFERENCE here;
    that would be the very false accusation D1 is about, just spelled
    differently -- the user has cited nothing at all about this hadith.
    """
    matn = db.get_record(conn, "hadith:bukhari:1").text_ar
    m = _only(verify_spans(conn, f"«{matn}» (Al-Baqarah 2:255)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "hadith:bukhari:1"
    assert m.given_reference is None


def test_a_hadith_citation_never_attaches_to_an_ayah_quotation(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Bukhari 1)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"
    assert m.given_reference is None


def test_a_hadith_citation_cannot_rescue_a_wrong_verse_citation(conn):
    """Both kinds present, the verse one wrong: the verse quotation must still
    be flagged. A fix that simply preferred "the reference of the same kind as
    the nearest one" would pass the two tests above and fail this."""
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Bukhari 1) (2:4)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.given_reference.surah == 2


def test_a_quranic_citation_cannot_rescue_a_wrong_hadith_citation(conn):
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    m = _only(verify_spans(conn, f"«{matn}» (112:1) (Bukhari 1)"))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.given_reference.hadith_no == "1"


def test_cross_kind_attachment_is_impossible_by_construction():
    """Not "no cross-kind citation is near enough" -- there is no route.

    `_NearbyReferences` has one field per kind, each typed to the one
    reference class that cites it, and `for_kind` is the only way out. A
    distance-based guard would have to be remembered at every call site; this
    holds even if a future caller forgets.
    """
    from sanad.verify.engine import _NearbyReferences

    verse = Reference(112, 1, "112:1", 0)
    hadith = HadithReference("bukhari", "1", "Bukhari 1", 0)

    verse_only = _NearbyReferences(ayah=verse, hadith=None, nearest=verse)
    assert verse_only.for_kind("ayah") is verse
    assert verse_only.for_kind("hadith") is None

    hadith_only = _NearbyReferences(ayah=None, hadith=hadith, nearest=hadith)
    assert hadith_only.for_kind("hadith") is hadith
    assert hadith_only.for_kind("ayah") is None

    both = _NearbyReferences(ayah=verse, hadith=hadith, nearest=hadith)
    assert both.for_kind("ayah") is verse
    assert both.for_kind("hadith") is hadith
    # A kind nothing cites gets nothing, rather than falling back to "any".
    assert both.for_kind("tafsir") is None


def test_the_window_is_not_what_keeps_the_kinds_apart(conn):
    """A verse citation immediately adjacent to a hadith quotation -- zero
    distance, nothing for a window to exclude -- still does not attach.
    Pins that the fix is structural, so nobody is tempted to widen or narrow
    `window=180` to influence it."""
    from sanad.verify.references import nearest_reference

    matn = db.get_record(conn, "hadith:bukhari:1").text_ar
    m = _only(verify_spans(conn, f"(2:255)«{matn}»(2:255)"))
    assert m.verdict is Verdict.EXACT
    assert m.given_reference is None
    # And the same at the level below, with the window shut to nothing.
    verse = Reference(2, 255, "2:255", 0)
    assert nearest_reference([verse], 0, kind="hadith", window=10_000) is None


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
    """The findings' generalisation of D1, in both citation languages and in
    both orders, with the verse citation nearer than the hadith one."""
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    latin = "Bukhari 2866"
    arabic = f"{_SAHIH_AL_BUKHARI_AR} {_arabic_indic(2866)}"
    for citation in (latin, arabic):
        for text in (f"(112:1) «{matn}» ({citation})",
                     f"({citation}) «{matn}» (112:1)",
                     f"(112:1) ({citation}) «{matn}»"):
            m = _only([x for x in verify_spans(conn, text) if x.span.text == matn])
            assert m.verdict is Verdict.EXACT, text
            assert m.record.id == "hadith:bukhari:2866"


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


def test_no_hadith_verifies_under_a_quranic_citation_or_vice_versa(conn):
    """The D1 property swept across both corpora at once: a citation of the
    other kind is never allowed to decide a verdict. Every scorable record,
    quoted verbatim with a citation of the WRONG kind attached, must reach
    exactly the verdict it reaches with no citation at all."""
    bad = []
    checked = 0
    for r in db.iter_records(conn):
        if r.unscorable_reason is not None:
            continue
        wrong_kind = "(Bukhari 1)" if r.kind == "ayah" else "(2:255)"
        plain = _only(verify_spans(conn, f"«{r.text_ar}»"))
        crossed = _only(verify_spans(conn, f"«{r.text_ar}» {wrong_kind}"))
        checked += 1
        if crossed.verdict is not plain.verdict or crossed.given_reference is not None:
            bad.append((r.id, plain.verdict, crossed.verdict))
    assert checked == 13348, checked
    assert bad == [], f"{len(bad)} differed, e.g. {bad[:5]}"


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


def test_a_hadith_citation_does_not_attach_through_the_bismillah_retry(conn):
    """The Bismillah retry has its own reference comparison, reached only
    after the text as quoted has failed at every tier. It must obey the same
    kind rule as the main path -- a branch that took a different route to the
    citation would be a second place for D1 to come back."""
    rec = db.get_record(conn, "quran:112:1")
    m = _only(verify_spans(conn, f"«{rec.bismillah} {rec.text_ar}» (Bukhari 1)"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"
    assert m.given_reference is None
    # ... and a verse citation on that same path still works, right and wrong.
    assert _only(verify_spans(
        conn, f"«{rec.bismillah} {rec.text_ar}» (112:1)")).verdict is Verdict.EXACT
    assert _only(verify_spans(
        conn, f"«{rec.bismillah} {rec.text_ar}» (2:255)")
    ).verdict is Verdict.WRONG_REFERENCE
