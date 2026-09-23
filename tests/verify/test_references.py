import pytest

from sanad.verify.references import (
    HadithReference,
    Reference,
    nearest_reference,
    parse_citations,
    parse_references,
)


def test_parses_numeric_reference():
    refs = parse_references("see 2:255 for this")
    assert (refs[0].surah, refs[0].ayah) == (2, 255)


def test_parses_named_surah_with_numbers():
    refs = parse_references("Al-Baqarah 2:255")
    assert (refs[0].surah, refs[0].ayah) == (2, 255)


def test_parses_bare_surah_name():
    refs = parse_references("as stated in Al-Ikhlas")
    assert refs[0].surah == 112
    assert refs[0].ayah is None


def test_surah_name_spelling_variants():
    for spelling in ("Al-Fatihah", "al fatiha", "AL-FATIHA"):
        assert parse_references(spelling)[0].surah == 1


def test_records_position_in_text():
    text = "aaaa 112:1 bbbb"
    assert parse_references(text)[0].start == text.index("112:1")


def test_ignores_out_of_range_surah():
    assert parse_references("999:1") == []


def test_ignores_out_of_range_ayah():
    # Al-Fatihah has 7 verses; 300 is impossible
    assert parse_references("1:300") == []


def test_no_reference_returns_empty():
    assert parse_references("no citation here") == []


def test_nearest_reference_picks_closest():
    refs = [Reference(2, 255, "2:255", 0), Reference(112, 1, "112:1", 500)]
    assert nearest_reference(refs, 480).surah == 112


def test_nearest_reference_respects_window():
    refs = [Reference(2, 255, "2:255", 0)]
    assert nearest_reference(refs, 5000, window=180) is None


def test_nearest_reference_on_empty_list():
    assert nearest_reference([], 0) is None


@pytest.mark.parametrize("text", [
    "Maryam told me she had finished reading it.",
    "My colleague Yusuf sent the draft yesterday.",
    "Ibrahim and Muhammad will both attend.",
    "Yunus is presenting after lunch.",
])
def test_ordinary_personal_names_are_not_references(text):
    assert parse_references(text) == []


@pytest.mark.parametrize("text,expected", [
    ("as stated in Al-Ikhlas", 112),
    ("see Surah Maryam", 19),
    ("chapter Yusuf describes this", 12),
    ("Al-Baqarah discusses it", 2),
])
def test_qualified_or_prefixed_names_still_resolve(text, expected):
    assert parse_references(text)[0].surah == expected


def test_arabic_indic_digits_parse_correctly():
    r = parse_references("٢:٢٥٥")[0]
    assert (r.surah, r.ayah) == (2, 255)


@pytest.mark.parametrize("text,number", [
    ("Bukhari 1", "1"),
    ("Sahih al-Bukhari, no. 1", "1"),
    ("al-Bukhari, Book 1, Hadith 1", "1"),
    ("Sahih Bukhari 7124", "7124"),
])
def test_parses_hadith_citations(text, number):
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].collection == "bukhari"
    assert refs[0].hadith_no == number


def test_bare_collection_name_is_not_a_reference():
    """'Bukhari' names a collection, not a text -- same rule as bare 'Maryam'."""
    assert not [r for r in parse_references("as Bukhari reports")
                if isinstance(r, HadithReference)]


def test_collection_name_governs_a_colon_pair():
    """'Bukhari 1:1' is kitab 1 hadith 1, never surah 1 ayah 1."""
    refs = parse_references("Bukhari 1:1")
    assert not any(isinstance(r, Reference) for r in refs)
    assert any(isinstance(r, HadithReference) for r in refs)


def test_a_plain_verse_citation_is_still_a_verse():
    refs = parse_references("Al-Baqarah 2:255")
    assert any(isinstance(r, Reference) and r.surah == 2 and r.ayah == 255
               for r in refs)
    assert not any(isinstance(r, HadithReference) for r in refs)


def test_out_of_range_number_does_not_fall_back_to_a_verse_reading():
    refs = parse_references("Bukhari 99999")
    assert not any(isinstance(r, Reference) for r in refs)


def test_out_of_range_number_is_also_not_a_hadith_reference():
    """The brief's own check above only rules out a *verse* reading -- an
    out-of-range hadith number could still slip through as a HadithReference
    without failing it. Confirm it doesn't."""
    refs = parse_references("Bukhari 99999")
    assert not any(isinstance(r, HadithReference) for r in refs)


