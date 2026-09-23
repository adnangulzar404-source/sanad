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
import ast
import re
from pathlib import Path

import pytest
from sanad.corpus import db
from sanad.corpus.scope import CORPUS_SCOPE

from eval.runner import MISATTRIBUTED, VERIFIED, Case, load_cases, run_eval

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


# --- the same denial, one surface further out ------------------------------
#
# The test above was written to stop R25(a) recurring and reads claim notes
# and nothing else. So `index.html` -- GitHub Pages, the most public thing
# this project has -- went on telling readers "No Hadith edition is bundled
# anywhere" and "Adapter only, no edition shipped" for the whole of Stage A2,
# and the suite stayed green. A guard that covers one surface of a
# multi-surface claim is a guard against being caught, not against the
# defect.
#
# The rule enforced here: a public surface may say what it does not carry,
# but not out of sight of what the project does carry. Wherever a reader
# meets a denial, "al-Bukhari" has to be in the same breath -- the same
# element on a page, the same paragraph in prose, the same string in code --
# so meeting the absence means also meeting the corpus.
#
# Scope is deliberately not "the whole repository". `docs/superpowers/**`
# holds dated plans, specs and research that were true when they were
# written; editing those to match today would be falsifying the record, not
# fixing copy.
_PUBLIC_SURFACES = ("index.html", "README.md", "CONTRIBUTING.md",
                    "REPO_STATUS.md", "docs/SOURCES.md", "web/index.html")
_PUBLIC_TREES = (("web/src", ("*.ts", "*.tsx", "*.html")),
                 ("api/sanad", ("*.py",)))

# A negation standing within a short reach of a word about carrying a text.
# Bounded by the sentence it sits in -- "." ends the reach -- so a negation
# in one sentence cannot be paired with a noun from the next.
_DENIAL = re.compile(
    r"\b(no|not|never|none|neither|without)\b[^.]{0,60}?"
    r"\b(bundl\w*|ship(?:s|ped|ping)?|includ\w*|import\w*|available|"
    r"present|edition|corpus)\b",
    re.IGNORECASE)
_MENTIONS_HADITH = re.compile(r"hadith|bukhari", re.IGNORECASE)
_THE_FACT = re.compile(r"al[-\s]?Bukhari", re.IGNORECASE)
# DDL is not copy. `schema.py`'s CREATE TABLE names a `hadith_no` column and
# a NOT NULL constraint three lines from the word "edition", which reads as a
# denial to any regex and to no reader.
_SQL = re.compile(r"\b(CREATE\s+(TABLE|VIRTUAL|INDEX)|SELECT\s|INSERT\s+INTO)",
                  re.IGNORECASE)


