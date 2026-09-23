"""Tests on the eval CASES themselves, not on what the engine does with them.

`test_runner.py` asks whether the suite passes. This file asks whether the
suite is capable of failing -- which is a different question, and the one this
project keeps getting wrong. Four tests on this branch turned out to be
incapable of failing, two of them because the plan text that specified them was
itself wrong, and one of the eleven Arabic-in-transit defects was inside the
test written to catch Arabic-in-transit defects.

So: every Arabic string in `eval/cases/` that is meant to be corpus text is
compared against the database, byte for byte, here. And every string that is
meant to DIFFER from corpus text is checked to still differ -- a mutation case
whose mutation was quietly normalised away by an editor, a copy-paste, or a
YAML round-trip is a case that passes while testing nothing.
"""
from pathlib import Path

import pytest
from sanad.corpus import db
from sanad.corpus.scope import CORPUS_SCOPE

from eval.runner import VERIFIED, Case, load_cases, run_eval

CASES = Path("eval/cases")
DB = "data/sanad-quran.db"


@pytest.fixture(scope="module")
def conn():
    return db.connect(DB)


@pytest.fixture(scope="module")
def cases():
    return load_cases(CASES)


@pytest.fixture(scope="module")
def hadith_cases(cases):
    ids = {c.id for c in _load_file("hadith.yaml")}
    return [c for c in cases if c.id in ids]


def _load_file(name: str) -> list[Case]:
    import yaml
    raw = yaml.safe_load((CASES / name).read_text(encoding="utf-8"))
    return [Case(**item) for item in raw]


def _representations(conn, record_id: str) -> list[str]:
    """Every stored text a quotation of this record could legitimately be.

    A hadith is indexed under two: its primary matn, and the full printed
    entry (matn + the secondary narrations the edition appends). Both are
    correct things for a reader to have quoted.
    """
    rec = db.get_record(conn, record_id)
    assert rec is not None, f"case names a record that is not in the corpus: {record_id}"
    texts = [rec.text_ar]
    texts += [row["text_ar"] for row in conn.execute(
        "SELECT text_ar FROM record_variants WHERE record_id = ?", (record_id,))]
    return texts


# --- the cases exist and are wired into the gate -------------------------

def test_hadith_case_file_is_loaded_by_the_runner(cases, hadith_cases):
    # Not "the file parses" -- "the runner picked it up". A case file that
    # `load_cases` never globs is a gate that is not gating.
    assert len(hadith_cases) >= 18
    assert set(hadith_cases) <= set(cases)


def test_hadith_cases_run_clean(conn, hadith_cases):
    metrics = run_eval(conn, hadith_cases)
    assert metrics.failures == [], f"failing cases: {metrics.failures}"
    assert metrics.false_verifications == 0


# --- the Arabic is what it claims to be ----------------------------------

def test_quoted_records_appear_verbatim_in_the_case_text(conn, hadith_cases):
    """Every hadith case that expects EXACT really does contain corpus bytes.

    This is the guard against the specific failure that has bitten this
    project eleven times: Arabic that looks right, reads right, and is not the
    bytes in the database -- at which point the case still passes or fails for
    reasons that have nothing to do with what it says it is testing.
    """
    checked = 0
    for case in hadith_cases:
        if case.expect_verdict != "EXACT" or case.expect_record is None:
            continue
        texts = _representations(conn, case.expect_record)
        assert any(t in case.text for t in texts), (
            f"{case.id}: expects EXACT against {case.expect_record} but none of that "
            f"record's stored representations appears verbatim in the case text")
        checked += 1
    assert checked >= 6, "the byte check stopped covering the cases it was written for"


def test_wrong_reference_cases_quote_the_record_verbatim_too(conn, hadith_cases):
    """WRONG_REFERENCE means "right text, wrong citation" -- so the text must
    be right. A case that misquotes AND miscites would get the expected
    verdict for the wrong reason and would stop testing the citation logic.
    """
    checked = 0
    for case in hadith_cases:
        if case.expect_verdict != "WRONG_REFERENCE" or case.expect_record is None:
            continue
        texts = _representations(conn, case.expect_record)
        assert any(t in case.text for t in texts), (
            f"{case.id}: expects WRONG_REFERENCE against {case.expect_record}, so the "
            f"quoted text must be that record's text verbatim -- it is not")
        checked += 1
    assert checked >= 4


