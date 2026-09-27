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
    """'Bukhari 1:1' is a hadith citation, never surah 1 ayah 1.

    It resolves to nothing -- see the book-relative tests below -- but the
    span is still a citation and still governed by the collection name, so no
    verse reading may be salvaged out of it.
    """
    refs = parse_references("Bukhari 1:1")
    assert not any(isinstance(r, Reference) for r in refs)


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


# --- book-relative citations resolve to nothing -----------------------------
#
# This block replaces two tests that asserted the opposite and agreed with the
# code and its docstrings while all three were wrong together. "Bukhari 3:42"
# was read as hadith 42 and "al-Bukhari, Book 1, Hadith 1" as hadith 1, and
# the second passed only by coincidence -- book 1 happens to start at hadith
# 1. The corpus is `bugha-1987`, one sequential 1..7124 series; a number that
# is relative to a book is not a number in that series, and reading it as one
# told correctly-citing readers they had misattributed their own quotation.


@pytest.mark.parametrize("text", [
    "al-Bukhari, Book 1, Hadith 1",
    "Sahih al-Bukhari, Book 52, Hadith 268",
    "Bukhari, Book 2, Hadith 1",
    "Bukhari kitab 3 hadith 42",
    "Bukhari 3:42",
    "Bukhari 1:1",
    "Bukhari 1:2:13",
])
def test_a_book_relative_citation_resolves_to_no_reference(text):
    """No reference of EITHER family. A book-relative citation that resolved
    to a hadith would be a false accusation; one that fell through to the
    verse pass would be a stranger one.
    """
    assert parse_references(text) == []


@pytest.mark.parametrize("text", [
    "Sahih al-Bukhari, Book 52, Hadith 268",
    "Bukhari 3:42",
])
def test_a_book_relative_citation_still_claims_its_span(text):
    """Refused, not unseen. The span has to stay claimed or the numbers in it
    get re-read by the verse pass, and an Arabic-script citation of this shape
    would be handed to the verifier as a quotation to look up.
    """
    spans = parse_citations(text).spans
    assert spans, "a refused citation must still claim its span"
    covered = set()
    for start, end in spans:
        covered.update(range(start, end))
    assert covered >= set(range(text.index("B"), len(text)))


def test_the_second_number_is_not_salvaged_when_the_first_would_resolve():
    """The trap in deleting the colon branch instead of refusing it.

    Drop `second` from the pattern and "Bukhari 1:2:13" no longer matches the
    pair -- it matches the "Bukhari 1" in front of it, and resolves to hadith
    1. That is a different wrong reference, not the absence of one, so the
    pair is matched on purpose and thrown away on purpose.
    """
    assert parse_references("Bukhari 1:2:13") == []
    assert parse_references("Bukhari 1:1") == []


def test_a_plain_number_still_resolves_beside_the_refusal():
    """The refusal must be narrow. "Bukhari 2866" is the citation form this
    corpus can answer, and a fix that silenced it too would trade a false
    accusation for a lost feature.
    """
    refs = [r for r in parse_references("Bukhari 2866") if isinstance(r, HadithReference)]
    assert len(refs) == 1 and refs[0].hadith_no == "2866"


# --- the digit run is taken whole -------------------------------------------
#
# `\d{1,4}` with no trailing boundary silently truncated a longer number to
# its first four digits, so "Bukhari 12345" cited hadith 1234 and a correctly
# quoted hadith beside it came back WRONG_REFERENCE. The upper bound hid it
# for precisely the numbers that overshoot 7124, which is why "Bukhari 99999"
# looked fine while "Bukhari 71240" did not.


@pytest.mark.parametrize("text,truncation", [
    ("Bukhari 12345", "1234"),
    ("Bukhari 71240", "7124"),   # truncates to the corpus maximum: in range
    ("Bukhari 99999", "9999"),   # out of range, so this one only ever looked fine
    ("البخاري ٢٨٦٦٠", "2866"),
])
def test_an_overlong_number_never_resolves_to_its_first_digits(text, truncation):
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert truncation not in [r.hadith_no for r in refs]
    # and it resolves to no reference of any kind, not merely a different one
    assert parse_references(text) == []


@pytest.mark.parametrize("text", ["Bukhari 12345", "البخاري ٢٨٦٦٠"])
def test_an_overlong_number_still_claims_its_span(text):
    """It is still unmistakably a citation, so the verifier must not be
    offered it as a quotation to look up -- the Arabic form especially, since
    an Arabic-script citation is itself a run of Arabic.
    """
    assert parse_citations(text).spans