def _segments(path: Path) -> list[str]:
    """The unit a reader takes in at once, which differs by surface.

    A character window was tried first and is wrong in both directions: it
    pairs a denial in one table row with a noun from the row below, and it
    reads Python comments and identifiers as prose (`x: str | None = None`
    followed by a comment about "the edition" scans as a denial). Structure
    is the honest unit.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".html", ".htm", ".ts", ".tsx"):
        # Markup and JSX here are written one element per line, so a line is
        # an element -- and a table row is one line, cells and all.
        return text.splitlines()
    if path.suffix == ".md":
        return re.split(r"\n\s*\n", text)
    if path.suffix == ".py":
        # String literals only. A comment is not a public surface, and the
        # comment in `claims.py` that quotes the old denial in order to
        # explain why it was wrong must not be read as making it.
        return [n.value for n in ast.walk(ast.parse(text))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    raise AssertionError(f"no segmentation rule for {path}")


def _denials_out_of_sight(segment: str) -> list[str]:
    """Denials about hadith in `segment` that never name al-Bukhari."""
    if not _MENTIONS_HADITH.search(segment) or _THE_FACT.search(segment):
        return []
    if _SQL.search(segment):
        return []
    return [m.group(0) for m in _DENIAL.finditer(segment)]


def _public_surface_paths() -> list[Path]:
    paths = [Path(p) for p in _PUBLIC_SURFACES]
    for root, patterns in _PUBLIC_TREES:
        for pattern in patterns:
            paths += sorted(Path(root).rglob(pattern))
    found = [p for p in paths if p.is_file()]
    assert len(found) > 20, (
        "the surface list has stopped resolving to files; a scan of nothing "
        "passes for the wrong reason")
    return found


def test_no_public_surface_denies_that_a_hadith_corpus_exists():
    offenders = {}
    for path in _public_surface_paths():
        found = [d for seg in _segments(path) for d in _denials_out_of_sight(seg)]
        if found:
            offenders[str(path)] = found
    assert not offenders, (
        f"a public surface denies the hadith corpus out of sight of it: "
        f"{offenders}. This corpus contains all 7,129 hadith of Sahih "
        f"al-Bukhari; say what is absent if you must, but say it beside what "
        f"is present.")


# The scan above asks whether the fact is within sight of the denial, which
# is the right question for a NEW phrasing and the wrong one for a flat
# contradiction: moving "Sahih al-Bukhari" onto the same line as "No Hadith
# edition is bundled anywhere" satisfies it and makes the page worse. These
# are statements that are simply false about this project, wherever they
# stand and whatever stands beside them. Every one of them was live text on
# GitHub Pages or in a claim note during Stage A2.
_FALSE_ON_ANY_SURFACE = (
    "no hadith edition is bundled",
    "no licensed hadith edition",
    "no hadith corpus is bundled",
    "no hadith edition is shipped",
    "bundled anywhere",
    "no edition shipped",
    "no edition is shipped",
    "adapter only",
    "hadith adapter present",
    "licensed texts not bundled",
    "treat as unverified until an edition is imported",
)


def test_no_public_surface_states_one_of_the_falsehoods_outright():
    offenders = {}
    for path in _public_surface_paths():
        # Segments, not raw file text, for the same reason as the scan above:
        # `claims.py` quotes the old denial in a comment in order to explain
        # why it was wrong, and a comment is not something a reader is told.
        lowered = " \n ".join(_segments(path)).lower()
        said = [p for p in _FALSE_ON_ANY_SURFACE if p in lowered]
        if said:
            offenders[str(path)] = said
    assert not offenders, (
        f"a public surface states as fact something that is not: {offenders}. "
        f"Sahih al-Bukhari has been in this corpus since Stage A2; no wording "
        f"beside it makes these true.")


@pytest.mark.parametrize("phrase", _FALSE_ON_ANY_SURFACE)
def test_each_falsehood_is_a_phrase_that_would_be_recognised(phrase):
    """Mutation guard for the list above.

    A blocklist of phrases nobody would write is a blocklist that can never
    fire. Each entry has to be lowercase (it is matched against lowercased
    text), non-trivial, and actually about hadith or about bundling -- not a
    fragment so generic it would match anything, nor so specific it only
    matches a string that no longer exists anywhere.
    """
    assert phrase == phrase.lower() and len(phrase) >= 12
    assert re.search(r"hadith|bundl|edition|adapter|imported", phrase)


@pytest.mark.parametrize("historical", [
    ("No Hadith edition is bundled anywhere, so “not found” here "
     "means “not in this corpus”, never “fabricated”."),
    ("Loaded: Al-Fatiha, Ayat al-Kursi. Hadith adapter present; licensed "
     "texts not bundled."),
    ("<tr><td>Hadith editions</td><td>Written permission or a clearly "
     "licensed subset</td><td>Adapter only — no edition shipped</td></tr>"),
    ("No licensed Hadith edition is bundled. Treat as unverified until an "
     "edition is imported."),
])
def test_the_surface_scan_catches_the_four_denials_that_shipped(historical):
    """The scan has to fail on the text it was written for.

    These four strings are what `index.html` actually said while the suite
    was green -- pasted here so the scan is proved capable of failing without
    depending on the current contents of any file. A scan that reports
    nothing looks identical whether it is working or broken.
    """
    assert _denials_out_of_sight(historical), (
        "the scan no longer sees a denial that shipped to GitHub Pages")


def test_a_denial_beside_the_fact_is_not_an_offence():
    """The rule is sight of the truth, not silence about absence.

    Saying a surface carries no hadith is honest and sometimes necessary --
    the Phase 0 page really does carry none. What made the old copy a defect
    was that a reader met the absence and never met the corpus.
    """
    assert not _denials_out_of_sight(
        "This page carries no hadith edition; the Stage A engine holds "
        "Sahih al-Bukhari.")


# --- the gate itself -----------------------------------------------------

def test_verified_verdicts_are_the_two_that_endorse_a_quotation():
    # If a third verdict were ever added to VERIFIED, every case in the suite
    # that merely avoids EXACT would stop being a gate against it.
    assert VERIFIED == {"EXACT", "EXACT_ORTHOGRAPHY"}


def _two_verified_spans(conn) -> str:
    """Text with two spans that both verify, built from corpus bytes."""
    return (f"«{db.get_record(conn, 'quran:112:1').text_ar}» and "
            f"«{db.get_record(conn, 'hadith:bukhari:2866').text_ar}»")


def test_gate_catches_an_extra_verified_span_in_a_case_that_expects_one(conn):
    """THE case the old gate could not see.

    The gate used to ask a question about the CASE -- "does this case expect a
    verified verdict?" -- and stop looking if the answer was yes. So a case
    quoting a genuine ayah and something the author believed was not
    scripture, expecting EXACT for the ayah, had no gate on its second span at
    all: a fabrication verifying there was invisible to CI.

    This case is exactly that shape. `expect_verdict: EXACT` is satisfied by
    the first span, and the second verifies too. Under the case-level gate it
    passed clean. Under the budget it is a false verification, because the
    case licensed one verified span and got two.
    """
    case = Case(
        id="unlicensed-second-verification",
        text=_two_verified_spans(conn),
        rationale="second span verifies and the case never said it could",
        expect_verdict="EXACT",
        expect_record="quran:112:1",
    )
    # Precondition, asserted rather than assumed: this case really does satisfy
    # the OLD gate's condition for switching itself off.
    assert case.expect_verdict in VERIFIED
    assert case.verified_span_budget() == 1

    metrics = run_eval(conn, [case])
    assert metrics.false_verifications == 1, metrics.failures
    assert any("FALSE VERIFICATION" in f and "licenses 1" in f
               for f in metrics.failures), metrics.failures


def test_a_case_may_declare_a_larger_budget_and_then_is_held_to_it(conn):
    """The escape hatch is not a mute button.

    A case whose text genuinely holds two verifiable quotations says so, and
    passes. The same case with a third verified span would trip again -- the
    budget arms the gate at n+1 rather than turning it off, which is the
    whole difference between this and the old behaviour.
    """
    text = _two_verified_spans(conn)
    declared = Case(id="declared", text=text, rationale="r",
                    expect_verdict="EXACT", expect_verified_spans=2)
    assert run_eval(conn, [declared]).false_verifications == 0

    third = db.get_record(conn, "hadith:bukhari:1366").text_ar
    grown = Case(id="grown", text=f"{text} «{third}»", rationale="r",
                 expect_verdict="EXACT", expect_verified_spans=2)
    metrics = run_eval(conn, [grown])
    assert metrics.false_verifications == 1, metrics.failures
    assert any("3 span(s) verified" in f for f in metrics.failures), metrics.failures


def test_the_budget_counts_every_excess_span_not_just_the_first(conn):
    """Two fabrications verifying is twice the damage of one, and the headline
    number CI prints has to say so rather than capping at 1 per case.
    """
    a = db.get_record(conn, "quran:112:1").text_ar
    b = db.get_record(conn, "hadith:bukhari:2866").text_ar
    c = db.get_record(conn, "hadith:bukhari:1366").text_ar
    case = Case(id="three", text=f"«{a}» «{b}» «{c}»", rationale="r",
                expect_verdict="NOT_FOUND")
    metrics = run_eval(conn, [case])
    assert metrics.false_verifications == 3, metrics.failures


def test_the_default_budget_is_the_tightest_reading_of_the_case(conn):
    assert Case(id="a", text="t", rationale="r").verified_span_budget() == 0
    assert Case(id="b", text="t", rationale="r",
                expect_verdict="NOT_FOUND").verified_span_budget() == 0
    assert Case(id="c", text="t", rationale="r",
                expect_verdict="NEAR_MATCH").verified_span_budget() == 0
    assert Case(id="d", text="t", rationale="r",
                expect_verdict="WRONG_REFERENCE").verified_span_budget() == 0
    assert Case(id="e", text="t", rationale="r",
                expect_verdict="EXACT").verified_span_budget() == 1
    assert Case(id="f", text="t", rationale="r",
                expect_verdict="EXACT_ORTHOGRAPHY").verified_span_budget() == 1
    assert Case(id="g", text="t", rationale="r",
                expect_verdict="EXACT", expect_verified_spans=0
                ).verified_span_budget() == 0


def test_a_nonsense_budget_is_rejected_at_load_time():
    """A budget is the number of false verifications the gate will tolerate.
    Guessing at a malformed one is how a gate quietly stops gating: `True`
    would pass `isinstance(x, int)` and mean 1, a negative would silently
    mean 0, and "2" would blow up somewhere far from here.
    """
    for field in ("expect_verified_spans", "expect_misattributed_spans"):
        for bad in (-1, True, "2", 1.5):
            with pytest.raises(ValueError, match="non-negative int"):
                Case(id="x", text="y", rationale="z", **{field: bad})
        Case(id="x", text="y", rationale="z", **{field: 0})


def test_only_the_one_case_that_needs_a_budget_declares_one(cases):
    """A creeping habit of declaring budgets would hollow the gate out one
    case at a time, and nothing else would notice. Today exactly one case in
    the suite has two genuinely verifiable quotations in it; if a second ever
    earns a budget, this assertion is where someone has to look at it.
    """
    declared = {c.id: c.expect_verified_spans for c in cases
                if c.expect_verified_spans is not None}
    assert declared == {"hadith-correct-citation-not-flagged-by-a-distant-one": 2}


# --- the other half of the gate: false misattributions -------------------

def test_misattributed_verdicts_are_the_one_that_accuses_the_reader():
    # The mirror of `test_verified_verdicts_are_the_two_that_endorse_a
    # _quotation`. If a verdict is ever dropped from this set, every case in
    # the suite that merely avoids it stops being a gate against it.
    assert MISATTRIBUTED == {"WRONG_REFERENCE"}


def test_gate_catches_a_wrong_reference_no_case_licensed(conn):
    """THE case the old gate could not see, in the other direction.

    This is the shape of both Criticals the whole-branch review found: a
    correctly quoted, correctly cited text answered WRONG_REFERENCE. Neither
    was caught, because the only cover for a false accusation was
    `forbid_verdict`, which a case has to declare -- and nobody declares a
    prohibition against a defect nobody suspects.

    Deliberately written WITHOUT `forbid_verdict`, so it fails only if the
    structural budget is doing the work. Its second span really is a
    misattribution (an ayah attributed to Sahih al-Bukhari), so the case is
    not fabricating a failure to catch.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    ayah = db.get_record(conn, "quran:112:1").text_ar
    case = Case(
        id="unlicensed-misattribution",
        text=f"«{matn}» (Bukhari 2866) and «{ayah}» (Bukhari 1)",
        rationale="the second span is a real misattribution and nothing declares it",
        expect_verdict="EXACT",
        expect_record="hadith:bukhari:2866",
    )
    assert case.forbid_verdict is None
    assert case.misattributed_span_budget() == 0

    metrics = run_eval(conn, [case])
    assert metrics.false_misattributions == 1, metrics.failures
    assert any("FALSE MISATTRIBUTION" in f and "licenses 0" in f
               for f in metrics.failures), metrics.failures


