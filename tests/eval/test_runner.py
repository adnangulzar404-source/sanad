from pathlib import Path

from eval.runner import load_cases, run_eval
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


def test_a_mutation_case_is_never_verified():
    conn = db.connect("data/sanad-quran.db")
    cases = [c for c in load_cases(CASES) if c.id.startswith("mutation-")]
    assert cases
    metrics = run_eval(conn, cases)
    assert metrics.false_verifications == 0
