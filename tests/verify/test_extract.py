import pytest

from sanad.verify.extract import extract_spans


def test_extracts_guillemet_quote():
    spans = extract_spans('He said «قُلْ هُوَ ٱللَّهُ أَحَدٌ» today.')
    assert any(s.kind == "wrapped" and "قُلْ" in s.text for s in spans)


def test_extracts_curly_quote():
    # U+201C/U+201D: left/right double quotation mark
    spans = extract_spans('"قُلْ هُوَ ٱللَّهُ أَحَدٌ"')
    assert any(s.kind == "wrapped" for s in spans)


def test_extracts_straight_quote():
    # U+0022: quotation mark (ASCII)
    spans = extract_spans('"قُلْ هُوَ ٱللَّهُ أَحَدٌ"')
    assert any(s.kind == "wrapped" for s in spans)


def test_extracts_ornate_parenthesis():
    spans = extract_spans('﴿قُلْ هُوَ ٱللَّهُ أَحَدٌ﴾')
    assert any(s.kind == "wrapped" for s in spans)


def test_extracts_bare_arabic_run():
    spans = extract_spans("Islam teaches إِنَّا أَعْطَيْنَاكَ ٱلْكَوْثَرَ in this surah.")
    assert any("أَعْطَيْنَٰ" in s.text or "أَعْطَيْنَا" in s.text for s in spans)


def test_offsets_point_into_the_original_text():
    text = "before قُلْ هُوَ ٱللَّهُ أَحَدٌ after"
    span = extract_spans(text)[0]
    assert text[span.start:span.end].strip() == span.text


def test_ignores_short_arabic_fragments():
    assert extract_spans("the word الله alone") == []


def test_deduplicates_overlapping_extractions():
    # a wrapped quote also matches the bare-Arabic pattern; only one span
    spans = extract_spans('«قُلْ هُوَ ٱللَّهُ أَحَدٌ»')
    assert len(spans) == 1


def test_returns_empty_for_pure_latin():
    assert extract_spans("no arabic here at all") == []


def test_handles_multiple_distinct_quotes():
    text = "«قُلْ هُوَ ٱللَّهُ أَحَدٌ» and «ٱللَّهُ ٱلصَّمَدُ»"
    assert len(extract_spans(text)) == 2


def test_spans_are_sorted_by_position():
    text = "«ٱللَّهُ ٱلصَّمَدُ» then «قُلْ هُوَ ٱللَّهُ أَحَدٌ»"
    spans = extract_spans(text)
    assert spans == sorted(spans, key=lambda s: s.start)


@pytest.mark.parametrize("ch", [
    "«",  # « U+00AB
    "“",  # " U+201C
    '"',  # " U+0022
    "『",  # 『 U+300E
    "【",  # 【 U+3010
    "﴿",  # ﴿ U+FD3F
    "»",  # » U+00BB
    "”",  # " U+201D
    "』",  # 』 U+300F
    "】",  # 】 U+3011
    "﴾",  # ﴾ U+FD3E
])
def test_wrapped_pattern_contains_every_delimiter(ch):
    from sanad.verify.extract import _WRAPPED
    assert ch in _WRAPPED.pattern


# No record carries an empty matn. Six did, and both causes are now fixed in
# the parser rather than tolerated here:
#
#   3584, 4063, 6050 -- the narration IS in the file, but on a "# ( ... )"
#                       verse line AFTER the numbered entry. The parser used
#                       to flush and then discard every non-numbered "#"
#                       chunk, taking these three matns (and the closing
#                       verse of 62 other records) with them. Such a line is
#                       now read as a continuation of the unit already open.
#   218, 1620, 5833  -- the edition puts its "*" isnad/matn separator at the
#                       very end of the entry, where it separates nothing.
#                       That is not a matn-less hadith, it is an unusable
#                       mark: 5833's matn is right there in front of it. All
#                       three now keep their whole text as matn, the same
#                       answer the four entries with no "*" at all already
#                       got. 218 and 1620 are bare supporting chains in the
#                       printed edition, so their whole text is a chain;
#                       they are kept because a citable record silently
#                       vanishing from the corpus is worse than one that
#                       nobody would ever quote.
#
# An empty record could not produce a false verification either -- both
# `_exact_at_tier` and `_best_fuzzy` return early on an empty needle, and
# `extract_spans` never yields an empty span -- but it is a hazard the build
# now refuses to ship at all; see `_hadith_records`.


def test_every_real_record_is_extractable_when_quoted():
    from sanad.corpus import db
    conn = db.connect("data/sanad-quran.db")
    missed = [r.id for r in db.iter_records(conn)
              if r.text_ar and not extract_spans("«" + r.text_ar + "»")]
    assert missed == [], f"{len(missed)} records produce no span: {missed[:10]}"


def test_no_record_has_an_empty_scored_text():
    from sanad.corpus import db
    conn = db.connect("data/sanad-quran.db")
    empty = {r.id for r in db.iter_records(conn) if not r.text_ar.strip()}
    assert empty == set()


def test_an_empty_record_cannot_be_matched():
    from sanad.corpus import db
    from sanad.verify.engine import verify_spans
    conn = db.connect("data/sanad-quran.db")
    for quotation in ("«»", "«   »", ""):
        assert verify_spans(conn, quotation) == []