def test_a_case_may_declare_a_misattribution_budget_and_then_is_held_to_it(conn):
    """Same escape hatch, same refusal to be a mute button: a declared budget
    arms the gate at n+1 rather than switching it off.
    """
    matn = db.get_record(conn, "hadith:bukhari:2866").text_ar
    ayah = db.get_record(conn, "quran:112:1").text_ar
    one = f"«{ayah}» (Bukhari 1)"
    two = f"{one} and «{matn}» (2:255)"
    declared = Case(id="declared-wr", text=two, rationale="r",
                    expect_verdict="WRONG_REFERENCE",
                    expect_misattributed_spans=2)
    assert run_eval(conn, [declared]).false_misattributions == 0

    third = db.get_record(conn, "hadith:bukhari:1366").text_ar
    grown = Case(id="grown-wr", text=f"{two} and «{third}» (2:255)", rationale="r",
                 expect_verdict="WRONG_REFERENCE", expect_misattributed_spans=2)
    metrics = run_eval(conn, [grown])
    assert metrics.false_misattributions == 1, metrics.failures
    assert any("3 span(s) reported WRONG_REFERENCE" in f
               for f in metrics.failures), metrics.failures


def test_the_default_misattribution_budget_is_the_tightest_reading_of_the_case():
    assert Case(id="a", text="t", rationale="r").misattributed_span_budget() == 0
    for verdict in ("EXACT", "EXACT_ORTHOGRAPHY", "NEAR_MATCH", "NOT_FOUND"):
        assert Case(id="b", text="t", rationale="r",
                    expect_verdict=verdict).misattributed_span_budget() == 0
    assert Case(id="c", text="t", rationale="r",
                expect_verdict="WRONG_REFERENCE").misattributed_span_budget() == 1
    assert Case(id="d", text="t", rationale="r", expect_verdict="WRONG_REFERENCE",
                expect_misattributed_spans=0).misattributed_span_budget() == 0


def test_no_case_needs_a_misattribution_budget(cases):
    """Measured when the gate was added: every one of the 54 cases then in the
    suite already produced exactly the default number of WRONG_REFERENCE
    spans, so the symmetric gate cost no declarations at all. If a case ever
    earns one, this is where someone has to look at whether the text really
    holds two separate misattributions or the engine has grown a new one.
    """
    declared = {c.id: c.expect_misattributed_spans for c in cases
                if c.expect_misattributed_spans is not None}
    assert declared == {}


def test_whole_suite_still_has_zero_false_verifications(conn, cases):
    metrics = run_eval(conn, cases)
    assert metrics.false_verifications == 0
    assert metrics.false_misattributions == 0
    assert metrics.failures == []
