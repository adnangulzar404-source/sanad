# tests/eval/test_ask_runner.py — the Ask eval gate (task 12, spec §10).
#
# Two-sided by construction: `run_ask_gate` tracks BOTH directions
# independently (`block_failures` for attacks that slipped through,
# `pass_failures` for legitimate briefs the guards wrongly blocked). A gate
# that only asserted one of these could read green while the other class of
# defect went undetected — see sanad-verify-dont-assert and this branch's
# Stage A2 history, where a one-sided counter read 54/54 while two Critical
# bugs were live because it structurally could not see the other error class.
from pathlib import Path

from eval.ask_runner import load_ask_cases, run_ask_gate

CASES = Path("eval/cases/ask")


def test_every_must_block_case_is_blocked():
    m = run_ask_gate(load_ask_cases(CASES))
    assert m.block_failures == [], m.block_failures


def test_every_must_pass_case_passes():
    m = run_ask_gate(load_ask_cases(CASES))
    assert m.pass_failures == [], m.pass_failures


def test_gate_counts_all_fixtures():
    m = run_ask_gate(load_ask_cases(CASES))
    assert m.total >= 9   # 7 adversarial + 2 collisions
