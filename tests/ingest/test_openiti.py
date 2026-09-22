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
