"""Adversarial evaluation harness.

False verification -- reporting a misquote as EXACT or EXACT_ORTHOGRAPHY -- is
the one metric that gates CI. Everything else is tracked and reported.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sanad.corpus import db
from sanad.verify.claims import detect_claims, route_risk
from sanad.verify.engine import Verdict, verify_spans

VERIFIED = {Verdict.EXACT.value, Verdict.EXACT_ORTHOGRAPHY.value}

# Every verdict the engine can actually produce. A case whose expect_verdict
# does not spell one of these correctly (a typo such as "EXCAT") must be
# rejected loudly at load time -- a typo that silently never matches would
# make every such case pass vacuously (verdict != "EXCAT" is trivially true
# for any real verdict), which defeats the entire point of a gate.
_VALID_VERDICTS = {v.value for v in Verdict}


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    rationale: str
    expect_verdict: str | None = None
    expect_record: str | None = None
    expect_claim: str | None = None
    expect_risk: str | None = None

    def __post_init__(self) -> None:
        if self.expect_verdict is not None and self.expect_verdict not in _VALID_VERDICTS:
            raise ValueError(
                f"case {self.id!r}: expect_verdict {self.expect_verdict!r} is not a real "
                f"Verdict (expected one of {sorted(_VALID_VERDICTS)})")


@dataclass
class Metrics:
    total: int = 0
    passed: int = 0
    false_verifications: int = 0
    failures: list[str] = field(default_factory=list)
    by_verdict: dict[str, int] = field(default_factory=dict)


def load_cases(directory: Path) -> list[Case]:
    cases: list[Case] = []
    seen: dict[str, str] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            case = Case(**raw)
            # Two cases sharing an id would let one silently shadow the other
            # -- e.g. in any lookup keyed by id, or in a future report that
            # indexes results by case id. Reject the duplicate at load time
            # rather than let it pass silently.
            if case.id in seen:
                raise ValueError(
                    f"duplicate case id {case.id!r} in {path} (first seen in {seen[case.id]})")
            seen[case.id] = str(path)
            cases.append(case)
    return cases


def run_eval(conn, cases: list[Case]) -> Metrics:
    m = Metrics(total=len(cases))

    for case in cases:
        problems: list[str] = []
        matches = verify_spans(conn, case.text)
        top = matches[0] if matches else None
        verdict = top.verdict.value if top else None

        if verdict:
            m.by_verdict[verdict] = m.by_verdict.get(verdict, 0) + 1

        # The gate: a case whose expectation is not a verified verdict must
        # never actually produce one -- in ANY span, not just the first. A
        # false verification landing in a second or later span (e.g. a
        # two-quotation case where only the second is the fabrication) is
        # exactly as dangerous as one in the first, and must not be invisible
        # to CI just because `matches[0]` happened to be clean. Per-case
        # verdict/record assertions below stay scoped to `top` -- only this
        # gate broadens to scan every match.
        if case.expect_verdict not in VERIFIED and any(
                mt.verdict.value in VERIFIED for mt in matches):
            m.false_verifications += 1
            problems.append(
                f"FALSE VERIFICATION: expected {case.expect_verdict}, got "
                f"{[mt.verdict.value for mt in matches]}")

        if case.expect_verdict is not None and verdict != case.expect_verdict:
            problems.append(f"verdict: expected {case.expect_verdict}, got {verdict}")

        if case.expect_record is not None:
            got = top.record.id if top and top.record else None
            if got != case.expect_record:
                problems.append(f"record: expected {case.expect_record}, got {got}")

        if case.expect_claim is not None:
            kinds = {c.kind for c in detect_claims(case.text)}
            if case.expect_claim not in kinds:
                problems.append(f"claim: expected {case.expect_claim}, got {sorted(kinds)}")

        if case.expect_risk is not None:
            got_risk = route_risk(case.text).value
            if got_risk != case.expect_risk:
                problems.append(f"risk: expected {case.expect_risk}, got {got_risk}")

        if problems:
            m.failures.append(f"{case.id}: " + "; ".join(problems))
        else:
            m.passed += 1

    return m


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sanad-eval")
    parser.add_argument("--cases", type=Path, default=Path("eval/cases"))
    parser.add_argument("--db", type=Path, default=Path("data/sanad-quran.db"))
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    m = run_eval(db.connect(args.db), cases)

    print(f"cases               {m.total}")
    print(f"passed              {m.passed}")
    print(f"failed              {len(m.failures)}")
    print(f"false verifications {m.false_verifications}")
    print("verdict distribution:")
    for verdict, count in sorted(m.by_verdict.items()):
        print(f"  {verdict:<20} {count}")

    for failure in m.failures:
        print(f"  FAIL {failure}", file=sys.stderr)

    if m.false_verifications:
        print("\nGATE FAILED: a misquote was reported as verified.", file=sys.stderr)
        return 1
    return 1 if m.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