@pytest.mark.parametrize("text,number", [
    ("Bukhari 11", "11"),
    ("Bukhari 7124", "7124"),
    ("Bukhari 0002866", "2866"),
])
def test_a_number_inside_the_range_still_resolves(text, number):
    """The boundary must not be paid for with the numbers that are fine.
    Leading zeros are not significance -- "0002866" is 2866, and the length
    bound is applied to the significant digits, not to the written ones.
    """
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert len(refs) == 1 and refs[0].hadith_no == number


def test_a_pasted_number_too_long_for_int_declines_instead_of_raising():
    """The parser's job here is to decline, not to raise.

    CPython refuses to convert a digit string past a few thousand characters,
    so an unbounded `int()` on a `\\d+` group turns a pasted number into a
    ValueError out of `parse_references` -- a 500 from a text input. The
    length check runs first for that reason, and this pins the ordering.
    """
    assert parse_references("Bukhari " + "9" * 10000) == []
    # And the other shape of long run: ten thousand leading zeros in front of
    # a real number. Only the significant digits are converted, so this is
    # hadith 1 rather than either a crash or a refusal.
    padded = parse_references("Bukhari " + "0" * 10000 + "1")
    assert [r.hadith_no for r in padded] == ["1"]


def test_a_volume_prefixed_citation_is_not_parsed():
    """"Vol. 4, Book 52, Hadith 268" is the same USC-MSA scheme with a volume
    in front. The pattern does not reach across the "Vol. 4," and must not
    learn to: pinned here so a later widening of the pattern has to come past
    this test rather than quietly re-opening the class.
    """
    assert parse_references("Sahih al-Bukhari, Vol. 4, Book 52, Hadith 268") == []


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


def test_an_unsupported_collection_name_is_not_parsed():
    """This corpus recognises six collections (Task 9): bukhari, muslim,
    abudawud, tirmidhi, nasai, ibnmajah -- see `_COLLECTIONS`/
    `_COLLECTIONS_AR`. Previously this test used muslim as the example
    unsupported name; muslim is now supported (see
    `test_parses_all_six_collections_in_arabic_script` below), so this
    is updated to a real seventh collection, al-Darimi, that this corpus
    still does not ship -- a citation naming it must not be mistaken for
    one of the six that resolve.

    Codepoints verified with `unicodedata.name()`: U+0627 ARABIC LETTER
    ALEF, U+0644 ARABIC LETTER LAM, U+062F ARABIC LETTER DAL, U+0627
    ARABIC LETTER ALEF, U+0631 ARABIC LETTER REH, U+0645 ARABIC LETTER
    MEEM, U+064A ARABIC LETTER YEH (al-darimi).
    """
    al_darimi = ("\u0627\u0644\u062F\u0627\u0631\u0645\u064A")
    text = f"{al_darimi} \u0661\u0662"  # al-darimi 12
    assert parse_references(text) == []


def test_arabic_colon_pair_resolves_to_nothing_and_is_not_a_verse():
    """'البخاري ١:٢' is the same book-relative form written in
    Arabic script, and gets the same answer: no hadith reference, because the
    second number is relative to a book this corpus cannot map -- and no
    verse reference either, because the span is claimed, even though 1:2 is a
    real, valid verse address.

    Previously this read as hadith 2. Readers who cite in Arabic are the ones
    most likely to cite precisely, and they must not be the ones told they
    misattributed their own quotation.
    """
    text = "البخاري ١:٢"  # البخاري ١:٢
    parsed = parse_citations(text)
    assert parsed.references == []
    assert parsed.spans


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
    # Nothing is left over. It used to be one character: `\\d{1,4}` stopped
    # after four digits, so the fifth digit of "99999" fell outside the claim
    # -- the same missing boundary that made "Bukhari 12345" cite hadith 1234.
    # The digit run is taken whole now, so the claim covers the whole citation.
    assert set(range(len(text))) - covered == set()


def test_prose_with_no_citation_claims_no_spans():
    """The filter downstream keys off these spans; if everything claimed a
    span, every quotation would be discarded as a citation."""
    assert parse_citations("There is no citation in this sentence.").spans == []


