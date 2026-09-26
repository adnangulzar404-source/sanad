# eval/ask_runner.py — Task 12: the Ask eval gate (spec §10, layer 1).
#
# This gates the GUARDS, not the model: no Claude call, no network, no API
# keys. The fixtures under eval/cases/ask/ are synthetic stage-3 outputs
# (what a Selection would look like if Claude had already produced it), fed
# straight into `pipeline.guards.check`.
#
# Two-sided by construction, per this branch's Stage A2 history
# (sanad-verify-dont-assert): a gate that only counts attacks blocked reads
# green even if it also blocks every legitimate brief -- the exact shape of
# "satisfied by blocking everything, Ask returns nothing". So this gate
# tracks BOTH directions independently:
#   - block_failures: a `must_block` fixture (an attack: fabricated id, id
#     outside the candidate set, Arabic in prose, a grading claim, a
#     unanimity claim, an over-length summary) that the guards let through.
#   - pass_failures: a `must_block: false` fixture (a legitimate brief that
#     merely collides with a guard's pattern -- citing "Sahih al-Bukhari
#     2866", naming al-Hasan al-Basri) that the guards wrongly blocked.
# Either list being non-empty fails the gate.
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sanad.pipeline.guards import check
from sanad.pipeline.types import SelectedItem, Selection


@dataclass(frozen=True)
class AskCase:
    id: str
    candidate_ids: list[str]
    selection: Selection
    must_block: bool


@dataclass
class AskMetrics:
    total: int = 0
    passed: int = 0
    block_failures: list[str] = field(default_factory=list)   # should block, didn't
    pass_failures: list[str] = field(default_factory=list)     # should pass, blocked


def load_ask_cases(directory: Path) -> list[AskCase]:
    cases: list[AskCase] = []
    seen: set[str] = set()
    for path in sorted(Path(directory).glob("*.json")):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            if raw["id"] in seen:
                raise ValueError(f"duplicate ask case id {raw['id']!r}")
            seen.add(raw["id"])
            sel = Selection(
                summary=raw["selection"]["summary"],
                items=[SelectedItem(i["record_id"], i["framing"])
                       for i in raw["selection"]["items"]])
            cases.append(AskCase(raw["id"], list(raw["candidate_ids"]),
                                 sel, bool(raw["must_block"])))
    return cases


def run_ask_gate(cases: list[AskCase]) -> AskMetrics:
    m = AskMetrics(total=len(cases))
    for c in cases:
        results = check(c.selection, set(c.candidate_ids))
        blocked = not all(g.passed for g in results)
        if c.must_block and not blocked:
            m.block_failures.append(c.id)
        elif not c.must_block and blocked:
            offenders = [g.name for g in results if not g.passed]
            m.pass_failures.append(f"{c.id} (blocked by {offenders})")
        else:
            m.passed += 1
    return m


def main(argv: list[str] | None = None) -> int:
    cases = load_ask_cases(Path("eval/cases/ask"))
    m = run_ask_gate(cases)
    print(f"ask cases {m.total}  passed {m.passed}")
    if m.block_failures:
        print(f"GATE FAILED: attacks that were NOT blocked: {m.block_failures}",
              file=sys.stderr)
    if m.pass_failures:
        print(f"GATE FAILED: correct briefs that WERE blocked: {m.pass_failures}",
              file=sys.stderr)
    return 1 if (m.block_failures or m.pass_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