def test_the_mutation_case_is_still_mutated(conn, hadith_cases):
    """The counterpart: deliberately different, and still different.

    `hadith-one-word-altered` is one character away from hadith 1. If that
    character is ever repaired -- by an editor normalising Arabic, by a
    round-trip through a tool, by someone "fixing the typo" -- the case starts
    quoting the corpus exactly, the engine correctly answers EXACT, and the
    case fails loudly instead of silently passing as a misquote test that no
    longer contains a misquote. Both halves are asserted so neither drift can
    hide.
    """
    case = next(c for c in hadith_cases if c.id == "hadith-one-word-altered")
    matn = db.get_record(conn, "hadith:bukhari:1").text_ar
    assert matn not in case.text, (
        "hadith-one-word-altered now contains the corpus text verbatim; "
        "the mutation has been undone and the case tests nothing")
    # Still recognisably the same narration, not an unrelated string: one
    # character shorter, and sharing both ends with it.
    assert len(case.text) == len(matn) - 1
    assert case.text[:10] == matn[:10] and case.text[-10:] == matn[-10:]


def test_texts_absent_from_the_corpus_really_are_absent(conn, hadith_cases):
    """The two "not in this corpus" cases must not be in the corpus.

    Their Arabic cannot be copied out of the database -- that is the point of
    them -- so it is the one Arabic in this suite that was typed. If either
    string ever turns out to BE corpus text, the case is asserting the
    opposite of what it says, so it is checked directly against every stored
    representation rather than trusted.
    """
    absent = [c for c in hadith_cases if c.expect_scope_caveat]
    assert len(absent) == 2
    for case in absent:
        needle = case.text.strip()
        assert needle
        hit = conn.execute(
            "SELECT id FROM records WHERE text_ar = ? "
            "UNION SELECT record_id FROM record_variants WHERE text_ar = ?",
            (needle, needle)).fetchone()
        assert hit is None, f"{case.id}: {needle!r} is in the corpus after all ({hit})"


def test_no_case_asserts_an_authenticity_claim(cases):
    """Sanad may say a text is IN Sahih al-Bukhari. It may never say a hadith
    IS sahih, and no case may assert or depend on that. The eval suite is
    where such a claim would be easiest to smuggle in, because a rationale
    reads like prose rather than like an assertion -- but a case justified by
    "this hadith is sound" is a case that will one day be defended on those
    grounds.
    """
    forbidden = ("is sahih", "is authentic", "is sound", "sound hadith",
                 "authentic hadith", "is da'if", "is weak", "is fabricated",
                 "is a fabrication")
    for case in cases:
        haystack = f"{case.id} {case.rationale}".lower()
        for phrase in forbidden:
            assert phrase not in haystack, (
                f"{case.id}: rationale contains an authenticity claim ({phrase!r}); "
                f"Sanad verifies wording, it does not grade")


# --- the new expectation fields are load-bearing -------------------------

def test_forbid_verdict_rejects_a_verdict_that_does_not_exist():
    """A typo in `forbid_verdict` would make the case pass forever.

    `expect_verdict: EXCAT` fails loudly, because no real verdict equals it.
    `forbid_verdict: WRONG_REFRENCE` does the opposite: no real verdict can
    ever equal it either, so the prohibition can never trip and the case is
    permanently, invisibly green. Rejected at load time for that reason.
    """
    with pytest.raises(ValueError, match="not a real"):
        Case(id="x", text="y", rationale="z", forbid_verdict="WRONG_REFRENCE")
    # and the valid spelling is accepted
    Case(id="x", text="y", rationale="z", forbid_verdict="WRONG_REFERENCE")


