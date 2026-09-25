from sanad.pipeline.guards import check, contains_arabic, word_count
from sanad.pipeline.types import Selection, SelectedItem

CANDS = {"quran:2:183", "hadith:bukhari:2866"}

def _sel(summary="Sources on the topic.", items=None):
    return Selection(summary=summary,
                     items=items or [SelectedItem("quran:2:183", "A framing.")])

def _blocked(sel, name):
    results = check(sel, CANDS)
    g = next(r for r in results if r.name == name)
    return not g.passed

def test_all_pass_on_a_clean_brief():
    assert all(r.passed for r in check(_sel(), CANDS))

def test_blocks_id_outside_candidate_set():
    sel = _sel(items=[SelectedItem("quran:9:9999", "Fabricated.")])
    assert _blocked(sel, "cited_id_in_candidates")

def test_blocks_arabic_in_framing():
    sel = _sel(items=[SelectedItem("quran:2:183", "It reads كتب عليكم.")])
    assert _blocked(sel, "no_arabic_in_prose")

def test_blocks_arabic_in_summary():
    assert _blocked(_sel(summary="The verse الصيام is relevant."), "no_arabic_in_prose")

def test_blocks_overlong_summary():
    assert _blocked(_sel(summary=" ".join(["word"] * 81)), "length_bounds")

def test_blocks_overlong_framing():
    sel = _sel(items=[SelectedItem("quran:2:183", " ".join(["w"] * 26))])
    assert _blocked(sel, "length_bounds")

def test_blocks_unanimity_claim():
    assert _blocked(_sel(summary="All scholars agree this is obligatory."),
                    "no_unanimity")

def test_blocks_grading_claim():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866", "This hadith is sahih.")])
    assert _blocked(sel, "no_grading")

# --- collisions that MUST PASS (a guard that suppresses correct output fails) ---
def test_citation_of_sahih_al_bukhari_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "Reported in Sahih al-Bukhari 2866 on striving.")])
    assert all(r.passed for r in check(sel, CANDS))

def test_naming_al_hasan_al_basri_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "Narrated via al-Hasan al-Basri about patience.")])
    assert all(r.passed for r in check(sel, CANDS))


# =====================================================================
# Fix round 1 (task-8-review.md) — C1/C2/I1/I3, hyphen-tolerant grading,
# tolerant collection-title exemption, diacritic-folded unanimity.
# =====================================================================

# --- ruling a: hyphenation must not bypass grading detection (C1) ---

def test_blocks_hyphenated_al_sahih():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "This narration is al-sahih and trustworthy.")])
    assert _blocked(sel, "no_grading")

def test_blocks_hyphenated_non_sahih():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866", "This report is non-sahih.")])
    assert _blocked(sel, "no_grading")

def test_blocks_hyphenated_quasi_daif():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "It is considered quasi-daif by some.")])
    assert _blocked(sel, "no_grading")

def test_blocks_al_sahih_graded_by_scholars():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866", "graded al-Sahih by scholars")])
    assert _blocked(sel, "no_grading")

# --- ruling b: tolerant collection-title exemption must PASS (C2) ---

def test_sahih_bukhari_without_al_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "Reported in Sahih Bukhari 2866 on striving.")])
    assert all(r.passed for r in check(sel, CANDS))

def test_the_sahih_of_bukhari_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "This is found in the Sahih of Bukhari.")])
    assert all(r.passed for r in check(sel, CANDS))

def test_sahih_al_bukhaari_alt_spelling_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "The hadith is recorded in Sahih al-Bukhaari 2866.")])
    assert all(r.passed for r in check(sel, CANDS))

def test_sahih_muslim_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "This is also found in Sahih Muslim.")])
    assert all(r.passed for r in check(sel, CANDS))

# --- ruling c: dropping the name-particle exemption must not create new
# false negatives (a real grading term next to an invented name still blocks)

def test_abu_sahih_no_longer_a_false_negative():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "According to Abu Sahih this report stands uncontested.")])
    assert _blocked(sel, "no_grading")

def test_ibn_daif_no_longer_a_false_negative():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "The narrator Ibn Daif reported this chain.")])
    assert _blocked(sel, "no_grading")

# --- ruling d: diacritic-folded unanimity, plus new phrasings ---

def test_blocks_ijma_with_macron():
    # Built from codepoints via chr(), not typed glyphs, per
    # sanad-character-transit-defect: U+0101 LATIN SMALL LETTER A WITH MACRON.
    ijma = "ijm" + chr(0x0101)
    assert _blocked(_sel(summary=f"This is a matter of {ijma} (consensus) among jurists."),
                    "no_unanimity")

def test_blocks_ijma_with_macron_and_ayin():
    # U+0101 a-macron + U+02BF MODIFIER LETTER LEFT HALF RING (ayin).
    ijmaa = "ijm" + chr(0x0101) + chr(0x02BF)
    assert _blocked(_sel(summary=f"This is a matter of {ijmaa} among jurists."),
                    "no_unanimity")

