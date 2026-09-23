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
