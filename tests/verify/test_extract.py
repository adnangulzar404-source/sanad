from sanad.verify.extract import extract_spans


def test_extracts_guillemet_quote():
    spans = extract_spans('He said «قُلْ هُوَ ٱللَّهُ أَحَدٌ» today.')
    assert any(s.kind == "wrapped" and "قُلْ" in s.text for s in spans)


def test_extracts_curly_quote():
    spans = extract_spans('"قُلْ هُوَ ٱللَّهُ أَحَدٌ"')
    assert len(spans) >= 1


def test_extracts_ornate_parenthesis():
    spans = extract_spans('﴿قُلْ هُوَ ٱللَّهُ أَحَدٌ﴾')
    assert len(spans) >= 1


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
