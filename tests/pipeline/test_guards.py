from sanad.pipeline.guards import check
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