# --- M2: one floor, asked for in one place ---------------------------------
#
# `engine._is_only_a_citation` asks this module's question -- "would what is
# left still have been a span?" -- and answered it with its own copy of the
# two numbers: `floor = 2 if span.kind == "wrapped" else 6`. Two literals in
# two files with no way of disagreeing out loud. Lowering the extractor's
# minimum would have left the engine deleting quotations the extractor had
# just accepted, and nothing would have failed.
#
# The floors are not asserted to be 2 and 6 here. That would pin the numbers
# without checking that either module uses them. What is asserted is that
# both modules stop at the same character, measured by running them.

def _letters(n: int) -> str:
    """`n` Arabic letters, space-separated, built from codepoints.

    Space-separated so a bare run can be made long enough for the run regex
    (7 characters) while carrying fewer than that many LETTERS -- which is
    what the floor counts. Codepoints rather than typed Arabic, for the
    reason this project has learned eleven times.
    """
    return " ".join(chr(0x0628 + (i % 10)) for i in range(n))


def _extractor_floor(kind: str) -> int:
    """The fewest letters `extract_spans` will keep, found by asking it."""
    for n in range(1, 16):
        text = _letters(n)
        if kind == "wrapped":
            text = "«" + text + "»"
        spans = [s for s in extract_spans(text) if s.kind == kind]
        if spans:
            return n
    raise AssertionError(f"extract_spans never produced a {kind} span")


def _engine_floor(kind: str) -> int:
    """The fewest letters the engine will leave standing beside a citation."""
    from sanad.verify.engine import _is_only_a_citation
    from sanad.verify.extract import Span
    for n in range(1, 16):
        # One covered character, then the letters: the remainder the engine
        # measures is exactly `_letters(n)`.
        text = "x" + _letters(n)
        span = Span(text=text, start=0, end=len(text), kind=kind)
        if not _is_only_a_citation(span, [(0, 1)]):
            return n
    raise AssertionError(f"the engine discarded every {kind} span")


@pytest.mark.parametrize("kind", ["wrapped", "arabic-run"])
def test_the_engine_and_the_extractor_stop_at_the_same_character(kind):
    from sanad.verify.extract import minimum_chars
    assert _extractor_floor(kind) == minimum_chars(kind)
    assert _engine_floor(kind) == minimum_chars(kind)


def test_the_two_kinds_do_not_share_a_floor():
    """Otherwise the test above would pass with one number for both, and the
    distinction the floors exist to draw -- a reader who typed quotation
    marks has said they are quoting; a bare run has said nothing -- would be
    gone without a failure.
    """
    from sanad.verify.extract import minimum_chars
    assert minimum_chars("wrapped") < minimum_chars("arabic-run")


def test_every_kind_the_extractor_produces_has_a_floor():
    from sanad.verify.extract import minimum_chars
    text = "«" + _letters(4) + "» and " + _letters(9)
    kinds = {s.kind for s in extract_spans(text)}
    assert kinds == {"wrapped", "arabic-run"}, kinds
    for kind in kinds:
        assert minimum_chars(kind) > 0


def test_a_kind_with_no_judgement_behind_it_is_refused():
    """Not a default. A third span kind is a question about how much Arabic
    makes that kind a quotation, and silently handing it the bare-run floor
    would answer it by accident in two modules at once.
    """
    from sanad.verify.extract import minimum_chars
    with pytest.raises(ValueError, match="no minimum is defined"):
        minimum_chars("footnote")


# The agreement test above is genuine and it is not enough: it compares three
# measurements of the same constant, so lowering `MIN_RUN_CHARS` from 6 to 5
# moves all three together and the whole 545-test suite still passes. The
# first fix round's report claimed otherwise and cited a test by name that is
# not in this repository. These two pin the VALUES, in the product's own
# terms -- what counts as a quotation -- so the numbers cannot be changed in
# silence. Keep both: the agreement test says the two modules use one floor,
# and these say which floor it is.


def test_a_bare_run_becomes_a_quotation_at_six_letters_and_not_five():
    """A bare run of Arabic has said nothing about itself. Five letters --
    two short words -- is ordinary prose; the floor is where a run stops
    being likely to be anything but a quotation. Both directions, because a
    test of one is satisfied by a floor of zero or of infinity."""
    assert [s for s in extract_spans(_letters(5)) if s.kind == "arabic-run"] == []
    assert [s for s in extract_spans(_letters(6)) if s.kind == "arabic-run"] != []


def test_a_wrapped_quote_becomes_a_quotation_at_two_letters_and_not_one():
    """Someone who typed quotation marks has told you they are quoting, so
    the floor is low -- but not absent: a single letter inside guillemets is
    not a quotation of anything this corpus can answer."""
    assert extract_spans("«" + _letters(1) + "»") == []
    assert extract_spans("«" + _letters(2) + "»") != []


def test_the_engine_has_no_floor_of_its_own_to_fall_back_on():
    """`engine._is_only_a_citation` must ASK for the floor, not carry a copy.

    The copy it used to carry -- `floor = 2 if span.kind == "wrapped" else 6`
    -- is indistinguishable from `minimum_chars` on the two kinds that exist,
    which is why restoring it passes all 105 verify/engine tests. The one
    place the two differ is a kind nobody has judged yet: `minimum_chars`
    refuses it, and the copy quietly hands it the bare-run number. So that is
    where this is measured.
    """
    from sanad.verify.engine import _is_only_a_citation
    from sanad.verify.extract import Span
    text = "x" + _letters(9)
    span = Span(text=text, start=0, end=len(text), kind="footnote")
    with pytest.raises(ValueError, match="no minimum is defined"):
        _is_only_a_citation(span, [(0, 1)])