def test_colon_pair_takes_the_second_number_as_the_hadith_number():
    """'Bukhari, Book 3, Hadith 42' and a bare 'Bukhari 3:42' must both read
    as hadith 42 -- the kitab/book number is discarded, never mistaken for
    the hadith number just because it happens to come first."""
    refs = [r for r in parse_references("Bukhari 3:42") if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].hadith_no == "42"


# --- Arabic-script hadith citations -----------------------------------------
#
# The Qur'an path already accepts Arabic-Indic (U+0660-0669) and Eastern
# Arabic (U+06F0-06F9) digits alongside ASCII, for free, because Python's
# `re` module's `\d` and the builtin `int()` both already understand them
# (see test_arabic_indic_digits_parse_correctly above). The hadith path
# below reuses that instead of writing a second digit-normalizing routine.

_BUKHARI_342_FORMS = [
    ("صحيح البخاري ٣٤٢",  # صحيح البخاري ٣٤٢
     "342"),
    ("البخاري ٣٤٢",  # البخاري ٣٤٢
     "342"),
    ("رواه البخاري ٣٤٢",  # رواه البخاري ٣٤٢
     "342"),
    ("البخاري ۳۴۲",  # البخاري ۳۴۲ (Eastern Arabic digits)
     "342"),
    ("البخاري 342",  # البخاري 342 (ASCII digits after an Arabic name)
     "342"),
    ("البخاري حديث ٣٤٢",  # البخاري حديث ٣٤٢ ("hadith" connector word)
     "342"),
    ("البخاري رقم ٣٤٢",  # البخاري رقم ٣٤٢ ("number" connector word)
     "342"),
    ("بخاري ٣٤٢",  # بخاري ٣٤٢ (bare, without the definite article)
     "342"),
]


@pytest.mark.parametrize("text,number", _BUKHARI_342_FORMS)
def test_parses_arabic_hadith_citations(text, number):
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].collection == "bukhari"
    assert refs[0].hadith_no == number


def test_bare_arabic_collection_name_is_not_a_reference():
    """'رواه البخاري' (narrated by al-Bukhari) with no
    number attached names a collection, not a text -- same rule as the
    Latin bare-name case above."""
    text = "رواه البخاري"  # رواه البخاري
    assert not [r for r in parse_references(text) if isinstance(r, HadithReference)]


def test_arabic_verse_citation_is_unaffected_by_hadith_parsing():
    """'الإخلاص ١١٢:١' (Al-Ikhlas 112:1, written with the
    Arabic surah name and Arabic-Indic digits) already resolves as a verse
    on the Qur'an path; adding hadith parsing must not disturb that or
    spuriously add a HadithReference alongside it."""
    text = "الإخلاص ١١٢:١"  # الإخلاص ١١٢:١
    refs = parse_references(text)
    assert any(isinstance(r, Reference) and r.surah == 112 and r.ayah == 1 for r in refs)
    assert not any(isinstance(r, HadithReference) for r in refs)


def test_arabic_out_of_range_number_is_not_a_hadith_reference():
    text = "البخاري ٩٩٩٩٩"  # البخاري ٩٩٩٩٩
    refs = parse_references(text)
    assert not any(isinstance(r, HadithReference) for r in refs)
    assert not any(isinstance(r, Reference) for r in refs)


def test_other_arabic_collection_name_is_not_parsed():
    """Only Bukhari exists in the corpus so far (see _COLLECTIONS/_COLLECTIONS_AR);
    a citation naming a different collection must not be mistaken for it."""
    text = "مسلم ١٢"  # مسلم ١٢ (Muslim 12)
    assert parse_references(text) == []


def test_arabic_colon_pair_takes_the_second_number():
    """'البخاري ١:٢' (kitab 1, hadith 2) must never also read as
    surah 1 ayah 2 (a real, valid verse address) -- same claimed-span rule
    as the Latin 'Bukhari 1:1' case above."""
    text = "البخاري ١:٢"  # البخاري ١:٢
    refs = parse_references(text)
    assert not any(isinstance(r, Reference) for r in refs)
    hadith_refs = [r for r in refs if isinstance(r, HadithReference)]
    assert len(hadith_refs) == 1
    assert hadith_refs[0].hadith_no == "2"


# --- Task 6, D3: the hadith-number lower bound ------------------------------
#
# The upper bound (MAX_HADITH_NO) was enforced from the start; the lower bound
# was not, so "Bukhari 0" parsed to hadith_no='0'. There is no hadith 0, and a
# reference to a record that cannot exist can only ever produce a spurious
# WRONG_REFERENCE downstream -- the same "a miss costs less than noise" rule
# that governs bare surah names in this module.


