# Fixture provenance: tests/fixtures/bukhari_sample.txt was sliced verbatim
# from the pinned OpenITI Bukhari download (sha256
# 69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7 for
# /tmp/bukhari.txt) via the exact script in Task 2 Step 1 -- no Arabic was
# typed by hand. Fixture's own sha256 as generated on 2026-09-22:
# d1338229de2aace5432f3ddb384e99a3d367ca21e0c7f7be10567c8183cecffd
import re
from pathlib import Path

import pytest
from sanad_ingest.openiti import parse_openiti

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bukhari_sample.txt"
FULL = Path("/tmp/bukhari.txt")   # the real download; see Task 2 Step 1


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
def test_the_four_unmarked_hadith_keep_all_text_as_matn():
    """2795, 6964-6966 carry no '*'. Guessing a boundary would invent a chain."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    unmarked = [u for u in parsed.units if u.isnad_ar is None]
    assert sorted(u.hadith_no for u in unmarked) == ["2795", "6964", "6965", "6966"]
    for u in unmarked:
        assert u.matn_ar.strip()


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
