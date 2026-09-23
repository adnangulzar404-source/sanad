from pathlib import Path

from eval.runner import Case, load_cases, run_eval
from sanad.corpus import db

CASES = Path("eval/cases")


def test_loads_every_case_file():
    cases = load_cases(CASES)
    assert len(cases) >= 19
    assert len({c.id for c in cases}) == len(cases), "case ids must be unique"


def test_full_suite_passes():
    metrics = run_eval(db.connect("data/sanad-quran.db"), load_cases(CASES))
    assert metrics.failures == [], f"failing cases: {metrics.failures}"


def test_no_false_verifications():
    metrics = run_eval(db.connect("data/sanad-quran.db"), load_cases(CASES))
    assert metrics.false_verifications == 0


def test_no_false_misattributions():
    # The second gated metric: a WRONG_REFERENCE no case licensed. Tracked
    # here beside its sibling because CI reads both, and because the whole
    # point of the addition is that the two are one severity class.
    metrics = run_eval(db.connect("data/sanad-quran.db"), load_cases(CASES))
    assert metrics.false_misattributions == 0


def test_a_mutation_case_is_never_verified():
    conn = db.connect("data/sanad-quran.db")
    cases = [c for c in load_cases(CASES) if c.id.startswith("mutation-")]
    assert cases
    metrics = run_eval(conn, cases)
    assert metrics.false_verifications == 0


def test_gate_catches_a_false_verification_in_a_second_span():
    # Regression pin for Fix 4: `run_eval` used to inspect only `matches[0]`,
    # so a false verification landing in a LATER span was invisible to the
    # gate. Build one case whose text produces two spans: the first is
    # genuinely NOT_FOUND (a fabrication, matching `expect_verdict`) and the
    # second is a real, unrelated verse that verifies EXACT on its own. Under
    # the old first-span-only check this case would pass silently, hiding a
    # verified quotation the case never claimed to expect. The broadened gate
    # must catch it as a false verification.
    conn = db.connect("data/sanad-quran.db")
    fabricated = "هذا كلام مخترع تماما وليس من القران الكريم ابدا"
    real_verse = db.get_record(conn, "quran:112:1").text_ar
    case = Case(
        id="second-span-offender",
        text=f"«{fabricated}» «{real_verse}»",
        rationale="second-span false verification must not hide behind matches[0]",
        expect_verdict="NOT_FOUND",
    )
    metrics = run_eval(conn, [case])
    assert metrics.false_verifications == 1
    assert any("FALSE VERIFICATION" in f for f in metrics.failures)