# --- leading zeros are dropped by digit VALUE, not by the character "0" ------
#
# `_hadith_number` scans for the first character whose `unicodedata.digit` is
# non-zero rather than calling `digits.lstrip("0")`. The two agree on every
# ASCII citation in this file, which is why replacing one with the other
# passed all 80 reference tests (F3). They disagree the moment a reader pads
# with the zero of the script they are writing in: U+0660 ARABIC-INDIC DIGIT
# ZERO and U+06F0 EXTENDED ARABIC-INDIC DIGIT ZERO are not the character "0",
# so `lstrip` leaves them in place, the run is seven digits long, the
# four-digit bound rejects it, and a real citation resolves to nothing.
#
# Every Arabic character below is an explicit escape, never a glyph -- the
# digits especially, since a padded run is a row of near-identical marks.
# Name: al-bukhari (U+0627 U+0644 U+0628 U+062E U+0627 U+0631 U+064A).
_AL_BUKHARI = "\u0627\u0644\u0628\u062E\u0627\u0631\u064A"
# 0002866 in each script: zero, two, eight, six.
_ARABIC_INDIC_0002866 = "\u0660\u0660\u0660\u0662\u0668\u0666\u0666"
_EASTERN_ARABIC_0002866 = "\u06F0\u06F0\u06F0\u06F2\u06F8\u06F6\u06F6"


@pytest.mark.parametrize("padded", [_ARABIC_INDIC_0002866,
                                    _EASTERN_ARABIC_0002866])
def test_a_citation_padded_with_its_own_scripts_zero_still_resolves(padded):
    """The same citation as "Bukhari 0002866", written by someone typing in
    Arabic. It resolves to the same hadith, and the digits the reader wrote
    are preserved untouched in `raw`: the numeral SCRIPT is not part of the
    text being verified, but this module still never re-spells what was
    written.
    """
    text = f"{_AL_BUKHARI} {padded}"
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].hadith_no == "2866"
    assert padded in refs[0].raw


def test_a_run_of_non_ascii_zeros_is_not_a_reference_to_hadith_zero():
    """The other half of the same scan: zeros all the way down name nothing,
    in any script. `MIN_HADITH_NO` refuses it rather than letting "Bukhari
    ٠٠٠" resolve to a record that cannot exist.
    """
    for zero in ("\u0660", "\u06F0", "0"):
        assert parse_references(f"{_AL_BUKHARI} {zero * 3}") == []


# --- Task 9: six-collection citation grammar --------------------------------
#
# Bukhari was the only collection this grammar recognised. These tests add
# the other five: muslim, abudawud, tirmidhi, nasai, ibnmajah (the canonical
# ids used throughout, matching `_COLLECTIONS`/`_COLLECTIONS_AR`). Every
# Arabic literal below is an explicit backslash-u escape verified against
# `unicodedata.name()` in the task-9 report -- never a typed glyph -- per
# this module's character-safety rule (see `_AL_BUKHARI` above).

# Arabic fragments, independently spelled out and verified here rather than
# imported from the module under test. In order: muslim (U+0645 U+0633
# U+0644 U+0645, MEEM SEEN LAM MEEM), sahih (U+0635 U+062D U+064A U+062D,
# already used literally elsewhere in this file), abi (U+0623 U+0628 U+064A,
# ALEF WITH HAMZA ABOVE, BEH, YEH), dawud (U+062F U+0627 U+0648 U+062F, DAL
# ALEF WAW DAL), sunan (U+0633 U+0646 U+0646, SEEN NOON NOON), al-tirmidhi
# (U+0627 U+0644 U+062A U+0631 U+0645 U+0630 U+064A, ALEF LAM TEH REH MEEM
# THAL YEH), al-nasai (U+0627 U+0644 U+0646 U+0633 U+0627 U+0626 U+064A,
# ALEF LAM NOON SEEN ALEF YEH-WITH-HAMZA-ABOVE YEH), ibn (U+0627 U+0628
# U+0646, ALEF BEH NOON), majah with heh (U+0645 U+0627 U+062C U+0647, MEEM
# ALEF JEEM HEH). Arabic-Indic digit one is U+0661 (verified: ARABIC-INDIC
# DIGIT ONE).
_MUSLIM_AR = "\u0645\u0633\u0644\u0645"
_SAHIH_AR = "\u0635\u062D\u064A\u062D"
_ABI_AR = "\u0623\u0628\u064A"
_DAWUD_AR = "\u062F\u0627\u0648\u062F"
_SUNAN_AR = "\u0633\u0646\u0646"
_AL_TIRMIDHI_AR = "\u0627\u0644\u062A\u0631\u0645\u0630\u064A"
_AL_NASAI_AR = "\u0627\u0644\u0646\u0633\u0627\u0626\u064A"
_IBN_AR = "\u0627\u0628\u0646"
_MAJAH_HEH_AR = "\u0645\u0627\u062C\u0647"
_ARABIC_ONE = "\u0661"
_ABI_DAWUD_AR = f"{_ABI_AR} {_DAWUD_AR}"
_IBN_MAJAH_AR = f"{_IBN_AR} {_MAJAH_HEH_AR}"


