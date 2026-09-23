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
from sanad.corpus.scope import CORPUS_SCOPE
from sanad.verify.claims import detect_claims, requires_handoff, route_risk
from sanad.verify.engine import Verdict, verify_spans

VERIFIED = {Verdict.EXACT.value, Verdict.EXACT_ORTHOGRAPHY.value}

# What `expect_scope_caveat: true` is actually asserting about the caveat that
# accompanies a NOT_FOUND. Absence from this corpus is not evidence of
# anything, so the caveat has to say two things or it is an accusation by
# omission: that Sahih al-Bukhari is the ONLY collection here, and that not
# finding a text does not make it fabricated. Both are substrings of the
# single wording chosen in R22, so a reworded caveat that quietly drops either
# half fails the cases that depend on it rather than passing on the strength
# of the field merely existing.
_SCOPE_CAVEAT_MUST_CONTAIN = (
    "Sahih al-Bukhari",
    "does not establish that a quotation is fabricated",
)

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
    # --- fields added for the Bukhari cases -------------------------------
    # `expect_verdict`/`expect_record` only ever describe the FIRST span, and
    # only the verdict/record pair. The four below exist because the hadith
    # layer's failure modes are not expressible that way. Each is checked
    # against every span, not just `matches[0]`.
    #
    # No span in the text may carry this verdict. Written for the defect where
    # a correctly cited hadith was called a misattribution because a Qur'anic
    # citation elsewhere in the sentence got attached to it: telling a reader
    # their correct citation is wrong is its own false claim, and it lands on
    # whichever span the distance bug touches -- not necessarily the first.
    forbid_verdict: str | None = None
    # Every span that matched something matched THIS record. The invariant for
    # a quotation that may legitimately fail to match at all (an isnad pasted
    # in front of its matn): whatever it does, it must not land on a DIFFERENT
    # hadith. Stated this way it survives a future improvement that correctly
    # matches the intended record, which pinning the measured verdict would
    # not.
    expect_no_other_record: str | None = None
    # The text yields no quotation to verify at all. An Arabic-script citation
    # is itself a run of Arabic, so "صحيح البخاري ٣٤٢" was once offered up as
    # a quotation and answered "not in this corpus". Without this field that
    # case is untestable: no spans means no verdict, and every expectation
    # keyed off a verdict passes vacuously.
    expect_no_quotation: bool | None = None
    # `requires_handoff(route_risk(text))`. Distinct from `expect_risk`: the
    # risk code is what the router decided, the handoff is what the reader
    # actually gets, and it is the handoff that keeps a machine from answering
    # a personal question.
    expect_handoff: bool | None = None
    # The result carries the corpus-scope caveat, and that caveat still says
    # what it has to say -- see `_SCOPE_CAVEAT_MUST_CONTAIN`. Used by the cases
    # where NOT_FOUND must not be readable as a verdict on the text.
    expect_scope_caveat: bool | None = None

    def __post_init__(self) -> None:
        # Both verdict fields are validated: an `expect_verdict` typo makes a
        # case fail loudly, but a `forbid_verdict` typo makes it pass
        # vacuously forever -- no real verdict can ever equal "WRONG_REFRENCE"
        # -- which is the exact failure mode this check exists to prevent.
        for field_name in ("expect_verdict", "forbid_verdict"):
            value = getattr(self, field_name)
            if value is not None and value not in _VALID_VERDICTS:
                raise ValueError(
                    f"case {self.id!r}: {field_name} {value!r} is not a real "
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

        if case.expect_handoff is not None:
            got_handoff = requires_handoff(route_risk(case.text))
            if got_handoff != case.expect_handoff:
                problems.append(
                    f"handoff: expected {case.expect_handoff}, got {got_handoff}")

        if case.forbid_verdict is not None:
            offenders = [mt.verdict.value for mt in matches
                         if mt.verdict.value == case.forbid_verdict]
            if offenders:
                problems.append(
                    f"forbidden verdict {case.forbid_verdict} produced "
                    f"{len(offenders)}x across {len(matches)} span(s)")

        if case.expect_no_other_record is not None:
            strays = sorted({mt.record.id for mt in matches if mt.record
                             and mt.record.id != case.expect_no_other_record})
            if strays:
                problems.append(
                    f"matched a different record than {case.expect_no_other_record}: "
                    f"{strays}")

        if case.expect_no_quotation is not None:
            got_any = bool(matches)
            if got_any == case.expect_no_quotation:
                problems.append(
                    f"quotations: expected "
                    f"{'none' if case.expect_no_quotation else 'at least one'}, got "
                    f"{[mt.span.text for mt in matches]}")

        if case.expect_scope_caveat:
            # The caveat is what stands between "not in this corpus" and the
            # reader hearing "not genuine". If the text DID resolve to a
            # record there is no absence to explain and the case is
            # mis-specified, so that is a failure too, not a silent pass.
            if top is not None and top.record is not None:
                problems.append(
                    f"scope caveat: expected an unresolved quotation, got "
                    f"{top.record.id}")
            missing = [s for s in _SCOPE_CAVEAT_MUST_CONTAIN if s not in CORPUS_SCOPE]
            if missing:
                problems.append(f"scope caveat no longer states: {missing}")

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
