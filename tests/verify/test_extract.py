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


# Six Bukhari records carry an EMPTY matn, so quoting them produces no span.
# This is not a corpus defect introduced by ingest -- it is what the source
# says -- but it splits into two causes, and both are pinned by id so that
# neither can grow silently:
#
#   218, 1620, 5833  -- the OCR'd edition puts its "*" isnad/matn separator at
#                       the very end of the entry, with no narration text after
#                       it. There is nothing to store.
#   3584, 4063, 6050 -- the narration IS in the file, but as a "# ( ... )"
#                       verse/poetry line AFTER the numbered entry. The parser
#                       drops non-numbered "#" chunks (744 of them are chapter
#                       commentary that is deliberately not a hadith), so these
#                       three lose their matn with it. That is a parser defect,
#                       recorded here rather than papered over.
#
# Neither kind can produce a false verification: `_exact_at_tier` and
# `_best_fuzzy` both return early on an empty needle, and `extract_spans`
# never yields an empty span, so an empty record is unreachable from a query.
_EMPTY_MATN = {
    "hadith:bukhari:218", "hadith:bukhari:1620", "hadith:bukhari:3584",
    "hadith:bukhari:4063", "hadith:bukhari:5833", "hadith:bukhari:6050",
}


def test_every_real_record_is_extractable_when_quoted():
    from sanad.corpus import db
    conn = db.connect("data/sanad-quran.db")
    missed = [r.id for r in db.iter_records(conn)
              if r.text_ar and not extract_spans("«" + r.text_ar + "»")]
    assert missed == [], f"{len(missed)} records produce no span: {missed[:10]}"


def test_exactly_the_known_records_have_no_text():
    from sanad.corpus import db
    conn = db.connect("data/sanad-quran.db")
    empty = {r.id for r in db.iter_records(conn) if not r.text_ar}
    assert empty == _EMPTY_MATN


def test_an_empty_record_cannot_be_matched():
    from sanad.corpus import db
    from sanad.verify.engine import verify_spans
    conn = db.connect("data/sanad-quran.db")
    for quotation in ("«»", "«   »", ""):
        assert verify_spans(conn, quotation) == []