def test_forbid_verdict_catches_an_offender_in_a_later_span(conn):
    """`expect_verdict` only ever inspects `matches[0]`.

    The defect `forbid_verdict` exists for -- a correct citation reported as a
    misattribution -- lands on whichever span the distance bug touches. Build
    a case whose FIRST span is a clean EXACT and whose second is a genuine
    WRONG_REFERENCE, and confirm the prohibition sees the second one. Without
    this, `forbid_verdict` could be scoped to the first span and every case
    using it would still pass.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    ayah = db.get_record(conn, "quran:112:1").text_ar
    case = Case(
        id="later-span-wrong-reference",
        text=f"«{matn}» (Bukhari 2866) and «{ayah}» (Bukhari 1)",
        rationale="second span is a real misattribution",
        expect_verdict="EXACT",
        forbid_verdict="WRONG_REFERENCE",
    )
    metrics = run_eval(conn, [case])
    assert any("forbidden verdict WRONG_REFERENCE" in f for f in metrics.failures), \
        metrics.failures


def test_expect_no_other_record_catches_a_match_on_the_wrong_record(conn):
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    case = Case(
        id="strays",
        text=matn,
        rationale="asserting the wrong record on purpose",
        expect_no_other_record="hadith:bukhari:1",
    )
    metrics = run_eval(conn, [case])
    assert any("matched a different record" in f for f in metrics.failures), metrics.failures


def test_expect_no_quotation_fails_when_a_quotation_is_found(conn):
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    yes = Case(id="a", text=matn, rationale="r", expect_no_quotation=True)
    assert any("quotations: expected none" in f
               for f in run_eval(conn, [yes]).failures)
    # and the inverse direction is checked too, so the field cannot be
    # satisfied merely by being present
    no = Case(id="b", text="plain English prose", rationale="r",
              expect_no_quotation=False)
    assert any("expected at least one" in f for f in run_eval(conn, [no]).failures)


def test_expect_handoff_fails_when_nothing_diverts(conn):
    case = Case(id="c", text="How many verses does Al-Ikhlas have?", rationale="r",
                expect_handoff=True)
    assert any("handoff: expected True" in f for f in run_eval(conn, [case]).failures)


def test_expect_scope_caveat_fails_when_the_text_resolves(conn):
    """The caveat explains an absence. If there is no absence, the case is
    mis-specified and must say so rather than pass on the strength of the
    caveat constant being intact.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    case = Case(id="d", text=matn, rationale="r", expect_scope_caveat=True)
    assert any("expected an unresolved quotation" in f
               for f in run_eval(conn, [case]).failures)


def test_scope_caveat_still_says_both_things_it_has_to_say():
    """Guarded here as well as in the runner, in plain sight.

    "Not in this corpus" is only honest next to a statement of what the corpus
    is. Drop either half -- the fact that Sahih al-Bukhari is the only
    collection here, or the fact that absence proves nothing -- and NOT_FOUND
    on a hadith starts reading as an accusation.
    """
    assert "Sahih al-Bukhari" in CORPUS_SCOPE
    assert "does not establish that a quotation is fabricated" in CORPUS_SCOPE


def test_no_claim_note_denies_that_a_hadith_corpus_is_bundled(conn):
    """Sanad must not contradict itself in a single response.

    The `hadith_unverifiable` note read "No licensed Hadith edition is bundled
    in this corpus" long after Sahih al-Bukhari was ingested, so a reader
    quoting a hadith Sanad had just verified word for word was told, on the
    same screen, that there was no hadith edition to check it against. A note
    that denies the corpus exists undermines every true verification printed
    beside it.
    """
    from sanad.verify.claims import detect_claims
    notes = " ".join(c.note for c in detect_claims("See Bukhari 2866 for this hadith."))
    assert notes, "the hadith claim rule stopped firing"
    for denial in ("no licensed hadith", "no hadith corpus", "not bundled",
                   "is bundled in this corpus"):
        assert denial not in notes.lower(), (
            f"a claim note still tells the reader {denial!r} while the corpus "
            f"contains 7,129 hadith")


# --- the gate itself -----------------------------------------------------

def test_verified_verdicts_are_the_two_that_endorse_a_quotation():
    # If a third verdict were ever added to VERIFIED, every case in the suite
    # that merely avoids EXACT would stop being a gate against it.
    assert VERIFIED == {"EXACT", "EXACT_ORTHOGRAPHY"}


def test_whole_suite_still_has_zero_false_verifications(conn, cases):
    metrics = run_eval(conn, cases)
    assert metrics.false_verifications == 0
    assert metrics.failures == []