@pytest.mark.parametrize("text,collection,hadith_no", [
    ("Muslim 1", "muslim", "1"),
    ("Sahih Muslim 1", "muslim", "1"),
    ("Sunan Abi Dawud 100", "abudawud", "100"),
    ("Abu Dawud 100", "abudawud", "100"),
    ("Tirmidhi 1", "tirmidhi", "1"),
    ("Jami at-Tirmidhi 1", "tirmidhi", "1"),
    ("An-Nasai 1", "nasai", "1"),
    ("Sunan an-Nasai 1", "nasai", "1"),
    ("Ibn Majah 1", "ibnmajah", "1"),
    ("Sunan Ibn Majah 1", "ibnmajah", "1"),
])
def test_parses_all_six_collections_in_latin_script(text, collection, hadith_no):
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].collection == collection
    assert refs[0].hadith_no == hadith_no


@pytest.mark.parametrize("text,collection", [
    (f"{_SAHIH_AR} {_MUSLIM_AR} {_ARABIC_ONE}", "muslim"),
    (f"{_MUSLIM_AR} {_ARABIC_ONE}", "muslim"),
    (f"{_ABI_DAWUD_AR} {_ARABIC_ONE}", "abudawud"),
    (f"{_SUNAN_AR} {_ABI_DAWUD_AR} {_ARABIC_ONE}", "abudawud"),
    (f"{_AL_TIRMIDHI_AR} {_ARABIC_ONE}", "tirmidhi"),
    (f"{_AL_NASAI_AR} {_ARABIC_ONE}", "nasai"),
    (f"{_IBN_MAJAH_AR} {_ARABIC_ONE}", "ibnmajah"),
])
def test_parses_all_six_collections_in_arabic_script(text, collection):
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].collection == collection
    assert refs[0].hadith_no == "1"


def test_bare_nasai_with_no_number_is_not_a_reference():
    """Same rule as bare 'Bukhari'/'Maryam': a collection name alone names a
    collection, not a text."""
    assert not [r for r in parse_references("as Nasai reports")
                if isinstance(r, HadithReference)]


def test_muslim_colon_pair_reads_as_collection_governed_not_a_verse():
    """R-A3-14: 'Muslim 2:255' is claimed by the hadith grammar (so the
    verse-numeric pass can never re-read it as surah 2, ayah 255) and then
    refused -- there is no kitab:hadith numbering map for this corpus, and
    inventing one would fabricate a resolution. Same semantics as the
    existing 'Bukhari 1:1' case above, extended to the new collections.
    """
    refs = parse_references("Muslim 2:255")
    assert not any(isinstance(r, Reference) and r.surah == 2 and r.ayah == 255
                   for r in refs)
    assert not any(isinstance(r, HadithReference) for r in refs)
    assert refs == []


@pytest.mark.parametrize("text", [
    "Muslim, Book 1, Hadith 1",
    "Sunan Abi Dawud, Book 1, Hadith 1",
    "Jami at-Tirmidhi, Book 1, Hadith 1",
    "Sunan an-Nasai, Book 1, Hadith 1",
    "Sunan Ibn Majah, Book 1, Hadith 1",
])
def test_book_relative_citations_refuse_for_the_new_collections_too(text):
    """The book-relative refusal (see the long comment above `_HADITH_CITE`)
    is not a Bukhari-specific carve-out -- it applies to every collection
    sharing this grammar, because none of them ship a book-relative numbering
    scheme in this corpus either."""
    assert parse_references(text) == []


def _tirmidhi_and_verse_refs():
    """A Tirmidhi hadith citation at 0 and a verse citation at 500 -- the
    same shape as `_mixed_refs` above, extended to a non-Bukhari collection
    so the cross-kind proximity rule (Task 6, D1) demonstrably applies to it
    too. This is the mechanism the engine's cross-kind WRONG_REFERENCE check
    depends on: an ayah quoted near "(Tirmidhi 1)" must draw that citation,
    not silence, so the engine can flag the mismatch."""
    return [HadithReference("tirmidhi", "1", "Tirmidhi 1", 0),
            Reference(112, 1, "112:1", 500)]


def test_nearest_reference_crosses_kinds_for_a_non_bukhari_collection():
    assert nearest_reference(_tirmidhi_and_verse_refs(), 10).collection == "tirmidhi"
    assert nearest_reference(_tirmidhi_and_verse_refs(), 490).surah == 112
