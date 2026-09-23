# Fixture provenance: tests/fixtures/bukhari_sample.txt was sliced verbatim
# from the pinned OpenITI Bukhari download (sha256
# 69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7 for
# /tmp/bukhari.txt) via the exact script in Task 2 Step 1 -- no Arabic was
# typed by hand. Fixture's own sha256 as generated on 2026-09-22:
# d1338229de2aace5432f3ddb384e99a3d367ca21e0c7f7be10567c8183cecffd
import hashlib
import re
from pathlib import Path

import pytest
from sanad_ingest.openiti import parse_openiti

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bukhari_sample.txt"
FULL = Path("/tmp/bukhari.txt")   # the real download; see Task 2 Step 1

# sha256 of the sorted, comma-joined ids of every record the secondary-narration
# rule cuts. Measured, not chosen; see test_exactly_the_measured_records_are_cut.
_CUT_ID_DIGEST = "64800b05668f46547ccf6311534bf1d69f6bf3c638ab3f4c17ac122866ff64cf"


@pytest.fixture(scope="module")
def sample():
    return parse_openiti(FIXTURE.read_text(encoding="utf-8"))


def test_extracts_the_meta_header_verbatim(sample):
    assert "#META# 045.EdYEAR" in sample.attribution
    assert "1407 - 1987" in sample.attribution
    assert "#META#Header#End#" in sample.attribution


def test_first_hadith_splits_isnad_from_matn(sample):
    first = sample.units[0]
    assert first.hadith_no == "1"
    assert first.record_id == "hadith:bukhari:1"
    # The isnad ends at the '*'; the matn begins with the famous words.
    # Both strings are compared against the FILE, never against typed Arabic.
    raw = FIXTURE.read_text(encoding="utf-8")
    unit = raw[raw.index("# 1 "):raw.index("# 2 ")]
    unit = unit.replace("~~", "").replace("\n", " ")
    unit = re.sub(r"PageV\d+P\d+", "", unit)
    expect_isnad, expect_matn = unit[len("# 1 "):].split("*", 1)
    assert first.isnad_ar == " ".join(expect_isnad.split())
    assert first.matn_ar == " ".join(expect_matn.split())


def test_matn_carries_no_structural_markers(sample):
    for u in sample.units:
        for marker in ("~~", "@QB@", "@QE@", "*", "PageV"):
            assert marker not in u.matn_ar, f"{marker} leaked into {u.record_id}"
        assert not re.search(r"ms\d{4}", u.matn_ar)
        assert not re.search(r"\\\s*\d+\s*\\", u.matn_ar)


def test_quranic_quotation_text_survives_marker_stripping(sample):
    """@QB@...@QE@ markers go; the words between them stay.

    The fixture's very first @QB@...@QE@ pair (line 40 of
    bukhari_sample.txt) sits inside a "###" bab-heading line -- the chapter
    title itself quotes an ayah. That text is correctly stored as bab_ar,
    not as any hadith's isnad/matn, so it must not be the pair this test
    looks for. Excluding heading lines finds the first quotation that is
    actually inside a hadith (hadith 3's matn), which is what this
    invariant -- "a hadith quoting an ayah contains that ayah" -- is about.
    """
    raw = FIXTURE.read_text(encoding="utf-8")
    body = "\n".join(l for l in raw.splitlines() if not l.startswith("###"))
    inner = re.search(r"@QB@(.+?)@QE@", body, re.DOTALL)
    assert inner, "fixture must contain at least one Qur'anic quotation in a hadith"
    words = " ".join(inner.group(1).replace("~~", "").split())
    joined = " ".join(u.matn_ar for u in sample.units) + " ".join(
        u.isnad_ar or "" for u in sample.units
    )
    assert words[:30] in joined


def test_bab_headings_are_not_records(sample):
    for u in sample.units:
        assert not u.matn_ar.lstrip().startswith("باب")


# --- whole-file assertions: these are the measured facts from the plan ---

@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_full_file_yields_the_measured_record_count():
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    assert len(parsed.units) == 7129


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_every_record_id_is_unique():
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    ids = [u.record_id for u in parsed.units]
    assert len(set(ids)) == len(ids), "record ids must be unique"


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_repeat_marked_units_are_distinct_records():
    """619 م is a different narration from 619 -- 25 degrees vs 27."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    six19 = [u for u in parsed.units if u.hadith_no == "619"]
    assert len(six19) == 2
    assert len({u.record_id for u in six19}) == 2
    assert sum(u.is_repeat for u in six19) == 1
    assert six19[0].matn_ar != six19[1].matn_ar


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_collision_without_a_repeat_marker_still_gets_distinct_ids():
    """3905 is printed twice, neither marked م -- an edition artifact."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    both = [u for u in parsed.units if u.hadith_no == "3905"]
    assert len(both) == 2
    assert both[0].record_id != both[1].record_id


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_content_hash_matches_the_pinned_value():
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    assert parsed.content_sha256 == (
        "69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7"
    )