@pytest.mark.parametrize("text", [
    "Bukhari 0",
    "Sahih al-Bukhari, no. 0",
    "Bukhari 000",
    "Bukhari 1:0",          # kitab 1, hadith 0 -- the second number is the one
    "صحيح البخاري ٠",
    "البخاري ٠",
])
def test_hadith_zero_is_not_a_reference(text):
    assert not [r for r in parse_references(text) if isinstance(r, HadithReference)]


# A "and it does not fall back to a verse reading" companion was written here
# and then DELETED, because mutation testing showed it could not fail: with
# both the range check and the span claim stripped out, "Bukhari 0" and
# "Bukhari 1:0" still yield no `Reference`, since ayah 0 is not a valid verse
# address under any surah. A rejected hadith number is structurally incapable
# of reading as a verse. (The same holds for the pre-existing
# `test_out_of_range_number_does_not_fall_back_to_a_verse_reading` above,
# which is left as found -- it is not this task's to change.)


def test_the_first_real_hadith_number_still_parses():
    """The bound is `< 1`, not `<= 1`: hadith 1 is the most-quoted hadith in
    the collection. A test for the rejection of 0 that did not also pin 1
    would pass just as happily against an off-by-one."""
    refs = [r for r in parse_references("Bukhari 1") if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].hadith_no == "1"


# --- Task 6, D1: attachment is by PROXIMITY, across kinds ---------------------
#
# The rule is two-part and the halves live in different modules. Here:
# a citation attaches to the quotation it is nearest to, whatever kind of
# record that citation addresses -- `nearest_reference` does not filter by
# kind, and must not, or an ayah attributed to Sahih al-Bukhari would draw no
# citation at all and be reported Verified without complaint. The second half
# -- that a kind mismatch between the attached citation and the record the
# text was found in is a WRONG_REFERENCE -- is the engine's, and is tested
# there.


def _mixed_refs():
    """A hadith citation at 0 and a verse citation at 500."""
    return [HadithReference("bukhari", "2866", "Bukhari 2866", 0),
            Reference(112, 1, "112:1", 500)]


def test_nearest_reference_crosses_kinds_on_proximity():
    """Whichever is nearer wins, full stop. A kind filter here would silently
    discard the citation that makes a misattribution detectable."""
    assert nearest_reference(_mixed_refs(), 10).hadith_no == "2866"
    assert nearest_reference(_mixed_refs(), 490).surah == 112


def test_a_hadith_citation_is_returned_for_a_position_with_no_verse_near():
    assert nearest_reference(_mixed_refs(), 0).hadith_no == "2866"


def test_the_window_still_applies_across_kinds():
    """Kind does not affect reach; distance still does."""
    assert nearest_reference(_mixed_refs(), 5000, window=180) is None


# --- Task 6, concern 1: spans that READ as a citation, resolved or not -------


def test_parse_citations_reports_the_references_parse_references_does():
    text = "«x» (Bukhari 1) and (2:255)"
    assert parse_citations(text).references == parse_references(text)


def test_parse_citations_spans_cover_a_resolved_citation():
    text = "see Bukhari 342 here"
    spans = parse_citations(text).spans
    start = text.index("Bukhari 342")
    assert (start, start + len("Bukhari 342")) in spans


@pytest.mark.parametrize("text", [
    "\u0635\u062d\u064a\u062d \u0627\u0644\u0628\u062e\u0627\u0631\u064a \u0669\u0669\u0669\u0669\u0669",
    "Bukhari 99999",
    "\u0635\u062d\u064a\u062d \u0627\u0644\u0628\u062e\u0627\u0631\u064a \u0660",
    "Bukhari 0",
])
def test_an_unresolvable_citation_still_reports_its_span(text):
    """The point of `spans` being separate from `references`.

    A citation whose number is out of range resolves to nothing, but the text
    is still unmistakably a citation and must not be offered to the verifier
    as a quotation to look up -- which is what used to happen, and left the
    reader told that "sahih al-bukhari 99999" is not in this corpus.
    """
    parsed = parse_citations(text)
    assert parsed.references == []
    assert parsed.spans, "an unresolved citation must still claim its span"
    covered = set()
    for start, end in parsed.spans:
        covered.update(range(start, end))
    # What is left uncovered must be too slight to read as a quotation. (It is
    # not always empty: `\\d{1,4}` stops after four digits, so the fifth digit
    # of "99999" is outside the claim. That leftover is one character, which
    # is the point -- no run of it can survive extraction.)
    assert len(set(range(len(text))) - covered) <= 1


def test_prose_with_no_citation_claims_no_spans():
    """The filter downstream keys off these spans; if everything claimed a
    span, every quotation would be discarded as a citation."""
    assert parse_citations("There is no citation in this sentence.").spans == []