def test_blocks_consensus_among_scholars():
    assert _blocked(_sel(summary="There is consensus among scholars on this ruling."),
                    "no_unanimity")

def test_blocks_scholars_have_all_agreed():
    assert _blocked(_sel(summary="The scholars have all agreed on this matter."),
                    "no_unanimity")

def test_blocks_no_disagreement_among():
    assert _blocked(_sel(summary="There is no disagreement among the scholars on this."),
                    "no_unanimity")

# --- ruling e: failing guards must name the offending value ---

def test_arabic_detail_names_the_framing_record_id():
    sel = _sel(items=[SelectedItem("quran:2:183", "It reads كتب عليكم.")])
    g = next(r for r in check(sel, CANDS) if r.name == "no_arabic_in_prose")
    assert "quran:2:183" in g.detail

def test_arabic_detail_names_the_summary():
    g = next(r for r in check(_sel(summary="The verse الصيام is relevant."), CANDS)
             if r.name == "no_arabic_in_prose")
    assert "summary" in g.detail

def test_length_detail_names_field_and_count():
    sel = _sel(items=[SelectedItem("quran:2:183", " ".join(["w"] * 26))])
    g = next(r for r in check(sel, CANDS) if r.name == "length_bounds")
    assert "quran:2:183" in g.detail and "26" in g.detail

def test_length_detail_names_summary_and_count():
    g = next(r for r in check(_sel(summary=" ".join(["word"] * 81)), CANDS)
             if r.name == "length_bounds")
    assert "summary" in g.detail and "81" in g.detail

def test_unanimity_detail_quotes_matched_phrase():
    g = next(r for r in check(_sel(summary="All scholars agree this is obligatory."), CANDS)
             if r.name == "no_unanimity")
    assert "all scholars agree" in g.detail.lower()

def test_grading_detail_quotes_matched_term():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866", "This hadith is sahih.")])
    g = next(r for r in check(sel, CANDS) if r.name == "no_grading")
    assert "sahih" in g.detail.lower()

# --- ruling f: minors ---

def test_arabic_extended_a_annotation_mark_detected():
    # U+08E6 ARABIC SMALL HIGH LIGATURE ALEF WITH YEH BARREE (Extended-A),
    # built from the codepoint via chr() rather than a typed glyph, per
    # sanad-character-transit-defect: eyeballing a pasted glyph cannot
    # confirm which codepoint it actually is.
    mark = chr(0x08E6)
    assert contains_arabic(f"plain text {mark} fragment")

def test_matrook_alt_spelling_blocks():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "Scholars consider this hadith matrook.")])
    assert _blocked(sel, "no_grading")

def test_contains_arabic_direct():
    assert contains_arabic("كتب") is True
    assert contains_arabic("sahih") is False

def test_word_count_direct():
    assert word_count("one two three") == 3
    assert word_count("") == 0


# =====================================================================
# Fix round 2 (ruling g) — the collection-title exemption must require a
# TITLE BOUNDARY after the collection name (a hadith number, end-of-clause
# punctuation, end-of-string, or an "and"/"or" connector to another title),
# not just the bare name. Otherwise a punctuation-free run-on where a real
# grading claim happens to be followed by a bare collection name slips
# through unblocked.
# =====================================================================

# --- must BLOCK: run-on sentences the ruling-b fix newly let through ---

def test_blocks_sahih_bukhari_runon_has_documented():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "This narration is sahih Bukhari has documented similarly.")])
    assert _blocked(sel, "no_grading")

def test_blocks_sahih_bukhari_runon_also_lists():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "It is considered sahih Bukhari also lists other versions.")])
    assert _blocked(sel, "no_grading")

# --- hard constraint: every title-boundary form must still PASS ---

def test_sahih_muslim_with_number_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866", "Sahih Muslim 1234")])
    assert all(r.passed for r in check(sel, CANDS))

# (test_sahih_bukhari_without_al_passes, test_sahih_al_bukhaari_alt_spelling_passes,
# test_the_sahih_of_bukhari_passes, test_citation_of_sahih_al_bukhari_passes, and
# test_naming_al_hasan_al_basri_passes above already cover the number/period/
# end-of-string/original/unrelated hard-constraint rows verbatim.)

# --- round-1 must-BLOCK sanity check, named explicitly in the ruling ---

def test_graded_al_sahih_by_majority_of_scholars_blocks():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "This report is graded al-Sahih by the majority of "
                                   "hadith scholars.")])
    assert _blocked(sel, "no_grading")

def test_sahih_muslim_hadith_itself_graded_sahih_blocks():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "This Sahih Muslim hadith is itself graded sahih.")])
    assert _blocked(sel, "no_grading")