# --- round 1 review fixes ---


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_noisy_flags_without_filtering():
    """Sec 10: noise is flagged, never corrected. The real file has 9 such
    records (a stray digit, variant-reading brackets, a bare '?'). This
    pins that (a) the scan actually finds them -- an earlier report
    wrongly claimed zero, which meant this requirement had no coverage at
    all -- and (b) the flagged text is still present, unmodified, in the
    unit it was flagged from. Filtering it out would defeat the point."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    assert parsed.noisy, "the pinned file is known to contain noise characters"
    by_id = {u.record_id: u for u in parsed.units}
    for record_id, offending in parsed.noisy:
        assert isinstance(record_id, str)
        assert isinstance(offending, str) and offending
        assert record_id in by_id, f"{record_id} was flagged but is not a unit"
        for ch in offending:
            assert ch in by_id[record_id].matn_ar, (
                f"noisy() reported {ch!r} for {record_id} but it isn't in "
                "the stored matn -- noise must be reported, not filtered"
            )


def _strip_heading_markers(s: str) -> str:
    """Independent (re-implemented, not imported) mirror of the module's
    marker stripping, used only to compute an expected value from the raw
    file for the tests below."""
    s = s.replace("~~", " ")
    s = re.sub(r"PageV\d+P\d+", " ", s)
    s = re.sub(r"ms\d{4}", " ", s)
    s = re.sub(r"\\\s*\d+\s*\\", " ", s)
    s = s.replace("@QB@", " ").replace("@QE@", " ")
    return " ".join(s.split())


def _expected_bab_ar(raw: str, hadith_no: str) -> str:
    """Reconstruct the expected bab_ar for a given hadith number straight
    from the raw file: locate the nearest preceding '### ||' heading line,
    take every line between it and the hadith line, strip each line's own
    leading marker ('~~', '### ||...', or '# '), join with spaces, then
    apply marker stripping and the same cosmetic paren/number trim the
    parser applies. All anchors here are ASCII digits/markers, never typed
    Arabic."""
    hi = raw.index(f"\n# {hadith_no} ")
    heading_start = raw.rindex("### ||", 0, hi)
    frags = []
    for line in raw[heading_start:hi].splitlines():
        if line.startswith("~~"):
            frags.append(line[2:])
        elif re.match(r"^###\s*\|\|+\s*", line):
            frags.append(re.sub(r"^###\s*\|\|+\s*", "", line))
        elif line.startswith("# "):
            frags.append(line[2:])
        elif line.strip():
            frags.append(line)
    cleaned = _strip_heading_markers(" ".join(frags))
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()
    return re.sub(r"^\d+\s+", "", cleaned)


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_multiline_bab_heading_is_assembled_whole():
    """Hadith 9's bab heading spans the '### ||' line plus five more
    '#'/'~~' lines quoting an ayah before its wrapping '(' closes. A parser
    that reads only the '### ||' line's own text truncates the heading
    mid-quotation."""
    raw = FULL.read_text(encoding="utf-8")
    parsed = parse_openiti(raw)
    nine = next(u for u in parsed.units if u.hadith_no == "9")
    assert nine.bab_ar == _expected_bab_ar(raw, "9")


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_bab_heading_closed_on_the_immediate_next_line_keeps_its_word():
    """Hadith 1432's heading closes on the very next '~~' line, with no
    intervening numbered '#' chunk at all. The word that closes it is real
    content (not markup) and must survive."""
    raw = FULL.read_text(encoding="utf-8")
    parsed = parse_openiti(raw)
    unit = next(u for u in parsed.units if u.hadith_no == "1432")
    assert unit.bab_ar == _expected_bab_ar(raw, "1432")


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_bab_ar_and_kitab_ar_carry_no_leading_number():
    """Display headings drop their leading printed number:
    '2 كتاب الإيمان' -> 'كتاب الإيمان'. Universal, regardless of whether
    the field's wrapping parens could also be stripped (that depends on
    the raw text actually starting with '(' and ending with ')'; see
    test_bab_ar_and_kitab_ar_strip_matched_wrapping_parens below).
    matn_ar/isnad_ar are unaffected -- this is cosmetic, for chapter_ar
    display only."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    for u in parsed.units:
        assert not re.match(r"^\d", u.kitab_ar), u.kitab_ar
        if u.bab_ar:
            assert not re.match(r"^\d", u.bab_ar), u.bab_ar


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_bab_ar_and_kitab_ar_strip_matched_wrapping_parens():
    """When the captured heading text is wholly wrapped -- starts with '('
    and ends with ')' -- both are dropped, not just the leading number:
    kitab 2 -> 'كتاب الإيمان', not '( 2 كتاب الإيمان )' or '2 كتاب الإيمان'.

    This is *not* universal: some headings carry commentary after their
    own closing paren (e.g. hadith 274's bab_ar is
    "( 20 باب ... ) وقال بهز ..." -- the title itself is balanced, but the
    field's full text is not wholly wrapped, so nothing is stripped rather
    than mangling the trailing commentary). And bab_ar's parens are only
    ever fully assembled and resolvable when the source itself provides a
    closing paren somewhere reachable -- 12 headings never do (see
    test_bab_ar_paren_imbalance_is_a_bounded_known_source_defect) and
    kitab_ar has the same, not-yet-fixed, single-line-only limitation for
    17 of its 100 headings. This test only asserts the positive case: a
    resolvable heading with nothing trailing its own closing paren comes
    out markup-free."""
    raw = FULL.read_text(encoding="utf-8")
    # "### | ( 2 <name> )" -> strip parens and the leading number by hand,
    # from the raw line itself, never typed.
    kitab2_line = next(
        line for line in raw.splitlines() if re.match(r"^###\s*\|(?!\|)\s*\(\s*2\s", line)
    )
    expected_kitab2 = re.sub(r"^###\s*\|(?!\|)\s*\(\s*2\s+", "", kitab2_line).rstrip(") ").strip()

    parsed = parse_openiti(raw)
    two = next(u for u in parsed.units if u.kitab_no == 2)
    assert two.kitab_ar == expected_kitab2
    nine = next(u for u in parsed.units if u.hadith_no == "9")
    assert not nine.bab_ar.startswith("(")
    assert not nine.bab_ar.endswith(")")


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_bab_ar_paren_imbalance_is_a_bounded_known_source_defect():
    """A strict "no bab_ar is ever unbalanced" invariant does not hold: 12
    headings in the pinned edition never close their own '(' anywhere
    before the next hadith or section begins -- verified by hand against
    the raw file (e.g. hadith 1000's heading reads "... وخسف القمر" with
    no closing paren anywhere before hadith 1000 itself starts). No amount
    of continuation-reading can supply a character the source never wrote.
    This test pins that the defect is exactly this bounded, known set, so
    a real regression (more truncation) is caught, while an unfixable
    source typo is not mistaken for one."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    unbalanced = {u.bab_ar for u in parsed.units
                  if u.bab_ar and u.bab_ar.count("(") != u.bab_ar.count(")")}
    assert len(unbalanced) == 12
    hadith_nos_affected = {u.hadith_no for u in parsed.units if u.bab_ar in unbalanced}
    assert "1000" in hadith_nos_affected


# --- fix round 1: secondary narrations and empty matns ---------------------
#
# Arabic anchors are built from codepoints, never typed. See MEMORY: eleven
# bugs in this project came from Arabic silently altered in transit, one of
# them inside the test written to catch them.
_QAL = "".join(chr(c) for c in (0x0642, 0x0627, 0x0644))            # قال
_WA_QAL = chr(0x0648) + _QAL                                        # وقال
_HADDATHANA = "".join(chr(c) for c in (0x062D, 0x062F, 0x062B, 0x0646, 0x0627))
_HADDATHANI = "".join(chr(c) for c in (0x062D, 0x062F, 0x062B, 0x0646, 0x064A))


def _raw_unit_text(raw: str, hadith_no: str) -> str:
    """The unit's full printed text, reassembled from the raw file.

    Independent (re-implemented, not imported) mirror of the parser's line
    handling: a numbered "# N ..." line, then every "~~" continuation and
    every *non-numbered* "# " line that follows, up to the next numbered
    unit or "###" section. The non-numbered "# " lines are the ones the
    round-1 parser dropped on the floor (the edition prints poetry on its
    own "#" line), so a test that ignored them could not see the defect.
    """
    hi = raw.index(f"\n# {hadith_no} ")
    lines = raw[hi + 1:].splitlines()
    frags = [lines[0][2:]]
    for line in lines[1:]:
        if line.startswith("~~"):
            frags.append(line[2:])
        elif line.startswith("###"):
            break
        elif line.startswith("# "):
            rest = line[2:]
            if re.match(r"^\d+\s", rest):
                break
            frags.append(rest)
        else:
            break
    return _strip_heading_markers(" ".join(frags))


def _raw_matn(raw: str, hadith_no: str) -> str:
    """The unit's matn: everything after the edition's '*' boundary."""
    text = _raw_unit_text(raw, hadith_no)
    return " ".join(text.split("*", 1)[1].split()) if "*" in text else text


@pytest.fixture(scope="module")
def full():
    return parse_openiti(FULL.read_text(encoding="utf-8"))


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_secondary_narration_is_cut_out_of_the_scored_matn(full):
    """The three boundaries named in the fix brief, by record.

    Each is an "attribution + narration verb" the edition uses to append a
    further chain after the primary matn. The cut lands immediately before
    the attribution, so `addenda_ar` opens with it.
    """
    by_id = {u.record_id: u for u in full.units}
    for record_id, opener in (("hadith:bukhari:10", _WA_QAL),
                              ("hadith:bukhari:22", _QAL),
                              ("hadith:bukhari:40", _QAL)):
        u = by_id[record_id]
        assert u.addenda_ar, f"{record_id} must carry an addendum"
        assert u.addenda_ar.startswith(opener + " "), record_id
        assert _HADDATHANA in u.addenda_ar or record_id == "hadith:bukhari:10"
        assert _HADDATHANA not in u.matn_ar, f"{record_id} matn still holds a chain"


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_nothing_is_lost_when_an_addendum_is_cut_away(full):
    """`full_text` reassembles the edition's text, byte for byte.

    Recomputed from the raw file, not from the parser's own output: a cut
    that dropped or re-spaced a character would pass a self-comparison. This
    is also what licenses the build to store `full_text(u)` as the record's
    second, scored representation -- the string it indexes is the edition's,
    not an approximation of it.

    The count is pinned exactly rather than floored. A floor ("more than 100")
    cannot see a skip condition that silently stops covering records, which is
    how the ordinal-suffixed repeats went unchecked: `_raw_matn` looks up a
    hadith by its printed number and finds the FIRST unit printed under it, so
    a "-2" record cannot be compared this way. There is exactly one cut record
    with an ordinal suffix and it is asserted separately, below.
    """
    from sanad_ingest.openiti import full_text
    raw = FULL.read_text(encoding="utf-8")
    checked, suffixed = 0, []
    for u in full.units:
        if u.addenda_ar is None:
            continue
        if u.record_id != f"hadith:bukhari:{u.hadith_no}":
            suffixed.append(u)
            continue
        assert full_text(u) == _raw_matn(raw, u.hadith_no), u.record_id
        checked += 1
    assert checked == 383
    assert [u.record_id for u in suffixed] == ["hadith:bukhari:4537-2"]
    # The one repeat, against the SECOND printed occurrence of its number.
    second = raw[raw.index("\n# 4537 ") + 1:]
    assert full_text(suffixed[0]) == _raw_matn(second, "4537")


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_full_text_of_an_uncut_unit_is_its_matn(full):
    """No cut, no join: `full_text` must not invent a trailing space or a
    second copy of anything on the 6,745 units the rule never touched."""
    from sanad_ingest.openiti import full_text
    uncut = [u for u in full.units if u.addenda_ar is None]
    assert len(uncut) == 6745
    for u in uncut:
        assert full_text(u) == u.matn_ar, u.record_id


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_exactly_the_measured_records_are_cut(full):
    """384 cuts, pinned by count and by the exact set of record ids.

    The detection rule leans on a closed list of Arabic tokens that cannot be
    a narrator's name. A single mistyped codepoint in that list would silently
    stop rejecting a false boundary and start truncating real matn; that shows
    up here as a changed digest, which is the only cheap way to notice it.
    Regenerate after a deliberate rule change with:
      python -c "import hashlib; from sanad_ingest.openiti import parse_openiti; \
        u=parse_openiti(open('/tmp/bukhari.txt',encoding='utf-8').read()).units; \
        print(hashlib.sha256(','.join(sorted(x.record_id for x in u \
        if x.addenda_ar is not None)).encode()).hexdigest())"
    """
    cut = sorted(u.record_id for u in full.units if u.addenda_ar is not None)
    assert len(cut) == 384
    digest = hashlib.sha256(",".join(cut).encode("utf-8")).hexdigest()
    assert digest == _CUT_ID_DIGEST


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_a_bare_narration_verb_with_no_attribution_is_never_cut(full):
    """Where the source marks nothing, nothing is cut.

    These records contain a narration verb inside genuine matn -- "he told
    me and was truthful with me", "Gabriel informed me of it just now",
    "he said to Anas: tell me the harshest punishment". Cutting at the verb,
    or at the `qala` in front of it, would truncate the Prophet's words.
    Every one of them was reached by the rule and rejected by its guard.
    """
    by_id = {u.record_id: u for u in full.units}
    for record_id in ("hadith:bukhari:2943", "hadith:bukhari:504",
                      "hadith:bukhari:3723", "hadith:bukhari:4200",
                      "hadith:bukhari:5361", "hadith:bukhari:957",
                      "hadith:bukhari:5637", "hadith:bukhari:5813",
                      "hadith:bukhari:4155", "hadith:bukhari:4449"):
        u = by_id[record_id]
        assert u.addenda_ar is None, f"{record_id} must not be cut"


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_no_unit_has_an_empty_scored_matn(full):
    """Zero empty matns. An empty text_ar is a live verification hazard."""
    empty = [u.record_id for u in full.units if not u.matn_ar.strip()]
    assert empty == []


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_poetry_printed_on_its_own_line_stays_in_the_matn(full):
    """Root cause of three of the six empty matns.

    The edition prints verse on a "#"-prefixed line of its own. Those lines
    look exactly like the start of a new unit, and the round-1 parser flushed
    and then discarded them -- taking the whole matn of 3584, 4063 and 6050
    with them, and the closing verse of 62 other records.
    """
    raw = FULL.read_text(encoding="utf-8")
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("3584", "4063", "6050", "3585", "2681"):
        u = by_id[f"hadith:bukhari:{hadith_no}"]
        whole = u.matn_ar if u.addenda_ar is None else u.matn_ar + " " + u.addenda_ar
        assert whole == _raw_matn(raw, hadith_no), hadith_no
        assert whole.strip()


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_units_whose_boundary_mark_separates_nothing_keep_all_text_as_matn(full):
    """2795 and 6964-6966 carry no '*' at all; 218, 1620 and 5833 put it at
    the very end, so the mark separates nothing. Both cases are the same
    fact -- the source gives no usable boundary -- and get the same, already
    established answer: keep everything as matn rather than invent a chain,
    and never store an empty scored text.

    218 and 1620 are bare chains in the printed edition (they support the
    narration before them and have no matn of their own), so their whole
    text is a chain. 5833's matn is right there in the file, before the
    misplaced mark; excluding it on the "empty matn" signal would delete a
    real hadith. See the report for why neither is dropped.
    """
    unmarked = [u for u in full.units if u.isnad_ar is None]
    assert sorted(u.hadith_no for u in unmarked) == [
        "1620", "218", "2795", "5833", "6964", "6965", "6966"]
    for u in unmarked:
        assert u.matn_ar.strip()


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_addenda_carry_no_structural_markers(full):
    for u in full.units:
        if u.addenda_ar is None:
            continue
        assert u.addenda_ar == u.addenda_ar.strip()
        assert "  " not in u.addenda_ar
        for marker in ("~~", "@QB@", "@QE@", "*", "PageV", "#"):
            assert marker not in u.addenda_ar, f"{marker} leaked into {u.record_id}"


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_an_attribution_inside_reported_speech_is_not_a_boundary(full):
    """"fa-qala li: qala Ibn Abbas ..." -- "he said to me: Ibn Abbas said".

    The attribution is the CONTENT of the speech verb in front of it, so it
    is inside the narration, not a seam after it. 4449 is why this guard
    exists: cutting there moved 2,677 characters of the Musa and al-Khidr
    story out of the scored text and left a primary that stops mid-clause.

    Round 1 paid for this guard with a second one -- any bare trailing
    "qala" blocked a cut -- which cost two real addenda (3371, 4070). The
    forward signal replaced that blanket guard: both are now cut, and the
    narrow "speech verb + addressee" form below still holds 4449.
    """
    by_id = {u.record_id: u for u in full.units}
    assert by_id["hadith:bukhari:4449"].addenda_ar is None
    for record_id in ("hadith:bukhari:3371", "hadith:bukhari:4070"):
        assert by_id[record_id].addenda_ar is not None, record_id


def test_the_attribution_window_bounds_the_distance_in_characters():
    """The token cap and the character window are separate limits.

    On the pinned file the token cap always binds first -- the widest real
    attribution spans 24 characters against a window of 25 -- so this pins
    the window on a synthetic input rather than leaving the constant
    untested. An untested constant is one a later edit widens quietly.
    """
    from sanad_ingest.openiti import (
        _ATTRIBUTION_WINDOW,
        _NARRATION_VERBS,
        _split_secondary,
    )
    verb = _NARRATION_VERBS[0]
    baa = chr(0x0628)                       # a bare Arabic letter, no meaning
    primary = f"{baa * 20} {baa * 20}"
    for name_len, expect_cut in ((6, True), (40, False)):
        name = baa * name_len
        matn = f"{primary} {_QAL} {name} {verb} {baa * 20}"
        assert (len(_QAL) + 1 + name_len + 1 > _ATTRIBUTION_WINDOW) is not expect_cut
        got_primary, addenda = _split_secondary(matn, "hadith:bukhari:synthetic")
        if expect_cut:
            assert addenda == f"{_QAL} {name} {verb} {baa * 20}"
            assert got_primary == primary
        else:
            assert addenda is None and got_primary == matn


_AN = "".join(chr(c) for c in (0x0639, 0x0646))                     # عن
_AKHBARANI = "".join(chr(c) for c in (0x0623, 0x062E, 0x0628, 0x0631, 0x0646, 0x064A))
_WAW = chr(0x0648)
_HEADER = "#META#Header#End#"
_FAA = chr(0x0641)


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_a_chain_behind_the_verb_is_a_boundary_with_no_attribution_at_all(full):
    """What follows the verb is the signal, not what precedes it.

    Round 1 required a "qala <name>" in front of the narration verb and so
    saw only 155 of the boundaries this edition marks. These five carry a
    plainly marked second chain and no attribution the round-1 pattern could
    match: 3400 and 5989 open a fresh full chain with nothing in front of
    them at all, 1663 is introduced by "fa-qala", and 621 and 3896 hide the
    verb behind a wa-/fa- proclitic.
    """
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("621", "3896", "1663", "3400", "5989"):
        u = by_id[f"hadith:bukhari:{hadith_no}"]
        assert u.addenda_ar, f"{hadith_no} carries a marked secondary chain"
        assert (_HADDATHANA in u.addenda_ar or _HADDATHANI in u.addenda_ar
                or _AKHBARANI in u.addenda_ar)


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_the_wa_and_fa_proclitics_do_not_hide_a_narration_verb(full):
    """"wa-haddathani" and "fa-akhbarani" open a chain as surely as the bare
    verb does. Round 1 excluded them by lookbehind, which is what kept 621
    and 3896 whole."""
    by_id = {u.record_id: u for u in full.units}
    assert _WAW + _HADDATHANI in by_id["hadith:bukhari:621"].addenda_ar
    assert _FAA + _AKHBARANI in by_id["hadith:bukhari:3896"].addenda_ar


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_a_narration_verb_with_no_chain_behind_it_is_never_a_boundary(full):
    """The forward test's whole job: reject the verb inside genuine speech.

    1098 is the Prophet to Bilal -- "tell me the deed you most hope for",
    the verb followed by a prepositional phrase. 50 is Gabriel's "tell me
    about faith". 2943 and 3723 are the two counterexamples round 1 used to
    reject the brief's bare-verb fallback; the forward test excludes both
    without needing a special case.
    """
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("1098", "50", "2943", "3723"):
        assert by_id[f"hadith:bukhari:{hadith_no}"].addenda_ar is None, hadith_no


def test_an_object_pronoun_directly_after_the_verb_is_not_a_chain():
    """"akhbirni 'an al-islam" is "tell me ABOUT islam", not "X told me from
    Y". A chain always names its narrator first, so "'an" flush against the
    verb is the one position where it cannot be a chain link."""
    from sanad_ingest.openiti import _MIN_PRIMARY, _split_secondary
    baa = chr(0x0628)
    body = f"{baa * 20} {baa * 20}"
    assert len(body) >= _MIN_PRIMARY, "the primary must clear the stub floor"
    said = f"{body} {_AKHBARANI} {_AN} {body}"
    assert _split_secondary(said, "hadith:bukhari:synthetic") == (said, None)
    chain = f"{body} {_AKHBARANI} {baa * 6} {_AN} {baa * 6}"
    primary, addenda = _split_secondary(chain, "hadith:bukhari:synthetic")
    assert addenda == f"{_AKHBARANI} {baa * 6} {_AN} {baa * 6}"
    assert primary == body


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_a_request_to_narrate_is_not_a_boundary(full):
    """"qultu: akhbirni bi-shay'" -- "I said: tell me something you remember"
    (1570); "fa-haddathnahu bi-ma haddathana Anas" -- "we told him what Anas
    told us" (7072); "bi-mithl alladhi akhbarani Salim" -- "the like of that
    which Salim reported to me" (1606). In each the verb is governed by the
    word in front of it, so it opens a complement clause, not a chain, and
    cutting leaves the primary ending on "what" or "that which". Each form
    rejects exactly one record on this file; all three were found by reading
    every candidate the rule produced.
    """
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("1570", "7072", "1606"):
        assert by_id[f"hadith:bukhari:{hadith_no}"].addenda_ar is None, hadith_no


def test_a_unit_with_no_boundary_mark_is_never_split():
    """Synthetic, because the seven real ones are also caught by the
    short-primary guard and so could not tell the two rules apart.

    Here the leading chain is long enough to clear that guard: without the
    "the source marked nothing" branch the parser would cut at the second
    narration verb and store "qala Muhammad" as the scored text.
    """
    baa = chr(0x0628)
    chain = (f"{baa * 9} {baa * 9} {_QAL} {baa * 6} "
             f"{_HADDATHANA} {baa * 6} {_AN} {baa * 6}")
    unit = f"{_HEADER}\n### | {baa * 5}\n# 1 {chain} {baa * 9} {baa * 9}\n"
    (one,) = parse_openiti(unit).units
    assert one.isnad_ar is None
    assert one.addenda_ar is None
    assert one.matn_ar == f"{chain} {baa * 9} {baa * 9}"


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_units_the_source_never_split_are_never_split_here(full):
    """The seven units with no usable '*' carry isnad and matn as one string.
    Every narration verb in that string belongs to the leading chain, so a
    forward test cuts at the first narrator and leaves "haddathana Musaddad"
    as the scored text. The source marked no boundary, so none is invented.
    """
    for u in full.units:
        if u.isnad_ar is None:
            assert u.addenda_ar is None, u.record_id


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_an_interleaved_continuation_is_left_whole(full):
    """The edition sometimes breaks off mid-narration for a sub-narrator's
    aside and then resumes the same story. 2581 (Hudaybiyya), 2782
    (Heraclius) and 2880 (Khubayb) all do this, and in all three the rest of
    the narration sits behind the aside. Cutting there would move 4,279,
    3,406 and 1,001 characters of matn out of the scored text.

    They are the only three cuts on this file whose addendum would exceed
    _MAX_ADDENDUM, and all three were read by hand. The bound is a cap on
    blast radius, not a claim about Arabic: it means a rule this simple is
    not allowed to move a kilobyte of text on its own say-so.
    """
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("2581", "2782", "2880"):
        assert by_id[f"hadith:bukhari:{hadith_no}"].addenda_ar is None, hadith_no
    for u in full.units:
        if u.addenda_ar is not None:
            assert len(u.addenda_ar) <= 1000, u.record_id


def test_an_attribution_reported_by_a_speech_verb_is_not_a_boundary():
    """"fa-qala li: qala X, haddathani Y 'an Z" -- "he said TO ME: X said, Y
    narrated to me from Z". The attribution is the CONTENT of the speech verb
    in front of it, so the chain behind it is inside the narration.

    Synthetic, because the record this guard was written for (4449, 2,677
    characters of the Musa and al-Khidr story) is now also over _MAX_ADDENDUM
    and so would be held back by the size cap alone. A guard whose only real
    example is covered twice is a guard no test can see fail.
    """
    from sanad_ingest.openiti import _MIN_PRIMARY, _split_secondary
    baa = chr(0x0628)
    lii = "".join(chr(c) for c in (0x0644, 0x064A))           # "li" -- to me
    fa_qal = chr(0x0641) + _QAL                               # "fa-qala"
    body = f"{baa * 20} {baa * 20}"
    assert len(body) >= _MIN_PRIMARY, "the primary must clear the stub floor"
    said = (f"{body} {fa_qal} {lii} {_QAL} {baa * 6} "
            f"{_HADDATHANA} {baa * 6} {_AN} {baa * 6}")
    assert _split_secondary(said, "hadith:bukhari:synthetic") == (said, None)
    # the same string without the addressee IS a boundary
    told = said.replace(f"{fa_qal} {lii} ", "")
    primary, addenda = _split_secondary(told, "hadith:bukhari:synthetic")
    assert addenda == f"{_QAL} {baa * 6} {_HADDATHANA} {baa * 6} {_AN} {baa * 6}"
    assert primary == body


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_a_nameless_qala_travels_with_the_addendum_it_introduces(full):
    """"... bay'ihima | qala wa-haddathana Hammam ..." (2008, 1041).

    (6136 was the second example until round 5 put it on the do-not-cut
    audit: its primary, "the Prophet had a she-camel", names nothing.)

    A bare "qala" with no name in front of the verb is not enough on its own
    to call a boundary -- round 1 measured that and rejected it -- but once
    the chain behind the verb has settled the question, the "qala" belongs to
    the addendum. Leaving it behind ends the scored text on "he said".
    """
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("2008", "1041"):
        u = by_id[f"hadith:bukhari:{hadith_no}"]
        assert u.addenda_ar.startswith(_QAL + " "), hadith_no
        assert not u.matn_ar.endswith(" " + _QAL), hadith_no


def test_a_one_token_primary_is_not_a_boundary():
    """6477's matn is the single word "al-kaba'ir" followed by a second
    chain that carries the actual hadith. Cutting leaves a one-word scored
    text and moves the narration out of reach; leaving it whole keeps the
    narration searchable. Same reasoning as the empty-matn guard.
    """
    from sanad_ingest.openiti import _split_secondary
    baa = chr(0x0628)
    # 40 characters, so the stub floor is not what rejects this: the one-token
    # guard is. Two guards covering one input is two guards neither test can
    # see fail.
    stub = f"{baa * 40} {_HADDATHANA} {baa * 6} {_AN} {baa * 6}"
    assert _split_secondary(stub, "hadith:bukhari:synthetic") == (stub, None)


# --- fix round 3: editorial pointers are not quotable text -----------------
#
# "bi-hadha" ("with this") is what the edition prints where a narration
# repeats one already given in full. It is an Arabic commonplace, and until
# this round Sanad answered it with EXACT 1.0, Sahih al-Bukhari 1379 --
# manufacturing a hadith citation out of an everyday phrase.

_BI_HADHA = "".join(chr(c) for c in (0x0628, 0x0647, 0x0630, 0x0627))   # بهذا


def _one_unit(number: str, matn: str) -> str:
    baa = chr(0x0628)
    return (f"{_HEADER}\n### | {baa * 5}\n"
            f"# {number} {_HADDATHANA} {baa * 6} {_AN} {baa * 6} * {matn}\n")


def test_an_audited_editorial_pointer_is_marked_unscorable():
    unit = parse_openiti(_one_unit("1379", _BI_HADHA)).units[0]
    assert unit.unscorable_reason is not None
    # Marked, never rewritten: the edition's word is still the stored text.
    assert unit.matn_ar == _BI_HADHA


def test_the_mark_belongs_to_the_audited_record_not_to_the_words():
    """2866's matn is "al-harb khud'a" -- war is deceit -- and is genuine.

    The list is an audit of 17 named records, not a vocabulary of forbidden
    words. A record that is not on it stays scorable whatever it says, which
    is the only reason a four-letter matn like "bi-hadha" can be excluded
    without putting every short hadith at risk.
    """
    unit = parse_openiti(_one_unit("2866", _BI_HADHA)).units[0]
    assert unit.unscorable_reason is None


def test_the_audited_list_is_checked_against_the_text_it_audited():
    """Each entry pins the sha256 of the matn that was read in the source.

    An id alone would silently transfer the verdict to whatever a future
    edition prints under that number. The classification was made by reading
    one specific string; if that string changes, the build must stop and the
    record must be read again.
    """
    baa = chr(0x0628)
    with pytest.raises(ValueError, match="1379"):
        parse_openiti(_one_unit("1379", baa * 4))


# --- fix round 5: a cut may not leave a stub primary -----------------------


def test_a_cut_that_would_leave_a_stub_primary_is_refused():
    """Below the measured floor the record keeps all of its text, uncut.

    The two inputs differ only in the length of the primary, so the floor is
    the only thing that can decide between them: one character below it the
    cut is refused, at it the cut is made.
    """
    from sanad_ingest.openiti import _MIN_PRIMARY, _split_secondary
    baa = chr(0x0628)
    tail = f"{_QAL} {baa * 6} {_HADDATHANA} {baa * 6} {_AN} {baa * 6}"
    # Two tokens either way, so the one-token guard is not what decides this.
    half = (_MIN_PRIMARY - 1) // 2
    short = f"{baa * half} {baa * (_MIN_PRIMARY - 2 - half)}"
    assert len(short) == _MIN_PRIMARY - 1
    assert _split_secondary(f"{short} {tail}", "hadith:bukhari:x") == (
        f"{short} {tail}", None)
    exact = f"{baa * half} {baa * (_MIN_PRIMARY - 1 - half)}"
    assert len(exact) == _MIN_PRIMARY
    assert _split_secondary(f"{exact} {tail}", "hadith:bukhari:x") == (exact, tail)


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_the_stub_floor_un_cuts_exactly_the_measured_nine(full):
    """Every record the floor changes, named.

    Measured from the length distribution of the primaries the rule leaves
    behind: sorted, its lower quartile runs 18 19 20 20 21 21 22 25 25 | 32
    32 33 34 ..., and 25 -> 32 is the only gap in it wider than three. These
    nine are the records below that gap. Two of them (2390, 6949) are the
    fragments that answered a generic phrase with EXACT 1.0; the rest are
    genuine short matns whose standalone quotation this costs, which is
    recorded here so the trade is visible rather than implied.
    """
    from sanad_ingest.openiti import _MIN_PRIMARY
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("1366", "2301", "2390", "2405", "3179",
                      "5526", "5600", "6205", "6949"):
        u = by_id[f"hadith:bukhari:{hadith_no}"]
        assert u.addenda_ar is None, f"{hadith_no} must not be cut"
    # ... and nothing that IS cut sits below the floor.
    below = [u.record_id for u in full.units
             if u.addenda_ar is not None and len(u.matn_ar) < _MIN_PRIMARY]
    assert below == []


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_a_genuine_short_matn_above_the_floor_is_still_cut(full):
    """The floor is a floor, not a general refusal to cut short records.

    5381 ("truffles are from the manna, and their water is a cure for the
    eye") is 32 characters -- the first length above the gap -- and is still
    split from the second chain the edition appends to it.
    """
    u = {x.record_id: x for x in full.units}["hadith:bukhari:5381"]
    assert u.addenda_ar is not None
    assert len(u.matn_ar) == 32


# --- fix round 5: the audited do-not-cut list ------------------------------


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_an_audited_narrative_opener_is_never_cut(full):
    """632 and 6136 keep all of their text.

    The cut is textually right for both -- the edition really does print a
    short primary and then a second chain -- but the primary it leaves names
    nothing: "the Prophet passed by a man", "the Prophet had a she-camel".
    Scored on its own, that answers an everyday sentence of hadith literature
    with a confident Bukhari citation.

    Uncut, and NOT marked unscorable: the hadith itself is perfectly
    quotable, and an unscorable_reason would take its full printed text out
    of the corpus too.
    """
    by_id = {u.record_id: u for u in full.units}
    for hadith_no in ("632", "6136"):
        u = by_id[f"hadith:bukhari:{hadith_no}"]
        assert u.addenda_ar is None, hadith_no
        assert u.unscorable_reason is None, hadith_no
        assert len(u.matn_ar) > 300, hadith_no   # the whole printed hadith


def test_the_do_not_cut_list_is_checked_against_the_text_it_audited():
    """Same contract as the unscorable audit: the entry pins the sha256 of
    the matn that was read, so a changed text stops the build instead of
    inheriting a judgement made about a different string."""
    from sanad_ingest.openiti import _split_secondary
    baa = chr(0x0628)
    tail = f"{_QAL} {baa * 6} {_HADDATHANA} {baa * 6} {_AN} {baa * 6}"
    with pytest.raises(ValueError, match="632"):
        _split_secondary(f"{baa * 20} {baa * 20} {tail}", "hadith:bukhari:632")


def test_the_do_not_cut_list_only_binds_the_records_it_names():
    """A record not on the list is cut on the same input that the list
    refuses, so the list -- and not some other guard -- is what stops it."""
    from sanad_ingest.openiti import _split_secondary
    baa = chr(0x0628)
    tail = f"{_QAL} {baa * 6} {_HADDATHANA} {baa * 6} {_AN} {baa * 6}"
    body = f"{baa * 20} {baa * 20}"
    primary, addenda = _split_secondary(f"{body} {tail}", "hadith:bukhari:999999")
    assert primary == body
    assert addenda == tail
