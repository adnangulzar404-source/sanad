"""Adversarial evaluation harness.

Two metrics gate CI, and they are the two halves of one severity class.

A false VERIFICATION reports a misquote as EXACT or EXACT_ORTHOGRAPHY. A false
MISATTRIBUTION reports WRONG_REFERENCE against a quotation whose citation was
right, which tells a reader their correct citation is a misattribution. Both
are Sanad asserting something false about scripture, and the second is not the
lesser one: it is an accusation aimed at the reader.

Only the first was gated until the whole-branch review, and the asymmetry was
load-bearing rather than theoretical -- the branch shipped two false
WRONG_REFERENCEs (a Qur'anic ayah stored as a hadith matn, and `Book N, Hadith
M` read as an al-Bugha sequential number) while this suite reported 54/54 with
zero false verifications throughout. A defect class that only fails CI when a
case remembers to opt in with `forbid_verdict` is a defect class CI does not
cover. Everything else here is tracked and reported.
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
# The verdicts that accuse the READER of a misattribution rather than
# endorsing their quotation. Kept as a set, like VERIFIED, so a future verdict
# in the same class joins the gate by being added here rather than by every
# case remembering it.
MISATTRIBUTED = {Verdict.WRONG_REFERENCE.value}

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
    # How many spans in this text this case LICENSES to report a verified
    # verdict. Leave it unset unless the answer is neither 0 nor 1: see
    # `verified_span_budget`. Set it explicitly and the case is declaring the
    # shape of its own text, which is a stronger statement than the default,
    # not a weaker one -- a case with a budget of 2 that grows a third
    # verified span trips the gate.
    expect_verified_spans: int | None = None
    # The same declaration for the other half of the severity class: how many
    # spans in this text this case LICENSES to report WRONG_REFERENCE. Same
    # default rule, same meaning -- see `misattributed_span_budget`. Leave it
    # unset unless the answer is neither 0 nor 1.
    expect_misattributed_spans: int | None = None

    def verified_span_budget(self) -> int:
        """How many verified spans this case is allowed to produce.

        The gate used to be case-level: `expect_verdict not in VERIFIED and
        any(span is verified)`. That switched the gate OFF ENTIRELY for any
        case expecting EXACT or EXACT_ORTHOGRAPHY -- including for that case's
        OTHER spans. A case quoting a real ayah and a fabrication, expecting
        EXACT for the ayah, would let the fabrication verify invisibly: the
        gate saw a case that was allowed to verify and stopped looking.

        Budgeting makes it span-level. The default is deliberately the
        tightest reading of what the case already says: 0 when the case
        expects no verified verdict, 1 when it expects one. A case whose text
        genuinely contains more than one verifiable quotation has to say so,
        and then says exactly how many -- so the gate stays armed for the
        (n+1)th span instead of going quiet for all of them.
        """
        if self.expect_verified_spans is not None:
            return self.expect_verified_spans
        return 1 if self.expect_verdict in VERIFIED else 0

    def misattributed_span_budget(self) -> int:
        """How many WRONG_REFERENCE spans this case is allowed to produce.

        Deliberately the exact mirror of `verified_span_budget`, down to the
        default: 0 unless the case says it expects a misattribution, 1 if it
        does. `forbid_verdict` stays as it is -- it is a per-case statement
        that reads well in a rationale -- but it can no longer be the only
        thing standing between a false accusation and a green suite, because
        a case has to think of it. A budget applies whether anyone thought of
        it or not.

        Measured before it was adopted: across all 54 cases in the suite at
        the time, every case's WRONG_REFERENCE span count already equalled
        this default exactly, so the symmetric gate cost zero declarations.
        The reviewer's worry that a blanket rule would be noisy is answered by
        that measurement rather than by argument.
        """
        if self.expect_misattributed_spans is not None:
            return self.expect_misattributed_spans
        return 1 if self.expect_verdict in MISATTRIBUTED else 0

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
        # A negative budget would be silently equivalent to 0 and a non-int
        # (True, "2", 1.5) would compare in ways nobody intended. Either is a
        # mistake in a number that decides how many false verifications the
        # gate tolerates, so neither is guessed at.
        for field_name in ("expect_verified_spans", "expect_misattributed_spans"):
            budget = getattr(self, field_name)
            if budget is not None and (not isinstance(budget, int)
                                       or isinstance(budget, bool) or budget < 0):
                raise ValueError(
                    f"case {self.id!r}: {field_name} must be a "
                    f"non-negative int, got {budget!r}")


@dataclass
class Metrics:
    total: int = 0
    passed: int = 0
    false_verifications: int = 0
    false_misattributions: int = 0
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

        # THE GATE. Counted per span against a budget, not asked as a yes/no
        # question about the case -- see `Case.verified_span_budget`.
        #
        # Two earlier shapes of this check were each weaker than they looked.
        # The first inspected only `matches[0]`, so a false verification in a
        # later span was invisible. The second scanned every span but only
        # for cases that expected nothing verified, so a case expecting EXACT
        # had the gate switched off for ALL of its spans -- a real ayah plus a
        # fabricated hadith, expecting EXACT for the ayah, would let the
        # fabrication verify in silence. Both times the gate looked like it
        # covered the whole text and covered part of it.
        #
        # Every span is counted now, and a case may only verify as many as it
        # has declared. Per-case verdict/record assertions below stay scoped
        # to `top`; only this gate reads every match.
        verified = [mt.verdict.value for mt in matches if mt.verdict.value in VERIFIED]
        budget = case.verified_span_budget()
        if len(verified) > budget:
            # Counted as one breach per excess span: two fabrications verifying
            # in one case is twice the damage of one, and the headline number
            # in CI should say so.
            m.false_verifications += len(verified) - budget
            problems.append(
                f"FALSE VERIFICATION: {len(verified)} span(s) verified but this case "
                f"licenses {budget} (expect_verdict={case.expect_verdict}); all "
                f"verdicts {[mt.verdict.value for mt in matches]}")

        # THE OTHER HALF OF THE GATE. Same shape, same per-span counting, for
        # the verdict that tells a reader their citation is wrong. This is
        # structural rather than opt-in on purpose: `forbid_verdict` already
        # existed and both of the branch's false WRONG_REFERENCEs went past it,
        # because no case had thought to forbid the verdict on a text nobody
        # suspected.
        misattributed = [mt.verdict.value for mt in matches
                         if mt.verdict.value in MISATTRIBUTED]
        wr_budget = case.misattributed_span_budget()
        if len(misattributed) > wr_budget:
            m.false_misattributions += len(misattributed) - wr_budget
            problems.append(
                f"FALSE MISATTRIBUTION: {len(misattributed)} span(s) reported "
                f"WRONG_REFERENCE but this case licenses {wr_budget} "
                f"(expect_verdict={case.expect_verdict}); all verdicts "
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
    print(f"false misattributions {m.false_misattributions}")
    print("verdict distribution:")
    for verdict, count in sorted(m.by_verdict.items()):
        print(f"  {verdict:<20} {count}")

    for failure in m.failures:
        print(f"  FAIL {failure}", file=sys.stderr)

    if m.false_verifications:
        print("\nGATE FAILED: a quotation verified that no case licensed.",
              file=sys.stderr)
        return 1
    if m.false_misattributions:
        print("\nGATE FAILED: a quotation was called a misattribution that no "
              "case licensed.", file=sys.stderr)
        return 1
    return 1 if m.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
