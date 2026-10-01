"""Regression guard for the committed corpus, data/sanad-quran.db.

Tanzil's txt-2 export prepends the Bismillah to the text of ayah 1 for every
surah except At-Tawbah -- e.g. it would store 112:1 with the Bismillah
prefixed onto "Say: He is Allah, the One" instead of just that verse,
corrupting similarity scoring for 112 of the corpus's 6,236 records --
disproportionately the short, heavily-quoted ones. The Arabic source is now
Tanzil's XML export, which models the Bismillah as separate metadata; these
tests assert that the shipped database reflects that.

See tests/ingest/test_tanzil.py and tests/ingest/test_build.py for the
equivalent checks against fixtures, independent of this committed database.
"""
from sanad.corpus import db

from tests._corpus import MATERIALIZED_DB

# The committed DB is now SOURCE-ONLY (Stage A3 Task 4): no norms, no
# record_variants, no records_fts. Every test in this file reads derived data,
# so it reads the shared, session-cached materialized DB (Task 5) rather than
# materializing its own copy inline.
DB_PATH = MATERIALIZED_DB

# 112:1, "Say: He is Allah, the One" -- built from explicit codepoints,
# verified against the built database, rather than a literal in the source
# file. Tanzil's Uthmani text orders the combining marks on the word "Allah"
# here as SHADDA (U+0651) then FATHA (U+064E); a hand-typed or copy-pasted
# literal with the exact same visual rendering can silently end up in the
# opposite, equally-legible order (FATHA then SHADDA) depending on input
# method or editor/terminal normalization, and would then fail this
# exact-equality check for a reason that has nothing to do with the
# Bismillah bug this test exists to guard against.
_QURAN_112_1_CODEPOINTS = (
    0x0642, 0x064F, 0x0644, 0x0652, 0x0020,  # first word
    0x0647, 0x064F, 0x0648, 0x064E, 0x0020,  # second word
    0x0671, 0x0644, 0x0644, 0x0651, 0x064E, 0x0647, 0x064F, 0x0020,  # "Allah"
    0x0623, 0x064E, 0x062D, 0x064E, 0x062F, 0x064C,  # last word
)
_QURAN_112_1 = "".join(chr(cp) for cp in _QURAN_112_1_CODEPOINTS)


def test_bismillah_is_not_prepended_to_verse_text():
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "quran:112:1").text_ar == _QURAN_112_1


def test_bismillah_stored_separately_where_it_applies():
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "quran:112:1").bismillah is not None


def test_al_fatiha_1_1_is_the_bismillah_itself():
    conn = db.connect(DB_PATH)
    r = db.get_record(conn, "quran:1:1")
    assert r.text_ar.startswith(chr(0x0628) + chr(0x0650) + chr(0x0633) + chr(0x0652)
                                 + chr(0x0645) + chr(0x0650))  # "Bismi..."
    assert r.bismillah is None


def test_at_tawbah_has_no_bismillah():
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "quran:9:1").bismillah is None


def test_exactly_112_records_carry_a_bismillah():
    conn = db.connect(DB_PATH)
    n = conn.execute("SELECT count(*) FROM records WHERE bismillah IS NOT NULL").fetchone()[0]
    assert n == 112  # 114 surahs, minus Al-Fatiha where it is verse 1, minus At-Tawbah


# --- fix round 3: an editorial pointer is not a verifiable quotation -------
#
# These run against the SHIPPED database, because the hazard is what the
# product answers, not what the build produces. Every Arabic literal is built
# from codepoints for the reason given at the top of this file.

_BI_HADHA = "".join(chr(c) for c in (0x0628, 0x0647, 0x0630, 0x0627))   # بهذا
_MITHLAHU = "".join(chr(c) for c in (0x0645, 0x062B, 0x0644, 0x0647))   # مثله
_NAHWAHU = "".join(chr(c) for c in (0x0646, 0x062D, 0x0648, 0x0647))    # نحوه
# "al-harb khud'a" -- war is deceit. Sahih al-Bukhari 2866, 10 characters,
# genuine, and shorter than three of the seventeen excluded records.
_AL_HARB_KHUDA = "".join(chr(c) for c in (
    0x0627, 0x0644, 0x062D, 0x0631, 0x0628, 0x0020, 0x062E, 0x062F, 0x0639, 0x0629))
# Surah Ta-Ha, ayah 1 -- two characters, the shortest record in the corpus.
_TA_HA = "".join(chr(c) for c in (0x0637, 0x0647))

_UNSCORABLE_IDS = tuple(f"hadith:bukhari:{n}" for n in (
    "127", "237", "335", "394", "549", "557", "1379", "1915", "2483", "3457",
    "3750", "3777", "3801", "3957", "4540", "5454", "5837",
))


def test_an_editorial_pointer_is_not_verified_as_a_hadith():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    for phrase in (_BI_HADHA, _MITHLAHU, _NAHWAHU):
        matches = verify_spans(conn, f"«{phrase}»")
        assert len(matches) == 1
        assert matches[0].verdict is Verdict.NOT_FOUND, phrase
        assert matches[0].record is None, phrase


def test_a_famous_short_hadith_still_verifies_exactly():
    """"al-harb khud'a" is printed, byte-identically, seven times across five
    collections (Bukhari 2866; Muslim 1739, 1740; Abu Dawud 2636; Tirmidhi
    1675; Task 15 adds Ibn Majah 2833, 2834). Task 12 added the fourth copy,
    and with it the FIRST case anywhere in this corpus of the tie-break's
    "lowest id wins" rule choosing a non-Bukhari winner: the full id
    "hadith:abudawud:2636" sorts before "hadith:bukhari:2866"
    lexicographically ("a" < "b"), so Abu Dawud is the disclosed match.
    Tirmidhi's fifth copy does not change the winner -- "hadith:tirmidhi:..."
    sorts after every other collection's own id ("t" is the latest letter)
    -- it only grows `also_at` by one, and Ibn Majah's own two copies do the
    same: "hadith:ibnmajah:..." sorts between "hadith:bukhari:..." and
    "hadith:muslim:...", so both land in `also_at`'s middle, not at either
    end. Verified, not assumed -- read directly from `verify_spans`'s own
    tie-break output.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_AL_HARB_KHUDA}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    assert matches[0].record.id == "hadith:abudawud:2636"
    assert matches[0].also_at == [
        "hadith:bukhari:2866", "hadith:ibnmajah:2833", "hadith:ibnmajah:2834",
        "hadith:muslim:1739", "hadith:muslim:1740", "hadith:tirmidhi:1675",
    ]


def test_the_shortest_ayah_still_verifies_exactly():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_TA_HA}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    assert matches[0].record.id == "quran:20:1"


def test_every_unscorable_record_still_resolves_by_reference():
    """Sahih al-Bukhari 1379 is a real hadith and must still be reachable.

    This is the lookup behind GET /records/{id}: excluded from scoring, still
    in the corpus, still citable, still displayable with its full text and the
    further narrations the edition appends.
    """
    conn = db.connect(DB_PATH)
    for record_id in _UNSCORABLE_IDS:
        rec = db.get_record(conn, record_id)
        assert rec is not None, record_id
        assert rec.text_ar.strip(), record_id
        assert rec.reference_display, record_id


# --- fix round 5: both representations, against the SHIPPED database -------
#
# The Arabic here is read out of the corpus rather than typed: this project
# has shipped eleven defects from Arabic silently altered in transit, one of
# them inside the test written to catch them. The record ids and the verdicts
# are the assertions; the text is data.

_ISRA_MIRAJ = ("hadith:bukhari:342", "hadith:bukhari:3164")


def test_the_isra_miraj_verifies_both_as_matn_and_as_printed():
    """342 and 3164 were cut in the middle of one continuous narration.

    The rule fired on a sub-narrator's chain aside, but what follows is the
    same story going on in the Prophet's first person -- the fifty prayers,
    the returns to Musa, "they are five and they are fifty", Sidrat
    al-Muntaha. ~700 characters of Sahih al-Bukhari each, and quoting the
    whole hadith as the edition prints it returned NOT_FOUND 0.64.

    Both directions are asserted for both records. The cut is still there and
    is still arguably in the wrong place; what changed is that it no longer
    costs a verification either way.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    for record_id in _ISRA_MIRAJ:
        rec = db.get_record(conn, record_id)
        assert rec.addenda_ar, f"{record_id} must still be a cut record"
        for quoted in (rec.text_ar, rec.text_ar + " " + rec.addenda_ar):
            matches = verify_spans(conn, f"«{quoted}»")
            assert len(matches) == 1, record_id
            assert matches[0].verdict is Verdict.EXACT, (record_id, len(quoted))
            assert matches[0].record.id == record_id, (record_id, len(quoted))


def test_the_full_printed_text_of_every_cut_record_verifies():
    """The corpus-wide form of the test above: all 1,335 of them.

    A sample cannot show this. The defect it guards against is one record
    somewhere in the corpus whose full text is unreachable, which is exactly
    what a sample misses.

    "Reaches the record" allows `also_at`: a handful of Bukhari records are
    printed with byte-identical matns (383 and 774, "the Prophet used to
    spread his arms when he prayed until the whiteness of his armpits
    showed"), and the engine's long-standing rule for tied text is to select
    the lowest id and disclose the rest. That is the same answer for a tie
    between two records as for a tie between two representations, and the
    quotation is verified either way.

    Task 11 (Sahih Muslim): 391 + 120 = 511. Muslim's 120 scorable cut records
    are its own -- none of its NEVER_CUT/UNSCORABLE work reverses or
    introduces a cut, it only judges primaries `_split_secondary` already cut,
    per the audit's own scope note in audit_lists.py.

    Task 12 (Sunan Abi Dawud), first build: 391 + 120 + 68 = 579. Abu Dawud
    contributed 69 cut records total (`addenda_ar IS NOT NULL`), one of which --
    hadith:abudawud:2225, the `_EDITORIAL_DISCUSSION` record -- was also on
    `UNSCORABLE["abudawud"]` and so was excluded from this scorable-only count,
    leaving 68.

    Fix round 1 (R-A3-18): 1,335. The compiler-commentary split
    (`_split_compiler_commentary`) cuts Abu Dawud's own "qala Abu Dawud ..."
    remarks away from primaries they were fused with -- 806 records carry the
    marker, most gaining a fresh cut -- and the cut-override table
    (`CUT_OVERRIDE["abudawud"]`) corrects 11 more `_split_secondary`
    boundaries. Of the resulting cut records, 36 have a post-split primary
    that is itself editorial apparatus (fix round 1's addition to
    `UNSCORABLE["abudawud"]`) and 2 more (2225, 2331) were already on that
    list before this round, so this scorable-only count excludes them.
    Measured directly from the fixed build, not derived by hand from the
    individual deltas above: the population sizes overlap (13 of the 806
    marker records were already cut by `_split_secondary`; some of the 36
    newly-excluded primaries are among the 806) in ways not worth re-deriving
    on top of a number the build itself reports.

    Fix round 2 (R-A3-22): 1,344. `_ABUDAWUD_COMMENTARY_NEAR` (the one-token-
    gap fallback) and `_split_lului_commentary` (Abu Ali al-Lu'lu'i's own
    voice, the same defect class, a different speaker) together add 9 more
    scorable cut records: `hadith:abudawud:4129`, `5239`, `911`, `1096`,
    `1391`, `3220`, `3437`, `4924`, `5190`. 1,335 + 9 = 1,344.

    Fix round 3 (R-A3-23): 1,346. `_split_heard_commentary` ("sami'tu" +
    ACCUSATIVE kunya, the grammatical case the marker above never covered)
    adds 2 more scorable cut records: `hadith:abudawud:1234`, `1854`.
    1,344 + 2 = 1,346.

    Task 13 (Jami at-Tirmidhi): 5,037. R-A3-19 generalises the compiler-
    commentary split into a per-collection table and adds Tirmidhi's own
    marker set -- almost every hadith in this collection carries Abu Isa's
    own grading remark ("hadha hadith hasan sahih", "wa fi al-bab 'an ...")
    immediately after the matn, so the great majority of the collection is
    cut: 3,691 scorable Tirmidhi records carry an addendum.
    1,346 + 3,691 = 5,037.

    Task 14 (Sunan an-Nasai): 5,305. R-A3-20 adds al-Nasai's own kunya
    marker plus `_NASAI_FORMULA` (the "khalafahu"/"hadha hadith"/"hadha
    khata'"/"wa-l-sawab" family): 274 Nasai records carry an addendum, 6 of
    which are ALSO on `UNSCORABLE["nasai"]` (648, 1786, 4588, 5123, 5194,
    5695 -- the kunya marker fires on a record whose primary matn the
    Step 4 pointer audit separately excludes), leaving 268 scorable.
    5,037 + 268 = 5,305.

    Fix round 1 (R-A3-25): 5,358. `_NASAI_FORMULA`'s comparative-isnad
    family extension (see `test_nasai_record_count_and_scorability`'s
    fix-round note) adds 60 more cut Nasai records; 7 of those are ALSO on
    `UNSCORABLE["nasai"]` (2232, 2295, 2412, 3492, 4098, 4360, 4787),
    leaving 53 more scorable-cut records. 5,305 + 53 = 5,358. Tirmidhi's
    46/566 fix (also this round, see
    `test_tirmidhi_record_count_and_scorability`'s note) does not change
    this count: both are, and remain, `UNSCORABLE["tirmidhi"]`.

    Task 15 (Sunan Ibn Majah): 5,618. Its 166 cut records are all scorable --
    none is also on `UNSCORABLE["ibnmajah"]` -- so every one adds to this
    count. 5,452 + 166 = 5,618.

    Task 16 A1 (Bukhari + Muslim commentary split): 5,719, +101. 81 Bukhari
    newly-cut records are all scorable. Muslim gains 25 newly-cut records, but
    5 of them are the split-exposed pointer/deferral heads that joined
    `UNSCORABLE["muslim"]`, so only 20 are scorable: 81 + 20 = 101. Every one
    of the 101 verifies EXACT in both directions -- matn alone and matn +
    addendum -- which is the whole point of the split: the genuine matn, once
    fused with al-Bukhari's or Muslim's own commentary, is now reachable.

    Task 16 A2 (pointer/deferral sweep): 5,718, -1. muslim:1669-6, previously a
    scorable cut record, is a pure deferral and moves to UNSCORABLE (its A1
    addendum stays as a "full" variant); the other 24 A2 exclusions had no
    addendum and never counted here.

    Task 16 A2 fix-round (back-reference and omission shapes): 5,710, -8. Of the
    151 records newly moved to UNSCORABLE, 8 previously carried an addendum and
    so counted here as scorable-cut; they drop out (their addendum stays as a
    "full" variant). The other 143 had no addendum and never counted here.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, text_ar, addenda_ar FROM records"
        " WHERE addenda_ar IS NOT NULL AND unscorable_reason IS NULL").fetchall()
    assert len(rows) == 5699  # A2 fix-round: -8; A2 round 3: -7; A2 round 4: -2 (tirmidhi:595, 1096); A2 round 5: -2 (abudawud:1176, muslim:2359-6 -- newly-unscorable records that carried an addendum)
    failures = []
    for row in rows:
        for quoted in (row["text_ar"], row["text_ar"] + " " + row["addenda_ar"]):
            matches = verify_spans(conn, f"«{quoted}»")
            reached = (len(matches) == 1
                       and matches[0].verdict is Verdict.EXACT
                       and matches[0].record is not None
                       and row["id"] in [matches[0].record.id] + matches[0].also_at)
            if not reached:
                failures.append((row["id"], len(quoted)))
    assert failures == []


def test_a_narrative_opener_is_no_longer_a_verifiable_quotation():
    """The two openers the cut left behind, both of which returned EXACT 1.0.

    "The Prophet passed by a man" (632) and "The Prophet had a she-camel"
    (6136) name no act, ruling or speech; the narration each introduces is
    entirely in the appended second chain. They are everyday sentences of
    hadith literature, and answering one with a confident Bukhari citation
    fabricates a reference out of a commonplace.

    Each stub is read out of the pre-round-5 cut point rather than typed:
    the assertion is that the prefix of the record's own text ending there
    no longer matches anything. These two are judged by hand, by meaning, on
    the `_NEVER_CUT` audit list -- no length rule reaches them, and round 5's
    attempt at one is gone (see the test below).
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    for record_id, cut_at in (("hadith:bukhari:632", 32),
                              ("hadith:bukhari:6136", 33)):
        rec = db.get_record(conn, record_id)
        stub = rec.text_ar[:cut_at]
        assert rec.addenda_ar is None, f"{record_id} must no longer be cut"
        matches = verify_spans(conn, f"«{stub}»")
        assert len(matches) == 1, record_id
        assert matches[0].verdict is Verdict.NOT_FOUND, (record_id, stub)
        assert matches[0].record is None, record_id
        # ... and the hadith itself is still perfectly verifiable.
        whole = verify_spans(conn, f"«{rec.text_ar}»")
        assert whole[0].verdict is Verdict.EXACT, record_id
        assert whole[0].record.id == record_id, record_id


def test_a_short_matn_verifies_on_its_own_and_as_printed():
    """The nine records a length floor would have refused to cut.

    Round 5 briefly carried a 32-character minimum primary. It made these
    nine unverifiable as standalone quotations -- "la tuki fa-yuka 'alayki"
    (1366) is eighteen characters and a complete saying of the Prophet, and
    it is exactly the kind of short, memorable wording a person quotes. That
    is the Critical this round exists to fix, so the floor was removed and
    the trade this test documents is the one that replaced it: BOTH
    directions verify for all nine.

    The two records the floor called hazards (2390, 6949) are here too. Both
    were read in the raw source: each is an abridged matn the edition itself
    prints -- 2390's own addendum ends "Shu'ba abridged it" -- followed by a
    fresh full chain. A quotation of one is a real quotation of Bukhari.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    for hadith_no in ("1366", "2301", "2390", "2405", "3179",
                      "5526", "5600", "6205", "6949"):
        rec = db.get_record(conn, f"hadith:bukhari:{hadith_no}")
        assert rec.addenda_ar, f"{hadith_no} must be cut"
        assert len(rec.text_ar) <= 25, hadith_no
        for quoted in (rec.text_ar, rec.text_ar + " " + rec.addenda_ar):
            m = verify_spans(conn, f"«{quoted}»")
            assert len(m) == 1, (hadith_no, len(quoted))
            assert m[0].verdict is Verdict.EXACT, (hadith_no, len(quoted))
            assert rec.id in [m[0].record.id] + list(m[0].also_at), \
                (hadith_no, len(quoted))


def test_no_record_appears_twice_in_its_own_match():
    """Over every cut record, in both directions: a record indexed under two
    representations must never list itself in `also_at`."""
    from sanad.verify.engine import verify_spans
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, text_ar, addenda_ar FROM records"
        " WHERE addenda_ar IS NOT NULL AND unscorable_reason IS NULL").fetchall()
    for row in rows:
        for quoted in (row["text_ar"], row["text_ar"] + " " + row["addenda_ar"]):
            m = verify_spans(conn, f"«{quoted}»")[0]
            assert m.record.id not in m.also_at, row["id"]
            assert len(m.also_at) == len(set(m.also_at)), row["id"]


def test_the_index_holds_one_row_per_scorable_representation():
    """26,598 = 25,222 scorable records + 1,376 full-text representations.

    Asserted as three numbers that have to add up, not as one total: a record
    dropping out of the index while a variant row appears would keep the
    total right.

    Task 11 (Sahih Muslim): these numbers moved from (13348, 392, 13740) when
    Muslim joined Bukhari and the Qur'an in the same committed database.
    Muslim contributes 7,460 hadith records, of which 6,739 are scorable and
    122 carry a second ("full", cut) representation -- see
    test_muslim_record_count_and_scorability below for the per-collection
    breakdown these totals are built from.

    Task 12 (Sunan Abi Dawud), first build, moved these to (25258, 583,
    25841). Abu Dawud contributed 5,274 hadith records, of which 5,171 were
    scorable and 69 carried a second ("full", cut) representation.

    Fix round 1 (R-A3-18) moved these to (25222, 1376, 26598). The
    compiler-commentary split and the cut-override table together change
    which Abu Dawud primaries are scorable (5,171 -> 5,135, see
    test_abudawud_record_count_and_scorability below) and which records carry
    a second representation (69 -> 1,376 corpus-wide, since almost every one
    of the 806 marker records gains an addendum where most had none before).

    Fix round 2 (R-A3-22) moves these to (25222, 1385, 26607): scorable is
    unchanged (no record's scorability changes, only where 9 more primaries
    are cut), variants gains the same 9 records as
    `test_the_full_printed_text_of_every_cut_record_verifies` above.

    Fix round 3 (R-A3-23) moves these to (25222, 1387, 26609): scorable is
    unchanged again, variants gains 2 more records (1234, 1854).

    Task 13 (Jami at-Tirmidhi) moves these to (29118, 5142, 34260). Tirmidhi
    contributes 3,976 hadith records, of which 3,896 are scorable
    (25,222 + 3,896 = 29,118) and 3,755 carry a second ("full", cut)
    representation, of which 3,691 are scorable-primary cuts and 64 are
    excluded-primary cuts (both counted here; see
    test_every_other_excluded_record_is_excluded_whole for the excluded
    side): 1,387 + 3,755 = 5,142.

    Task 14 (Sunan an-Nasai) moves these to (34834, 5416, 40250). Nasai
    contributes 5,769 hadith records, of which 5,716 are scorable
    (29,118 + 5,716 = 34,834) and 274 carry a second ("full", cut)
    representation, of which 268 are scorable-primary cuts and 6 are
    excluded-primary cuts: 5,142 + 274 = 5,416.

    Fix round 1 (R-A3-25) moves these to (34832, 5478, 40310). Two records
    (1738, 3492) move from scorable to `UNSCORABLE["nasai"]` -- the
    comparative-isnad family extension now cuts a "mursal"/"nحوه" pointer
    tag off their tail that used to keep them looking like short-but-
    complete matns -- so Nasai's scorable count drops 5,716 -> 5,714
    (29,118 + 5,714 = 34,832). Nasai's own cut count rises 274 -> 334 (60
    more records gain a second representation, covering the rest of the
    comparative-isnad family: `وافقه`/`تابعه`/`أرسله`/`رفعه`/`وقفه`/
    `أوقفه`/`أسنده`/bare `مرسل`/`موقوفا`/`هذا الصواب`/`لم يسمع`/`لم
    يرفعه`). This also moved Tirmidhi's own cut count 3,755 -> 3,757 (see
    `test_tirmidhi_record_count_and_scorability`'s fix-round note: a
    `_split_compiler_commentary` bug this round's own new bare-tag markers
    exposed, not a Nasai-specific change), so the cumulative baseline this
    task's own delta is measured against is 5,144, not 5,142: 5,144 + 334 =
    5,478.

    Task 15 (Sunan Ibn Majah) moves these to (39170, 5740, 44910). Ibn Majah
    contributes 4,341 hadith records, of which 4,340 are scorable
    (34,830 + 4,340 = 39,170) and 166 carry a second ("full", cut)
    representation, all 166 of them scorable-primary cuts (0 excluded-primary
    -- `UNSCORABLE["ibnmajah"]`'s one entry, 413, was never cut in the first
    place): 5,574 + 166 = 5,740. Indexed rises by exactly scorable-primaries
    + variants (4,340 + 166 = 4,506): 40,404 + 4,506 = 44,910.
    """
    conn = db.connect(DB_PATH)
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE unscorable_reason IS NULL").fetchone()[0]
    variants = conn.execute("SELECT count(*) FROM record_variants").fetchone()[0]
    indexed = conn.execute("SELECT count(*) FROM records_fts").fetchone()[0]
    # Task 15: scorable +4340, variants +166 (all scorable-primary cuts),
    # indexed +4506 (4340 new primaries + 166 new variant rows).
    # Task 16 A1: scorable -5 (5 Muslim primaries the commentary split exposed
    # as pointers/deferrals, now UNSCORABLE), variants +106 (81 Bukhari + 25
    # Muslim newly-cut records), indexed +101 (+106 variant rows, -5 primaries).
    # Task 16 A2 (pointer/deferral sweep): scorable -25 (1 Bukhari + 24 Muslim
    # deferrals now UNSCORABLE), variants unchanged (24 have no addendum;
    # muslim:1669-6 already had one and keeps its "full" variant), indexed -25
    # (each loses only its primary row).
    # Task 16 A2 fix-round (back-reference/omission shapes): scorable -151 (132
    # Muslim + 6 Abu Dawud + 13 Tirmidhi back-references/omission/isnad-scaffold
    # records now UNSCORABLE), variants unchanged (those that carry an addendum
    # keep their "full" variant), indexed -151 (each loses only its primary row).
    # Task 16 pre-Part-B cleanup, C0 (A2 residue): scorable -5 (5 more Muslim
    # back-reference singletons the fix round's grouping missed, none carrying
    # an addendum), variants unchanged, indexed -5 (each loses only its
    # primary row).
    # A2 round 3 (position-independent whole-string sweep): scorable -50,
    # indexed -50 (this tuple pin was NOT updated for round 3 when it landed --
    # it skipped from C0's 38,989 straight to 38,984 while the two reps pins
    # below correctly recorded the -50; re-measured here against a fresh build:
    # correct post-round-3 value is (38934, 5846, 44780)).
    # A2 round 4 (editorial omission/comparison sweep): scorable -46, indexed
    # -46 (46 pure-apparatus primaries now UNSCORABLE, none carrying an
    # addendum, so variants unchanged): (38888, 5846, 44734).
    # A2 round 5 (vocabulary-free content-mass net): scorable -28, indexed -28
    # (28 content-mass pointers now UNSCORABLE). variants unchanged: the two
    # that carry an addendum (abudawud:1176, muslim:2359-6) keep their "full"
    # variant row, and only the 28 primary FTS rows leave: (38860, 5846, 44706).
    assert (scorable, variants, indexed) == (38860, 5846, 44706)


# --- C1: nothing scorable as a hadith is wholly a Qur'anic quotation --------


def _quran_blobs(conn) -> list[str]:
    """Each surah as one space-joined standard-tier string, space-padded.

    Per surah, because that is what "a Qur'anic quotation" means: a reader
    can quote consecutive ayat, and cannot quote across the end of one surah
    into the start of another. Space-padded so a match falls on token
    boundaries. This is deliberately written out again here rather than
    imported from the ingest package, so the test and the build-time
    invariant are two independent statements of the same rule -- a mistake in
    one does not silently license the other.
    """
    by_surah: dict[int, list[str]] = {}
    for row in conn.execute("SELECT surah, norm_standard FROM records"
                            " WHERE kind = 'ayah' ORDER BY surah, ayah"):
        by_surah.setdefault(row["surah"], []).append(row["norm_standard"])
    return [f" {' '.join(v)} " for v in by_surah.values()]


def test_no_scorable_hadith_representation_is_wholly_quranic():
    """Every scorable representation, swept -- not the one record that failed.

    `hadith:bukhari:4575`'s cut left a primary matn that was verbatim Qur'an
    53:9-10, so those two verses returned EXACT / Sahih al-Bukhari 4575, and
    the same verses cited "(53:9)" returned WRONG_REFERENCE: scripture
    attributed to a hadith collection, and a correctly citing reader told they
    had misattributed it.

    The existing cross-kind sweep could not see it. It compared ayah rows
    against hadith rows for an exact tie, and 4575's matn was two ayat JOINED,
    which no single ayah row can equal. Asserting the one record would have
    left the class exactly as open; the sweep is the assertion.

    Measured here and independently by the reviewer: exactly one of the 7,504
    Bukhari-only scorable representations was wholly Qur'anic, and it is the
    record now on the do-not-cut audit. The expected answer is zero.

    Task 11 (Sahih Muslim): the same sweep over 14,365 representations
    (Bukhari's 7,504 plus Muslim's 6,861) is still zero, but only after
    `UNSCORABLE["muslim"]` excludes the 144 pointer/deferral records this
    guard flagged on the first measured build -- "bi-mithlihi", "mithlahu",
    "bi-hadha al-hadith" and seven other stock cross-reference phrases that
    are also, by coincidence of brevity, verbatim substrings of the Qur'an.
    None of them are Qur'an quotations; see audit_lists.py's "muslim" section
    and the task-11 report for the full accounting.

    Task 12 (Sunan Abi Dawud), first build: the sweep covered 19,605
    representations (14,365 plus Abu Dawud's 5,240) and was still zero, after
    `UNSCORABLE["abudawud"]` excluded the 23 records
    `_reject_wholly_quranic_representations` flagged on the first measured
    build (22 false-positive short editorial pointers plus the one genuine
    wholly-Qur'anic report, hadith:abudawud:3979 -- see audit_lists.py's
    "abudawud" section and the task-12 report).

    Fix round 1 (R-A3-18): the compiler-commentary split changes both terms --
    5,135 scorable Abu Dawud primaries (18,986 total scorable hadith
    corpus-wide) plus 1,376 full-text representations corpus-wide, 20,362
    total -- and materialize.py's own gate caught a second genuine
    wholly-Qur'anic report this round surfaced, hadith:abudawud:3980 (see
    audit_lists.py's `_QURANIC_QUOTE` group). The sweep is still zero.

    Fix round 2 (R-A3-22) moves the representation count to 20,371 (1,385
    full-text representations corpus-wide instead of 1,376; scorable primary
    count unchanged). The sweep is still zero: none of the 9 newly-cut
    primaries or their newly-added full-text representations is wholly
    Qur'anic -- every one is either a well-known Prophetic saying (4129,
    5239) or a narrator's/transmitter's remark, neither of which the sweep
    would expect to find inside a surah.

    Fix round 3 (R-A3-23) moves the representation count to 20,373 (1,387
    full-text representations corpus-wide instead of 1,385; scorable primary
    count unchanged again -- 1234 and 1854 were already scorable). The sweep
    is still zero: 'Ali's travel-prayer routine and the Prophet's "it is
    only sea game" ruling are ordinary hadith wording, not Qur'an.

    Task 13 (Jami at-Tirmidhi) moves the representation count to 28,024
    (22,882 scorable hadith primaries corpus-wide plus 5,142 full-text
    representations). Unlike every round above, the sweep did NOT stay zero
    on the first measured build: hadith:tirmidhi:2929 is a tafsir report
    whose isnad says the Prophet "qara'a" (recited) and whose entire matn is
    verbatim Qur'an 5:45's own retaliation-law clause -- exactly the
    `sanad-hadith-quranic-matn-hazard` class, missed by the ≤40-character
    hand-audit because the same wording reads as plausible reported speech in
    isolation. It joined `UNSCORABLE["tirmidhi"]`'s `_QURANIC_QUOTE` group
    alongside 2934, and the sweep is zero again.

    Task 14 (Sunan an-Nasai) moves the representation count to 34,014
    (28,598 scorable hadith primaries corpus-wide plus 5,416 full-text
    representations). The sweep is zero on the first measured build: al-
    Mujtaba's own tafsir/ahkam sections contain no matn that is wholly a
    Qur'an quotation, and none of the 53 `UNSCORABLE["nasai"]` records
    needed re-classifying against this guard.

    Fix round 1 (R-A3-25) moves the representation count to 34,074 (see
    `test_the_index_holds_one_row_per_scorable_representation`'s fix-round
    note for the full breakdown: Nasai's scorable primaries drop by 2,
    variants rise by 62 across Nasai and Tirmidhi). The sweep is still
    zero: none of the newly-covered comparative-isnad-family cuts, nor
    the two newly-unscorable pointer records, is wholly Qur'anic.

    Fix round 2 (R-A3-27) moves the representation count to 34,168 (Nasai's
    scorable primaries drop by another 2 -- 207-2, 353 to `UNSCORABLE`'s
    `_CHAIN_LEAK` group -- and variants rise by 96 across the six-shape
    sweep). The sweep is still zero: none of the newly-covered "مختصر"/"لم
    يذكر"/"رواه"/"روى"/"اللفظ ل"/"اختلف على"/"غير محفوظ" cuts is wholly
    Qur'anic.

    Task 15 (Sunan Ibn Majah) moves the representation count to 38,674:
    32,934 scorable hadith primaries corpus-wide (39,170 total scorable
    records minus the Qur'an's own 6,236 ayat -- see
    `test_the_index_holds_one_row_per_scorable_representation` for the full
    scorable/variants breakdown) plus 5,740 full-text representations. The
    sweep is still zero on the first measured build:
    `build._reject_wholly_quranic_representations` (the same build-time gate
    this sweep independently re-implements) raised nothing while
    materializing Ibn Majah, and this independent, test-owned sweep confirms
    it -- none of its 4,340 scorable primaries or 166 full-text variants is
    wholly a Qur'an quotation.

    Task 16 A1 (Bukhari + Muslim commentary split) moves the representation
    count to 38,775 (+101: -5 Muslim primaries now UNSCORABLE, +106 full-text
    variants, 81 Bukhari + 25 Muslim). The sweep is still zero -- and this is
    the guard the whole split exists to keep honest. The Muslim split exposed
    five short pointer/deferral heads ("bi-mithlihi" and kin) whose norm
    collides with an ayah representation; each is on `UNSCORABLE["muslim"]`
    (see audit_lists.py) so it never reaches this sweep, and no Bukhari or
    Muslim primary or variant that DOES reach it is wholly Qur'anic.

    Task 16 A2 (pointer/deferral sweep) moves the representation count to
    38,750 (-25 scorable hadith primaries now UNSCORABLE; variants unchanged).
    The sweep is still zero.

    Task 16 A2 fix-round (back-reference and omission shapes) moves it to
    38,599 (-151 scorable hadith primaries now UNSCORABLE across Muslim (132),
    Abu Dawud (6) and Tirmidhi (13); variants unchanged). The sweep is still
    zero: none of the 151 newly-unscorable pointer/back-reference/omission
    records was itself wholly Qur'anic, and none that still reaches this sweep
    is either.

    Task 16 pre-Part-B cleanup, C0 (A2 residue) moves it to 38,594 (-5 more
    Muslim primaries now UNSCORABLE; variants unchanged). The sweep is still
    zero: none of the 5 is itself wholly Qur'anic.

    Task 16 A2 round 3 (position-independent whole-string sweep) moves it to
    38,544 (-50 scorable hadith primaries now UNSCORABLE; variants unchanged).
    The sweep is still zero: none of the 50 is itself wholly Qur'anic (997-6's
    basmala sits inside a chain-meta pointer, not a standalone ayah), and none
    that still reaches this sweep is either.
    """
    conn = db.connect(DB_PATH)
    blobs = _quran_blobs(conn)
    assert len(blobs) == 114, "the Qur'an is not in this database"
    reps = [(r["id"], "primary", r["norm_standard"]) for r in conn.execute(
        "SELECT id, norm_standard FROM records"
        " WHERE kind = 'hadith' AND unscorable_reason IS NULL")]
    reps += [(r["record_id"], r["variant"], r["norm_standard"]) for r in conn.execute(
        "SELECT v.record_id, v.variant, v.norm_standard FROM record_variants v"
        " JOIN records r ON r.id = v.record_id")]
    # Task 16 A2 round 4 (editorial omission/comparison sweep) moved it to
    # 38,498 (-46 scorable hadith primaries now UNSCORABLE across Muslim (38),
    # Abu Dawud (5), Tirmidhi (2), Nasai (1); variants unchanged). A2 round 5
    # (vocabulary-free content-mass net) moves it to 38,470 (-28 more scorable
    # primaries now UNSCORABLE across Muslim (19), Abu Dawud (4), Bukhari (4),
    # Ibn Majah (1); variants unchanged -- the two pointers that carry an
    # addendum, abudawud:1176 and muslim:2359-6, keep their "full" variant row
    # in record_variants, which this count includes regardless of whether the
    # primary is scorable, so only the 28 primary reps drop). The sweep is still
    # zero: none of the 74 pure-apparatus records is wholly Qur'anic.
    assert len(reps) == 38470, "the sweep stopped covering what it was written for"
    offenders = [(rid, variant) for rid, variant, norm in reps
                 if norm.strip() and any(f" {norm} " in b for b in blobs)]
    assert offenders == []


def test_the_sweep_can_actually_find_something():
    """The sweep above asserts an empty list, which is the shape of assertion
    that passes when its own machinery is broken. The same containment test,
    pointed at a string that IS wholly Qur'anic -- Qur'an 53:9 and 53:10
    joined, read out of the database rather than typed -- must find it.
    """
    conn = db.connect(DB_PATH)
    blobs = _quran_blobs(conn)
    joined = " ".join(
        r["norm_standard"] for r in conn.execute(
            "SELECT norm_standard FROM records WHERE id IN"
            " ('quran:53:9', 'quran:53:10') ORDER BY ayah"))
    assert any(f" {joined} " in b for b in blobs)


def test_the_corrected_record_is_still_verifiable_as_printed():
    """4575 is uncut, so its one representation is the whole printed hadith --
    the ayah and the narration about it -- and that still verifies as the
    hadith it is. The fix removes a false claim; it must not remove a record.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:bukhari:4575")
    assert rec.addenda_ar is None
    assert rec.unscorable_reason is None
    m = verify_spans(conn, f"«{rec.text_ar}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    assert m[0].record.id == "hadith:bukhari:4575"


def test_the_ayat_that_were_answered_as_a_hadith_are_not():
    """The reader's side of the same fact, at both tiers that can verify.

    Qur'an 53:9-10 quoted as the corpus stores them (diacritics and all), and
    the same two verses with their diacritics stripped -- which is exactly the
    undiacritized form the edition printed and the form the false EXACT came
    back on. Neither may resolve to a hadith, and neither may be called a
    wrong reference when cited as the Qur'an.
    """
    from sanad.arabic.normalize import normalize
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rows = [db.get_record(conn, f"quran:53:{a}") for a in (9, 10)]
    verbatim = " ".join(r.text_ar for r in rows)
    undiacritized = " ".join(normalize(r.text_ar, "standard") for r in rows)
    for quoted in (verbatim, undiacritized):
        for text in (f"«{quoted}»", f"«{quoted}» (53:9)"):
            for m in verify_spans(conn, text):
                assert m.record is None or m.record.kind != "hadith", text
                assert m.verdict is not Verdict.WRONG_REFERENCE, text


# --- I1: unscorability is judged, and applied, per representation -----------


def test_the_longest_addendum_in_the_edition_is_reachable():
    """Hadith 237's full printed text, against the shipped corpus.

    237 is the only record that is both on the unscorable audit list and
    carries an addendum, and its addendum is the longest in this edition at
    869 characters -- the complete narration of the camel entrails placed on
    the Prophet's back at the Ka'ba. The audit ruled on its 40-character
    primary, a "bayna" clause ending at the chain-transfer mark, and that
    ruling was applied to both representations: quoting the hadith as the
    edition prints it returned NOT_FOUND at 0.393.

    The earlier justification for excluding it -- "237's story is at 3641" --
    is true of the story and false of the text. 3641 narrates the same event
    in different words with a different chain, and Sanad verifies wording.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:bukhari:237")
    assert rec.unscorable_reason and len(rec.addenda_ar) == 869
    whole = rec.text_ar + " " + rec.addenda_ar
    m = verify_spans(conn, f"«{whole}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    assert m[0].record.id == "hadith:bukhari:237"


def test_the_excluded_primary_of_that_record_is_still_excluded():
    """The half of the ruling that was right stays right: the chain-transfer
    fragment on its own is apparatus, and answering it with a Bukhari
    citation would be the `_UNSCORABLE` defect all over again."""
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:bukhari:237")
    m = verify_spans(conn, f"«{rec.text_ar}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.NOT_FOUND
    assert m[0].record is None


def test_every_other_excluded_record_is_excluded_whole():
    """Among Bukhari's 17 excluded records, 237 is the exception with a
    second representation; the other sixteen have nothing but their primary.

    Task 11 (Sahih Muslim): 721 more excluded records joined 237 in this
    count. Two of Muslim's are the same shape as 237 -- a pointer/deferral
    primary that a `_split_secondary` cut also gave a real addendum to --
    "hadith:muslim:1915-3" (pointer primary "the chain, and in his version",
    addendum: Ibn Miqsam's addition "and drowning is martyrdom too") and
    "hadith:muslim:546-3" (pointer primary "with this chain", addendum: a
    narrator naming Mu'ayqib). Everything else, in both collections, is
    excluded whole -- asserted rather than assumed, because "which records are
    affected" is the entire safety argument.

    Task 12 (Sunan Abi Dawud), first build: 103 more excluded records joined
    this count. One of Abu Dawud's was the same shape -- "hadith:abudawud:2225"
    (`_EDITORIAL_DISCUSSION`: Abu Dawud's own numbered remark about how other
    narrators transmitted the isnad/wording differently, carrying its own
    addendum). Everything else Abu Dawud contributed was excluded whole.

    Fix round 1 (R-A3-18): 36 more excluded records joined this count (877
    total), and the compiler-commentary split gives 37 more of Abu Dawud's
    excluded records their own addendum -- every one of the 36 new
    `UNSCORABLE["abudawud"]` entries was excluded BECAUSE the split cut its
    compiler commentary into an addendum in the first place, and 2331
    (already `_LEXICAL_GLOSS`) gained one the same way. 38 Abu Dawud records
    now carry a second representation, not one.

    Task 13 (Jami at-Tirmidhi): 80 more excluded records join this count
    (957 total). 64 of the 80 carry their own addendum -- almost every
    `_POINTER`/`_DEFERRAL` entry is a pointer word immediately followed by
    Abu Isa's own grading remark, and R-A3-19's split cuts that remark into
    an addendum the same way it does for a scorable primary. The 16 that
    carry none are the bare brackets (162, 3615-2), the three
    `_EDITORIAL_DISCUSSION` units with no trailing text at all, and the
    remaining pointer/deferral/Qur'anic-quote records whose printed unit
    ends where the primary does.

    Task 14 (Sunan an-Nasai): 53 more excluded records join this count
    (1,010 total). 6 of the 53 carry their own addendum -- the kunya
    marker fires on a record the Step 4 pointer audit separately excludes
    (648, 1786, 4588, 5123, 5194, 5695). The other 47 carry none: plain
    pointers, chain-continuation leaks, bare classification tags and
    truncated openings have nothing left after the primary to cut.

    Fix round 1 (R-A3-25): 2 more excluded records join this count (1,012
    total) -- 1738 and 3492 move from scorable to `UNSCORABLE["nasai"]`
    once the comparative-isnad family extension cuts a trailing pointer
    tag off each, leaving a bare chain-continuation fragment with no
    narrative content of its own. The comparative-isnad family extension
    also gives 7 MORE already-excluded Nasai records their own addendum
    for the first time -- their pointer text used to end flush with a
    now-covered formula (2232, 2295, 2412, 3492, 4098, 4360, 4787),
    exactly like the 6 kunya-marker records above. Independently, the
    `_split_compiler_commentary` fix this round's own new bare-tag markers
    exposed (see that function's comment) also lets Tirmidhi's 46 and 566
    -- already excluded, already in this table with `n=0` -- correctly
    cut their own "wa hadha asahh"-shaped tail for the first time, so they
    now carry an addendum too.

    Fix round 2 (R-A3-27): 2 more excluded records join this count (1,014
    total) -- 207-2 and 353 move from scorable to `UNSCORABLE["nasai"]`'s
    `_CHAIN_LEAK` group once the new "لم يذكر" arm cuts a trailing
    "and he did not mention <name>" remark off each, both already carrying
    that remark as an addendum.

    Task 15 (Sunan Ibn Majah): 1 more excluded record joins this count
    (1,015 total) -- hadith:ibnmajah:413, `UNSCORABLE["ibnmajah"]`'s one
    entry, a bare "نحوه" pointer with nothing after it to cut, so it carries
    no addendum (n=0, not present in the dict below).

    Task 16 A1: 5 more excluded records join this count (1,020 total), and all
    five are the same shape as 237 -- a pointer/deferral primary the Muslim
    commentary split exposed AND gave a real addendum to (1159-7, 1238-2,
    1532-2, 1647-2, 1855-3). Each carries a second representation (n=1), added
    to the dict below alongside Muslim's earlier 1915-3 and 546-3.

    Task 16 A2: 25 more excluded records join this count (1,045 total) -- the
    non-length-capped pointer/deferral sweep (1 Bukhari, 24 Muslim). Only ONE
    of the 25, muslim:1669-6, carries a second representation (its A1 addendum);
    it is added to the dict. The other 24 are excluded whole (n=0, absent from
    the dict): they are pure deferrals with no addendum to keep.

    Task 16 A2 fix-round: 151 more excluded records join this count (1,196
    total) -- the back-reference/omission-shape sweep (132 Muslim, 6 Abu Dawud,
    13 Tirmidhi). 8 of the 151 carry a second representation (an addendum a
    prior round had already cut): muslim:1433-7 and tirmidhi 328/493/888/985/
    1389/1452/2824-2; each is added to the dict. The other 143 are excluded
    whole (n=0, absent from the dict): back-references, meta-comments, omission
    notes and isnad-scaffold heads with no addendum to keep.

    Task 16 pre-Part-B cleanup, C0 (A2 residue): 5 more excluded records join
    this count (1,201 total) -- muslim:1302-2, 1913-2, 1977-8, 2153-5 (the
    same pure "bimana hadith X 'an Y" shape) and 1704-2 (adjudicated in
    context: a back-reference plus a narrator's-doubt remark). All 5 are
    excluded whole (n=0, absent from the dict): none carries an addendum.
    """
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT r.id, count(v.record_id) AS n FROM records r"
        " LEFT JOIN record_variants v ON v.record_id = r.id"
        " WHERE r.unscorable_reason IS NOT NULL GROUP BY r.id").fetchall()
    # A2 round 3 added 50 excluded records but did not update this count (its
    # docstring stops at C0's 1,201); round 4 adds 46 more. Re-measured against
    # a fresh build: 1,201 -> 1,251 (round 3) -> 1,297 (round 4). A2 round 5
    # (content-mass net) adds 28 more: 1,297 -> 1,325.
    assert len(rows) == 1325
    assert {r["id"]: r["n"] for r in rows if r["n"]} == {
        "hadith:bukhari:237": 1,
        # A2 round 5: two content-mass pointers carry an A1 addendum, so they
        # are excluded as a primary but keep their "full" variant row (n=1).
        "hadith:abudawud:1176": 1,
        "hadith:muslim:2359-6": 1,
        "hadith:muslim:1159-7": 1,
        "hadith:muslim:1238-2": 1,
        "hadith:muslim:1433-7": 1,  # A2 fix-round: isnad-scaffold head with an A1 addendum
        "hadith:muslim:1532-2": 1,
        "hadith:muslim:1647-2": 1,
        "hadith:muslim:1669-6": 1,
        "hadith:muslim:1855-3": 1,
        "hadith:muslim:1915-3": 1,
        "hadith:muslim:546-3": 1,
        "hadith:abudawud:180": 1,
        "hadith:abudawud:209": 1,
        "hadith:abudawud:263": 1,
        "hadith:abudawud:300": 1,
        "hadith:abudawud:308": 1,
        "hadith:abudawud:533": 1,
        "hadith:abudawud:960": 1,
        "hadith:abudawud:1200": 1,
        "hadith:abudawud:1302": 1,
        "hadith:abudawud:1405": 1,
        "hadith:abudawud:1604": 1,
        "hadith:abudawud:1636": 1,
        "hadith:abudawud:1948": 1,
        "hadith:abudawud:2084": 1,
        "hadith:abudawud:2097": 1,
        "hadith:abudawud:2225": 1,
        "hadith:abudawud:2331": 1,
        "hadith:abudawud:2397": 1,
        "hadith:abudawud:2468": 1,
        "hadith:abudawud:2580": 1,
        "hadith:abudawud:2585": 1,
        "hadith:abudawud:3099": 1,
        "hadith:abudawud:3100": 1,
        "hadith:abudawud:3162": 1,
        "hadith:abudawud:3226": 1,
        "hadith:abudawud:3291": 1,
        "hadith:abudawud:3434": 1,
        "hadith:abudawud:3552": 1,
        "hadith:abudawud:3604": 1,
        "hadith:abudawud:3952": 1,
        "hadith:abudawud:3980": 1,
        "hadith:abudawud:3997": 1,
        "hadith:abudawud:4013": 1,
        "hadith:abudawud:4022": 1,
        "hadith:abudawud:4118": 1,
        "hadith:abudawud:4287": 1,
        "hadith:abudawud:4571": 1,
        "hadith:abudawud:4897": 1,
        "hadith:tirmidhi:1051": 1,
        "hadith:tirmidhi:1104": 1,
        "hadith:tirmidhi:111": 1,
        "hadith:tirmidhi:119": 1,
        "hadith:tirmidhi:127": 1,
        "hadith:tirmidhi:1328": 1,
        "hadith:tirmidhi:148": 1,
        "hadith:tirmidhi:1605": 1,
        "hadith:tirmidhi:163": 1,
        "hadith:tirmidhi:166": 1,
        "hadith:tirmidhi:1662": 1,
        "hadith:tirmidhi:1697": 1,
        "hadith:tirmidhi:1904-2": 1,
        "hadith:tirmidhi:196": 1,
        "hadith:tirmidhi:2282": 1,
        "hadith:tirmidhi:2286": 1,
        "hadith:tirmidhi:2296": 1,
        "hadith:tirmidhi:2534": 1,
        "hadith:tirmidhi:2534-2": 1,
        "hadith:tirmidhi:2543-2": 1,
        "hadith:tirmidhi:256": 1,
        "hadith:tirmidhi:2568-2": 1,
        "hadith:tirmidhi:2570": 1,
        "hadith:tirmidhi:280": 1,
        "hadith:tirmidhi:285": 1,
        "hadith:tirmidhi:2864": 1,
        "hadith:tirmidhi:2929": 1,
        "hadith:tirmidhi:2934": 1,
        "hadith:tirmidhi:299": 1,
        "hadith:tirmidhi:30": 1,
        "hadith:tirmidhi:343": 1,
        "hadith:tirmidhi:3435-2": 1,
        "hadith:tirmidhi:347": 1,
        "hadith:tirmidhi:349": 1,
        "hadith:tirmidhi:434": 1,
        "hadith:tirmidhi:441": 1,
        "hadith:tirmidhi:444": 1,
        "hadith:tirmidhi:504": 1,
        "hadith:tirmidhi:529": 1,
        "hadith:tirmidhi:535": 1,
        "hadith:tirmidhi:540": 1,
        "hadith:tirmidhi:559": 1,
        "hadith:tirmidhi:569": 1,
        "hadith:tirmidhi:574": 1,
        "hadith:tirmidhi:599": 1,
        "hadith:tirmidhi:612": 1,
        "hadith:tirmidhi:627": 1,
        "hadith:tirmidhi:634": 1,
        "hadith:tirmidhi:636": 1,
        "hadith:tirmidhi:648": 1,
        "hadith:tirmidhi:654": 1,
        "hadith:tirmidhi:701": 1,
        "hadith:tirmidhi:704": 1,
        "hadith:tirmidhi:709": 1,
        "hadith:tirmidhi:717": 1,
        "hadith:tirmidhi:722": 1,
        "hadith:tirmidhi:786": 1,
        "hadith:tirmidhi:800": 1,
        "hadith:tirmidhi:836": 1,
        "hadith:tirmidhi:872": 1,
        "hadith:tirmidhi:915": 1,
        "hadith:tirmidhi:926": 1,
        "hadith:tirmidhi:968": 1,
        "hadith:tirmidhi:971": 1,
        "hadith:tirmidhi:46": 1,
        "hadith:tirmidhi:566": 1,
        # A2 fix-round: back-reference/omission records carrying an addendum
        "hadith:tirmidhi:328": 1,
        "hadith:tirmidhi:493": 1,
        "hadith:tirmidhi:888": 1,
        "hadith:tirmidhi:985": 1,
        "hadith:tirmidhi:1389": 1,
        "hadith:tirmidhi:1452": 1,
        "hadith:tirmidhi:2824-2": 1,
        "hadith:nasai:648": 1,
        "hadith:nasai:1786": 1,
        "hadith:nasai:4588": 1,
        "hadith:nasai:5123": 1,
        "hadith:nasai:5194": 1,
        "hadith:nasai:5695": 1,
        "hadith:nasai:2232": 1,
        "hadith:nasai:2295": 1,
        "hadith:nasai:2412": 1,
        "hadith:nasai:3492": 1,
        "hadith:nasai:4098": 1,
        "hadith:nasai:4360": 1,
        "hadith:nasai:4787": 1,
        "hadith:nasai:207-2": 1,
        "hadith:nasai:353": 1,
        # A2 round 3 (absorbed here now): the round-3 whole-string sweep added
        # these seven excluded records that already carried an addendum a prior
        # round had cut, but did not update this dict (its pin stopped at C0).
        "hadith:abudawud:4555": 1,
        "hadith:abudawud:5035": 1,
        "hadith:muslim:2036-2": 1,
        "hadith:muslim:2821-2": 1,
        "hadith:nasai:3903": 1,
        "hadith:tirmidhi:1299": 1,
        "hadith:tirmidhi:890": 1,
        # A2 round 4: two of the 46 pure-apparatus records carry an addendum a
        # prior round cut (their "full" variant is kept, the pointer head is not).
        "hadith:tirmidhi:595": 1,
        "hadith:tirmidhi:1096": 1,
    }


def test_exactly_one_hadith_representation_sits_inside_an_ayah():
    """The population of the R40 behaviour, swept rather than sampled.

    `verify.engine._ayat_containing` withholds a hadith verdict when the
    reader cites an ayah their words are inside of. How often that can happen
    is a fact about this corpus, and the honest form of it is a number over
    every scorable representation, not the one example that prompted the fix.

    In the Bukhari-only corpus this was exactly one pair: Sahih al-Bukhari
    3658's whole matn, "the moon split", inside Qur'an 54:1, which ends with
    the same two words carrying a prefixed waw. Both tiers agreed on it -- the
    withholding tier found nothing the disclosure tier did not.

    Task 11 (Sahih Muslim) moved this from one pair to four, and broke the
    "both tiers agree" equality for the first time -- read in the source, not
    assumed to still hold:

    - "hadith:muslim:274-13", the matn "da'hu" ("leave him") -- the Prophet's
      own two-word reply telling Abd al-Rahman ibn Awf to keep leading the
      prayer (Task 11's audit left this one OFF `UNSCORABLE`: it is a genuine,
      complete saying, just a very short one). At three letters it is a
      substring of four unrelated ayat at BOTH tiers, which is exactly the
      corpus fact `_ayat_containing`/`_contains_at` exist to catch and
      `verify.engine` exists to withhold on, not a defect in either.
    - "hadith:muslim:1473", "laqad kana lakum fi rasuli Llahi uswatun
      hasanatun" -- a narrator quoting the opening clause of Qur'an 33:21.
      Found at the withholding (aggressive) tier but NOT confirmed at the
      disclosure (standard) one: the hadith's plain transcription spells "fi"
      with a dotted ya (U+064A), the Qur'an's Uthmani rasm spells the same
      word with a dotless alif maqsura (U+0649) -- a real, common, benign
      divergence between modern and Qur'anic orthography that the aggressive
      tier folds together and the standard tier does not. This is the first
      record in the corpus where the two tiers disagree; it is noted here and
      in the task-11 report as a question for verify.engine (should the
      disclosure tier tolerate this one substitution?), not fixed by this
      ingestion task.
    - "hadith:muslim:2380-5", the matn "< la-ittakhadhta 'alayhi ajran >"
      (Khidr's reply in the Qur'an 18:77 story, as Ubayy ibn Ka'b recited it)
      -- also withheld-not-disclosed, for an unrelated reason: the edition
      itself prints this one variant reading wrapped in literal "<" ">"
      angle brackets (a qira'a note, present in the raw OpenITI file, not
      introduced by this parser), so its stored text never matches the ayah's
      clean text at the standard tier either. Left as printed; see the
      task-11 report.

    If either number ever moves again, someone has to read the new record in
    the source, the same discipline as
    `build._reject_wholly_quranic_representations` at the other end of the
    pipeline.

    Task 12 (Sunan Abi Dawud), first build, moved the representation count
    (14,365 to 19,605) without moving either list: re-read in full against the
    built database, no Abu Dawud representation sat inside an ayah at either
    tier.

    Fix round 1 (R-A3-18) moves the representation count to 20,362 (5,135
    scorable Abu Dawud primaries instead of 5,171, plus 1,376 full-text
    representations corpus-wide instead of 69) without moving either list:
    re-run against the fixed build, still no Abu Dawud representation -- new
    or old -- sits inside an ayah at either tier.

    Fix round 2 (R-A3-22) moves the representation count to 20,371 (1,385
    full-text representations corpus-wide instead of 1,376) without moving
    either list: re-run against the fixed build, none of the 9 newly-cut Abu
    Dawud records sits inside an ayah at either tier.

    Fix round 3 (R-A3-23) moves the representation count to 20,373 (1,387
    full-text representations corpus-wide instead of 1,385) without moving
    either list: re-run against the fixed build, neither 1234 nor 1854 sits
    inside an ayah at either tier.

    Task 13 (Jami at-Tirmidhi) moves the representation count to 28,024
    without moving either list: re-run against the fixed build, including
    Tirmidhi's large tafsir section, no Tirmidhi representation -- scorable
    or excluded-with-addendum -- sits inside an ayah at either tier. (2929's
    own matn, which IS wholly inside an ayah, is excluded before this sweep
    runs at all; see `UNSCORABLE["tirmidhi"]`'s `_QURANIC_QUOTE` group and
    `test_no_scorable_hadith_representation_is_wholly_quranic` above.)

    Task 14 (Sunan an-Nasai) moves the representation count to 34,014
    without moving either list: re-run against the fixed build, no Nasai
    representation -- scorable or excluded-with-addendum -- sits inside an
    ayah at either tier.

    Fix round 1 (R-A3-25) moves the representation count to 34,074 (same
    breakdown as `test_the_index_holds_one_row_per_scorable_representation`'s
    fix-round note) without moving either list: re-run against the fixed
    build, none of the newly-cut Nasai or Tirmidhi representations sits
    inside an ayah at either tier.

    Fix round 2 (R-A3-27) moves the representation count to 34,168 (same
    breakdown as `test_no_scorable_hadith_representation_is_wholly_quranic`'s
    fix-round note) without moving either list: re-run against the fixed
    build, none of the six-shape sweep's newly-cut Nasai representations
    sits inside an ayah at either tier.

    Task 15 (Sunan Ibn Majah) moves the representation count to 38,674 (same
    breakdown as `test_no_scorable_hadith_representation_is_wholly_quranic`'s
    own Task 15 note) and DOES move the withheld list, by one:
    hadith:ibnmajah:2073 is the byte-identical twin of hadith:muslim:1473
    above -- the same narrator quoting the same opening clause of Qur'an
    33:21 -- and inherits the exact same disposition for the exact same
    reason: withheld at the aggressive tier, not confirmed at the standard
    one, because this edition's own plain transcription spells "fi" with a
    dotted ya where the Qur'an's Uthmani rasm spells it with a dotless alif
    maqsura. The disclosed list does not move. This is also, independently,
    why the two records tie in `verify_spans` and Muslim's own full id wins
    the tie -- see `eval/cases/hadith.yaml`'s
    `hadith-muslim-quranic-primary-verifies-as-printed` case.

    Task 16 A1 (Bukhari + Muslim commentary split) moves the representation
    count to 38,775 (same +101 breakdown as
    `test_no_scorable_hadith_representation_is_wholly_quranic`'s Task 16 note)
    without moving either list: re-run against the fixed build, none of the
    newly-cut Bukhari or Muslim full-text representations, and none of the 5
    Muslim records the split newly excluded, sits inside an ayah at either
    tier.

    Task 16 A2 (pointer/deferral sweep) moves the representation count to
    38,750 (-25 scorable hadith primaries) without moving either list: none of
    the 25 newly-excluded deferrals was in the withheld or disclosed set.

    Task 16 A2 fix-round (back-reference/omission shapes) moves the
    representation count to 38,599 (-151 scorable hadith primaries) without
    moving either list: none of the 151 newly-excluded back-reference/omission
    records was in the withheld or disclosed set.

    Task 16 pre-Part-B cleanup, C0 (A2 residue) moves the representation count
    to 38,594 (-5 scorable hadith primaries) without moving either list: none
    of the 5 newly-excluded Muslim back-reference records was in the withheld
    or disclosed set.
    """
    from sanad.verify.engine import _ayat_containing, _contains_at
    conn = db.connect(DB_PATH)
    reps = conn.execute(
        "SELECT r.id AS rid, 'primary' AS variant, r.text_ar AS text_ar"
        " FROM records r WHERE r.kind = 'hadith' AND r.unscorable_reason IS NULL"
        " UNION ALL "
        "SELECT v.record_id, v.variant, v.text_ar FROM record_variants v"
        " JOIN records r ON r.id = v.record_id WHERE r.kind = 'hadith'"
    ).fetchall()
    # A2 round 4: -46 scorable primaries now UNSCORABLE (see the wholly-Qur'anic
    # sweep's Task 16 A2 round 4 note); variants unchanged.
    # A2 round 5: -28 more scorable primaries now UNSCORABLE (content-mass net);
    # variants unchanged (the two addenda-carrying pointers keep their "full"
    # variant row): 38,498 -> 38,470.
    assert len(reps) == 38470, len(reps)

    withheld, disclosed = [], []
    for rep in reps:
        hits = _ayat_containing(conn, rep["text_ar"], "aggressive")
        if not hits:
            continue
        withheld.append((rep["rid"], rep["variant"], [h.id for h in hits]))
        strict = [h.id for h in hits
                  if _contains_at(h, rep["text_ar"], "standard")]
        if strict:
            disclosed.append((rep["rid"], rep["variant"], strict))

    assert withheld == [
        ("hadith:bukhari:3658", "primary", ["quran:54:1"]),
        ("hadith:muslim:274-13", "primary",
         ["quran:2:260", "quran:4:142", "quran:11:6", "quran:18:57"]),
        ("hadith:muslim:1473", "primary", ["quran:33:21"]),
        ("hadith:muslim:2380-5", "primary", ["quran:18:77"]),
        ("hadith:ibnmajah:2073", "primary", ["quran:33:21"]),
    ]
    assert disclosed == [
        ("hadith:bukhari:3658", "primary", ["quran:54:1"]),
        ("hadith:muslim:274-13", "primary",
         ["quran:2:260", "quran:4:142", "quran:11:6", "quran:18:57"]),
    ]


# --- Task 11: Sahih Muslim ---------------------------------------------------
#
# Every Arabic literal below is a codepoint tuple read out of the built
# database with a one-off script, per the top-of-file convention, never typed.


def test_muslim_record_count_and_scorability():
    """The measured, lockfile-pinned facts about the second hadith collection.

    7,460 is `expected_records` in corpus.lock.toml, itself pinned from the
    first measured build (Task 11), not assumed. 721 unscorable and 122 cut
    are the audit's own output: see audit_lists.py's "muslim" section and the
    task-11 report for what each of the 721 is and why.

    Task 16 A1: 726 unscorable and 147 cut. Muslim's compiler-commentary
    markers ("qala Muslim", "qala Abu al-Husayn") cut 26 records, 25 of them
    gaining a fresh addendum (one already had one); and the split exposed 5
    short pointer/deferral heads that joined `UNSCORABLE["muslim"]`
    (721 -> 726), moving 5 records from scorable to unscorable (6,739 ->
    6,734). The raw source and its lockfile pins are untouched.

    Task 16 A2 (non-length-capped pointer/deferral sweep): 750 unscorable, 147
    cut (unchanged). 24 more Muslim records join `UNSCORABLE["muslim"]` --
    partial-quote deferrals ("bi-hadha al-isnad ... ila qawlihi X wa-lam
    yadhkur ma ba'dahu") that name where another version stops without
    delivering narration; each escaped Task 11's 30-char floor only because
    its endpoint phrase padded the length. 6,734 -> 6,710 scorable. cut is
    unchanged: 23 of the 24 carry no addendum, and muslim:1669-6 already had
    one (from A1) that it keeps as a scorable "full" variant.

    Task 16 A2 fix-round (back-reference and omission shapes): 882 unscorable,
    147 cut (unchanged). A2's first pass caught the endpoint-locator deferrals
    but left the broader class the review named -- pure back-references
    ("bi-hadha al-isnad mithla hadith fulan"), meta-comments ("hadith fulan
    atammu wa-atwal"), omission notes ("wa-lam yadhkur X") and isnad-scaffold
    heads -- that deliver no narration of their own yet verified EXACT. 132
    more Muslim records, each hand-read at full length, join
    `UNSCORABLE["muslim"]` (750 -> 882); 6,710 -> 6,578 scorable. cut is
    unchanged (the class is a matn of pure pointer/comment; addenda that some
    carry stay as "full" variants). This also resolves the 1644-3/1532-2
    inconsistency the review flagged: 1644-3 ("bi-hadha al-isnad mithla hadith
    Abd al-Razzaq") is now UNSCORABLE alongside its class-mate 1532-2.

    Task 16 pre-Part-B cleanup, C0 (A2 residue): 887 unscorable, 147 cut
    (unchanged). 5 more pure "bimana hadith X 'an Y" back-reference singletons
    join `UNSCORABLE["muslim"]` (882 -> 887; 6,578 -> 6,573 scorable): four
    slipped the fix round's duplicate-string grouping because each is a
    unique string, and the fifth (1704-2) was adjudicated in context -- a
    back-reference plus a narrator's-doubt remark about a transmitted
    numeral, no narrative content of its own. None carries an addendum, so
    cut is unchanged.
    """
    conn = db.connect(DB_PATH)
    total = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='muslim'"
    ).fetchone()[0]
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='muslim'"
        " AND unscorable_reason IS NULL").fetchone()[0]
    unscorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='muslim'"
        " AND unscorable_reason IS NOT NULL").fetchone()[0]
    cut = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='muslim'"
        " AND addenda_ar IS NOT NULL").fetchone()[0]
    # A2 round 4: -38 Muslim primaries now UNSCORABLE (editorial omission/
    # comparison sweep). This pin also absorbs round 3's -38 Muslim, which the
    # round-3 commit updated only in the two reps pins, not here (re-measured
    # against a fresh build): scorable 6573 -> 6535 (round 3) -> 6497 (round 4).
    # A2 round 5 (vocabulary-free content-mass net): -19 more Muslim primaries
    # (19 of the 28 content-mass pointers are Muslim; 274-13 "da'hu" and 581-2
    # are genuine short matns, kept): 6497 -> 6478, 963 -> 982.
    assert (total, scorable, unscorable, cut) == (7460, 6478, 982, 147)


def test_abudawud_record_count_and_scorability():
    """The measured, lockfile-pinned facts about the third hadith collection.

    5,274 is `expected_records` in corpus.lock.toml, pinned from the first
    measured build (Task 12) -- one fewer than the raw file's own numbered
    units, because unit "1" in the raw text is a mis-wrapped kitab heading
    ("kitab al-tahara"), not a hadith; see the `_KITAB_WORD` branch in
    `openiti.py`'s `flush()`. `expected_records` and `content_sha256` in the
    lockfile are unchanged by fix round 1 below -- the raw source file was
    never touched, only how its matns are split.

    103 unscorable and 69 cut, first build: the audit's own output; see
    audit_lists.py's "abudawud" section for what each of the 103 is and why.

    139 unscorable and 862 cut, fix round 1 (R-A3-18): the compiler-commentary
    split (`_split_compiler_commentary`) cuts Abu Dawud's own "qala Abu Dawud
    ..." remarks -- fused into 793 matns with no addendum at all, and into 13
    more that already had one -- into an addendum instead, closing the
    Class-B defect where quoting the genuine matn alone (e.g.
    hadith:abudawud:65, the qultayn hadith) fell below the verification
    threshold. The cut-override table (`CUT_OVERRIDE["abudawud"]`) separately
    corrects 11 `_split_secondary` boundaries that left a dangling "qala
    <name>" attribution fragment on the primary. Once the post-split
    primaries are read the same way the original 103 were -- every one 30
    characters or fewer, by hand, against its own context -- 36 more turned
    out to be editorial apparatus (pointer/deferral/an editorial remark about
    a wording variant/two wholly-Qur'anic qira'a reports) and joined
    `UNSCORABLE["abudawud"]`; 103 + 36 = 139.

    139 unscorable (unchanged) and 871 cut, fix round 2 (R-A3-22): the marker
    missed two records where a word intervened between the verb and "Abu
    Dawud" (`_ABUDAWUD_COMMENTARY_NEAR`, `hadith:abudawud:4129`/`5239`) --
    4129 also needed `NEAR_MISS_CUT_OVERRIDE` for a nested attribution the
    widened marker alone did not reach -- and Abu Ali al-Lu'lu'i's own voice
    turned out to be the same defect, a different speaker
    (`_split_lului_commentary`, 7 more records: 911, 1096, 1391, 3220, 3437,
    4924, 5190). 862 + 2 + 7 = 871. Unscorable is unchanged because every
    newly-cut primary is a genuine, complete, quotable matn -- see
    `tests/ingest/test_real_corpus.py`'s fix-round-2 section below for each
    one verified against the materialized DB.

    139 unscorable (unchanged) and 873 cut, fix round 3 (R-A3-23): the
    marker only ever recognised the compiler's kunya in the NOMINATIVE case;
    two records quote him in the ACCUSATIVE instead ("sami'tu Aba Dawud
    yaqulu ...", `_split_heard_commentary`, `hadith:abudawud:1234`/`1854`).
    871 + 2 = 873. 1234 additionally needed `NEAR_MISS_CUT_OVERRIDE` for a
    dangling narrator attribution the heard-marker alone did not reach, the
    same shape as 4129 in fix round 2. Unscorable is unchanged for the same
    reason as before -- both are genuine, complete, quotable matns.

    145 unscorable and 873 cut (unchanged), Task 16 A2 fix-round: the same
    back-reference/omission sweep run across Muslim was confirmed on the other
    five collections. Abu Dawud yielded 6 records that deliver no narration of
    their own (back-references and editorial/omission remarks: 1349, 3487,
    4322, 4453, 5032, 5175) and join `UNSCORABLE["abudawud"]`; 139 + 6 = 145.
    cut is unchanged -- none of the six is a newly-cut primary.
    """
    conn = db.connect(DB_PATH)
    total = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='abudawud'"
    ).fetchone()[0]
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='abudawud'"
        " AND unscorable_reason IS NULL").fetchone()[0]
    unscorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='abudawud'"
        " AND unscorable_reason IS NOT NULL").fetchone()[0]
    cut = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='abudawud'"
        " AND addenda_ar IS NOT NULL").fetchone()[0]
    # A2 round 4: -5 Abu Dawud primaries now UNSCORABLE. Also absorbs round 3's
    # -6 (updated only in the reps pins at the time): 5129 -> 5123 -> 5118.
    # A2 round 5 (content-mass net): -4 more (abudawud:1176, 1354, 3609, 4045):
    # 5118 -> 5114, 156 -> 160.
    assert (total, scorable, unscorable, cut) == (5274, 5114, 160, 873)


# Three spot-checked Abu Dawud matns, read BYTE-EXACT from the materialized
# DB and reproduced here as codepoints (never retyped glyphs), per the
# char-safety convention used throughout this file. Chosen to bracket the
# collection and exercise the `_KITAB_WORD` fix directly: record 1 is the
# real first hadith (proving the mis-wrapped kitab-heading unit was NOT
# mistaken for it), record 2201 is the well-known "innama al-a'malu
# bi-l-niyyat" ("actions are but by intentions"), and record 5274 is the
# collection's own last hadith.
_ABUDAWUD_1_MATN = "".join(chr(c) for c in (
    0x0623, 0x0646, 0x0020, 0x0627, 0x0644, 0x0646, 0x0628, 0x064a,
    0x0020, 0x0635, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644, 0x0644,
    0x0647, 0x0020, 0x0639, 0x0644, 0x064a, 0x0647, 0x0020, 0x0648,
    0x0633, 0x0644, 0x0645, 0x0020, 0x0643, 0x0627, 0x0646, 0x0020,
    0x0625, 0x0630, 0x0627, 0x0020, 0x0630, 0x0647, 0x0628, 0x0020,
    0x0627, 0x0644, 0x0645, 0x0630, 0x0647, 0x0628, 0x0020, 0x0623,
    0x0628, 0x0639, 0x062f,
))

_ABUDAWUD_2201_MATN = "".join(chr(c) for c in (
    0x0625, 0x0646, 0x0645, 0x0627, 0x0020, 0x0627, 0x0644, 0x0623,
    0x0639, 0x0645, 0x0627, 0x0644, 0x0020, 0x0628, 0x0627, 0x0644,
    0x0646, 0x064a, 0x0627, 0x062a, 0x0020, 0x0648, 0x0625, 0x0646,
    0x0645, 0x0627, 0x0020, 0x0644, 0x0643, 0x0644, 0x0020, 0x0627,
    0x0645, 0x0631, 0x0626, 0x0020, 0x0645, 0x0627, 0x0020, 0x0646,
    0x0648, 0x0649, 0x0020, 0x0641, 0x0645, 0x0646, 0x0020, 0x0643,
    0x0627, 0x0646, 0x062a, 0x0020, 0x0647, 0x062c, 0x0631, 0x062a,
    0x0647, 0x0020, 0x0625, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644,
    0x0644, 0x0647, 0x0020, 0x0648, 0x0631, 0x0633, 0x0648, 0x0644,
    0x0647, 0x0020, 0x0641, 0x0647, 0x062c, 0x0631, 0x062a, 0x0647,
    0x0020, 0x0625, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644, 0x0644,
    0x0647, 0x0020, 0x0648, 0x0631, 0x0633, 0x0648, 0x0644, 0x0647,
    0x0020, 0x0648, 0x0645, 0x0646, 0x0020, 0x0643, 0x0627, 0x0646,
    0x062a, 0x0020, 0x0647, 0x062c, 0x0631, 0x062a, 0x0647, 0x0020,
    0x0644, 0x062f, 0x0646, 0x064a, 0x0627, 0x0020, 0x064a, 0x0635,
    0x064a, 0x0628, 0x0647, 0x0627, 0x0020, 0x0623, 0x0648, 0x0020,
    0x0627, 0x0645, 0x0631, 0x0623, 0x0629, 0x0020, 0x064a, 0x062a,
    0x0632, 0x0648, 0x062c, 0x0647, 0x0627, 0x0020, 0x0641, 0x0647,
    0x062c, 0x0631, 0x062a, 0x0647, 0x0020, 0x0625, 0x0644, 0x0649,
    0x0020, 0x0645, 0x0627, 0x0020, 0x0647, 0x0627, 0x062c, 0x0631,
    0x0020, 0x0625, 0x0644, 0x064a, 0x0647,
))

_ABUDAWUD_5274_MATN = "".join(chr(c) for c in (
    0x064a, 0x0624, 0x0630, 0x064a, 0x0646, 0x064a, 0x0020, 0x0628,
    0x0646, 0x0020, 0x0622, 0x062f, 0x0645, 0x0020, 0x064a, 0x0633,
    0x0628, 0x0020, 0x0627, 0x0644, 0x062f, 0x0647, 0x0631, 0x0020,
    0x0648, 0x0623, 0x0646, 0x0627, 0x0020, 0x0627, 0x0644, 0x062f,
    0x0647, 0x0631, 0x0020, 0x0628, 0x064a, 0x062f, 0x064a, 0x0020,
    0x0627, 0x0644, 0x0623, 0x0645, 0x0631, 0x0020, 0x0623, 0x0642,
    0x0644, 0x0628, 0x0020, 0x0627, 0x0644, 0x0644, 0x064a, 0x0644,
    0x0020, 0x0648, 0x0627, 0x0644, 0x0646, 0x0647, 0x0627, 0x0631,
    0x0020, 0x0642, 0x0627, 0x0644, 0x0020, 0x0628, 0x0646, 0x0020,
    0x0627, 0x0644, 0x0633, 0x0631, 0x062d, 0x0020, 0x0639, 0x0646,
    0x0020, 0x0628, 0x0646, 0x0020, 0x0627, 0x0644, 0x0645, 0x0633,
    0x064a, 0x0628, 0x0020, 0x0645, 0x0643, 0x0627, 0x0646, 0x0020,
    0x0633, 0x0639, 0x064a, 0x062f, 0x0020, 0x0648, 0x0627, 0x0644,
    0x0644, 0x0647, 0x0020, 0x0623, 0x0639, 0x0644, 0x0645,
))


def test_abudawud_hadith_1_is_the_real_first_hadith_not_the_kitab_heading():
    """Guards the `_KITAB_WORD` fix directly against the materialized DB.

    Before the fix, `hadith:abudawud:1` held the matn "kitab al-tahara" (a
    book title) and the real first hadith was pushed to a fabricated "-2"
    occurrence suffix. Both wrongs are checked here.
    """
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:abudawud:1")
    assert rec.text_ar == _ABUDAWUD_1_MATN
    assert conn.execute(
        "SELECT count(*) FROM records WHERE id='hadith:abudawud:1-2'"
    ).fetchone()[0] == 0


def test_abudawud_spot_checked_matns_are_byte_exact():
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "hadith:abudawud:2201").text_ar == _ABUDAWUD_2201_MATN
    assert db.get_record(conn, "hadith:abudawud:5274").text_ar == _ABUDAWUD_5274_MATN


# "al-harb khud'a" -- war is deceit. The SAME codepoints as Bukhari's
# _AL_HARB_KHUDA above: Sahih Muslim prints this saying too (1739, 1740),
# Task 12 found a fourth copy at Abu Dawud 2636, and Task 13 a fifth at
# Tirmidhi 1675.
def test_a_genuine_short_hadith_shared_across_collections_still_verifies():
    """Bukhari 2866, Muslim 1739/1740, (Task 12) Abu Dawud 2636, (Task 13)
    Tirmidhi 1675, and (Task 15) Ibn Majah 2833/2834 all print the same
    three words.

    The tie-break rule ("lowest id wins, the rest are disclosed") was proven
    within one collection (383 and 774, both Bukhari); Task 11 exercised it
    firing ACROSS collections for the first time (Bukhari won the tie then).
    Task 12 changed WHICH collection wins, without changing the rule: Abu
    Dawud's full id sorts first lexicographically ("hadith:abudawud:..." <
    "hadith:bukhari:..."), so it is the winner now and the rest move into
    `also_at`. Task 15 adds two more entries without changing the winner --
    "hadith:ibnmajah:..." sorts between "hadith:bukhari:..." and
    "hadith:muslim:...". See `test_a_famous_short_hadith_still_verifies_exactly`
    above for the same fact asserted the other direction.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_AL_HARB_KHUDA}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    assert matches[0].record.id == "hadith:abudawud:2636"
    assert matches[0].also_at == [
        "hadith:bukhari:2866", "hadith:ibnmajah:2833", "hadith:ibnmajah:2834",
        "hadith:muslim:1739", "hadith:muslim:1740", "hadith:tirmidhi:1675",
    ]


# "da'hu" -- "leave him." The Prophet's own reply telling Abd al-Rahman ibn
# Awf to keep leading the prayer at Tabuk. Two letters shorter than the
# shortest record Bukhari's audit left genuine ("la tuki fa-yuka 'alayki",
# 1366), and it is why Task 11's audit is a judgement about MEANING and not a
# length rule: it sits in the exact same character range as the 721 records
# just below it that are NOT genuine.
_MUSLIM_DAHU = "".join(chr(c) for c in (0x062F, 0x0639, 0x0647))


def test_the_shortest_genuine_muslim_hadith_still_verifies_exactly():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_MUSLIM_DAHU}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    assert matches[0].record.id == "hadith:muslim:274-13"


# "bi-hadha al-isnad mithlahu" -- "with this chain, the like of it." Sahih
# Muslim's single most common editorial pointer (108 records print exactly
# this string); a stand-in for the 721-record `UNSCORABLE["muslim"]` list the
# same way Bukhari's "bi-hadha" stands in for its 17.
_MUSLIM_POINTER = "".join(chr(c) for c in (
    0x0628, 0x0647, 0x0630, 0x0627, 0x0020, 0x0627, 0x0644, 0x0625, 0x0633,
    0x0646, 0x0627, 0x062F, 0x0020, 0x0645, 0x062B, 0x0644, 0x0647))


def test_a_muslim_editorial_pointer_is_not_verified_as_a_hadith():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_MUSLIM_POINTER}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.NOT_FOUND
    assert matches[0].record is None


# "rafa'ahu" -- "he raised it [to the Prophet]." An isnad question-and-answer
# about attribution, not a report of anything said. Its own reason
# (_ATTRIBUTION_NOTE) because it is not a comparison to another narration
# (_POINTER) or a mid-sentence deferral (_DEFERRAL) -- Bukhari's three
# existing reasons do not fit it.
_MUSLIM_ATTRIBUTION = "".join(chr(c) for c in (0x0631, 0x0641, 0x0639, 0x0647))


def test_the_attribution_note_is_not_verified_as_a_hadith():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_MUSLIM_ATTRIBUTION}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.NOT_FOUND
    assert matches[0].record is None


# "marra bi-rajulin min al-ansari ya'izu akhahu" -- "[the Prophet] passed by a
# man of the Ansar admonishing his brother." Unit 36's SECOND chain reports
# only this narrative frame; the actual saying ("shyness is part of faith")
# is unit 36's own primary matn and is not repeated here, and the source
# starts a fresh numbered unit immediately after -- there is nothing to
# reattach, so this is `_TRUNCATED_STUB`, Bukhari's `_STUB_OPENER` shape
# (632, 6136) without a cut to reverse.
_MUSLIM_STUB = "".join(chr(c) for c in (
    0x0645, 0x0631, 0x0020, 0x0628, 0x0631, 0x062C, 0x0644, 0x0020, 0x0645,
    0x0646, 0x0020, 0x0627, 0x0644, 0x0623, 0x0646, 0x0635, 0x0627, 0x0631,
    0x0020, 0x064A, 0x0639, 0x0638, 0x0020, 0x0623, 0x062E, 0x0627, 0x0647))


def test_the_truncated_stub_is_not_verified_as_a_hadith():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_MUSLIM_STUB}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.NOT_FOUND
    assert matches[0].record is None
    # ... and unit 36's own primary, the actual saying, still verifies.
    rec = db.get_record(conn, "hadith:muslim:36")
    whole = verify_spans(conn, f"«{rec.text_ar}»")
    assert whole[0].verdict is Verdict.EXACT
    assert whole[0].record.id == "hadith:muslim:36"


# --- Task 12 fix round 2 (R-A3-22): the marker's two near-misses, plus a ----
# different speaker's own voice ------------------------------------------

# "la tarkabu l-khazz wa-la l-nimar" -- "do not ride on khazz [silk-mixed
# cloth] or leopard-skin [saddle-cloths]." hadith:abudawud:4129's genuine
# matn. Fix round 1's marker required the verb immediately in front of "Abu
# Dawud"; the source here reads "... qala LANA Abu Dawud ..." with one word
# between them, so the marker never fired and this returned NOT_FOUND. Two
# further nested "qala <name>" remarks sat between the genuine matn and that
# marker, with no chain-transmission verb for `_split_secondary` to anchor
# on -- `NEAR_MISS_CUT_OVERRIDE` is the hand-audited second cut that reaches
# this exact wording.
_ABUDAWUD_4129_MATN = "".join(chr(c) for c in (
    0x0644, 0x0627, 0x0020, 0x062A, 0x0631, 0x0643, 0x0628, 0x0648, 0x0627,
    0x0020, 0x0627, 0x0644, 0x062E, 0x0632, 0x0020, 0x0648, 0x0644, 0x0627,
    0x0020, 0x0627, 0x0644, 0x0646, 0x0645, 0x0627, 0x0631))

# "man qata'a sidratan sawwaba Allahu ra'sahu fi l-nar" -- "whoever cuts a
# lote tree, Allah plunges his head into the Fire." hadith:abudawud:5239's
# genuine matn. The source itself prints a duplicated "abu" -- "su'ila ABU
# Abu Dawud 'an ma'na hadha l-hadith ..." -- so the tight marker never fired.
_ABUDAWUD_5239_MATN = "".join(chr(c) for c in (
    0x0645, 0x0646, 0x0020, 0x0642, 0x0637, 0x0639, 0x0020, 0x0633, 0x062F,
    0x0631, 0x0629, 0x0020, 0x0635, 0x0648, 0x0628, 0x0020, 0x0627, 0x0644,
    0x0644, 0x0647, 0x0020, 0x0631, 0x0623, 0x0633, 0x0647, 0x0020, 0x0641,
    0x064A, 0x0020, 0x0627, 0x0644, 0x0646, 0x0627, 0x0631))


def test_the_two_near_miss_gap_records_now_verify():
    """4129 and 5239: the marker's own near-misses, not on Task 12's original
    792-record population (the marker never matched their fused text_ar
    either, before or after fix round 1), found instead by an outside review
    sweeping for the verb within a few tokens of the compiler's name.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "hadith:abudawud:4129").text_ar == _ABUDAWUD_4129_MATN
    assert db.get_record(conn, "hadith:abudawud:5239").text_ar == _ABUDAWUD_5239_MATN
    for record_id, matn in (("hadith:abudawud:4129", _ABUDAWUD_4129_MATN),
                            ("hadith:abudawud:5239", _ABUDAWUD_5239_MATN)):
        matches = verify_spans(conn, f"«{matn}»")
        assert len(matches) == 1, record_id
        assert matches[0].verdict is Verdict.EXACT, record_id
        assert matches[0].record.id == record_id, record_id


# --- Task 12 fix round 3 (R-A3-23): the marker's own case-blind spot -------
#
# Both markers above only ever recognised the compiler's kunya in the
# NOMINATIVE ("Abu Dawud" as the grammatical subject of "qala"/"su'ila"). An
# adversarial re-review found two further records where the compiler is
# quoted in the ACCUSATIVE instead -- "sami'tu ABA Dawud yaqulu ..." ("I
# heard Abu Dawud say ...", he is the object of "I heard", not the subject of
# "he said") -- a case no nominative-only marker could ever match.

# "anna Aliyyan ... kana idha safara sara ba'da ma taghrubu l-shamsu hatta
# takada an tuzlima thumma yanzilu fa-yusalli l-maghriba thumma yad'u
# bi-'asha'ihi fa-yata'ashsha thumma yusalli l-'isha'a thumma yartahilu
# wa-yaqulu hakadha kana rasulu Llahi salla Llahu 'alayhi wa-sallama yasna'"
# -- "'Ali, when he travelled, would ride on until the sun had nearly set,
# then dismount and pray maghrib, then call for his supper and have it,
# then pray 'isha, then set off again, saying: this is how the Messenger of
# Allah used to do it." hadith:abudawud:1234's genuine matn. Fused, with no
# marker before this fix round, onto "qala 'Uthman 'an 'Abd Allah ibn
# Muhammad ibn 'Amr ibn 'Ali SAMI'TU ABA DAWUD yaqulu ..." -- a narrator
# (Uthman) reporting that he heard Abu Dawud say something, itself a further
# narration comparison, not part of 'Ali's own hadith.
_ABUDAWUD_1234_MATN = "".join(chr(c) for c in (
    0x0623, 0x0646, 0x0020, 0x0639, 0x0644, 0x064a, 0x0627, 0x0020, 0x0631,
    0x0636, 0x064a, 0x0020, 0x0627, 0x0644, 0x0644, 0x0647, 0x0020, 0x0639,
    0x0646, 0x0647, 0x0020, 0x0643, 0x0627, 0x0646, 0x0020, 0x0625, 0x0630,
    0x0627, 0x0020, 0x0633, 0x0627, 0x0641, 0x0631, 0x0020, 0x0633, 0x0627,
    0x0631, 0x0020, 0x0628, 0x0639, 0x062f, 0x0020, 0x0645, 0x0627, 0x0020,
    0x062a, 0x063a, 0x0631, 0x0628, 0x0020, 0x0627, 0x0644, 0x0634, 0x0645,
    0x0633, 0x0020, 0x062d, 0x062a, 0x0649, 0x0020, 0x062a, 0x0643, 0x0627,
    0x062f, 0x0020, 0x0623, 0x0646, 0x0020, 0x062a, 0x0638, 0x0644, 0x0645,
    0x0020, 0x062b, 0x0645, 0x0020, 0x064a, 0x0646, 0x0632, 0x0644, 0x0020,
    0x0641, 0x064a, 0x0635, 0x0644, 0x064a, 0x0020, 0x0627, 0x0644, 0x0645,
    0x063a, 0x0631, 0x0628, 0x0020, 0x062b, 0x0645, 0x0020, 0x064a, 0x062f,
    0x0639, 0x0648, 0x0020, 0x0628, 0x0639, 0x0634, 0x0627, 0x0626, 0x0647,
    0x0020, 0x0641, 0x064a, 0x062a, 0x0639, 0x0634, 0x0649, 0x0020, 0x062b,
    0x0645, 0x0020, 0x064a, 0x0635, 0x0644, 0x064a, 0x0020, 0x0627, 0x0644,
    0x0639, 0x0634, 0x0627, 0x0621, 0x0020, 0x062b, 0x0645, 0x0020, 0x064a,
    0x0631, 0x062a, 0x062d, 0x0644, 0x0020, 0x0648, 0x064a, 0x0642, 0x0648,
    0x0644, 0x0020, 0x0647, 0x0643, 0x0630, 0x0627, 0x0020, 0x0643, 0x0627,
    0x0646, 0x0020, 0x0631, 0x0633, 0x0648, 0x0644, 0x0020, 0x0627, 0x0644,
    0x0644, 0x0647, 0x0020, 0x0635, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644,
    0x0644, 0x0647, 0x0020, 0x0639, 0x0644, 0x064a, 0x0647, 0x0020, 0x0648,
    0x0633, 0x0644, 0x0645, 0x0020, 0x064a, 0x0635, 0x0646, 0x0639
))

# "asabna sarman min jarad fa-kana rajulun minna yadribu bi-sawtihi wa-huwa
# muhrim fa-qila lahu inna hadha la yasluh fa-dhukira dhalika li-l-nabiyyi
# salla Llahu 'alayhi wa-sallama fa-qala innama huwa min saydi l-bahr" --
# "we came upon a swarm of locusts, and a man among us, while in ihram,
# began striking them with his whip. He was told: this is not permissible.
# That was mentioned to the Prophet, and he said: it is only sea game."
# hadith:abudawud:1854's genuine matn -- the Prophet's own ruling completes
# it. Fused, with no marker before this fix round, onto "sami'tu Aba Dawud
# yaqulu Abu l-Muhazzam da'if wa-l-hadithani jami'an wahm" -- al-Lu'lu'i's
# own remark, with no "qala" before it at all (the accusative verb itself is
# the whole first-person clause), judging the narration's own reliability.
_ABUDAWUD_1854_MATN = "".join(chr(c) for c in (
    0x0623, 0x0635, 0x0628, 0x0646, 0x0627, 0x0020, 0x0635, 0x0631, 0x0645,
    0x0627, 0x0020, 0x0645, 0x0646, 0x0020, 0x062c, 0x0631, 0x0627, 0x062f,
    0x0020, 0x0641, 0x0643, 0x0627, 0x0646, 0x0020, 0x0631, 0x062c, 0x0644,
    0x0020, 0x0645, 0x0646, 0x0627, 0x0020, 0x064a, 0x0636, 0x0631, 0x0628,
    0x0020, 0x0628, 0x0633, 0x0648, 0x0637, 0x0647, 0x0020, 0x0648, 0x0647,
    0x0648, 0x0020, 0x0645, 0x062d, 0x0631, 0x0645, 0x0020, 0x0641, 0x0642,
    0x064a, 0x0644, 0x0020, 0x0644, 0x0647, 0x0020, 0x0625, 0x0646, 0x0020,
    0x0647, 0x0630, 0x0627, 0x0020, 0x0644, 0x0627, 0x0020, 0x064a, 0x0635,
    0x0644, 0x062d, 0x0020, 0x0641, 0x0630, 0x0643, 0x0631, 0x0020, 0x0630,
    0x0644, 0x0643, 0x0020, 0x0644, 0x0644, 0x0646, 0x0628, 0x064a, 0x0020,
    0x0635, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644, 0x0644, 0x0647, 0x0020,
    0x0639, 0x0644, 0x064a, 0x0647, 0x0020, 0x0648, 0x0633, 0x0644, 0x0645,
    0x0020, 0x0641, 0x0642, 0x0627, 0x0644, 0x0020, 0x0625, 0x0646, 0x0645,
    0x0627, 0x0020, 0x0647, 0x0648, 0x0020, 0x0645, 0x0646, 0x0020, 0x0635,
    0x064a, 0x062f, 0x0020, 0x0627, 0x0644, 0x0628, 0x062d, 0x0631
))


def test_the_two_accusative_near_miss_records_now_verify():
    """1234 and 1854: the marker's own case-blind spot, not found by any
    gap widening (R-A3-22's own sweep never varied grammatical case), found
    instead by an adversarial re-review reading the accusative form
    directly.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "hadith:abudawud:1234").text_ar == _ABUDAWUD_1234_MATN
    assert db.get_record(conn, "hadith:abudawud:1854").text_ar == _ABUDAWUD_1854_MATN
    for record_id, matn in (("hadith:abudawud:1234", _ABUDAWUD_1234_MATN),
                            ("hadith:abudawud:1854", _ABUDAWUD_1854_MATN)):
        matches = verify_spans(conn, f"«{matn}»")
        assert len(matches) == 1, record_id
        assert matches[0].verdict is Verdict.EXACT, record_id
        assert matches[0].record.id == record_id, record_id


# "anna rasula Llahi ... ru'iya 'ala jabhatihi wa-'ala arnabatihi atharu tinin
# min salatin sallaha bi-l-nas" -- "the Messenger of Allah was seen, on his
# forehead and the tip of his nose, the trace of mud from a prayer he had led
# the people in." hadith:abudawud:911's genuine matn, fused with a remark by
# Abu Ali al-Lu'lu'i -- the primary transmitter of Abu Dawud's own Sunan, not
# the compiler himself -- for which no marker existed before this fix round.
# hadith:abudawud:894 prints the identical matn with no such remark, proving
# this is the same fused-commentary shape and not a difference in narration.
_ABUDAWUD_911_MATN = "".join(chr(c) for c in (
    0x0623, 0x0646, 0x0020, 0x0631, 0x0633, 0x0648, 0x0644, 0x0020, 0x0627,
    0x0644, 0x0644, 0x0647, 0x0020, 0x0635, 0x0644, 0x0649, 0x0020, 0x0627,
    0x0644, 0x0644, 0x0647, 0x0020, 0x0639, 0x0644, 0x064A, 0x0647, 0x0020,
    0x0648, 0x0633, 0x0644, 0x0645, 0x0020, 0x0631, 0x0626, 0x064A, 0x0020,
    0x0639, 0x0644, 0x0649, 0x0020, 0x062C, 0x0628, 0x0647, 0x062A, 0x0647,
    0x0020, 0x0648, 0x0639, 0x0644, 0x0649, 0x0020, 0x0623, 0x0631, 0x0646,
    0x0628, 0x062A, 0x0647, 0x0020, 0x0623, 0x062B, 0x0631, 0x0020, 0x0637,
    0x064A, 0x0646, 0x0020, 0x0645, 0x0646, 0x0020, 0x0635, 0x0644, 0x0627,
    0x0629, 0x0020, 0x0635, 0x0644, 0x0627, 0x0647, 0x0627, 0x0020, 0x0628,
    0x0627, 0x0644, 0x0646, 0x0627, 0x0633))


def test_the_lului_fused_matn_verifies_via_its_byte_identical_sibling():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    assert db.get_record(conn, "hadith:abudawud:911").text_ar == _ABUDAWUD_911_MATN
    assert db.get_record(conn, "hadith:abudawud:894").text_ar == _ABUDAWUD_911_MATN
    matches = verify_spans(conn, f"«{_ABUDAWUD_911_MATN}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    # Byte-identical duplicate, lowest-id tie-break: 894, not 911 -- the same
    # rule already proven for the al-harb-khud'a duplicate above, applied to
    # a pair this fix round created rather than one the original ingest did.
    assert matches[0].record.id == "hadith:abudawud:894"
    assert matches[0].also_at == ["hadith:abudawud:911"]


# --- Task 12 fix round 2 (R-A3-22): the reusable near-miss detector ---------
#
# `find_near_misses` (openiti.py) is a reusable AUDIT: run a collection's
# shipped marker against a deliberately widened variant of the same marker,
# over the collection's real printed text, and report every record the
# widened variant finds that the shipped one does not. It never changes what
# gets cut -- it only surfaces candidates a human has not yet read.
#
# Both calls below are PINNED to an exact, already-read result, not merely
# asserted empty: an unexpectedly non-empty (or newly-grown) result is
# exactly the class of miss R-A3-22 found by outside review instead of by the
# build, and a test that only asserted "no new near-misses" would go on
# passing the moment a genuinely new one appeared, the same way the shipped
# tight marker went on passing for 4129 and 5239.
#
# The window (one intervening token) is deliberately NOT widened further:
# gaps of 2, 3 and 4 tokens were swept by hand during this fix round and
# added no further genuine record beyond the two already fixed (see the
# task-12 report's fix-round-2 section for the full sweep). A wider window
# than the fix actually needs is exactly the over-cut risk this whole round
# exists to avoid.


def _real_abudawud_units():
    from pathlib import Path

    from sanad_ingest.fetch import fetch_source
    from sanad_ingest.lockfile import load_lockfile
    from sanad_ingest.openiti import parse_openiti

    sources = {s.id: s for s in load_lockfile(Path("ingest/corpus.lock.toml"))}
    locked = sources["openiti-abudawud-jk000142"]
    raw = fetch_source(locked, Path(".corpus-cache"))
    return parse_openiti(raw, collection="abudawud").units


def test_no_unaudited_near_miss_for_the_abudawud_compiler_marker():
    """R-A3-22/R-A3-23's own detector, committed: sweep the real corpus for
    any "<verb> <=4-token-gap> Abu Dawud" the shipped marker set (tight,
    one-token-gap nominative fallback, or the accusative "heard" form) does
    not already catch -- varying BOTH token gap and grammatical case, not
    gap alone. R-A3-22's own version of this test swept gap only and stayed
    green while missing 1234/5239's accusative shape entirely (that is
    exactly the gap R-A3-23 found and this sweep now closes): the sweep
    below tries "qala"/"su'ila"/"sami'tu" against BOTH the nominative
    ("Abu Dawud") and accusative ("Aba Dawud") forms, at every gap 0-4.

    Clean: every record any widening of this sweep finds is already matched
    by the CONFIGURED pattern itself (tight nominative, near-fallback
    nominative, or tight accusative), so `find_near_misses` has nothing left
    to find even at a four-token, both-case sweep.
    """
    import re

    from sanad_ingest.openiti import (
        _ABUDAWUD_COMMENTARY, _ABUDAWUD_COMMENTARY_NEAR, _ABUDAWUD_HEARD,
        _ARABIC, find_near_misses)

    configured = re.compile(
        f"{_ABUDAWUD_COMMENTARY.pattern}|{_ABUDAWUD_COMMENTARY_NEAR.pattern}"
        f"|{_ABUDAWUD_HEARD.pattern}")
    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل|سمعت)(?:\s+\S+){{0,4}}"
        rf"\s+(?:أبو|أبا)\s+داود(?![{_ARABIC}])")
    assert find_near_misses(_real_abudawud_units(), configured, sweep) == []


def test_the_genitive_kunya_never_appears_in_scored_abudawud_text():
    """R-A3-23's explicit guard: "'an"/"min" + GENITIVE kunya ("Abi Dawud")
    names a narrator inside an isnad, not the compiler speaking, and must
    NEVER be treated as commentary -- a case-blind widening of the marker
    would cut genuine isnad, per the controller's own ruling. No code
    implements a genitive pattern (there is nothing to disable), so this
    test is the guard: it fails loudly if a genitive occurrence ever reaches
    scored text (matn or addendum) rather than staying silent in `isnad_ar`,
    which is never scored.

    Measured directly against the real corpus: the genitive form occurs
    exactly 3 times in the raw file -- twice in the `#META#` book title
    ("Sunan Abi Dawud", outside any unit), and once inside a unit
    (hadith:abudawud:507, "... 'an Abi Dawud ...", a narrator reference that
    sits in `isnad_ar`, before the "*" split). Zero occurrences reach
    `matn_ar`/`addenda_ar` for any record.
    """
    import re

    from sanad_ingest.openiti import _ARABIC, full_text_from_parts

    genitive = re.compile(rf"(?<![{_ARABIC}])أبي\s+داود(?![{_ARABIC}])")
    hits = [
        u.record_id for u in _real_abudawud_units()
        if genitive.search(full_text_from_parts(u.matn_ar, u.addenda_ar))
    ]
    assert hits == []


def test_the_abudawud_lului_near_miss_is_found_and_correctly_excluded():
    """The same sweep for `_ABUDAWUD_LULUI`, deliberately NOT widened in the
    shipped marker: `hadith:abudawud:2237` is a genuine near-miss the sweep
    finds ("... qala nasr akhbarani ABU ALI al-hanafi ..."), but "Abu Ali
    al-Hanafi" here is a NARRATOR'S NAME inside a fresh isnad `_split_
    secondary` already cut into this record's own addendum, not Abu Ali
    al-Lu'lu'i's voice -- read by hand, correctly left unmatched. Pinned to
    exactly this one record: the detector finding it and a human reading it
    out is what this test proves, not that the collection has zero near
    misses.
    """
    import re

    from sanad_ingest.openiti import _ABUDAWUD_LULUI, _ARABIC, find_near_misses

    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?قال(?:\s+\S+){{0,4}}\s+أبو\s+علي(?![{_ARABIC}])")
    assert find_near_misses(_real_abudawud_units(), _ABUDAWUD_LULUI, sweep) == [
        "hadith:abudawud:2237",
    ]


# --- Task 13: Jami at-Tirmidhi (R-A3-19) ------------------------------------
#
# Every Arabic literal below is a codepoint tuple read out of the built
# database with a one-off script, per the top-of-file convention, never typed.


def test_tirmidhi_record_count_and_scorability():
    """The measured, lockfile-pinned facts about the fourth hadith collection.

    3,976 is `expected_records` in corpus.lock.toml, the raw file's own
    numbered-unit count -- unlike Abu Dawud, no unit here is a mis-wrapped
    kitab heading.

    80 unscorable and 3,755 cut, measured against the shipped build.
    Al-Tirmidhi's kunya
    ("أبو عيسى") is the SAME verb+kunya construction `_compiler_commentary_
    markers` already builds for Abu Dawud, so `_TIRMIDHI_COMMENTARY`/
    `_TIRMIDHI_COMMENTARY_NEAR`/`_TIRMIDHI_HEARD` are derived from it, not
    hand-written. Two further formulas are Tirmidhi's own and not of the
    (verb, kunya) shape at all -- "wa fi al-bab 'an ..." (Abu Isa's own
    cross-reference to other Companions on the same topic) and "hadha hadith
    ..." (his classical grading verdict, "hasan sahih gharib" and siblings).
    Measurement while building this table found two MORE formulas beyond
    those the task brief named, both caught by deliberately measuring
    related phrases rather than assuming the brief's two were exhaustive:
    "wa fi al-hadith qissa[ tawila]" (18 occurrences, always trailing genuine
    narrative or an already-pointer-class remainder) and "wa hadha asahh"
    (18 occurrences, a bare isnad-comparison verdict that caught two genuine
    instances of the exact fused-commentary defect this ruling exists to
    close: hadith:tirmidhi:1771 and 1778, both left NOT_FOUND before this
    formula was added because their trailing "wa hadha asahh min ..." glued
    onto otherwise-complete, famous matns).

    `_TIRMIDHI_FORMULA` makes a preceding bare "qala" (with no kunya
    repeated) part of the SAME match rather than left dangling on the
    primary, matching every other marker's "cut on what follows" discipline.

    Unscorable moved from 79 to 80 during materialization, not during the
    marker work: `hadith:tirmidhi:2929` is a tafsir report whose isnad says
    the Prophet "recited" and whose matn is verbatim Qur'an 5:45 -- see
    `test_no_scorable_hadith_representation_is_wholly_quranic` above for the
    full account of how `_reject_wholly_quranic_representations` caught what
    the by-hand audit missed.

    `hadith:tirmidhi:2239` additionally needed `NEAR_MISS_CUT_OVERRIDE` for a
    transmitter's (not the compiler's) own dangling aside ("... qala
    Mahmud ..."), the same shape as Abu Dawud's 4129/1234 above.

    Two known, out-of-scope limitations, both pre-existing OpenITI
    transcription facts rather than defects this task introduces:
    - `hadith:tirmidhi:1904-2`'s bab heading leaks into its own display
      metadata (an upstream structural quirk affecting only how the chapter
      title renders for this one occurrence, not its scored text).
    - the "%" (poetry hemistich/caesura marker) and "<...>" (Qur'an
      variant-reading bracket) apparatus, already present un-stripped in
      Bukhari/Muslim/Abu Dawud's own shipped text_ar/addenda_ar (65/30/2
      records carrying a "%" and 5/2/3 carrying "<...>" respectively --
      measured directly against the built database), are a pre-existing,
      cross-collection OpenITI convention, not a Tirmidhi-specific gap
      R-A3-19 is scoped to close. Tirmidhi's own occurrences (10 records
      carrying a "%", 3 carrying "<...>") are left untouched, matching that
      precedent.

    Fix round 1 (R-A3-25) moves cut from 3,755 to 3,757, with unscorable and
    scorable both unchanged. This is a side effect of a Nasai-driven fix, not
    a Tirmidhi-specific change: `_split_compiler_commentary`'s candidate-
    selection logic used to pick the EARLIEST marker match and abort the
    entire cut if that match's head was empty, rather than trying a later
    match -- harmless while every marker's head was always non-empty in
    practice, but this round's new bare-tag markers (`مرسل`/`موقوفا`, which
    legitimately open a matn at position 0) can have an empty head, exposing
    the bug. `hadith:tirmidhi:46` and `566` (`_EDITORIAL_DISCUSSION`) both
    open on "qala Abu 'Isa" -- an empty-head match -- AND contain a second,
    later "qala Abu 'Isa" that is a genuine cut point into al-Tirmidhi's own
    further remark. Before this fix, the abort left both records uncut
    (`addenda_ar IS NULL`); after it, both correctly cut at the second
    occurrence. Both stay `_EDITORIAL_DISCUSSION` -- only shorter, with new
    sha256 pins in `UNSCORABLE["tirmidhi"]`. `249`, the third record in that
    group, was measured and confirmed unchanged.

    Task 16 A2 fix-round moves unscorable from 80 to 93, cut unchanged at
    3,757. The Muslim back-reference/omission sweep, confirmed across all six
    collections, found 13 Tirmidhi records that deliver no narration of their
    own (back-references, editorial remarks about a wording variant, omission
    notes and an isnad-scaffold head: 83, 84, 328, 493, 554, 888, 985, 1389,
    1452, 2261-2, 2824-2, 3799-3, 3832), each hand-read at full length; they
    join `UNSCORABLE["tirmidhi"]`. 80 + 13 = 93. cut is unchanged -- none is a
    newly-cut primary.
    """
    conn = db.connect(DB_PATH)
    total = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='tirmidhi'"
    ).fetchone()[0]
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='tirmidhi'"
        " AND unscorable_reason IS NULL").fetchone()[0]
    unscorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='tirmidhi'"
        " AND unscorable_reason IS NOT NULL").fetchone()[0]
    cut = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='tirmidhi'"
        " AND addenda_ar IS NOT NULL").fetchone()[0]
    # A2 round 4: -2 Tirmidhi primaries now UNSCORABLE. Also absorbs round 3's
    # -2 (updated only in the reps pins at the time): 3883 -> 3881 -> 3879.
    assert (total, scorable, unscorable, cut) == (3976, 3879, 97, 3757)


# hadith:tirmidhi:1, "la taqbalu salatu bi-ghayri tuhurin wa-la sadaqatun min
# ghulul, qala Hammad fi hadithihi illa bi-tuhur" -- "prayer without purity is
# not accepted, nor charity from misappropriated spoils." The collection's own
# first hadith.
_TIRMIDHI_1_MATN = "".join(chr(c) for c in (
    0x0644, 0x0627, 0x0020, 0x062a, 0x0642, 0x0628, 0x0644, 0x0020, 0x0635,
    0x0644, 0x0627, 0x0629, 0x0020, 0x0628, 0x063a, 0x064a, 0x0631, 0x0020,
    0x0637, 0x0647, 0x0648, 0x0631, 0x0020, 0x0648, 0x0644, 0x0627, 0x0020,
    0x0635, 0x062f, 0x0642, 0x0629, 0x0020, 0x0645, 0x0646, 0x0020, 0x063a,
    0x0644, 0x0648, 0x0644, 0x0020, 0x0642, 0x0627, 0x0644, 0x0020, 0x0647,
    0x0646, 0x0627, 0x062f, 0x0020, 0x0641, 0x064a, 0x0020, 0x062d, 0x062f,
    0x064a, 0x062b, 0x0647, 0x0020, 0x0627, 0x0644, 0x0627, 0x0020, 0x0628,
    0x0637, 0x0647, 0x0648, 0x0631,
))

# hadith:tirmidhi:3956, "qad adhhaba Allahu 'ankum 'ubiyyata al-jahiliyyati
# wa-fakhraha bi-l-aba'i, mu'minun taqiyyun wa-fajirun shaqiyyun, wa-l-nasu
# banu Adam wa-Adam min turab" -- Allah's removal of pre-Islamic tribal
# pride; the collection's own last plain-numbered hadith. Its own tail, "wa
# hadha asahh 'indana min al-hadithi al-awwal ...", is one of the two NEW
# markers this round found (`_TIRMIDHI_FORMULA`'s "wa hadha asahh" branch) --
# this record is a genuine, complete matn with a grading-comparison tail cut
# away from it.
_TIRMIDHI_3956_MATN = "".join(chr(c) for c in (
    0x0642, 0x062f, 0x0020, 0x0623, 0x0630, 0x0647, 0x0628, 0x0020, 0x0627,
    0x0644, 0x0644, 0x0647, 0x0020, 0x0639, 0x0646, 0x0643, 0x0645, 0x0020,
    0x0639, 0x0628, 0x064a, 0x0629, 0x0020, 0x0627, 0x0644, 0x062c, 0x0627,
    0x0647, 0x0644, 0x064a, 0x0629, 0x0020, 0x0648, 0x0641, 0x062e, 0x0631,
    0x0647, 0x0627, 0x0020, 0x0628, 0x0627, 0x0644, 0x0622, 0x0628, 0x0627,
    0x0621, 0x0020, 0x0645, 0x0624, 0x0645, 0x0646, 0x0020, 0x062a, 0x0642,
    0x064a, 0x0020, 0x0648, 0x0641, 0x0627, 0x062c, 0x0631, 0x0020, 0x0634,
    0x0642, 0x064a, 0x0020, 0x0648, 0x0627, 0x0644, 0x0646, 0x0627, 0x0633,
    0x0020, 0x0628, 0x0646, 0x0648, 0x0020, 0x0622, 0x062f, 0x0645, 0x0020,
    0x0648, 0x0622, 0x062f, 0x0645, 0x0020, 0x0645, 0x0646, 0x0020, 0x062a,
    0x0631, 0x0627, 0x0628,
))


def test_tirmidhi_hadith_1_is_byte_exact():
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:tirmidhi:1")
    assert rec.text_ar == _TIRMIDHI_1_MATN
    assert rec.unscorable_reason is None


def test_tirmidhi_spot_checked_matns_are_byte_exact():
    """The last plain-numbered record (3956) is the grading-tail spot check:
    its own matn is complete and byte-exact, and its printed text (matn plus
    the "wa hadha asahh ..." tail R-A3-19 cuts into `addenda_ar`) still
    verifies as this exact record."""
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:tirmidhi:3956")
    assert rec.text_ar == _TIRMIDHI_3956_MATN
    assert rec.unscorable_reason is None
    assert rec.addenda_ar, "3956 must carry its cut grading-comparison tail"
    for quoted in (rec.text_ar, rec.text_ar + " " + rec.addenda_ar):
        m = verify_spans(conn, f"«{quoted}»")
        assert len(m) == 1, len(quoted)
        assert m[0].verdict is Verdict.EXACT, len(quoted)
        assert m[0].record.id == "hadith:tirmidhi:3956", len(quoted)


# hadith:tirmidhi:2239, "fataha al-qustantiniyyati ma'a qiyami al-sa'ati" --
# "the conquest of Constantinople [comes] with the establishment of the
# Hour." A transmitter's own dangling aside ("... qala Mahmud, hadha hadith
# gharib ...", Mahmud ibn Ghaylan, not Abu Isa the compiler) sits between
# this genuine matn and the next chain, with no verb-governed marker to
# anchor on -- `NEAR_MISS_CUT_OVERRIDE["tirmidhi"]` is the hand-audited
# second cut that reaches this exact wording, the same shape as Abu Dawud's
# 4129/1234 above.
_TIRMIDHI_2239_MATN = "".join(chr(c) for c in (
    0x0641, 0x062a, 0x062d, 0x0020, 0x0627, 0x0644, 0x0642, 0x0633, 0x0637,
    0x0646, 0x0637, 0x064a, 0x0646, 0x064a, 0x0629, 0x0020, 0x0645, 0x0639,
    0x0020, 0x0642, 0x064a, 0x0627, 0x0645, 0x0020, 0x0627, 0x0644, 0x0633,
    0x0627, 0x0639, 0x0629,
))


def test_the_tirmidhi_near_miss_cut_override_verifies():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:tirmidhi:2239")
    assert rec.text_ar == _TIRMIDHI_2239_MATN
    assert rec.unscorable_reason is None
    m = verify_spans(conn, f"«{rec.text_ar}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    assert m[0].record.id == "hadith:tirmidhi:2239"


# "hadha asahh" caught two genuine defect-class records with no other marker
# present: 1771 ("he forbade predator hides") and 1778 ("she walked with one
# sandal"). Both must verify from their genuine matn alone -- the mandatory
# false-negative direction this task's Step 6a exists to prove.
def _real_tirmidhi_units():
    from pathlib import Path

    from sanad_ingest.fetch import fetch_source
    from sanad_ingest.lockfile import load_lockfile
    from sanad_ingest.openiti import parse_openiti

    sources = {s.id: s for s in load_lockfile(Path("ingest/corpus.lock.toml"))}
    locked = sources["openiti-tirmidhi-jk000140"]
    raw = fetch_source(locked, Path(".corpus-cache"))
    return parse_openiti(raw, collection="tirmidhi").units


def test_the_wa_hadha_asahh_catch_verifies_both_records():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    for record_id in ("hadith:tirmidhi:1771", "hadith:tirmidhi:1778"):
        rec = db.get_record(conn, record_id)
        assert rec.unscorable_reason is None, record_id
        assert rec.addenda_ar, f"{record_id} must be cut"
        assert "أصح" not in rec.text_ar, record_id
        m = verify_spans(conn, f"«{rec.text_ar}»")
        assert len(m) == 1, record_id
        assert m[0].verdict is Verdict.EXACT, record_id
        assert m[0].record.id == record_id, record_id


def test_no_unaudited_near_miss_for_the_tirmidhi_compiler_marker():
    """R-A3-19's own detector, run for Tirmidhi's verb+kunya marker exactly
    as `test_no_unaudited_near_miss_for_the_abudawud_compiler_marker` runs it
    for Abu Dawud's: sweep "qala"/"su'ila"/"sami'tu" against BOTH the
    nominative ("Abu 'Isa") and accusative ("Aba 'Isa") kunya forms, at every
    token gap 0-4, including the two extra formula phrases in `configured` so
    the sweep only reports gaps the shipped marker set does not already
    cover.

    Clean: every record any widening of this sweep finds is already matched
    by the configured pattern (tight nominative, near-fallback nominative, or
    tight accusative), so `find_near_misses` has nothing left to find even at
    a four-token, both-case sweep.
    """
    import re

    from sanad_ingest.openiti import (
        _ARABIC, _TIRMIDHI_COMMENTARY, _TIRMIDHI_COMMENTARY_NEAR,
        _TIRMIDHI_FORMULA, _TIRMIDHI_HEARD, find_near_misses)

    configured = re.compile(
        f"{_TIRMIDHI_COMMENTARY.pattern}|{_TIRMIDHI_COMMENTARY_NEAR.pattern}"
        f"|{_TIRMIDHI_HEARD.pattern}|{_TIRMIDHI_FORMULA.pattern}")
    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل|سمعت)(?:\s+\S+){{0,4}}"
        rf"\s+(?:أبو|أبا)\s+عيسى(?![{_ARABIC}])")
    assert find_near_misses(_real_tirmidhi_units(), configured, sweep) == []


# --- Task 14: Sunan an-Nasai (R-A3-20) ---------------------------------------
#
# Every Arabic literal below is a codepoint tuple read out of the built
# database with a one-off script, per the top-of-file convention, never typed.


def _real_nasai_units():
    from pathlib import Path

    from sanad_ingest.fetch import fetch_source
    from sanad_ingest.lockfile import load_lockfile
    from sanad_ingest.openiti import parse_openiti

    sources = {s.id: s for s in load_lockfile(Path("ingest/corpus.lock.toml"))}
    locked = sources["openiti-nasai-jk000130"]
    raw = fetch_source(locked, Path(".corpus-cache"))
    return parse_openiti(raw, collection="nasai").units


def test_nasai_record_count_and_scorability():
    """The measured, lockfile-pinned facts about the fifth hadith collection.

    5,769 is `expected_records` in corpus.lock.toml, the raw file's own
    numbered-unit count. 53 unscorable and 274 cut, measured against the
    shipped build.

    Fix round 1 (R-A3-25, task-14-review.md Finding 1) moves this to 55
    unscorable and 334 cut. The shipped `_NASAI_FORMULA` covered only
    "khalafahu" (76 occurrences); the review found al-Nasai's comparative-
    isnad critique convention is a FAMILY sharing that exact syntax --
    verb (+ optional wa/fa) + a narrator's name, appended after a complete
    matn with no structural marker -- and measured 49 scorable records
    whose genuine printed matn, quoted without that family's tail, did not
    verify (17 NOT_FOUND, 25 NEAR_MATCH, 7 EXACT to a different record, 0
    EXACT to themselves). `_NASAI_FORMULA` now also covers "wafaqahu"
    (agreement, the direct positive counterpart of "khalafahu"),
    "taba'ahu" (corroboration), "arsalahu" (mursal classification),
    "rafa'ahu" (marfu' classification), "waqafahu"/"awqafahu" (mawquf
    classification), "asnadahu" (musnad classification), bare "mursal"/
    "mawqufan" tags, "hadha al-sawab" (the uncovered half of "al-sawab"),
    and "lam yasma'/lam yarfa'hu" (disclosed non-audition/non-elevation --
    "lam yarfa'hu" was found DURING this fix round by continuing to
    measure past the review's own named list, exactly as required: 7 raw
    occurrences, one of them hadith:nasai:1806, a record the review itself
    named as broken). Every new boundary was read in context, not sampled;
    see `openiti.py`'s own comment block after `_NASAI_FORMULA` for the
    full per-record disposition and `audit_lists.py`'s updated Nasai
    section for every new/moved pin. Measured before/after against a
    `verify_spans` sweep: all 56 records whose text changed and remained
    scorable now verify EXACT (49 to themselves directly, 7 disclosed
    EXACT to a tied sibling record with genuinely identical wording, via
    `also_at` -- the same disclosed-tie mechanism as the 457 already-tied
    Nasai records measured in the original review). `hadith:nasai:400`
    additionally needed a dedicated fix, not a marker: its scored text was
    100% a critic's remark about the narrator Ayyub ("if Ayyub could avoid
    raising a report to the Prophet, he would not raise this one"), while
    the genuine, famous matn ("none of you should urinate in still
    water...") was stranded in `isnad_ar` because the source's own `*`
    chain-transfer marker landed one attribution too early --
    `_fix_nasai_400_isnad_matn_split` re-slices the isnad on the existing,
    vetted `_ATTRIBUTION` regex to recover it; corpus-wide sweep found no
    sibling records sharing this shape.

    Al-Nasai's kunya ("أبو عبد الرحمن") is the SAME verb+kunya construction
    `_compiler_commentary_markers` already builds for Abu Dawud/Tirmidhi, so
    `_NASAI_COMMENTARY`/`_NASAI_COMMENTARY_NEAR`/`_NASAI_HEARD` are derived
    from it, not hand-written -- but this kunya is ALSO Abdullah ibn Umar's
    own kunya, a genuine namesake collision the brief called out by name.
    Sweeping every "قال/سئل/سمعت <=4 tokens> (أبو|أبا) عبد الرحمن" occurrence
    in the real corpus (nominative AND accusative, gap 0-4) finds exactly
    three records the shipped marker correctly leaves uncut -- 597, 3005 and
    3211 -- each a narrator VOCATIVELY ADDRESSING Ibn Umar ("يا أبا عبد
    الرحمن ...") inside direct quoted speech, not al-Nasai's own remark
    (see `test_the_nasai_kunya_near_miss_is_found_and_correctly_excluded`).
    A further, wider sweep for the bare vocative phrase itself (no verb
    anchor at all, so never a `find_near_misses` candidate in the first
    place) finds 8 total occurrences in scored text (860, 891, 3354, 3473,
    5085 in addition to the three above) and confirms none of the eight
    were ever cut into an addendum.

    `_NASAI_FORMULA` (new for this task, not in the brief's own marker
    table) closes a further, substantial hazard: al-Nasai's "خالفه/
    خالفهما/خالفهم" family of comparative-isnad-critique notes ("so-and-so
    narrated it differently"), plus his "هذا حديث/هذا خطأ/والصواب" verdict
    phrases -- the same PHENOMENON as Tirmidhi's grading tail, but a
    different vocabulary, found by measuring related phrases rather than
    assuming the brief's named markers were exhaustive (same discipline
    Task 13's own report used to find "wa hadha asahh"). Every occurrence
    was read by hand; hadith:nasai:3047 is the one genuine exception
    (`COMMENTARY_NEVER_CUT["nasai"]`): "... the Prophet DIFFERED FROM THEM
    [the pagan practice] ..." is a report of the Prophet's own act, the
    same verb in an unrelated sense, immediately followed by a narrative
    connective rather than a narrator's name. Two further records needed
    `NEAR_MISS_CUT_OVERRIDE["nasai"]` for a dangling attribution the tight
    marker's own cut left stranded (5583, 5707 -- the same shape as Abu
    Dawud's 4129/1234 and Tirmidhi's 2239).

    Step 4's editorial-pointer/incipit audit read 54 short pointer-shaped
    candidates in context (isnad and addenda included, not by a length
    rule) and confirmed 53 as UNSCORABLE across four reasons: plain
    pointers (نحوه/مثله/بمثله/وساق الحديث/etc., 42 records), chain-
    continuation phrases that read as matn but are really isnad fragments
    (2), bare isnad-classification tags (مرسل/موقوفا with zero narrative
    content, 4), and truncated opening clauses missing their own predicate
    or ruling (5) -- e.g. hadith:nasai:4787 "من قتل له قتيل مرسل" ("whoever
    has a kinsman killed, mursal") is missing the very ruling ("... he has
    the choice of retaliation or blood-money", present in full at the
    parallel hadith:nasai:4786) that would make it independently
    quotable. The 54th candidate, hadith:nasai:4129 "لا ترجعوا بعدي كفارا
    مرسل" ("do not return to disbelief after me"), was READ and REJECTED
    from this list: it is a genuine, complete, independently-quotable
    imperative with only a trailing "mursal" classification tag, unlike
    the rest of the group -- see `test_the_nasai_mursal_tagged_matn_still_
    verifies` below, the mandatory false-negative-direction proof for
    exactly this judgement call.

    A raw-text measurement note, found independently while pinning this
    table: naive whitespace-based counting of both the genitive kunya and
    "هذا حديث" undercounts, because occurrences split across the source's
    own "~~" line-wrap continuation marker do not match a bare `\\s+`
    pattern. Every count in this docstring and test file was measured
    against `raw.replace("~~", " ")`, not the raw file directly.

    Fix round 2 (R-A3-27) moves this to (5769, 5712, 57, 430): the
    re-review's own probe found six further shapes `_NASAI_FORMULA` did not
    yet cover -- bare "مختصر" (abridged), "لم يذكر <name>" (did not mention),
    "رواه <name>"/"روى" (comparative citation, widened during derivation to
    also cover the bare, object-less form), "اللفظ ل<name>" (the wording is
    so-and-so's), "اختلف على/عليه <name>" (narrators differed over so-and-so
    -- note the irregular على -> عليه inflection under pronoun suffixation),
    and "غير محفوظ" (not preserved). Every occurrence was read in context,
    not sampled; `find_prefix_collisions` (a new, reusable, vocabulary-free
    detector: drop 1-8 trailing tokens from a scorable record's norm and
    check whether the head matches another record's complete text anywhere
    in the corpus) both derived the initial candidate list and, after the
    fix, still finds a 121-record residue -- overwhelmingly ordinary shared-
    head narration families, with a handful of documented, deliberately
    unfixed exceptions (see
    `test_prefix_collision_detector_nasai_residue_is_fully_read`).
    Unscorable rises by 2 (207-2, 353, `_CHAIN_LEAK`: the "لم يذكر" arm
    leaves each with zero narrative content ahead of it). `_fix_nasai_400_
    isnad_matn_split`'s own off-by-one (R-A3-28: `.start()` instead of
    `.end()` on the "قال" attribution, silently dropping that token from
    every field) is also fixed this round; see
    `test_isnad_matn_addenda_conserve_every_byte_of_the_presplit_unit`.
    """
    conn = db.connect(DB_PATH)
    total = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='nasai'"
    ).fetchone()[0]
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='nasai'"
        " AND unscorable_reason IS NULL").fetchone()[0]
    unscorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='nasai'"
        " AND unscorable_reason IS NOT NULL").fetchone()[0]
    cut = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='nasai'"
        " AND addenda_ar IS NOT NULL").fetchone()[0]
    # A2 round 4: -1 Nasai primary now UNSCORABLE. Also absorbs round 3's -3
    # (updated only in the reps pins at the time): 5712 -> 5709 -> 5708.
    assert (total, scorable, unscorable, cut) == (5769, 5708, 61, 430)


# hadith:nasai:1, "idha istayqaza ahadukum min nawmihi fa-la yaghmis yadahu fi
# wadu'ihi hatta yaghsilaha thalathan fa-inna ahadakum la yadri ayna batat
# yaduhu" -- the collection's own first hadith. The source marks NO "*"
# isnad/matn boundary anywhere in this unit (the same pre-existing OpenITI
# transcription fact as hadith:abudawud:208), so per the established
# fallback rule its leading chain is part of the stored, scored text rather
# than invented or silently dropped.
_NASAI_1_MATN = "".join(chr(c) for c in (
    0x623, 0x62e, 0x628, 0x631, 0x646, 0x627, 0x20, 0x642, 0x62a, 0x64a, 0x628, 0x629,
    0x20, 0x628, 0x646, 0x20, 0x633, 0x639, 0x64a, 0x62f, 0x20, 0x642, 0x627, 0x644,
    0x20, 0x62d, 0x62f, 0x62b, 0x646, 0x627, 0x20, 0x633, 0x641, 0x64a, 0x627, 0x646,
    0x20, 0x639, 0x646, 0x20, 0x627, 0x644, 0x632, 0x647, 0x631, 0x64a, 0x20, 0x639,
    0x646, 0x20, 0x623, 0x628, 0x64a, 0x20, 0x633, 0x644, 0x645, 0x629, 0x20, 0x639,
    0x646, 0x20, 0x623, 0x628, 0x64a, 0x20, 0x647, 0x631, 0x64a, 0x631, 0x629, 0x20,
    0x623, 0x646, 0x20, 0x627, 0x644, 0x646, 0x628, 0x64a, 0x20, 0x635, 0x644, 0x649,
    0x20, 0x627, 0x644, 0x644, 0x647, 0x20, 0x639, 0x644, 0x64a, 0x647, 0x20, 0x648,
    0x633, 0x644, 0x645, 0x20, 0x642, 0x627, 0x644, 0x20, 0x625, 0x630, 0x627, 0x20,
    0x627, 0x633, 0x62a, 0x64a, 0x642, 0x638, 0x20, 0x623, 0x62d, 0x62f, 0x643, 0x645,
    0x20, 0x645, 0x646, 0x20, 0x646, 0x648, 0x645, 0x647, 0x20, 0x641, 0x644, 0x627,
    0x20, 0x64a, 0x63a, 0x645, 0x633, 0x20, 0x64a, 0x62f, 0x647, 0x20, 0x641, 0x64a,
    0x20, 0x648, 0x636, 0x648, 0x626, 0x647, 0x20, 0x62d, 0x62a, 0x649, 0x20, 0x64a,
    0x63a, 0x633, 0x644, 0x647, 0x627, 0x20, 0x62b, 0x644, 0x627, 0x62b, 0x627, 0x20,
    0x641, 0x627, 0x646, 0x20, 0x623, 0x62d, 0x62f, 0x643, 0x645, 0x20, 0x644, 0x627,
    0x20, 0x64a, 0x62f, 0x631, 0x649, 0x20, 0x623, 0x64a, 0x646, 0x20, 0x628, 0x627,
    0x62a, 0x62a, 0x20, 0x64a, 0x62f, 0x647,
))


def test_nasai_hadith_1_is_byte_exact():
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:nasai:1")
    assert rec.text_ar == _NASAI_1_MATN
    assert rec.unscorable_reason is None


# hadith:nasai:3899, "sa'altu rafi' ibn khadij ... fa-amma shay'un ma'lumun
# mudmanun fa-la ba'sa bihi" -- Rafi' ibn Khadij's own ruling on leasing
# land. This is the record where the fix round found `_NASAI_FORMULA`
# needed an optional "و" proclitic in addition to its Arabic-letter boundary
# check: "وخالفه" ("and he differed from him") tripped a bare boundary
# lookbehind because "و" is itself an Arabic letter.
#
# R-A3-25/26 fix round (task-14-review.md Finding 1): this constant used to
# END with "... wafaqahu malik ibn anas 'ala isnadihi" ("Malik b. Anas
# agreed with him on its isnad") -- ALSO al-Nasai's own comparative-isnad
# note (the positive counterpart of "khalafahu", cut separately below it),
# not part of Rafi' ibn Khadij's ruling. `_NASAI_FORMULA` now covers
# "wafaqahu" too, so both notes live in `addenda_ar` and this constant ends
# at "... fa-la ba'sa bih".
_NASAI_3899_MATN = "".join(chr(c) for c in (
    0x633, 0x623, 0x644, 0x62a, 0x20, 0x631, 0x627, 0x641, 0x639, 0x20, 0x628, 0x646,
    0x20, 0x62e, 0x62f, 0x64a, 0x62c, 0x20, 0x639, 0x646, 0x20, 0x643, 0x631, 0x627,
    0x621, 0x20, 0x627, 0x644, 0x623, 0x631, 0x636, 0x20, 0x628, 0x627, 0x644, 0x62f,
    0x64a, 0x646, 0x627, 0x631, 0x20, 0x648, 0x627, 0x644, 0x648, 0x631, 0x642, 0x20,
    0x641, 0x642, 0x627, 0x644, 0x20, 0x644, 0x627, 0x20, 0x628, 0x623, 0x633, 0x20,
    0x628, 0x630, 0x644, 0x643, 0x20, 0x625, 0x646, 0x645, 0x627, 0x20, 0x643, 0x627,
    0x646, 0x20, 0x627, 0x644, 0x646, 0x627, 0x633, 0x20, 0x639, 0x644, 0x649, 0x20,
    0x639, 0x647, 0x62f, 0x20, 0x631, 0x633, 0x648, 0x644, 0x20, 0x627, 0x644, 0x644,
    0x647, 0x20, 0x635, 0x644, 0x649, 0x20, 0x627, 0x644, 0x644, 0x647, 0x20, 0x639,
    0x644, 0x64a, 0x647, 0x20, 0x648, 0x633, 0x644, 0x645, 0x20, 0x64a, 0x624, 0x627,
    0x62c, 0x631, 0x648, 0x646, 0x20, 0x639, 0x644, 0x649, 0x20, 0x627, 0x644, 0x645,
    0x627, 0x630, 0x64a, 0x627, 0x646, 0x627, 0x62a, 0x20, 0x648, 0x625, 0x642, 0x628,
    0x627, 0x644, 0x20, 0x627, 0x644, 0x62c, 0x62f, 0x627, 0x648, 0x644, 0x20, 0x641,
    0x64a, 0x633, 0x644, 0x645, 0x20, 0x647, 0x630, 0x627, 0x20, 0x648, 0x64a, 0x647,
    0x644, 0x643, 0x20, 0x647, 0x630, 0x627, 0x20, 0x648, 0x64a, 0x633, 0x644, 0x645,
    0x20, 0x647, 0x630, 0x627, 0x20, 0x648, 0x64a, 0x647, 0x644, 0x643, 0x20, 0x647,
    0x630, 0x627, 0x20, 0x641, 0x644, 0x645, 0x20, 0x64a, 0x643, 0x646, 0x20, 0x644,
    0x644, 0x646, 0x627, 0x633, 0x20, 0x643, 0x631, 0x627, 0x621, 0x20, 0x625, 0x644,
    0x627, 0x20, 0x647, 0x630, 0x627, 0x20, 0x641, 0x644, 0x630, 0x644, 0x643, 0x20,
    0x632, 0x62c, 0x631, 0x20, 0x639, 0x646, 0x647, 0x20, 0x641, 0x623, 0x645, 0x627,
    0x20, 0x634, 0x64a, 0x621, 0x20, 0x645, 0x639, 0x644, 0x648, 0x645, 0x20, 0x645,
    0x636, 0x645, 0x648, 0x646, 0x20, 0x641, 0x644, 0x627, 0x20, 0x628, 0x623, 0x633,
    0x20, 0x628, 0x647,
))


def test_nasai_spot_checked_matn_with_commentary_tail_is_byte_exact():
    """The compiler-commentary spot check: 3899's own matn is complete and
    byte-exact, and its printed text (matn plus the "وافقه مالك بن أنس على
    إسناده وخالفه في لفظه" tail `_NASAI_FORMULA` cuts into `addenda_ar`)
    still verifies as this exact record."""
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:nasai:3899")
    assert rec.text_ar == _NASAI_3899_MATN
    assert rec.unscorable_reason is None
    assert rec.addenda_ar, "3899 must carry its cut comparative-isnad tail"
    for quoted in (rec.text_ar, rec.text_ar + " " + rec.addenda_ar):
        m = verify_spans(conn, f"«{quoted}»")
        assert len(m) == 1, len(quoted)
        assert m[0].verdict is Verdict.EXACT, len(quoted)
        assert m[0].record.id == "hadith:nasai:3899", len(quoted)


# hadith:nasai:3047, "shahidtu 'Umara bi-Jam' fa-qala: inna ahla al-jahiliyyati
# kanu la yufidun hatta tatlu'a al-shamsu ... wa-inna rasula Allahi (s) khalafahum
# thumma afada qabla an tatlu'a al-shamsu" -- "I witnessed Umar at Jam'... and
# the Messenger of God DIFFERED FROM THEM [the pagan practice], then set off
# before sunrise." The one genuine exception `COMMENTARY_NEVER_CUT["nasai"]`
# holds out of every "khalafa*" occurrence: the same verb form, describing the
# Prophet's own act, not al-Nasai's comparative-isnad note.
_NASAI_3047_MATN = "".join(chr(c) for c in (
    0x634, 0x647, 0x62f, 0x62a, 0x20, 0x639, 0x645, 0x631, 0x20, 0x628, 0x62c, 0x645,
    0x639, 0x20, 0x641, 0x642, 0x627, 0x644, 0x20, 0x625, 0x646, 0x20, 0x623, 0x647,
    0x644, 0x20, 0x627, 0x644, 0x62c, 0x627, 0x647, 0x644, 0x64a, 0x629, 0x20, 0x643,
    0x627, 0x646, 0x648, 0x627, 0x20, 0x644, 0x627, 0x20, 0x64a, 0x641, 0x64a, 0x636,
    0x648, 0x646, 0x20, 0x62d, 0x62a, 0x649, 0x20, 0x62a, 0x637, 0x644, 0x639, 0x20,
    0x627, 0x644, 0x634, 0x645, 0x633, 0x20, 0x648, 0x64a, 0x642, 0x648, 0x644, 0x648,
    0x646, 0x20, 0x623, 0x634, 0x631, 0x642, 0x20, 0x62b, 0x628, 0x64a, 0x631, 0x20,
    0x648, 0x625, 0x646, 0x20, 0x631, 0x633, 0x648, 0x644, 0x20, 0x627, 0x644, 0x644,
    0x647, 0x20, 0x635, 0x644, 0x649, 0x20, 0x627, 0x644, 0x644, 0x647, 0x20, 0x639,
    0x644, 0x64a, 0x647, 0x20, 0x648, 0x633, 0x644, 0x645, 0x20, 0x62e, 0x627, 0x644,
    0x641, 0x647, 0x645, 0x20, 0x62b, 0x645, 0x20, 0x623, 0x641, 0x627, 0x636, 0x20,
    0x642, 0x628, 0x644, 0x20, 0x623, 0x646, 0x20, 0x62a, 0x637, 0x644, 0x639, 0x20,
    0x627, 0x644, 0x634, 0x645, 0x633,
))


def test_the_nasai_commentary_never_cut_exception_verifies_whole():
    """3047 must NOT be split -- `COMMENTARY_NEVER_CUT` keeps the Prophet's
    genuine act ("differed from them") inside the scored matn rather than
    stripping it as if it were al-Nasai's own comparative-isnad remark."""
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:nasai:3047")
    assert rec.text_ar == _NASAI_3047_MATN
    assert rec.addenda_ar is None
    assert rec.unscorable_reason is None
    m = verify_spans(conn, f"«{rec.text_ar}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    assert m[0].record.id == "hadith:nasai:3047"


# hadith:nasai:5583, "kullu muskirin haramun wa-kullu muskirin khamrun" --
# "every intoxicant is unlawful and every intoxicant is wine." A dangling
# attribution ("... qala al-Husayn, qala Ahmad, wa-hadha hadithun sahihun")
# the tight marker's own cut left stranded on the primary matn --
# `NEAR_MISS_CUT_OVERRIDE["nasai"]` moves it into the addendum, the same
# shape as Abu Dawud's 4129/1234 and Tirmidhi's 2239.
_NASAI_5583_MATN = "".join(chr(c) for c in (
    0x643, 0x644, 0x20, 0x645, 0x633, 0x643, 0x631, 0x20, 0x62d, 0x631, 0x627, 0x645,
    0x20, 0x648, 0x643, 0x644, 0x20, 0x645, 0x633, 0x643, 0x631, 0x20, 0x62e, 0x645,
    0x631,
))

# hadith:nasai:5707, "kana al-nabidhu alladhi yashrabuhu 'Umar ibn al-Khattab
# qad khullila" -- "the nabidh Umar ibn al-Khattab used to drink had
# fermented [into vinegar]." Same shape as 5583: a dangling "wa-mimma
# yadullu 'ala sihhati hadha hadithu al-Sa'ib" left stranded by the tight
# cut, where "hadha" is grammatically the subject of the DANGLING clause,
# not the start of the remark -- `NEAR_MISS_CUT_OVERRIDE["nasai"]` again.
_NASAI_5707_MATN = "".join(chr(c) for c in (
    0x643, 0x627, 0x646, 0x20, 0x627, 0x644, 0x646, 0x628, 0x64a, 0x630, 0x20, 0x627,
    0x644, 0x630, 0x64a, 0x20, 0x64a, 0x634, 0x631, 0x628, 0x647, 0x20, 0x639, 0x645,
    0x631, 0x20, 0x628, 0x646, 0x20, 0x627, 0x644, 0x62e, 0x637, 0x627, 0x628, 0x20,
    0x642, 0x62f, 0x20, 0x62e, 0x644, 0x644,
))


def test_the_nasai_near_miss_cut_overrides_verify():
    """5707 is unique. 5583's own matn ("kullu muskirin haramun wa-kullu
    muskirin khamrun") is al-Mujtaba's own repeated-near-identical-matn
    convention (the famous "every intoxicant is unlawful" hadith, printed
    four times over different chains: 5582, 5583, 5586, 5701) -- the tie
    is a genuine fact about the source, not a defect, so this asserts the
    match REACHES 5583 through `also_at` rather than that the engine's
    tie-break happens to select 5583 itself, the same idiom
    `test_a_famous_short_matn_verifies_in_both_directions` uses above."""
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    for record_id, expected in (
        ("hadith:nasai:5583", _NASAI_5583_MATN),
        ("hadith:nasai:5707", _NASAI_5707_MATN),
    ):
        rec = db.get_record(conn, record_id)
        assert rec.text_ar == expected, record_id
        assert rec.unscorable_reason is None, record_id
        assert rec.addenda_ar, f"{record_id} must carry its cut dangling tail"
        m = verify_spans(conn, f"«{rec.text_ar}»")
        assert len(m) == 1, record_id
        assert m[0].verdict is Verdict.EXACT, record_id
        assert rec.id in [m[0].record.id] + list(m[0].also_at), record_id


def test_the_nasai_repeated_matn_tie_discloses_all_four_occurrences():
    """al-Mujtaba's own repeated-near-identical-matn convention, checked
    directly: "kullu muskirin haramun wa-kullu muskirin khamrun" is printed
    four times (5582, 5583, 5586, 5701) over different chains, one of which
    (5583) also carries al-Nasai's own authentication remark cut into its
    addendum. A quotation of the bare matn must disclose all four via
    `also_at`, not silently pick one and hide the rest."""
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:nasai:5583")
    m = verify_spans(conn, f"«{rec.text_ar}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    tied = sorted([m[0].record.id] + list(m[0].also_at))
    assert tied == [
        "hadith:nasai:5582", "hadith:nasai:5583",
        "hadith:nasai:5586", "hadith:nasai:5701",
    ]


# Codepoints read out of the printed source (never retyped glyphs), per the
# top-of-file convention: "la tarji'u ba'di kuffaran" ("do not return to
# disbelief after me [by killing one another]"), WITHOUT the trailing
# "mursal" classification tag.
_NASAI_4129_MATN = "".join(chr(c) for c in (
    0x0644, 0x0627, 0x0020, 0x062a, 0x0631, 0x062c, 0x0639, 0x0648,
    0x0627, 0x0020, 0x0628, 0x0639, 0x062f, 0x064a, 0x0020, 0x0643,
    0x0641, 0x0627, 0x0631, 0x0627,
))


def test_the_nasai_mursal_tagged_matn_still_verifies():
    """hadith:nasai:4129 -- READ and REJECTED from `UNSCORABLE["nasai"]`
    during the Step 4 audit because it is a genuine, complete,
    independently-quotable imperative, unlike the 53 (now 55) confirmed
    pointer/chain-leak/classification-tag/truncated-opening records that
    share its short length and trailing "mursal" vocabulary. This is the
    mandatory false-negative-direction proof for that judgement call: if
    the boundary were drawn wrong, this hadith would silently stop
    verifying.

    R-A3-25/26 (task-14-review.md Finding 1 and 2): the ORIGINAL version of
    this test quoted `rec.text_ar` -- the stored string -- which at the time
    still carried the fused "... مرسل" tail, so the test was asserting that
    the broken text verified against itself: trivially true, and incapable
    of catching the very defect it claimed to guard (the printed matn, minus
    that tail, was actually NOT_FOUND at score 0.800 before this fix round).
    This version quotes `_NASAI_4129_MATN`, an independent literal derived
    from the printed source, not from whatever the pipeline currently
    happens to store -- so a future regression that re-fuses the tail into
    `text_ar` would still be caught here."""
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:nasai:4129")
    assert rec.unscorable_reason is None
    assert rec.text_ar == _NASAI_4129_MATN
    m = verify_spans(conn, f"«{_NASAI_4129_MATN}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    assert m[0].record.id == "hadith:nasai:4129"


def test_no_unaudited_near_miss_for_the_nasai_compiler_marker():
    """R-A3-20's own detector, run for Nasai's verb+kunya marker exactly as
    the Abu Dawud/Tirmidhi tests run it: sweep "qala"/"su'ila"/"sami'tu"
    against BOTH the nominative ("Abu Abd al-Rahman") and accusative ("Aba
    Abd al-Rahman") kunya forms, at every token gap 0-4, including
    `_NASAI_FORMULA` in `configured` so the sweep only reports gaps the
    shipped marker set does not already cover.

    NOT empty, unlike Abu Dawud/Tirmidhi's own version of this test: this
    kunya is ALSO Ibn Umar's, and three records (597, 3005, 3211) are
    genuine near-misses correctly excluded -- a narrator vocatively
    addressing Ibn Umar by his kunya inside quoted speech ("يا أبا عبد
    الرحمن ..."), not al-Nasai's own remark. Pinned to exactly these three
    ids, the same discipline as
    `test_the_abudawud_lului_near_miss_is_found_and_correctly_excluded`:
    the detector finding them and a human reading them out is what this
    test proves, not that the collection has zero near misses.
    """
    import re

    from sanad_ingest.openiti import (
        _ARABIC, _NASAI_COMMENTARY, _NASAI_COMMENTARY_NEAR, _NASAI_FORMULA,
        _NASAI_HEARD, find_near_misses)

    configured = re.compile(
        f"{_NASAI_COMMENTARY.pattern}|{_NASAI_COMMENTARY_NEAR.pattern}"
        f"|{_NASAI_HEARD.pattern}|{_NASAI_FORMULA.pattern}")
    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل|سمعت)(?:\s+\S+){{0,4}}"
        rf"\s+(?:أبو|أبا)\s+عبد\s+الرحمن(?![{_ARABIC}])")
    assert find_near_misses(_real_nasai_units(), configured, sweep) == [
        "hadith:nasai:3005",
        "hadith:nasai:3211",
        "hadith:nasai:597",
    ]


def test_no_unaudited_near_miss_for_the_nasai_comparative_isnad_family():
    """R-A3-25's root-cause fix for task-14-review.md Finding 3: every
    `find_near_misses` call site Task 12-14 shipped swept the NAME-ANCHORED
    axis only (varying token gap, then grammatical case, against the
    compiler's own kunya). But `_NASAI_FORMULA`'s comparative-isnad verbs
    (khalafahu, wafaqahu, taba'ahu, arsalahu, rafa'ahu, waqafahu, awqafahu,
    asnadahu) are NAME-FREE -- a bare verb plus an attached object pronoun,
    no narrator name anywhere in the pattern -- so a sweep built for the
    kunya axis structurally cannot see a gap in this family. That blind spot
    is exactly how Finding 1's 49 broken records went undetected: the family
    was under-covered (only "khalafahu" shipped) and nothing swept for its
    siblings.

    The name-free axis this family can be widened along is NOT token gap (there
    is no name to vary the gap to) -- it is the attached pronoun's own
    morphology: every verb above is shipped only in its 3rd-person-masculine-
    singular object form ("-ahu"). This sweep widens every root to also match
    3rd-person-feminine-singular ("-ha"), dual ("-huma"/"-ha" precedes hidden
    -- feminine dual is spelled identically to fem. singular in this table, so
    "-ha" covers both), and plural object forms ("-hum", "-hu" via alif or
    waw connector), then subtracts everything `configured` already covers.

    Not empty, same discipline as the kunya-axis test above: 5 hits, all
    read in context and confirmed genuine narrative, not al-Nasai's own
    voice -- "rafa'ahuma" ("he raised THEM [his hands]", prayer posture,
    1059/1265/878) and "rafa'aha" (same, a nursing mother lifting her child
    up out of prostration, 1204) never mean "he raised the report to the
    Prophet [marfu']" in these positions; "fa-arsalahum" (632) is "so he
    RELEASED the people [from the gathering]", not "transmitted it mursal".
    None of these forms is a suffix `_NASAI_FORMULA` matches (it accepts
    only bare "-hu", plus "-huma"/"-hum" on khalafahu/wafaqahu specifically,
    where those ARE measured to occur in the critique sense), so none is at
    risk of being wrongly cut; this test exists so that if a future edit
    widens a verb's suffix class, the person doing it re-reads these 5
    before doing so, exactly like the 597/3005/3211 kunya near-misses above.
    """
    import re

    from sanad_ingest.openiti import (
        _ARABIC, _NASAI_COMMENTARY, _NASAI_COMMENTARY_NEAR, _NASAI_FORMULA,
        _NASAI_HEARD, find_near_misses)

    configured = re.compile(
        f"{_NASAI_COMMENTARY.pattern}|{_NASAI_COMMENTARY_NEAR.pattern}"
        f"|{_NASAI_HEARD.pattern}|{_NASAI_FORMULA.pattern}")
    roots = "|".join((
        "خالف", "وافق", "تابع", "أرسل", "رفع", "وقف", "أوقف", "أسند"))
    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:{roots})(?:ه|ها|هما|هم|وه|اه)(?![{_ARABIC}])")
    assert find_near_misses(_real_nasai_units(), configured, sweep) == [
        "hadith:nasai:1059",
        "hadith:nasai:1204",
        "hadith:nasai:1265",
        "hadith:nasai:632",
        "hadith:nasai:878",
    ]


def test_the_genitive_kunya_never_appears_in_scored_nasai_text():
    """R-A3-20's explicit guard: "'an"/"min" + GENITIVE kunya ("Abi Abd
    al-Rahman") names a narrator inside an isnad, not the compiler
    speaking, and must NEVER be treated as commentary. No code implements
    a genitive pattern (there is nothing to disable): the safety here is
    by construction, not by this test's detection, which is why the
    regex below deliberately does NOT need to catch every raw form.

    Measured directly against the real corpus (with the source's own "~~"
    line-wrap marker replaced by a space first -- a naive `\\s+`-based
    count undercounts occurrences split across a line wrap): the genitive
    form occurs 19 times in the raw file (a first pass with a strict,
    no-proclitic-attached boundary found only 18 -- the 19th carries the
    single-letter proclitic "li-" attached directly, "li-abi 'Abd
    al-Rahman", which a same-class boundary bug would have missed the
    same way `_NASAI_FORMULA`'s own "[wf]?" proclitic fix was needed
    for). 18 of the 19 sit inside isnad chains and never reach scored
    text. The 19th, `hadith:nasai:1856`, is different and is EXPECTED to
    reach `matn_ar`: it is 'A'isha's own reported speech ("may Allah
    forgive Abu 'Abd al-Rahman", addressing Ibn 'Umar by his kunya after
    correcting a report of his), genuine narrative content, not the
    compiler's voice. This is safe regardless of proclitic form because
    `_compiler_commentary_markers` never builds a genitive pattern at all
    -- "'abi'" cannot match the "'abu'"/"'aba'" every marker requires, so
    no marker can ever fire on it whether or not a proclitic is attached.
    The strict (no-proclitic) regex below therefore correctly finds no
    hits: it is checking that the KUNYA-AS-COMMENTARY hazard never
    reaches scored text, not that the genitive string itself never does
    (1856 shows it legitimately can, as narrative).
    """
    import re

    from sanad_ingest.openiti import _ARABIC, full_text_from_parts

    genitive = re.compile(rf"(?<![{_ARABIC}])أبي\s+عبد\s+الرحمن(?![{_ARABIC}])")
    hits = [
        u.record_id for u in _real_nasai_units()
        if genitive.search(full_text_from_parts(u.matn_ar, u.addenda_ar))
    ]
    assert hits == []


def test_the_nasai_vocative_kunya_never_leaks_into_an_addendum():
    """The wider, verb-independent guard behind the near-miss test above:
    "يا أبا عبد الرحمن" (vocatively addressing Ibn Umar) occurs 8 times in
    scored Nasai text -- the 3 near-miss records plus 5 more with no verb
    anchor within 4 tokens (860, 891, 3354, 3473, 5085), so never even
    candidates for `find_near_misses`. None of the 8 have ever been cut
    into `addenda_ar` by any mechanism.
    """
    import re

    from sanad_ingest.openiti import _ARABIC, full_text_from_parts

    vocative = re.compile(rf"(?<![{_ARABIC}])يا\s+أبا\s+عبد\s+الرحمن(?![{_ARABIC}])")
    units = _real_nasai_units()
    hits = [u.record_id for u in units
            if vocative.search(full_text_from_parts(u.matn_ar, u.addenda_ar))]
    assert sorted(hits) == [
        "hadith:nasai:3005", "hadith:nasai:3211", "hadith:nasai:3354",
        "hadith:nasai:3473", "hadith:nasai:5085", "hadith:nasai:597",
        "hadith:nasai:860", "hadith:nasai:891",
    ]
    leaked = [u.record_id for u in units
              if u.addenda_ar and vocative.search(u.addenda_ar)]
    assert leaked == []


# --- R-A3-24: the committed DB must match a fresh build, row for row -------
#
# This is the guard the fix round found missing. Task 13's `_EDITORIAL_
# DISCUSSION` wording fix (a collection-agnostic reason string, corrected
# from a hardcoded "Abu Dawud's own numbered remark") landed in
# audit_lists.py, but `data/sanad-quran.db` was committed from a build run
# BEFORE that edit -- nothing re-ran `sanad-ingest build` afterward. Five
# records (hadith:abudawud:2225, hadith:abudawud:3099, hadith:tirmidhi:46,
# hadith:tirmidhi:249, hadith:tirmidhi:566) shipped the OLD, factually-wrong
# string on Tirmidhi records -- the exact user-facing misattribution the fix
# was written to close. No existing test caught it: none asserted the
# literal reason string.
#
# The CI step meant to catch exactly this drift
# (.github/workflows/ci.yml, "Verify the committed corpus matches a fresh
# build") calls `db.corpus_fingerprint` -- which reads `record_variants`
# and `records_fts` -- against the SOURCE-only committed DB, which has
# neither table. Confirmed directly: it raises `sqlite3.OperationalError:
# no such table: record_variants` rather than comparing anything. That gate
# has not functioned since the Stage A3 source/materialized split.
#
# `corpus_source_fingerprint` itself is not the gap: it covers every column
# a source DB carries, `unscorable_reason` included (checked directly
# against `SOURCE_FINGERPRINT_TABLES` in api/sanad/corpus/db.py -- built
# from `_RECORD_COLS` minus only the four derived norm/hash columns, so
# `unscorable_reason` is in scope). But a hash only ever says "something
# differs"; this test says what, which is why it would have caught the
# defect immediately rather than after a review asked "does the DB really
# match the code."
def test_the_committed_db_matches_a_fresh_build_row_for_row():
    from pathlib import Path
    import tempfile

    from sanad_ingest.build import build_corpus

    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = Path(tmp) / "fresh.db"
        build_corpus(Path("ingest/corpus.lock.toml"), fresh_path,
                     Path(".corpus-cache"))
        fresh = db.connect(str(fresh_path))
        committed = db.connect("data/sanad-quran.db")
        fresh_rows = {r["id"]: dict(r) for r in
                      fresh.execute("SELECT * FROM records").fetchall()}
        committed_rows = {r["id"]: dict(r) for r in
                          committed.execute("SELECT * FROM records").fetchall()}
        assert set(fresh_rows) == set(committed_rows), (
            f"record id sets differ: {set(fresh_rows) ^ set(committed_rows)}")
        mismatches = {}
        for rid, committed_row in committed_rows.items():
            fresh_row = fresh_rows[rid]
            diff = {col: (committed_row[col], fresh_row[col])
                    for col in committed_row
                    if committed_row[col] != fresh_row[col]}
            if diff:
                mismatches[rid] = diff
        assert mismatches == {}, (
            f"{len(mismatches)} record(s) in the committed DB do not match a "
            f"fresh build from the same lockfile, cache and code -- the "
            f"committed artifact is stale: {mismatches}")


import pytest as _pytest


@_pytest.mark.parametrize("source_id,collection", [
    ("openiti-bukhari-jk000110", "bukhari"),
    ("openiti-muslim-jk000109", "muslim"),
    ("openiti-abudawud-jk000142", "abudawud"),
    ("openiti-tirmidhi-jk000140", "tirmidhi"),
    ("openiti-nasai-jk000130", "nasai"),
    ("openiti-ibnmaja-jk000141", "ibnmajah"),
])
def test_isnad_matn_addenda_conserve_every_byte_of_the_presplit_unit(
        source_id, collection):
    """R-A3-28's corpus-wide byte-conservation invariant.

    `isnad_ar` + `matn_ar` + `addenda_ar` must reconstruct the same text as
    the unit's own `isnad`/`matn` pair BEFORE any split function
    (`_split_secondary`, `_apply_cut_override`, `_split_compiler_commentary`,
    `_split_lului_commentary`, `_split_heard_commentary`,
    `_fix_nasai_400_isnad_matn_split`) touched it -- captured directly from
    inside `parse_openiti` via `on_presplit`, not re-derived from the raw
    file, so this is independent of every one of those functions' own
    internal logic, not a self-comparison that could share their bug.

    This is exactly the invariant `_fix_nasai_400_isnad_matn_split`'s own
    off-by-one broke (R-A3-28): `new_isnad = isnad[: attributions[1].start()]`
    silently dropped the "قال" token attributions[1] itself matched -- present
    in neither `new_isnad` nor `new_matn`. No existing test could see it: the
    row-for-row guard only compares committed output to a fresh rebuild, and
    both share the same bug. Fixed by slicing to `.end()` instead; this test
    is the guard against a repeat, for this function and any future one.

    Whitespace is the only tolerance: every string here was already
    `_clean`-ed before capture, collapsing internal whitespace runs to a
    single space, so joining pieces back together can only ever disagree by
    how many separator spaces land between them, never by content.
    """
    import re
    from pathlib import Path

    from sanad_ingest.fetch import fetch_source
    from sanad_ingest.lockfile import load_lockfile
    from sanad_ingest.openiti import full_text_from_parts, parse_openiti

    sources = {s.id: s for s in load_lockfile(Path("ingest/corpus.lock.toml"))}
    raw = fetch_source(sources[source_id], Path(".corpus-cache"))

    presplit: dict[str, tuple[str | None, str]] = {}
    parsed = parse_openiti(raw, collection=collection,
                           on_presplit=lambda rid, isnad, matn:
                               presplit.__setitem__(rid, (isnad, matn)))

    def squash(s: str) -> str:
        s = re.sub(r"\s+", " ", s).strip()
        if collection == "tirmidhi":
            # The ONE other intentional, documented content removal in the
            # whole pipeline: `_strip_reference_numbers` deletes Shakir's own
            # bracketed cross-reference numbers ("[4]", "see hadith N") from
            # the primary matn -- editorial apparatus of the PRINTED EDITION,
            # not the hadith's own text, exactly like every marker this fix
            # round covers, just with its own dedicated function instead of
            # `_NASAI_FORMULA`'s table. Stripped from both sides here so this
            # test does not misreport tirmidhi's own well-understood,
            # already-tested behaviour as a NEW conservation violation.
            s = re.sub(r"\[\d+\]", "", s)
            s = re.sub(r"\s+", " ", s).strip()
        if collection == "ibnmajah":
            # The other intentional, documented content removal this fix
            # round adds: `_strip_stray_asterisk` deletes a literal "*" this
            # edition's own nested-repeat convention leaves in the primary
            # matn after `NEVER_CUT["ibnmajah"]` keeps hadith:ibnmajah:2131
            # whole -- see that function's own docstring. Stripped from both
            # sides here for the same reason as tirmidhi's brackets above.
            s = re.sub(r"\*", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
        return s

    checked = 0
    for u in parsed.units:
        pre_isnad, pre_matn = presplit[u.record_id]
        before = squash(pre_matn if pre_isnad is None
                        else f"{pre_isnad} {pre_matn}")
        reassembled = full_text_from_parts(u.matn_ar, u.addenda_ar)
        after = squash(reassembled if u.isnad_ar is None
                       else f"{u.isnad_ar} {reassembled}")
        assert before == after, (
            f"{u.record_id}: presplit {before!r} != reconstructed {after!r}")
        checked += 1
    assert checked == len(parsed.units)


_NASAI_PREFIX_COLLISION_RESIDUE = [
    "hadith:nasai:1207", "hadith:nasai:1361", "hadith:nasai:1375",
    "hadith:nasai:1613", "hadith:nasai:1668", "hadith:nasai:1671",
    "hadith:nasai:1693", "hadith:nasai:1729", "hadith:nasai:1740",
    "hadith:nasai:1754", "hadith:nasai:1973", "hadith:nasai:2016",
    "hadith:nasai:2025", "hadith:nasai:2134", "hadith:nasai:2186",
    "hadith:nasai:221", "hadith:nasai:2260", "hadith:nasai:231",
    "hadith:nasai:233", "hadith:nasai:2374", "hadith:nasai:2377",
    "hadith:nasai:2773", "hadith:nasai:2788", "hadith:nasai:2789",
    "hadith:nasai:2847", "hadith:nasai:2848", "hadith:nasai:2849",
    "hadith:nasai:2869", "hadith:nasai:2941", "hadith:nasai:3177",
    "hadith:nasai:3241", "hadith:nasai:3297", "hadith:nasai:3335",
    "hadith:nasai:338", "hadith:nasai:339", "hadith:nasai:3536",
    "hadith:nasai:3574", "hadith:nasai:3575", "hadith:nasai:3576",
    "hadith:nasai:3577", "hadith:nasai:3590", "hadith:nasai:37",
    "hadith:nasai:3710", "hadith:nasai:3733", "hadith:nasai:3735",
    "hadith:nasai:3774", "hadith:nasai:3812", "hadith:nasai:3834",
    "hadith:nasai:3835", "hadith:nasai:3836", "hadith:nasai:3837",
    "hadith:nasai:3838", "hadith:nasai:3839", "hadith:nasai:3840",
    "hadith:nasai:3841", "hadith:nasai:3847", "hadith:nasai:3850",
    "hadith:nasai:3851", "hadith:nasai:3879", "hadith:nasai:3884",
    "hadith:nasai:3885", "hadith:nasai:3909", "hadith:nasai:3910",
    "hadith:nasai:3921", "hadith:nasai:3976", "hadith:nasai:4049",
    "hadith:nasai:411", "hadith:nasai:412", "hadith:nasai:4125",
    "hadith:nasai:4126", "hadith:nasai:4127", "hadith:nasai:4175",
    "hadith:nasai:4277", "hadith:nasai:4279", "hadith:nasai:4334",
    "hadith:nasai:4342", "hadith:nasai:4420", "hadith:nasai:4447",
    "hadith:nasai:4480", "hadith:nasai:4482", "hadith:nasai:4493",
    "hadith:nasai:4495", "hadith:nasai:4519", "hadith:nasai:4521",
    "hadith:nasai:4524", "hadith:nasai:4535", "hadith:nasai:4537",
    "hadith:nasai:4568", "hadith:nasai:4634",
    "hadith:nasai:4668", "hadith:nasai:4673", "hadith:nasai:4691",
    "hadith:nasai:4736", "hadith:nasai:48", "hadith:nasai:4908",
    "hadith:nasai:4917", "hadith:nasai:4918", "hadith:nasai:4919",
    "hadith:nasai:4922", "hadith:nasai:4923", "hadith:nasai:4938",
    "hadith:nasai:4939", "hadith:nasai:4967", "hadith:nasai:497",
    "hadith:nasai:4996", "hadith:nasai:5094", "hadith:nasai:5096",
    "hadith:nasai:5166", "hadith:nasai:5248", "hadith:nasai:534",
    "hadith:nasai:5348", "hadith:nasai:5499", "hadith:nasai:553",
    "hadith:nasai:5548", "hadith:nasai:555", "hadith:nasai:5582",
    "hadith:nasai:5583", "hadith:nasai:5585", "hadith:nasai:5586",
    "hadith:nasai:5591", "hadith:nasai:5621", "hadith:nasai:5622",
    "hadith:nasai:5629", "hadith:nasai:5630", "hadith:nasai:5632",
    "hadith:nasai:5634", "hadith:nasai:5637", "hadith:nasai:5649",
    "hadith:nasai:5678", "hadith:nasai:5699", "hadith:nasai:5701",
    "hadith:nasai:605", "hadith:nasai:619", "hadith:nasai:687",
    "hadith:nasai:7", "hadith:nasai:736", "hadith:nasai:911",
    "hadith:nasai:996",
]


def test_prefix_collision_detector_nasai_residue_is_fully_read():
    """R-A3-27 item 1/4: `find_prefix_collisions`, run corpus-wide and
    gated as a test for al-Nasai ONLY.

    `find_prefix_collisions` is a LOWER BOUND (see its own docstring): a
    fused editorial tail is only findable this way if some other record
    happens to preserve the same head in full elsewhere in the corpus. This
    is exactly how the re-review's own probe found the six shapes this fix
    round covers -- dropping 1-8 trailing tokens from a scorable record and
    checking whether the head matches another record's complete text,
    corpus-wide.

    Run here against every collection (reported below, not asserted -- see
    the printed per-collection breakdown this test emits on failure) but
    PINNED only for nasai: bukhari/muslim/abudawud/tirmidhi/quran are
    Task 16's own scope (they were never audited by this fix round, and
    gating them here would fail immediately on collections nobody has read
    yet -- exactly the ruling's own instruction not to turn this on
    corpus-wide before Task 16 clears them).

    Every one of the 121 nasai ids below was read in context (fix round 2's
    own report has the full disposition). The overwhelming majority are the
    ordinary, correctly-scored feature of hadith literature -- multiple
    narrations of the same report sharing a head and differing only at the
    edges (e.g. the 3833 oath-expiation family: 3812/3834-3841/3847/3850/
    3851; the 4916 family: 4917-4923; the 5624 vessel-prohibition family:
    5629/5630/5632/5637/5649/5678). A handful are GENUINE residual defects
    this round's six named shapes do not cover, deliberately left unfixed
    and documented rather than silently dropped:

      - hadith:nasai:1207 ("زاد بن المثنى في الصلاة"): the "زاد <name> في
        حديثه" family the coordinator's own ruling named "mixed" and
        excluded this round (see openiti.py's comment on hadith:nasai:1838,
        where the same marker introduces substantial genuine continuing
        Prophetic speech -- cutting it in general is unsafe, even though
        this ONE occurrence, read alone, would be a clean cut).
      - hadith:nasai:3733 ("قال عطاء هو للآخر"), 4420 ("وقال قتيبة في
        حديثه فأكلنا لحمه"), 4938 ("وزعم أن عروة قال المجن أربعة دراهم"),
        5591 ("قال قتيبة عن النبي صلى الله عليه وسلم"), 3297 ("قال سمعت
        هذا من جابر"): a bare "قال <name> <remark>" shape with no
        anchoring vocabulary at all -- structurally the same hazard
        `_apply_cut_override`'s own docstring already rejected a generic
        fix for (a one-hop nested-attribution walk that also fired on
        454/3988's genuine narrative content). Out of scope for this
        round's six named shapes; left for a dedicated future pass.

    `hadith:nasai:5039` -- found while deriving the "روى" arm above, not by
    this detector (it produces no collision) -- is the one record this fix
    round protected with `COMMENTARY_NEVER_CUT` precisely because a bare
    marker match landing at the wrong position is worse than no match.

    Task 15 (Ibn Majah) widens this list from 121 to 142 ids, with NO
    removals: adding a sixth collection supplies 21 new completions this
    detector could not see before -- a Nasai record's own head, with 1-8
    trailing tokens dropped, now matches an Ibn Majah record's complete text
    (e.g. hadith:nasai:1668's "salat al-layl mathna mathna fa-idha khifta
    al-subha fa-awtir bi-wahida" against hadith:ibnmajah:1319's shorter
    "salat al-layl mathna mathna"). Every one of the 21 was read: the same
    ordinary, correctly-scored feature the other 121 already document --
    shorter and longer narrations of the same report sharing a head -- not a
    new editorial-leak shape. Ibn Majah's own residue (63 hits, all against
    the corpus as a whole) is measured and reported in the task's own review
    report but deliberately NOT pinned here or given its own gate, for the
    same reason bukhari/muslim/abudawud/tirmidhi/quran are not: it was read
    only at sample density (roughly 55 of 63), not exhaustively the way this
    round's six named shapes were audited for Nasai, so gating it now would
    freeze an under-read list rather than a fully-read one.

    Task 16 A2 round 5 (content-mass net) narrows this list from 142 to 138,
    with NO additions: four Nasai residues (951, 986, 987, 4598) lose their
    completion partner because it was pinned UNSCORABLE this round. All four
    completed against the same partner, bukhari:4745 ("sami'tu al-nabi [saw]"),
    a pure speech-frame pointer with no matn (see
    audit_lists._A2R5_CONTENT_MASS_POINTERS); once it leaves the scorable set
    the four heads no longer match any complete record. The four Nasai records
    themselves stay scorable -- they carry content past the shared frame -- they
    simply no longer trip this corpus-wide detector.
    """
    from sanad_ingest.openiti import find_prefix_collisions

    conn = db.connect(str(MATERIALIZED_DB))
    rows = conn.execute(
        "SELECT id, norm_standard FROM records WHERE norm_standard IS NOT "
        "NULL AND (kind != 'hadith' OR unscorable_reason IS NULL)"
    ).fetchall()
    norms = {r["id"]: r["norm_standard"] for r in rows if r["norm_standard"]}

    hits = find_prefix_collisions(norms)
    from collections import Counter
    per_collection = Counter(
        rid.split(":")[1] if rid.startswith("hadith:") else "quran"
        for rid, _dropped, _other in hits)

    nasai_hits = sorted(rid for rid, _d, _o in hits
                        if rid.startswith("hadith:nasai:"))
    assert nasai_hits == _NASAI_PREFIX_COLLISION_RESIDUE, (
        f"al-Nasai's prefix-collision residue changed -- a new hit needs "
        f"reading before this pin is widened, or a fixed one needs "
        f"removing from it. Per-collection counts: {dict(per_collection)}")


# --- A2 round 4 (Task 16): the complete audited partition of the bounded
# reference/deferral/omission population, pinned at the WIDE threshold.
#
# Round 3 pinned a thirteen-id residue band at the tuned default
# max_residue=2. That enshrined the threshold as the correctness boundary --
# the exact escape the class had used six times. Round 4 moves safety off the
# threshold entirely: the whole bounded population (W: find_pure_pointers at an
# effectively infinite residue cap, 584 records; O: an INDEPENDENT editorial
# omission/comparison sweep, 607 records) was hand-audited one record at a time
# in task-16-A2round4-audit.md and split into POINTER (unscorable) and KEEP
# (scorable). The two gates below pin that partition: re-admitting any audited
# pointer, or over-marking any audited keep, turns one of them RED. The lists
# are long BECAUSE the safety is the exhaustive partition, not a band.
_A2R4_AUDITED_POINTERS = [
    "hadith:abudawud:2011", "hadith:abudawud:3355", "hadith:abudawud:3379",
    "hadith:abudawud:3945", "hadith:abudawud:3959", "hadith:muslim:1162-4",
    "hadith:muslim:1178-3", "hadith:muslim:127-3", "hadith:muslim:1306-3",
    "hadith:muslim:1315-2", "hadith:muslim:1317-5", "hadith:muslim:143-2",
    "hadith:muslim:1530-2", "hadith:muslim:1676-4", "hadith:muslim:168-3",
    "hadith:muslim:1733-2", "hadith:muslim:1736-2", "hadith:muslim:1774-2",
    "hadith:muslim:1774-3", "hadith:muslim:1873-4", "hadith:muslim:1990-2",
    "hadith:muslim:2092-2", "hadith:muslim:2137-2", "hadith:muslim:2203-3",
    "hadith:muslim:2263-4", "hadith:muslim:2298-2", "hadith:muslim:2327-2",
    "hadith:muslim:2533-3", "hadith:muslim:2541-2", "hadith:muslim:2639-5",
    "hadith:muslim:2653-2", "hadith:muslim:2706-2", "hadith:muslim:2804-2",
    "hadith:muslim:2805-2", "hadith:muslim:3000-3", "hadith:muslim:410-2",
    "hadith:muslim:537-4", "hadith:muslim:57-3", "hadith:muslim:657-3", "hadith:muslim:679-3",
    "hadith:muslim:715-28", "hadith:muslim:792-4", "hadith:muslim:852-6", "hadith:nasai:4337",
    "hadith:tirmidhi:1096", "hadith:tirmidhi:595"
]

_PP_WIDE_KEEPS = [
    "hadith:abudawud:102", "hadith:abudawud:1088", "hadith:abudawud:1095",
    "hadith:abudawud:1125", "hadith:abudawud:113", "hadith:abudawud:1179",
    "hadith:abudawud:1181", "hadith:abudawud:1183", "hadith:abudawud:1187",
    "hadith:abudawud:1189", "hadith:abudawud:1489", "hadith:abudawud:1578",
    "hadith:abudawud:1621", "hadith:abudawud:1724", "hadith:abudawud:1735",
    "hadith:abudawud:1822", "hadith:abudawud:1930", "hadith:abudawud:2180",
    "hadith:abudawud:2252", "hadith:abudawud:2271", "hadith:abudawud:2411",
    "hadith:abudawud:2424", "hadith:abudawud:2491", "hadith:abudawud:2518",
    "hadith:abudawud:2630", "hadith:abudawud:2642", "hadith:abudawud:2716",
    "hadith:abudawud:2738", "hadith:abudawud:2742", "hadith:abudawud:2787",
    "hadith:abudawud:2884", "hadith:abudawud:2892", "hadith:abudawud:2913",
    "hadith:abudawud:292", "hadith:abudawud:3109", "hadith:abudawud:3320",
    "hadith:abudawud:339", "hadith:abudawud:346", "hadith:abudawud:3593", "hadith:abudawud:37",
    "hadith:abudawud:3738", "hadith:abudawud:3833", "hadith:abudawud:4238",
    "hadith:abudawud:4340", "hadith:abudawud:4371", "hadith:abudawud:4460",
    "hadith:abudawud:4516", "hadith:abudawud:4704", "hadith:abudawud:4720",
    "hadith:abudawud:4783", "hadith:abudawud:4819", "hadith:abudawud:4881",
    "hadith:abudawud:4917", "hadith:abudawud:4925", "hadith:abudawud:4926",
    "hadith:abudawud:5024", "hadith:abudawud:5047", "hadith:abudawud:5118",
    "hadith:abudawud:5178", "hadith:abudawud:5199", "hadith:abudawud:576",
    "hadith:abudawud:606", "hadith:abudawud:64", "hadith:abudawud:698", "hadith:abudawud:778",
    "hadith:abudawud:961", "hadith:abudawud:969", "hadith:abudawud:990", "hadith:bukhari:1427",
    "hadith:bukhari:1536", "hadith:bukhari:1651", "hadith:bukhari:1783", "hadith:bukhari:1895",
    "hadith:bukhari:1957", "hadith:bukhari:2274", "hadith:bukhari:2298", "hadith:bukhari:2582",
    "hadith:bukhari:260", "hadith:bukhari:287", "hadith:bukhari:2977", "hadith:bukhari:3048",
    "hadith:bukhari:3152", "hadith:bukhari:3778", "hadith:bukhari:404", "hadith:bukhari:42",
    "hadith:bukhari:4401", "hadith:bukhari:4516", "hadith:bukhari:4639", "hadith:bukhari:4657",
    "hadith:bukhari:4662", "hadith:bukhari:4674", "hadith:bukhari:4849", "hadith:bukhari:5147",
    "hadith:bukhari:5174", "hadith:bukhari:5219", "hadith:bukhari:525", "hadith:bukhari:5356",
    "hadith:bukhari:5566", "hadith:bukhari:5567", "hadith:bukhari:5717", "hadith:bukhari:5719",
    "hadith:bukhari:5747", "hadith:bukhari:6345", "hadith:bukhari:6453", "hadith:bukhari:6572",
    "hadith:bukhari:6655", "hadith:bukhari:6713", "hadith:bukhari:6798", "hadith:bukhari:6849",
    "hadith:bukhari:7062", "hadith:bukhari:943", "hadith:bukhari:947", "hadith:ibnmajah:1120",
    "hadith:ibnmajah:1281", "hadith:ibnmajah:1283", "hadith:ibnmajah:1600",
    "hadith:ibnmajah:21", "hadith:ibnmajah:2418", "hadith:ibnmajah:2490",
    "hadith:ibnmajah:2491", "hadith:ibnmajah:3389", "hadith:ibnmajah:3821",
    "hadith:ibnmajah:3906", "hadith:ibnmajah:4070", "hadith:ibnmajah:4083",
    "hadith:ibnmajah:44", "hadith:ibnmajah:687", "hadith:ibnmajah:736", "hadith:muslim:1012",
    "hadith:muslim:1014-3", "hadith:muslim:1017-4", "hadith:muslim:1017-6",
    "hadith:muslim:1017-7", "hadith:muslim:103", "hadith:muslim:1042-2", "hadith:muslim:1045-5",
    "hadith:muslim:1055-3", "hadith:muslim:1063-2", "hadith:muslim:1064-11",
    "hadith:muslim:108-3", "hadith:muslim:1089-2", "hadith:muslim:1103-4",
    "hadith:muslim:1106-8", "hadith:muslim:1111-4", "hadith:muslim:1112-2",
    "hadith:muslim:1115-2", "hadith:muslim:1118-2", "hadith:muslim:1121-3",
    "hadith:muslim:1126-5", "hadith:muslim:1129-3", "hadith:muslim:113-2",
    "hadith:muslim:1133-2", "hadith:muslim:1143-2", "hadith:muslim:1156-4",
    "hadith:muslim:1167-5", "hadith:muslim:1172-5", "hadith:muslim:1178-2",
    "hadith:muslim:1184-3", "hadith:muslim:119-2", "hadith:muslim:1194-2",
    "hadith:muslim:1199-5", "hadith:muslim:12-2", "hadith:muslim:1208-3", "hadith:muslim:1210",
    "hadith:muslim:1211-21", "hadith:muslim:1211-23", "hadith:muslim:1211-28",
    "hadith:muslim:1211-29", "hadith:muslim:1213-2", "hadith:muslim:1225-3",
    "hadith:muslim:1226-2", "hadith:muslim:1229-4", "hadith:muslim:123-4", "hadith:muslim:1231",
    "hadith:muslim:1240-3", "hadith:muslim:1253-2", "hadith:muslim:1257-2",
    "hadith:muslim:1260", "hadith:muslim:1270-3", "hadith:muslim:1292-2",
    "hadith:muslim:1296-3", "hadith:muslim:1306-7", "hadith:muslim:1319-2",
    "hadith:muslim:1321-2", "hadith:muslim:1325-2", "hadith:muslim:1337-4",
    "hadith:muslim:134-4", "hadith:muslim:1350-2", "hadith:muslim:1365-4",
    "hadith:muslim:1378-3", "hadith:muslim:1387-3", "hadith:muslim:1400-5",
    "hadith:muslim:1407-7", "hadith:muslim:1429-5", "hadith:muslim:1429-6",
    "hadith:muslim:1432-2", "hadith:muslim:1433-3", "hadith:muslim:1439-3",
    "hadith:muslim:1445-4", "hadith:muslim:1445-6", "hadith:muslim:1471-21",
    "hadith:muslim:1480-19", "hadith:muslim:1480-7", "hadith:muslim:1493-2",
    "hadith:muslim:15-2", "hadith:muslim:1503-3", "hadith:muslim:1515-2", "hadith:muslim:1528",
    "hadith:muslim:1536-25", "hadith:muslim:1542-7", "hadith:muslim:1547-7",
    "hadith:muslim:1548-2", "hadith:muslim:1558-2", "hadith:muslim:157-5",
    "hadith:muslim:157-6", "hadith:muslim:1575", "hadith:muslim:1584-6", "hadith:muslim:159-2",
    "hadith:muslim:1599-4", "hadith:muslim:160-3", "hadith:muslim:1604-4",
    "hadith:muslim:1616-5", "hadith:muslim:1623-3", "hadith:muslim:1628-8",
    "hadith:muslim:1629", "hadith:muslim:1633", "hadith:muslim:1646-3", "hadith:muslim:1649-4",
    "hadith:muslim:1649-8", "hadith:muslim:1650-4", "hadith:muslim:1656-4",
    "hadith:muslim:1656-6", "hadith:muslim:1657-3", "hadith:muslim:1658-5",
    "hadith:muslim:1660-2", "hadith:muslim:1668-2", "hadith:muslim:1669-3", "hadith:muslim:167",
    "hadith:muslim:1671-7", "hadith:muslim:1672-2", "hadith:muslim:1677-2",
    "hadith:muslim:1685-2", "hadith:muslim:1688-3", "hadith:muslim:1692-3",
    "hadith:muslim:1699-2", "hadith:muslim:1699-3", "hadith:muslim:1704",
    "hadith:muslim:1706-2", "hadith:muslim:1706-5", "hadith:muslim:1709-7",
    "hadith:muslim:1731-3", "hadith:muslim:1750-2", "hadith:muslim:1776-4",
    "hadith:muslim:1785-3", "hadith:muslim:1790-3", "hadith:muslim:1800-2",
    "hadith:muslim:1812-4", "hadith:muslim:1812-6", "hadith:muslim:182-2",
    "hadith:muslim:1835-7", "hadith:muslim:1837-2", "hadith:muslim:1844-3",
    "hadith:muslim:1845-2", "hadith:muslim:1869-4", "hadith:muslim:1876-6",
    "hadith:muslim:1876-7", "hadith:muslim:1879-2", "hadith:muslim:1885-2",
    "hadith:muslim:1889-2", "hadith:muslim:189-2", "hadith:muslim:1896-2",
    "hadith:muslim:1904-3", "hadith:muslim:1907-2", "hadith:muslim:1909",
    "hadith:muslim:1912-4", "hadith:muslim:1920", "hadith:muslim:1929-4",
    "hadith:muslim:1935-7", "hadith:muslim:1945-3", "hadith:muslim:1953-2",
    "hadith:muslim:1962-2", "hadith:muslim:1965-3", "hadith:muslim:1968-2",
    "hadith:muslim:1968-5", "hadith:muslim:1977-2", "hadith:muslim:1980-6",
    "hadith:muslim:1985-3", "hadith:muslim:1994", "hadith:muslim:1996-3",
    "hadith:muslim:2006-2", "hadith:muslim:2017-3", "hadith:muslim:2027-5",
    "hadith:muslim:2033-3", "hadith:muslim:2044-2", "hadith:muslim:2052-3",
    "hadith:muslim:2067-2", "hadith:muslim:2067-4", "hadith:muslim:2071-2",
    "hadith:muslim:2087-2", "hadith:muslim:2088-4", "hadith:muslim:2088-5",
    "hadith:muslim:21-3", "hadith:muslim:2104-2", "hadith:muslim:2107-8",
    "hadith:muslim:2109-2", "hadith:muslim:2133-4", "hadith:muslim:2141",
    "hadith:muslim:2144-5", "hadith:muslim:2146-3", "hadith:muslim:2155-3",
    "hadith:muslim:2179", "hadith:muslim:2190-2", "hadith:muslim:2192", "hadith:muslim:2196-2",
    "hadith:muslim:220-2", "hadith:muslim:2201-2", "hadith:muslim:2215-2",
    "hadith:muslim:2218-2", "hadith:muslim:2219-4", "hadith:muslim:2220-3",
    "hadith:muslim:2221-2", "hadith:muslim:2233-10", "hadith:muslim:2234-3",
    "hadith:muslim:2237", "hadith:muslim:2237-2", "hadith:muslim:2243-2",
    "hadith:muslim:2255-2", "hadith:muslim:2263-3", "hadith:muslim:2263-6",
    "hadith:muslim:2269-3", "hadith:muslim:227-2", "hadith:muslim:2279-4",
    "hadith:muslim:2299-2", "hadith:muslim:231-2", "hadith:muslim:2373-4",
    "hadith:muslim:2374-2", "hadith:muslim:2375", "hadith:muslim:2382-2",
    "hadith:muslim:2386-2", "hadith:muslim:2392-3", "hadith:muslim:2393-2",
    "hadith:muslim:2397", "hadith:muslim:240-3", "hadith:muslim:240-4", "hadith:muslim:2403-2",
    "hadith:muslim:2403-4", "hadith:muslim:2410-3", "hadith:muslim:2416-2",
    "hadith:muslim:2460-2", "hadith:muslim:2464-3", "hadith:muslim:2469-2",
    "hadith:muslim:2479-2", "hadith:muslim:2480-2", "hadith:muslim:251-2",
    "hadith:muslim:2511-6", "hadith:muslim:252", "hadith:muslim:2525-2", "hadith:muslim:2548-4",
    "hadith:muslim:2549-2", "hadith:muslim:255-2", "hadith:muslim:2563", "hadith:muslim:2563-4",
    "hadith:muslim:2570", "hadith:muslim:2577-4", "hadith:muslim:2604-2",
    "hadith:muslim:2607-4", "hadith:muslim:2641", "hadith:muslim:2645-4", "hadith:muslim:2677",
    "hadith:muslim:2687", "hadith:muslim:2704-5", "hadith:muslim:2709-2",
    "hadith:muslim:2710-5", "hadith:muslim:2725-2", "hadith:muslim:2727-2",
    "hadith:muslim:2737-3", "hadith:muslim:2738-2", "hadith:muslim:274", "hadith:muslim:2742",
    "hadith:muslim:2744-3", "hadith:muslim:275", "hadith:muslim:2758-3", "hadith:muslim:2773-2",
    "hadith:muslim:2802-3", "hadith:muslim:2810-4", "hadith:muslim:2811-3",
    "hadith:muslim:2811-4", "hadith:muslim:2845-3", "hadith:muslim:2846-3",
    "hadith:muslim:2847", "hadith:muslim:2870-3", "hadith:muslim:2875", "hadith:muslim:2876-4",
    "hadith:muslim:288-3", "hadith:muslim:2889-2", "hadith:muslim:2890-2",
    "hadith:muslim:2899-2", "hadith:muslim:2901-4", "hadith:muslim:2914", "hadith:muslim:2919",
    "hadith:muslim:2926", "hadith:muslim:2937-2", "hadith:muslim:3023-2",
    "hadith:muslim:3033-2", "hadith:muslim:316-3", "hadith:muslim:317-2", "hadith:muslim:33-2",
    "hadith:muslim:332-5", "hadith:muslim:334-3", "hadith:muslim:334-4", "hadith:muslim:344",
    "hadith:muslim:376", "hadith:muslim:392-3", "hadith:muslim:395-4", "hadith:muslim:397-2",
    "hadith:muslim:402-3", "hadith:muslim:404-3", "hadith:muslim:411-4", "hadith:muslim:411-5",
    "hadith:muslim:413-2", "hadith:muslim:418-7", "hadith:muslim:419-2", "hadith:muslim:419-3",
    "hadith:muslim:421-2", "hadith:muslim:425-2", "hadith:muslim:438-2", "hadith:muslim:44",
    "hadith:muslim:450-3", "hadith:muslim:455", "hadith:muslim:471-3", "hadith:muslim:48-4",
    "hadith:muslim:480-5", "hadith:muslim:481", "hadith:muslim:493-2", "hadith:muslim:495-2",
    "hadith:muslim:519-2", "hadith:muslim:526-2", "hadith:muslim:528-2", "hadith:muslim:528-3",
    "hadith:muslim:534-2", "hadith:muslim:54-2", "hadith:muslim:540-4", "hadith:muslim:544-2",
    "hadith:muslim:548-2", "hadith:muslim:564-4", "hadith:muslim:569-3", "hadith:muslim:57-2",
    "hadith:muslim:57-7", "hadith:muslim:572-2", "hadith:muslim:573-2", "hadith:muslim:573-5",
    "hadith:muslim:59-4", "hadith:muslim:594-3", "hadith:muslim:621-2", "hadith:muslim:632-2",
    "hadith:muslim:643-2", "hadith:muslim:646-2", "hadith:muslim:650-3", "hadith:muslim:662",
    "hadith:muslim:674-3", "hadith:muslim:693-3", "hadith:muslim:699-5", "hadith:muslim:699-6",
    "hadith:muslim:721-3", "hadith:muslim:724-2", "hadith:muslim:728-2", "hadith:muslim:728-4",
    "hadith:muslim:730-3", "hadith:muslim:746-2", "hadith:muslim:749-5", "hadith:muslim:763-15",
    "hadith:muslim:791", "hadith:muslim:798-2", "hadith:muslim:8-2", "hadith:muslim:820-2",
    "hadith:muslim:824-2", "hadith:muslim:830-2", "hadith:muslim:843-4", "hadith:muslim:843-5",
    "hadith:muslim:855-2", "hadith:muslim:856", "hadith:muslim:856-2", "hadith:muslim:866-2",
    "hadith:muslim:872-2", "hadith:muslim:881-3", "hadith:muslim:892-2", "hadith:muslim:905-2",
    "hadith:muslim:913-3", "hadith:muslim:926-3", "hadith:muslim:929-3", "hadith:muslim:935-2",
    "hadith:muslim:953", "hadith:muslim:987-6", "hadith:muslim:997-2", "hadith:nasai:1086",
    "hadith:nasai:1358", "hadith:nasai:1422", "hadith:nasai:1424", "hadith:nasai:1468",
    "hadith:nasai:1568", "hadith:nasai:1590", "hadith:nasai:1706", "hadith:nasai:1755",
    "hadith:nasai:1913", "hadith:nasai:2273", "hadith:nasai:2463", "hadith:nasai:2465",
    "hadith:nasai:2480", "hadith:nasai:2565", "hadith:nasai:287", "hadith:nasai:2902",
    "hadith:nasai:2910", "hadith:nasai:3210", "hadith:nasai:3271", "hadith:nasai:3363",
    "hadith:nasai:3491", "hadith:nasai:376", "hadith:nasai:3954", "hadith:nasai:3981",
    "hadith:nasai:4119", "hadith:nasai:4150", "hadith:nasai:4598", "hadith:nasai:4728",
    "hadith:nasai:4790", "hadith:nasai:4855", "hadith:nasai:4857", "hadith:nasai:4951",
    "hadith:nasai:4955", "hadith:nasai:5139", "hadith:nasai:5141", "hadith:nasai:5191",
    "hadith:nasai:5192", "hadith:nasai:5217", "hadith:nasai:667", "hadith:nasai:972",
    "hadith:tirmidhi:1282", "hadith:tirmidhi:1333", "hadith:tirmidhi:150",
    "hadith:tirmidhi:1587", "hadith:tirmidhi:1709", "hadith:tirmidhi:1714",
    "hadith:tirmidhi:1748", "hadith:tirmidhi:1751", "hadith:tirmidhi:1959",
    "hadith:tirmidhi:1988", "hadith:tirmidhi:2303", "hadith:tirmidhi:278",
    "hadith:tirmidhi:2954", "hadith:tirmidhi:318", "hadith:tirmidhi:3195",
    "hadith:tirmidhi:3637", "hadith:tirmidhi:495", "hadith:tirmidhi:52", "hadith:tirmidhi:533",
    "hadith:tirmidhi:560", "hadith:tirmidhi:567", "hadith:tirmidhi:588"
]

_OMISSION_SWEEP_KEEPS = [
    "hadith:abudawud:1009", "hadith:abudawud:1010", "hadith:abudawud:1038",
    "hadith:abudawud:104", "hadith:abudawud:1046", "hadith:abudawud:107",
    "hadith:abudawud:1146", "hadith:abudawud:1163", "hadith:abudawud:1214",
    "hadith:abudawud:1241", "hadith:abudawud:1290", "hadith:abudawud:1330",
    "hadith:abudawud:1347", "hadith:abudawud:1348", "hadith:abudawud:1365",
    "hadith:abudawud:142", "hadith:abudawud:1426", "hadith:abudawud:1458",
    "hadith:abudawud:1511", "hadith:abudawud:1558", "hadith:abudawud:1568",
    "hadith:abudawud:1569", "hadith:abudawud:1573", "hadith:abudawud:1574",
    "hadith:abudawud:1578", "hadith:abudawud:1580", "hadith:abudawud:160",
    "hadith:abudawud:1632", "hadith:abudawud:170", "hadith:abudawud:1705",
    "hadith:abudawud:1744", "hadith:abudawud:1802", "hadith:abudawud:1909",
    "hadith:abudawud:201", "hadith:abudawud:2024", "hadith:abudawud:2104",
    "hadith:abudawud:2112", "hadith:abudawud:2118", "hadith:abudawud:2170",
    "hadith:abudawud:2251", "hadith:abudawud:2271", "hadith:abudawud:2303",
    "hadith:abudawud:2429", "hadith:abudawud:2751", "hadith:abudawud:2829",
    "hadith:abudawud:2932", "hadith:abudawud:3142", "hadith:abudawud:319",
    "hadith:abudawud:3269", "hadith:abudawud:3298", "hadith:abudawud:3337",
    "hadith:abudawud:334", "hadith:abudawud:335", "hadith:abudawud:344", "hadith:abudawud:3488",
    "hadith:abudawud:3631", "hadith:abudawud:3692", "hadith:abudawud:378",
    "hadith:abudawud:3889", "hadith:abudawud:3936", "hadith:abudawud:3941",
    "hadith:abudawud:3973", "hadith:abudawud:3975", "hadith:abudawud:4121",
    "hadith:abudawud:4140", "hadith:abudawud:4153", "hadith:abudawud:4223",
    "hadith:abudawud:4310", "hadith:abudawud:4368", "hadith:abudawud:4427",
    "hadith:abudawud:4440", "hadith:abudawud:4475", "hadith:abudawud:4511",
    "hadith:abudawud:4512", "hadith:abudawud:4514", "hadith:abudawud:4573",
    "hadith:abudawud:4612", "hadith:abudawud:4635", "hadith:abudawud:4645",
    "hadith:abudawud:4650", "hadith:abudawud:4749", "hadith:abudawud:4757",
    "hadith:abudawud:4778", "hadith:abudawud:4788", "hadith:abudawud:4818",
    "hadith:abudawud:4941", "hadith:abudawud:4967", "hadith:abudawud:4976",
    "hadith:abudawud:5003", "hadith:abudawud:506", "hadith:abudawud:5066",
    "hadith:abudawud:5106", "hadith:abudawud:5146", "hadith:abudawud:5160",
    "hadith:abudawud:5217", "hadith:abudawud:54", "hadith:abudawud:584", "hadith:abudawud:666",
    "hadith:abudawud:733", "hadith:abudawud:750", "hadith:abudawud:761", "hadith:abudawud:763",
    "hadith:abudawud:773", "hadith:abudawud:774", "hadith:abudawud:807", "hadith:abudawud:834",
    "hadith:abudawud:847", "hadith:abudawud:963", "hadith:abudawud:964", "hadith:abudawud:967",
    "hadith:abudawud:972", "hadith:bukhari:1171", "hadith:bukhari:1340", "hadith:bukhari:1378",
    "hadith:bukhari:1390", "hadith:bukhari:1561", "hadith:bukhari:1882", "hadith:bukhari:1931",
    "hadith:bukhari:2041", "hadith:bukhari:2079", "hadith:bukhari:2372", "hadith:bukhari:2394",
    "hadith:bukhari:2442", "hadith:bukhari:2445", "hadith:bukhari:2518", "hadith:bukhari:2553",
    "hadith:bukhari:2562", "hadith:bukhari:2664", "hadith:bukhari:2782", "hadith:bukhari:2833",
    "hadith:bukhari:2892", "hadith:bukhari:2975", "hadith:bukhari:2978", "hadith:bukhari:3159",
    "hadith:bukhari:3219", "hadith:bukhari:3242", "hadith:bukhari:3318", "hadith:bukhari:3354",
    "hadith:bukhari:3355", "hadith:bukhari:3432", "hadith:bukhari:3603", "hadith:bukhari:3705",
    "hadith:bukhari:3811", "hadith:bukhari:3912", "hadith:bukhari:4032", "hadith:bukhari:4043",
    "hadith:bukhari:4076", "hadith:bukhari:4153", "hadith:bukhari:4156", "hadith:bukhari:4204",
    "hadith:bukhari:4243", "hadith:bukhari:430", "hadith:bukhari:4370", "hadith:bukhari:4387",
    "hadith:bukhari:4421", "hadith:bukhari:4426", "hadith:bukhari:4435", "hadith:bukhari:444",
    "hadith:bukhari:4456", "hadith:bukhari:4564", "hadith:bukhari:4581",
    "hadith:bukhari:4626-2", "hadith:bukhari:4686", "hadith:bukhari:4720",
    "hadith:bukhari:4944", "hadith:bukhari:4951", "hadith:bukhari:5287", "hadith:bukhari:5383",
    "hadith:bukhari:5560", "hadith:bukhari:5576", "hadith:bukhari:5821", "hadith:bukhari:5865",
    "hadith:bukhari:5924", "hadith:bukhari:6024", "hadith:bukhari:6132", "hadith:bukhari:6263",
    "hadith:bukhari:6264", "hadith:bukhari:6360", "hadith:bukhari:6434", "hadith:bukhari:6440",
    "hadith:bukhari:6442", "hadith:bukhari:6532", "hadith:bukhari:6576", "hadith:bukhari:6675",
    "hadith:bukhari:6708", "hadith:bukhari:6753", "hadith:bukhari:6789", "hadith:bukhari:6872",
    "hadith:bukhari:6894", "hadith:bukhari:6926", "hadith:bukhari:7040", "hadith:bukhari:707",
    "hadith:bukhari:74", "hadith:bukhari:78", "hadith:bukhari:817", "hadith:bukhari:818",
    "hadith:bukhari:972", "hadith:ibnmajah:1112", "hadith:ibnmajah:1652", "hadith:ibnmajah:169",
    "hadith:ibnmajah:1779", "hadith:ibnmajah:1794", "hadith:ibnmajah:183",
    "hadith:ibnmajah:2254", "hadith:ibnmajah:2598", "hadith:ibnmajah:3759",
    "hadith:ibnmajah:4053", "hadith:ibnmajah:4254", "hadith:muslim:1004-2",
    "hadith:muslim:1016-3", "hadith:muslim:104-3", "hadith:muslim:1040", "hadith:muslim:1040-3",
    "hadith:muslim:1049", "hadith:muslim:1059", "hadith:muslim:1064-3", "hadith:muslim:1064-4",
    "hadith:muslim:1064-5", "hadith:muslim:1066", "hadith:muslim:1080-4", "hadith:muslim:1100",
    "hadith:muslim:1101-4", "hadith:muslim:1111-2", "hadith:muslim:1112-2",
    "hadith:muslim:1121-5", "hadith:muslim:1125-2", "hadith:muslim:1129-3",
    "hadith:muslim:1156-4", "hadith:muslim:1159-3", "hadith:muslim:1167-4",
    "hadith:muslim:119-2", "hadith:muslim:119-3", "hadith:muslim:1190", "hadith:muslim:1211-11",
    "hadith:muslim:1211-23", "hadith:muslim:1213-2", "hadith:muslim:1226-10",
    "hadith:muslim:1230-5", "hadith:muslim:1240-3", "hadith:muslim:1243-2",
    "hadith:muslim:1264-2", "hadith:muslim:1271-2", "hadith:muslim:1273-2",
    "hadith:muslim:1280-4", "hadith:muslim:1280-6", "hadith:muslim:1282-2",
    "hadith:muslim:1303", "hadith:muslim:1306-5", "hadith:muslim:1325-2", "hadith:muslim:1327",
    "hadith:muslim:1353-2", "hadith:muslim:1359-2", "hadith:muslim:136-2",
    "hadith:muslim:1361-2", "hadith:muslim:1370", "hadith:muslim:1370-2",
    "hadith:muslim:1371-2", "hadith:muslim:1382-2", "hadith:muslim:1392-3",
    "hadith:muslim:1400-5", "hadith:muslim:1403-2", "hadith:muslim:1404-2",
    "hadith:muslim:1404-3", "hadith:muslim:1428-2", "hadith:muslim:143", "hadith:muslim:1430",
    "hadith:muslim:1434-2", "hadith:muslim:1438", "hadith:muslim:1438-10",
    "hadith:muslim:1438-9", "hadith:muslim:144", "hadith:muslim:144-2", "hadith:muslim:1456-2",
    "hadith:muslim:1457", "hadith:muslim:1457-2", "hadith:muslim:1471-4", "hadith:muslim:1479",
    "hadith:muslim:1499-2", "hadith:muslim:1501-6", "hadith:muslim:1504-5",
    "hadith:muslim:1525-4", "hadith:muslim:155-2", "hadith:muslim:1551-3",
    "hadith:muslim:1552-5", "hadith:muslim:1575", "hadith:muslim:1594", "hadith:muslim:160-3",
    "hadith:muslim:1616-5", "hadith:muslim:1628-3", "hadith:muslim:1633",
    "hadith:muslim:1644-2", "hadith:muslim:1646-2", "hadith:muslim:1649-2",
    "hadith:muslim:1654-2", "hadith:muslim:1654-4", "hadith:muslim:1654-5",
    "hadith:muslim:1656-2", "hadith:muslim:1657-3", "hadith:muslim:1661-2",
    "hadith:muslim:1665", "hadith:muslim:1669-3", "hadith:muslim:1677-2",
    "hadith:muslim:1681-4", "hadith:muslim:1682-4", "hadith:muslim:169-4",
    "hadith:muslim:1694-2", "hadith:muslim:17-2", "hadith:muslim:1704", "hadith:muslim:1705-2",
    "hadith:muslim:1706-5", "hadith:muslim:1715-2", "hadith:muslim:1742-3",
    "hadith:muslim:1768", "hadith:muslim:177", "hadith:muslim:1783-2", "hadith:muslim:1785-2",
    "hadith:muslim:179", "hadith:muslim:179-2", "hadith:muslim:18-2", "hadith:muslim:1814",
    "hadith:muslim:1835-7", "hadith:muslim:1848-4", "hadith:muslim:1851",
    "hadith:muslim:1863-3", "hadith:muslim:188", "hadith:muslim:1888-3", "hadith:muslim:1909",
    "hadith:muslim:1920", "hadith:muslim:1931-3", "hadith:muslim:194", "hadith:muslim:1945-2",
    "hadith:muslim:1954-3", "hadith:muslim:1968-5", "hadith:muslim:2001-3",
    "hadith:muslim:2006-2", "hadith:muslim:2010-2", "hadith:muslim:2012",
    "hadith:muslim:2012-2", "hadith:muslim:2032", "hadith:muslim:2052-3", "hadith:muslim:2059",
    "hadith:muslim:2065-2", "hadith:muslim:2066-2", "hadith:muslim:2067-2",
    "hadith:muslim:2067-5", "hadith:muslim:2071-2", "hadith:muslim:208-2",
    "hadith:muslim:2085-8", "hadith:muslim:2091-4", "hadith:muslim:2107-8",
    "hadith:muslim:2109", "hadith:muslim:2111-2", "hadith:muslim:2134", "hadith:muslim:2138",
    "hadith:muslim:214", "hadith:muslim:2154-2", "hadith:muslim:2165-2", "hadith:muslim:2175-2",
    "hadith:muslim:2177-3", "hadith:muslim:2189-2", "hadith:muslim:2199-2",
    "hadith:muslim:220-2", "hadith:muslim:2211-2", "hadith:muslim:2212-2",
    "hadith:muslim:2215-2", "hadith:muslim:2219-3", "hadith:muslim:222-2",
    "hadith:muslim:2223-2", "hadith:muslim:2233-3", "hadith:muslim:2250", "hadith:muslim:2257",
    "hadith:muslim:2261-3", "hadith:muslim:2261-5", "hadith:muslim:2263-3",
    "hadith:muslim:2268-5", "hadith:muslim:2307-3", "hadith:muslim:2309", "hadith:muslim:231-2",
    "hadith:muslim:2347", "hadith:muslim:235-3", "hadith:muslim:2380-6", "hadith:muslim:24-2",
    "hadith:muslim:2403-4", "hadith:muslim:2409", "hadith:muslim:2416-2", "hadith:muslim:2432",
    "hadith:muslim:2464-2", "hadith:muslim:2469-2", "hadith:muslim:2472",
    "hadith:muslim:2488-2", "hadith:muslim:2489-2", "hadith:muslim:2494", "hadith:muslim:251-2",
    "hadith:muslim:2511-6", "hadith:muslim:2522", "hadith:muslim:2522-2",
    "hadith:muslim:2525-3", "hadith:muslim:2527-2", "hadith:muslim:2533", "hadith:muslim:2548",
    "hadith:muslim:255-2", "hadith:muslim:2571", "hadith:muslim:2607-4", "hadith:muslim:2610",
    "hadith:muslim:2636", "hadith:muslim:2636-2", "hadith:muslim:2639-2",
    "hadith:muslim:2647-2", "hadith:muslim:2658-2", "hadith:muslim:2688-3",
    "hadith:muslim:2696", "hadith:muslim:2704-6", "hadith:muslim:2710-3",
    "hadith:muslim:2710-5", "hadith:muslim:2712", "hadith:muslim:2743-2", "hadith:muslim:2750",
    "hadith:muslim:2756-3", "hadith:muslim:2769", "hadith:muslim:2769-3", "hadith:muslim:278-5",
    "hadith:muslim:2786-2", "hadith:muslim:2786-4", "hadith:muslim:28-2",
    "hadith:muslim:2816-2", "hadith:muslim:2847", "hadith:muslim:2849-2", "hadith:muslim:2852",
    "hadith:muslim:2860", "hadith:muslim:2862", "hadith:muslim:2865", "hadith:muslim:2905-6",
    "hadith:muslim:2908-2", "hadith:muslim:2927-2", "hadith:muslim:2930-3",
    "hadith:muslim:2941-2", "hadith:muslim:2966", "hadith:muslim:2972-2", "hadith:muslim:2977",
    "hadith:muslim:300", "hadith:muslim:3024", "hadith:muslim:3024-2", "hadith:muslim:315-2",
    "hadith:muslim:316-3", "hadith:muslim:317-2", "hadith:muslim:325", "hadith:muslim:330-3",
    "hadith:muslim:332-5", "hadith:muslim:334", "hadith:muslim:334-3", "hadith:muslim:336-4",
    "hadith:muslim:336-5", "hadith:muslim:340", "hadith:muslim:348-2", "hadith:muslim:359-2",
    "hadith:muslim:368-4", "hadith:muslim:386", "hadith:muslim:392-3", "hadith:muslim:400-2",
    "hadith:muslim:404-2", "hadith:muslim:406-3", "hadith:muslim:411-5", "hadith:muslim:452",
    "hadith:muslim:455", "hadith:muslim:480-5", "hadith:muslim:50-2", "hadith:muslim:504-4",
    "hadith:muslim:517-2", "hadith:muslim:529", "hadith:muslim:541-2", "hadith:muslim:543-4",
    "hadith:muslim:561", "hadith:muslim:564-4", "hadith:muslim:57-2", "hadith:muslim:57-5",
    "hadith:muslim:593-7", "hadith:muslim:600", "hadith:muslim:607-3", "hadith:muslim:621",
    "hadith:muslim:625-2", "hadith:muslim:633-2", "hadith:muslim:64", "hadith:muslim:648",
    "hadith:muslim:675-4", "hadith:muslim:694-2", "hadith:muslim:699-2", "hadith:muslim:715-19",
    "hadith:muslim:715-7", "hadith:muslim:749-5", "hadith:muslim:749-6", "hadith:muslim:749-7",
    "hadith:muslim:763-9", "hadith:muslim:771-2", "hadith:muslim:804-2", "hadith:muslim:843-5",
    "hadith:muslim:846-2", "hadith:muslim:863-2", "hadith:muslim:881-3", "hadith:muslim:883-2",
    "hadith:muslim:901-3", "hadith:muslim:904-2", "hadith:muslim:920-2", "hadith:muslim:96",
    "hadith:muslim:979-4", "hadith:muslim:980", "hadith:muslim:987-2", "hadith:muslim:987-5",
    "hadith:nasai:2052", "hadith:nasai:2446", "hadith:nasai:2473", "hadith:nasai:2474",
    "hadith:nasai:2476", "hadith:nasai:2478", "hadith:nasai:2487", "hadith:nasai:3248",
    "hadith:nasai:3251", "hadith:nasai:3473", "hadith:nasai:3831", "hadith:nasai:3856",
    "hadith:nasai:4081", "hadith:nasai:4297", "hadith:nasai:4560", "hadith:nasai:4561",
    "hadith:nasai:4562", "hadith:nasai:4566", "hadith:nasai:4959", "hadith:nasai:5104",
    "hadith:nasai:5105", "hadith:nasai:5349", "hadith:nasai:5644", "hadith:nasai:609",
    "hadith:nasai:752", "hadith:nasai:901", "hadith:nasai:913", "hadith:tirmidhi:100",
    "hadith:tirmidhi:129", "hadith:tirmidhi:1418", "hadith:tirmidhi:1453",
    "hadith:tirmidhi:150", "hadith:tirmidhi:1573", "hadith:tirmidhi:1659",
    "hadith:tirmidhi:1709", "hadith:tirmidhi:1748", "hadith:tirmidhi:1750",
    "hadith:tirmidhi:2064", "hadith:tirmidhi:2179", "hadith:tirmidhi:2235",
    "hadith:tirmidhi:2246", "hadith:tirmidhi:2370", "hadith:tirmidhi:2434",
    "hadith:tirmidhi:2441", "hadith:tirmidhi:2514", "hadith:tirmidhi:2543",
    "hadith:tirmidhi:2690", "hadith:tirmidhi:2774", "hadith:tirmidhi:278",
    "hadith:tirmidhi:2839", "hadith:tirmidhi:2953-2", "hadith:tirmidhi:3166",
    "hadith:tirmidhi:3318", "hadith:tirmidhi:3365", "hadith:tirmidhi:3505",
    "hadith:tirmidhi:3508", "hadith:tirmidhi:3623", "hadith:tirmidhi:3629",
    "hadith:tirmidhi:3701", "hadith:tirmidhi:3837", "hadith:tirmidhi:620",
    "hadith:tirmidhi:621", "hadith:tirmidhi:626"
]


def test_pure_pointer_sweep_converges_to_audited_keeps():
    """R-A3-18 closure gate, round 4. `find_pure_pointers` run corpus-wide over
    every scorable hadith primary at the WIDE threshold (residue cap removed)
    must come back holding EXACTLY the audited KEEPs in `_PP_WIDE_KEEPS` -- no
    audited pointer re-admitted, no audited keep dropped -- and every id in
    `_A2R4_AUDITED_POINTERS` must be unscorable.

    The wide threshold is the point: correctness no longer sits at a tuned
    residue band. A NEW scorable record whose entire matn is reference /
    chain-meta / deferral / omission scaffold -- in any token order, at any
    residue size -- lands in the sweep's output and, not being in
    `_PP_WIDE_KEEPS`, breaks this pin for a reading. A MISSING id means an
    audited keep was wrongly marked unscorable: a real hadith became
    unverifiable.
    """
    from sanad_ingest.openiti import find_pure_pointers
    from sanad_ingest.audit_lists import UNSCORABLE

    conn = db.connect(str(MATERIALIZED_DB))
    rows = conn.execute(
        "SELECT id, norm_aggressive FROM records WHERE kind = 'hadith' "
        "AND unscorable_reason IS NULL AND norm_aggressive IS NOT NULL"
    ).fetchall()
    norms = {r["id"]: r["norm_aggressive"] for r in rows if r["norm_aggressive"]}

    hits = sorted(rid for rid, _n, _res in
                  find_pure_pointers(norms, max_residue=10**9))
    assert hits == sorted(_PP_WIDE_KEEPS), (
        "the wide pure-pointer partition changed. A NEW id is a scorable "
        "record whose matn is pure reference scaffold -- read it in context, "
        "add it to audit_lists.UNSCORABLE and task-16-A2round4-audit.md if it "
        "carries no quotable clause, or extend _PP_WIDE_KEEPS with its "
        "justification if it does. A MISSING id means an audited keep was "
        "wrongly marked unscorable.")

    unscorable = {k for coll in UNSCORABLE.values() for k in coll}
    readmitted = [p for p in _A2R4_AUDITED_POINTERS if p not in unscorable]
    assert readmitted == [], (
        f"audited pointers no longer pinned unscorable: {readmitted}")


def test_no_scorable_record_is_a_pure_omission_pointer():
    """R-A3-18 exhaustion gate, round 4 -- INDEPENDENTLY KEYED.

    `find_pure_pointers`' residue sweep cannot see a pointer that uses no
    reference anchor, or that an `غير`/`الا`/`قال`/`زاد` token pushes past its
    delivery guard (that guard exists to protect genuine `وزاد Y` additions).
    The omission/comparison pointers of this round -- `لم يذكر X` with no
    anchor, `غير أنه لم يذكر`, `الا قوله X فانه لم يذكره`, bare `نهى ... بمثله`
    -- all escaped it that way.

    So this gate keys on a DIFFERENT axis entirely: the editorial
    omission/comparison vocabulary, with the genuine `لم يذكر الله` ("did not
    remember Allah") narrative family excluded. Every scorable record it still
    matches must be an audited KEEP (`_OMISSION_SWEEP_KEEPS`): a record that
    delivers a clause of its own and merely NOTES what a parallel narration
    omits. A NEW pure omission pointer surfaces here even though the residue
    sweep is blind to it -- which is the whole point of a second key.
    """
    import re
    mark = re.compile(
        "لم يذكر|لم يقل|لم يذكرا|لم يذكروا|لم يقولوا|ليس في حديث|"
        "وليس في حديث|ليس في حديثه|ليس في حديثهم|ليس في حديثهما|وليس في")
    genuine = re.compile("لم يذكر الله|لم يذكر اسم الله|لم يذكروا الله|لم يذكر ربه")

    conn = db.connect(str(MATERIALIZED_DB))
    rows = conn.execute(
        "SELECT id, norm_aggressive FROM records WHERE kind = 'hadith' "
        "AND unscorable_reason IS NULL AND norm_aggressive IS NOT NULL"
    ).fetchall()
    hits = sorted(r["id"] for r in rows if r["norm_aggressive"]
                  and mark.search(r["norm_aggressive"])
                  and not genuine.search(r["norm_aggressive"]))
    assert hits == sorted(_OMISSION_SWEEP_KEEPS), (
        "the independent omission/comparison sweep changed. A NEW id is a "
        "scorable record that only notes what another narration omits -- read "
        "it against task-16-A2round4-audit.md and either pin it unscorable or "
        "add it to _OMISSION_SWEEP_KEEPS with its delivered clause named.")


# --- A2 round 5 (Task 16): the VOCABULARY-FREE content-mass partition --------
#
# The pure-pointer false-EXACT class escaped SEVEN closures. Each closure was a
# NARROWING FILTER with an exclusion the next pointer walked through; round 4's
# `find_pure_pointers` excluded any record carrying a qala/yaqul/zada/ghayr/illa
# `_PP_DELIVERS` marker (to protect a genuine "wa-zada Y"), so a content-free
# pointer wrapped in a speech FRAME -- "bi-hadha l-isnad mithlahu wa-qala
# sami'tu rasula llah", "sami'tu rasula llah yaqul fa-dhakara nahwa hadith
# Hatim" -- walked straight through it. Five such escapes were confirmed
# scorable (muslim:2556-3, 1822-2, 2987-3, 686-2, 144-5).
#
# `openiti.content_mass` keys on NO marker and NO position: it strips only
# non-matn scaffolding (honorific, basmala, isnad/chain names, the reference/
# deferral vocabulary, and a frame verb plus the narrator name it introduces)
# and counts what is LEFT. A pure pointer defers instead of delivering, so it
# reduces to ~0 content whatever frame it hid behind; a genuine "qala: <words>"
# keeps its words. There is no exclusion to walk through. K=3 is the AUDIT-SCOPE
# boundary (not a verdict knob): every scorable primary with content_mass <= K
# was read in task-16-A2round5-audit.md and split into 28 POINTER (now
# UNSCORABLE) and the KEEPs below (two one/two-word genuine matns the net
# surfaces, muslim:274-13 "da'hu" and 581-2, are keeps: they DELIVER a clause).
# K was validated by auditing the band just
# above it -- cm 4..7 holds no content-free / topic-deferral / bare-ruling
# pointer (the one "qala 'an"-shaped record there, nasai:5696, delivers the
# ruling "ijtanib kulla shay'in yanishsh"). Raising K only adds audited keeps;
# it can never let a pointer through while every record <= K is audited.
_CONTENT_MASS_K = 3

_A2R5_CONTENT_MASS_POINTERS = [
    "hadith:abudawud:1176", "hadith:abudawud:1354", "hadith:abudawud:3609",
    "hadith:abudawud:4045", "hadith:bukhari:1656", "hadith:bukhari:3332",
    "hadith:bukhari:4251", "hadith:bukhari:4745", "hadith:ibnmajah:1130",
    "hadith:muslim:109-2", "hadith:muslim:1183", "hadith:muslim:144-5", "hadith:muslim:1569",
    "hadith:muslim:1584-3", "hadith:muslim:1730-2", "hadith:muslim:1822-2",
    "hadith:muslim:1873-3", "hadith:muslim:198-3", "hadith:muslim:2047-3",
    "hadith:muslim:2359-6", "hadith:muslim:2556-3", "hadith:muslim:2649-2",
    "hadith:muslim:2987-3", "hadith:muslim:347-2",
    "hadith:muslim:57-4", "hadith:muslim:686-2", "hadith:muslim:851-3",
    "hadith:muslim:882",
]

_CONTENT_MASS_KEEPS = [
    "hadith:abudawud:1058", "hadith:abudawud:1106", "hadith:abudawud:1150",
    "hadith:abudawud:1186", "hadith:abudawud:1245", "hadith:abudawud:1344",
    "hadith:abudawud:1345", "hadith:abudawud:1436", "hadith:abudawud:144",
    "hadith:abudawud:1468", "hadith:abudawud:1502", "hadith:abudawud:1511",
    "hadith:abudawud:1585", "hadith:abudawud:1711", "hadith:abudawud:1729",
    "hadith:abudawud:1747", "hadith:abudawud:1777", "hadith:abudawud:178",
    "hadith:abudawud:1842", "hadith:abudawud:1891", "hadith:abudawud:1955",
    "hadith:abudawud:1968", "hadith:abudawud:2018", "hadith:abudawud:2060",
    "hadith:abudawud:2070", "hadith:abudawud:2085", "hadith:abudawud:2095",
    "hadith:abudawud:2113", "hadith:abudawud:2148", "hadith:abudawud:2154",
    "hadith:abudawud:2183", "hadith:abudawud:2205", "hadith:abudawud:2211",
    "hadith:abudawud:2230", "hadith:abudawud:2317", "hadith:abudawud:2329",
    "hadith:abudawud:2367", "hadith:abudawud:2370", "hadith:abudawud:2371",
    "hadith:abudawud:2378", "hadith:abudawud:2383", "hadith:abudawud:2487",
    "hadith:abudawud:2518", "hadith:abudawud:2545", "hadith:abudawud:2557",
    "hadith:abudawud:2562", "hadith:abudawud:2582", "hadith:abudawud:2593",
    "hadith:abudawud:2630", "hadith:abudawud:2636", "hadith:abudawud:2739",
    "hadith:abudawud:2761", "hadith:abudawud:2808", "hadith:abudawud:2820",
    "hadith:abudawud:2834", "hadith:abudawud:2836", "hadith:abudawud:2840",
    "hadith:abudawud:2919", "hadith:abudawud:2935", "hadith:abudawud:3047",
    "hadith:abudawud:3053", "hadith:abudawud:3085", "hadith:abudawud:3086",
    "hadith:abudawud:3127", "hadith:abudawud:3128", "hadith:abudawud:3143",
    "hadith:abudawud:3158", "hadith:abudawud:3216", "hadith:abudawud:3239",
    "hadith:abudawud:3269", "hadith:abudawud:3271", "hadith:abudawud:328",
    "hadith:abudawud:3425", "hadith:abudawud:3429", "hadith:abudawud:3438",
    "hadith:abudawud:3455", "hadith:abudawud:3458", "hadith:abudawud:3480",
    "hadith:abudawud:3483", "hadith:abudawud:3491", "hadith:abudawud:3508",
    "hadith:abudawud:3516", "hadith:abudawud:3548", "hadith:abudawud:3580",
    "hadith:abudawud:3656", "hadith:abudawud:3686", "hadith:abudawud:3701",
    "hadith:abudawud:3720", "hadith:abudawud:3769", "hadith:abudawud:3785",
    "hadith:abudawud:3786", "hadith:abudawud:3820", "hadith:abudawud:3821",
    "hadith:abudawud:3828", "hadith:abudawud:3867", "hadith:abudawud:3870",
    "hadith:abudawud:3879", "hadith:abudawud:3913", "hadith:abudawud:3933",
    "hadith:abudawud:3976", "hadith:abudawud:3982", "hadith:abudawud:3991",
    "hadith:abudawud:4030", "hadith:abudawud:4050", "hadith:abudawud:4081",
    "hadith:abudawud:4132", "hadith:abudawud:4148", "hadith:abudawud:4150",
    "hadith:abudawud:4159", "hadith:abudawud:4171", "hadith:abudawud:4226",
    "hadith:abudawud:4266", "hadith:abudawud:4314", "hadith:abudawud:4317",
    "hadith:abudawud:4318", "hadith:abudawud:4332", "hadith:abudawud:4392",
    "hadith:abudawud:4416", "hadith:abudawud:4423", "hadith:abudawud:4424",
    "hadith:abudawud:4433", "hadith:abudawud:4557", "hadith:abudawud:4558",
    "hadith:abudawud:4560", "hadith:abudawud:4561", "hadith:abudawud:4562",
    "hadith:abudawud:4563", "hadith:abudawud:4566", "hadith:abudawud:4580",
    "hadith:abudawud:4592", "hadith:abudawud:4594", "hadith:abudawud:4603",
    "hadith:abudawud:4619", "hadith:abudawud:4633", "hadith:abudawud:4717",
    "hadith:abudawud:4742", "hadith:abudawud:4820", "hadith:abudawud:4947",
    "hadith:abudawud:4964", "hadith:abudawud:4973", "hadith:abudawud:4976",
    "hadith:abudawud:5002", "hadith:abudawud:5037", "hadith:abudawud:5122",
    "hadith:abudawud:5128", "hadith:abudawud:5132", "hadith:abudawud:540",
    "hadith:abudawud:651", "hadith:abudawud:653", "hadith:abudawud:706", "hadith:abudawud:811",
    "hadith:abudawud:943", "hadith:abudawud:947", "hadith:bukhari:102", "hadith:bukhari:1081",
    "hadith:bukhari:1161", "hadith:bukhari:1171", "hadith:bukhari:1325", "hadith:bukhari:1466",
    "hadith:bukhari:156", "hadith:bukhari:1614", "hadith:bukhari:1639", "hadith:bukhari:1643",
    "hadith:bukhari:1653", "hadith:bukhari:1657", "hadith:bukhari:1837", "hadith:bukhari:1840",
    "hadith:bukhari:2035", "hadith:bukhari:2039", "hadith:bukhari:2040", "hadith:bukhari:2075",
    "hadith:bukhari:2117", "hadith:bukhari:2129", "hadith:bukhari:2158", "hadith:bukhari:2163",
    "hadith:bukhari:2164", "hadith:bukhari:2270", "hadith:bukhari:2342", "hadith:bukhari:238",
    "hadith:bukhari:2398", "hadith:bukhari:2678", "hadith:bukhari:2696", "hadith:bukhari:2720",
    "hadith:bukhari:2865", "hadith:bukhari:2866", "hadith:bukhari:2885", "hadith:bukhari:2954",
    "hadith:bukhari:3179", "hadith:bukhari:3327", "hadith:bukhari:333", "hadith:bukhari:3350",
    "hadith:bukhari:346", "hadith:bukhari:3658", "hadith:bukhari:374", "hadith:bukhari:3855",
    "hadith:bukhari:3883", "hadith:bukhari:3938", "hadith:bukhari:4229", "hadith:bukhari:4411",
    "hadith:bukhari:4419", "hadith:bukhari:4446", "hadith:bukhari:4472", "hadith:bukhari:448",
    "hadith:bukhari:4585", "hadith:bukhari:4587", "hadith:bukhari:4639", "hadith:bukhari:466",
    "hadith:bukhari:4662", "hadith:bukhari:4674", "hadith:bukhari:4758", "hadith:bukhari:4766",
    "hadith:bukhari:4824", "hadith:bukhari:5033", "hadith:bukhari:5083", "hadith:bukhari:5090",
    "hadith:bukhari:5115", "hadith:bukhari:5124", "hadith:bukhari:5132", "hadith:bukhari:5134",
    "hadith:bukhari:5197", "hadith:bukhari:5198", "hadith:bukhari:5205", "hadith:bukhari:5232",
    "hadith:bukhari:5272", "hadith:bukhari:5274", "hadith:bukhari:5277", "hadith:bukhari:5291",
    "hadith:bukhari:5306", "hadith:bukhari:5308", "hadith:bukhari:5358", "hadith:bukhari:5369",
    "hadith:bukhari:537", "hadith:bukhari:5370", "hadith:bukhari:5373", "hadith:bukhari:5408",
    "hadith:bukhari:5480", "hadith:bukhari:5500", "hadith:bukhari:5520", "hadith:bukhari:5526",
    "hadith:bukhari:5564", "hadith:bukhari:5577", "hadith:bukhari:5592", "hadith:bukhari:5600",
    "hadith:bukhari:5627", "hadith:bukhari:5675", "hadith:bukhari:5687", "hadith:bukhari:5801",
    "hadith:bukhari:5908", "hadith:bukhari:6068", "hadith:bukhari:6272", "hadith:bukhari:6278",
    "hadith:bukhari:6369", "hadith:bukhari:6375", "hadith:bukhari:6427", "hadith:bukhari:6500",
    "hadith:bukhari:6562", "hadith:bukhari:674", "hadith:bukhari:6842", "hadith:bukhari:6850",
    "hadith:bukhari:6863", "hadith:bukhari:6906", "hadith:bukhari:6907", "hadith:bukhari:730",
    "hadith:bukhari:731", "hadith:bukhari:75", "hadith:bukhari:765", "hadith:bukhari:848",
    "hadith:bukhari:886", "hadith:bukhari:959", "hadith:ibnmajah:1028", "hadith:ibnmajah:1029",
    "hadith:ibnmajah:1038", "hadith:ibnmajah:1184", "hadith:ibnmajah:1242",
    "hadith:ibnmajah:1286", "hadith:ibnmajah:1299", "hadith:ibnmajah:1324",
    "hadith:ibnmajah:1342", "hadith:ibnmajah:1353", "hadith:ibnmajah:1461",
    "hadith:ibnmajah:1473", "hadith:ibnmajah:1495", "hadith:ibnmajah:1504",
    "hadith:ibnmajah:1506", "hadith:ibnmajah:1507", "hadith:ibnmajah:1560",
    "hadith:ibnmajah:1562", "hadith:ibnmajah:1574", "hadith:ibnmajah:1575",
    "hadith:ibnmajah:1576", "hadith:ibnmajah:1579", "hadith:ibnmajah:1580",
    "hadith:ibnmajah:1592", "hadith:ibnmajah:1613", "hadith:ibnmajah:1648",
    "hadith:ibnmajah:1661", "hadith:ibnmajah:1678", "hadith:ibnmajah:1679",
    "hadith:ibnmajah:1680", "hadith:ibnmajah:1683", "hadith:ibnmajah:173",
    "hadith:ibnmajah:1743", "hadith:ibnmajah:1802", "hadith:ibnmajah:1808",
    "hadith:ibnmajah:1832", "hadith:ibnmajah:1833", "hadith:ibnmajah:1847",
    "hadith:ibnmajah:1881", "hadith:ibnmajah:1884", "hadith:ibnmajah:1885",
    "hadith:ibnmajah:1978", "hadith:ibnmajah:1979", "hadith:ibnmajah:2042",
    "hadith:ibnmajah:2078", "hadith:ibnmajah:2115", "hadith:ibnmajah:2150",
    "hadith:ibnmajah:2154", "hadith:ibnmajah:2161", "hadith:ibnmajah:2165",
    "hadith:ibnmajah:2168", "hadith:ibnmajah:2169", "hadith:ibnmajah:2173",
    "hadith:ibnmajah:2174", "hadith:ibnmajah:2179", "hadith:ibnmajah:2180",
    "hadith:ibnmajah:2185", "hadith:ibnmajah:2192", "hadith:ibnmajah:2193",
    "hadith:ibnmajah:2194", "hadith:ibnmajah:2195", "hadith:ibnmajah:2218",
    "hadith:ibnmajah:2222", "hadith:ibnmajah:2266", "hadith:ibnmajah:2267",
    "hadith:ibnmajah:2268", "hadith:ibnmajah:2296", "hadith:ibnmajah:234",
    "hadith:ibnmajah:235", "hadith:ibnmajah:2370", "hadith:ibnmajah:2381",
    "hadith:ibnmajah:2390", "hadith:ibnmajah:2441", "hadith:ibnmajah:2477",
    "hadith:ibnmajah:2495", "hadith:ibnmajah:2500", "hadith:ibnmajah:2509",
    "hadith:ibnmajah:2510", "hadith:ibnmajah:2512", "hadith:ibnmajah:2514",
    "hadith:ibnmajah:2516", "hadith:ibnmajah:2592", "hadith:ibnmajah:2645",
    "hadith:ibnmajah:2650", "hadith:ibnmajah:2654", "hadith:ibnmajah:2667",
    "hadith:ibnmajah:2668", "hadith:ibnmajah:2676", "hadith:ibnmajah:2735",
    "hadith:ibnmajah:2747", "hadith:ibnmajah:2748", "hadith:ibnmajah:2769",
    "hadith:ibnmajah:2773", "hadith:ibnmajah:2833", "hadith:ibnmajah:2834",
    "hadith:ibnmajah:2964", "hadith:ibnmajah:2965", "hadith:ibnmajah:2966",
    "hadith:ibnmajah:2969", "hadith:ibnmajah:2974", "hadith:ibnmajah:2996",
    "hadith:ibnmajah:3005", "hadith:ibnmajah:3032", "hadith:ibnmajah:3047",
    "hadith:ibnmajah:3101", "hadith:ibnmajah:3161", "hadith:ibnmajah:3162",
    "hadith:ibnmajah:3186", "hadith:ibnmajah:3189", "hadith:ibnmajah:3202",
    "hadith:ibnmajah:3210", "hadith:ibnmajah:3230", "hadith:ibnmajah:3242",
    "hadith:ibnmajah:3250", "hadith:ibnmajah:3262", "hadith:ibnmajah:3265",
    "hadith:ibnmajah:3302", "hadith:ibnmajah:3308", "hadith:ibnmajah:3315",
    "hadith:ibnmajah:3316", "hadith:ibnmajah:3317", "hadith:ibnmajah:3323",
    "hadith:ibnmajah:3325", "hadith:ibnmajah:3326", "hadith:ibnmajah:3332",
    "hadith:ibnmajah:3387", "hadith:ibnmajah:3388", "hadith:ibnmajah:3391",
    "hadith:ibnmajah:3404", "hadith:ibnmajah:3420", "hadith:ibnmajah:3424",
    "hadith:ibnmajah:3428", "hadith:ibnmajah:3430", "hadith:ibnmajah:3459",
    "hadith:ibnmajah:3501", "hadith:ibnmajah:3506", "hadith:ibnmajah:3507",
    "hadith:ibnmajah:3528", "hadith:ibnmajah:3533", "hadith:ibnmajah:3579",
    "hadith:ibnmajah:3582", "hadith:ibnmajah:3589", "hadith:ibnmajah:3615",
    "hadith:ibnmajah:3628", "hadith:ibnmajah:3630", "hadith:ibnmajah:3638",
    "hadith:ibnmajah:3642", "hadith:ibnmajah:3643", "hadith:ibnmajah:3647",
    "hadith:ibnmajah:3654", "hadith:ibnmajah:3655", "hadith:ibnmajah:3656",
    "hadith:ibnmajah:3704", "hadith:ibnmajah:3731", "hadith:ibnmajah:3738",
    "hadith:ibnmajah:3745", "hadith:ibnmajah:3746", "hadith:ibnmajah:3777",
    "hadith:ibnmajah:3852", "hadith:ibnmajah:4052", "hadith:ibnmajah:4057",
    "hadith:ibnmajah:411", "hadith:ibnmajah:417", "hadith:ibnmajah:4252",
    "hadith:ibnmajah:426", "hadith:ibnmajah:429", "hadith:ibnmajah:433", "hadith:ibnmajah:443",
    "hadith:ibnmajah:445", "hadith:ibnmajah:463", "hadith:ibnmajah:464", "hadith:ibnmajah:472",
    "hadith:ibnmajah:473", "hadith:ibnmajah:476", "hadith:ibnmajah:607", "hadith:ibnmajah:651",
    "hadith:ibnmajah:681", "hadith:ibnmajah:74", "hadith:ibnmajah:75", "hadith:ibnmajah:854",
    "hadith:ibnmajah:915", "hadith:ibnmajah:929", "hadith:ibnmajah:931", "hadith:ibnmajah:957",
    "hadith:ibnmajah:985", "hadith:muslim:1004-2", "hadith:muslim:1005",
    "hadith:muslim:1018-2", "hadith:muslim:1024-2", "hadith:muslim:1032-3",
    "hadith:muslim:1055-4", "hadith:muslim:1059-3", "hadith:muslim:1068-2",
    "hadith:muslim:1075-4", "hadith:muslim:1078-2", "hadith:muslim:1080-10",
    "hadith:muslim:1103-4", "hadith:muslim:1106-11", "hadith:muslim:1107",
    "hadith:muslim:1115-2", "hadith:muslim:1121-3", "hadith:muslim:1130-2",
    "hadith:muslim:1141-2", "hadith:muslim:1142-2", "hadith:muslim:1146-2",
    "hadith:muslim:1151-3", "hadith:muslim:1151-7", "hadith:muslim:1176-2",
    "hadith:muslim:1178-2", "hadith:muslim:1184-3", "hadith:muslim:1189-4",
    "hadith:muslim:1211-12", "hadith:muslim:1211-15", "hadith:muslim:1215-2",
    "hadith:muslim:1225-3", "hadith:muslim:1226-10", "hadith:muslim:1226-8",
    "hadith:muslim:1250-2", "hadith:muslim:1252-2", "hadith:muslim:1257-2",
    "hadith:muslim:1262-2", "hadith:muslim:1271", "hadith:muslim:1286-3",
    "hadith:muslim:1288-2", "hadith:muslim:1288-3", "hadith:muslim:1289-2",
    "hadith:muslim:1296-5", "hadith:muslim:1301-4", "hadith:muslim:1319-2",
    "hadith:muslim:1328", "hadith:muslim:133", "hadith:muslim:1332", "hadith:muslim:1344-2",
    "hadith:muslim:1399-7", "hadith:muslim:1406-8", "hadith:muslim:1407-7",
    "hadith:muslim:1415-2", "hadith:muslim:1415-3", "hadith:muslim:1415-4",
    "hadith:muslim:1417", "hadith:muslim:1427-3", "hadith:muslim:1427-4",
    "hadith:muslim:1439-3", "hadith:muslim:1442-3", "hadith:muslim:1445-7",
    "hadith:muslim:1455-2", "hadith:muslim:1459-4", "hadith:muslim:1471-11",
    "hadith:muslim:1471-17", "hadith:muslim:1480-20", "hadith:muslim:1499-2",
    "hadith:muslim:1504-10", "hadith:muslim:1506", "hadith:muslim:1510-2",
    "hadith:muslim:1511", "hadith:muslim:1513", "hadith:muslim:1514", "hadith:muslim:1516",
    "hadith:muslim:1518", "hadith:muslim:1536-11", "hadith:muslim:1536-17",
    "hadith:muslim:1536-22", "hadith:muslim:1536-23", "hadith:muslim:1539-8",
    "hadith:muslim:1545", "hadith:muslim:1547-2", "hadith:muslim:1547-6",
    "hadith:muslim:1547-7", "hadith:muslim:1550-2", "hadith:muslim:1565",
    "hadith:muslim:1581-2", "hadith:muslim:1584-6", "hadith:muslim:1596-2",
    "hadith:muslim:1596-4", "hadith:muslim:1604-4", "hadith:muslim:1605-2",
    "hadith:muslim:1625-13", "hadith:muslim:1625-14", "hadith:muslim:1625-8",
    "hadith:muslim:1626", "hadith:muslim:1626-2", "hadith:muslim:1656-6",
    "hadith:muslim:1658-5", "hadith:muslim:1660-2", "hadith:muslim:1669-3",
    "hadith:muslim:1671-5", "hadith:muslim:1691-5", "hadith:muslim:17-7",
    "hadith:muslim:1701-2", "hadith:muslim:1706-2", "hadith:muslim:1709-7",
    "hadith:muslim:1724", "hadith:muslim:1731", "hadith:muslim:1739", "hadith:muslim:1740",
    "hadith:muslim:1742-4", "hadith:muslim:1750-2", "hadith:muslim:176",
    "hadith:muslim:1792-2", "hadith:muslim:1796-2", "hadith:muslim:1815-2",
    "hadith:muslim:1838-3", "hadith:muslim:1838-4", "hadith:muslim:1844-3",
    "hadith:muslim:1848-2", "hadith:muslim:1848-4", "hadith:muslim:1852-2",
    "hadith:muslim:1874", "hadith:muslim:1879-2", "hadith:muslim:1888-3",
    "hadith:muslim:1889-3", "hadith:muslim:1896-2", "hadith:muslim:1911-2",
    "hadith:muslim:1929-4", "hadith:muslim:1929-5", "hadith:muslim:1938-3",
    "hadith:muslim:1941-2", "hadith:muslim:1953-2", "hadith:muslim:1966-4",
    "hadith:muslim:1977-2", "hadith:muslim:1995-2", "hadith:muslim:1995-6",
    "hadith:muslim:1997-11", "hadith:muslim:1997-8", "hadith:muslim:1998-2",
    "hadith:muslim:200-3", "hadith:muslim:2023", "hadith:muslim:2024", "hadith:muslim:2025",
    "hadith:muslim:2025-2", "hadith:muslim:2027-5", "hadith:muslim:2043", "hadith:muslim:2044",
    "hadith:muslim:2051-2", "hadith:muslim:2080-3", "hadith:muslim:2082-3",
    "hadith:muslim:2085-2", "hadith:muslim:2089", "hadith:muslim:2101", "hadith:muslim:2114",
    "hadith:muslim:2116", "hadith:muslim:2123-3", "hadith:muslim:2144-5", "hadith:muslim:2151",
    "hadith:muslim:2155-3", "hadith:muslim:2165-2", "hadith:muslim:2187",
    "hadith:muslim:2219-3", "hadith:muslim:2223-2", "hadith:muslim:2232-2",
    "hadith:muslim:2233-6", "hadith:muslim:2243-2", "hadith:muslim:2255-2",
    "hadith:muslim:2269-3", "hadith:muslim:2307-3", "hadith:muslim:2310-2",
    "hadith:muslim:2341-7", "hadith:muslim:2347-2", "hadith:muslim:2350", "hadith:muslim:2379",
    "hadith:muslim:2380-5", "hadith:muslim:2382-2", "hadith:muslim:2392-3",
    "hadith:muslim:2400-2", "hadith:muslim:2410-3", "hadith:muslim:2422",
    "hadith:muslim:2464-4", "hadith:muslim:2480-2", "hadith:muslim:2488-2",
    "hadith:muslim:2520-2", "hadith:muslim:2522-2", "hadith:muslim:2548-3",
    "hadith:muslim:2549-2", "hadith:muslim:2559-3", "hadith:muslim:2559-6",
    "hadith:muslim:2591-2", "hadith:muslim:261-2", "hadith:muslim:2612-2",
    "hadith:muslim:2641", "hadith:muslim:2670", "hadith:muslim:2704-5", "hadith:muslim:2709-2",
    "hadith:muslim:2721-2", "hadith:muslim:2737-3", "hadith:muslim:2738-2",
    "hadith:muslim:2751-2", "hadith:muslim:2756-2", "hadith:muslim:2774-2",
    "hadith:muslim:2784-2", "hadith:muslim:2801-2", "hadith:muslim:2810-4",
    "hadith:muslim:2811-4", "hadith:muslim:2843-2", "hadith:muslim:2853-2",
    "hadith:muslim:2869", "hadith:muslim:287-2", "hadith:muslim:2894-2",
    "hadith:muslim:2923-2", "hadith:muslim:2935", "hadith:muslim:2939-3",
    "hadith:muslim:2984-2", "hadith:muslim:2987-2", "hadith:muslim:3024-2",
    "hadith:muslim:313-2", "hadith:muslim:332-4", "hadith:muslim:373", "hadith:muslim:392-6",
    "hadith:muslim:406-3", "hadith:muslim:419-3", "hadith:muslim:453-4", "hadith:muslim:463",
    "hadith:muslim:467-4", "hadith:muslim:47-3", "hadith:muslim:504-3", "hadith:muslim:517-2",
    "hadith:muslim:518-2", "hadith:muslim:540-4", "hadith:muslim:541-2", "hadith:muslim:546-2",
    "hadith:muslim:548-2", "hadith:muslim:555", "hadith:muslim:572-3", "hadith:muslim:572-4",
    "hadith:muslim:572-7", "hadith:muslim:572-9", "hadith:muslim:578", "hadith:muslim:580-4",
    "hadith:muslim:581", "hadith:muslim:592-2", "hadith:muslim:592-3", "hadith:muslim:612-3",
    "hadith:muslim:621-2", "hadith:muslim:627-4", "hadith:muslim:632-2", "hadith:muslim:649-3",
    "hadith:muslim:650-3", "hadith:muslim:650-4", "hadith:muslim:674-5", "hadith:muslim:678-2",
    "hadith:muslim:694-2", "hadith:muslim:700-8", "hadith:muslim:708-2", "hadith:muslim:724-2",
    "hadith:muslim:750", "hadith:muslim:754-2", "hadith:muslim:792-6", "hadith:muslim:804-2",
    "hadith:muslim:81-2", "hadith:muslim:823", "hadith:muslim:830-2", "hadith:muslim:838-2",
    "hadith:muslim:863-2", "hadith:muslim:872-2", "hadith:muslim:879-3", "hadith:muslim:892-2",
    "hadith:muslim:907-2", "hadith:muslim:939-2", "hadith:muslim:944-2", "hadith:muslim:945-3",
    "hadith:muslim:946-2", "hadith:muslim:957", "hadith:muslim:967", "hadith:muslim:969-2",
    "hadith:muslim:970-3", "hadith:muslim:979-8", "hadith:nasai:1014", "hadith:nasai:1015",
    "hadith:nasai:105", "hadith:nasai:1086", "hadith:nasai:121", "hadith:nasai:1316",
    "hadith:nasai:1355", "hadith:nasai:142", "hadith:nasai:1516", "hadith:nasai:1531",
    "hadith:nasai:1661", "hadith:nasai:1683", "hadith:nasai:1684", "hadith:nasai:1687",
    "hadith:nasai:1706", "hadith:nasai:1755", "hadith:nasai:179", "hadith:nasai:1824",
    "hadith:nasai:1829", "hadith:nasai:1905", "hadith:nasai:1982", "hadith:nasai:199",
    "hadith:nasai:1999", "hadith:nasai:2005", "hadith:nasai:2029", "hadith:nasai:2030",
    "hadith:nasai:2139", "hadith:nasai:2143", "hadith:nasai:2176", "hadith:nasai:2181",
    "hadith:nasai:2224", "hadith:nasai:2225", "hadith:nasai:2226", "hadith:nasai:2227",
    "hadith:nasai:2228", "hadith:nasai:2229", "hadith:nasai:226", "hadith:nasai:2273",
    "hadith:nasai:2292", "hadith:nasai:2355", "hadith:nasai:2356", "hadith:nasai:2362",
    "hadith:nasai:2364", "hadith:nasai:2465", "hadith:nasai:2610", "hadith:nasai:2611",
    "hadith:nasai:2616", "hadith:nasai:2683", "hadith:nasai:2707", "hadith:nasai:2708",
    "hadith:nasai:2715", "hadith:nasai:2716", "hadith:nasai:2728", "hadith:nasai:2730",
    "hadith:nasai:2772", "hadith:nasai:2786", "hadith:nasai:2838", "hadith:nasai:2885",
    "hadith:nasai:2886", "hadith:nasai:2940", "hadith:nasai:2977", "hadith:nasai:3015",
    "hadith:nasai:3045", "hadith:nasai:3206", "hadith:nasai:3213", "hadith:nasai:3214",
    "hadith:nasai:3334", "hadith:nasai:3452", "hadith:nasai:35", "hadith:nasai:3571",
    "hadith:nasai:3706", "hadith:nasai:3711", "hadith:nasai:3715", "hadith:nasai:3716",
    "hadith:nasai:3717", "hadith:nasai:3718", "hadith:nasai:3720", "hadith:nasai:3721",
    "hadith:nasai:3724", "hadith:nasai:3725", "hadith:nasai:3726", "hadith:nasai:3727",
    "hadith:nasai:3729", "hadith:nasai:3738", "hadith:nasai:3754", "hadith:nasai:3833",
    "hadith:nasai:3870", "hadith:nasai:3878", "hadith:nasai:3884", "hadith:nasai:3885",
    "hadith:nasai:3886", "hadith:nasai:3887", "hadith:nasai:3888", "hadith:nasai:3891",
    "hadith:nasai:3893", "hadith:nasai:3905", "hadith:nasai:3914", "hadith:nasai:3916",
    "hadith:nasai:3917", "hadith:nasai:4071", "hadith:nasai:4213", "hadith:nasai:4216",
    "hadith:nasai:4244", "hadith:nasai:4245", "hadith:nasai:4246", "hadith:nasai:4247",
    "hadith:nasai:4253", "hadith:nasai:43", "hadith:nasai:4343", "hadith:nasai:4386",
    "hadith:nasai:4438", "hadith:nasai:4442", "hadith:nasai:4498", "hadith:nasai:4505",
    "hadith:nasai:4509", "hadith:nasai:4511", "hadith:nasai:4512", "hadith:nasai:4518",
    "hadith:nasai:4529", "hadith:nasai:4531", "hadith:nasai:4535", "hadith:nasai:4536",
    "hadith:nasai:4572", "hadith:nasai:4580", "hadith:nasai:4591", "hadith:nasai:46",
    "hadith:nasai:4626", "hadith:nasai:4627", "hadith:nasai:4632", "hadith:nasai:4654",
    "hadith:nasai:4657", "hadith:nasai:4658", "hadith:nasai:4659", "hadith:nasai:466",
    "hadith:nasai:4660", "hadith:nasai:4671", "hadith:nasai:4674", "hadith:nasai:4693",
    "hadith:nasai:4702", "hadith:nasai:4705", "hadith:nasai:4777", "hadith:nasai:4842",
    "hadith:nasai:4843", "hadith:nasai:4844", "hadith:nasai:4847", "hadith:nasai:4849",
    "hadith:nasai:4911", "hadith:nasai:4914", "hadith:nasai:4924", "hadith:nasai:4934",
    "hadith:nasai:4950", "hadith:nasai:4962", "hadith:nasai:4973", "hadith:nasai:4974",
    "hadith:nasai:4976", "hadith:nasai:5050", "hadith:nasai:5051", "hadith:nasai:5055",
    "hadith:nasai:5056", "hadith:nasai:5057", "hadith:nasai:5068", "hadith:nasai:5092",
    "hadith:nasai:5097", "hadith:nasai:5111", "hadith:nasai:5112", "hadith:nasai:5115",
    "hadith:nasai:5153", "hadith:nasai:5160", "hadith:nasai:5165", "hadith:nasai:5166",
    "hadith:nasai:5186", "hadith:nasai:5204", "hadith:nasai:5228", "hadith:nasai:5229",
    "hadith:nasai:5230", "hadith:nasai:5231", "hadith:nasai:5243", "hadith:nasai:5249",
    "hadith:nasai:5269", "hadith:nasai:5273", "hadith:nasai:5274", "hadith:nasai:5276",
    "hadith:nasai:5283", "hadith:nasai:5286", "hadith:nasai:533", "hadith:nasai:5343",
    "hadith:nasai:5368", "hadith:nasai:548", "hadith:nasai:5483", "hadith:nasai:5544",
    "hadith:nasai:5545", "hadith:nasai:5574", "hadith:nasai:5575", "hadith:nasai:5576",
    "hadith:nasai:5584", "hadith:nasai:5587", "hadith:nasai:5588", "hadith:nasai:5595",
    "hadith:nasai:5597", "hadith:nasai:5599", "hadith:nasai:5602", "hadith:nasai:5612",
    "hadith:nasai:5615", "hadith:nasai:5616", "hadith:nasai:5617", "hadith:nasai:5618",
    "hadith:nasai:5624", "hadith:nasai:5625", "hadith:nasai:5626", "hadith:nasai:5627",
    "hadith:nasai:5628", "hadith:nasai:5631", "hadith:nasai:5634", "hadith:nasai:5639",
    "hadith:nasai:5642", "hadith:nasai:5679", "hadith:nasai:5728", "hadith:nasai:5733",
    "hadith:nasai:5745", "hadith:nasai:658", "hadith:nasai:676", "hadith:nasai:83",
    "hadith:nasai:91", "hadith:nasai:961", "hadith:nasai:986", "hadith:nasai:987",
    "hadith:tirmidhi:1044", "hadith:tirmidhi:1082", "hadith:tirmidhi:1101",
    "hadith:tirmidhi:1124", "hadith:tirmidhi:1186", "hadith:tirmidhi:1220",
    "hadith:tirmidhi:1224", "hadith:tirmidhi:1231", "hadith:tirmidhi:1248",
    "hadith:tirmidhi:1271", "hadith:tirmidhi:1273", "hadith:tirmidhi:1279",
    "hadith:tirmidhi:1280", "hadith:tirmidhi:1304", "hadith:tirmidhi:1310",
    "hadith:tirmidhi:133", "hadith:tirmidhi:1337", "hadith:tirmidhi:1390",
    "hadith:tirmidhi:1392", "hadith:tirmidhi:1466", "hadith:tirmidhi:1675",
    "hadith:tirmidhi:1677", "hadith:tirmidhi:1695", "hadith:tirmidhi:1708",
    "hadith:tirmidhi:1710", "hadith:tirmidhi:1725", "hadith:tirmidhi:1733",
    "hadith:tirmidhi:1738", "hadith:tirmidhi:1742", "hadith:tirmidhi:1756",
    "hadith:tirmidhi:1760", "hadith:tirmidhi:1771", "hadith:tirmidhi:1772",
    "hadith:tirmidhi:1778", "hadith:tirmidhi:1808", "hadith:tirmidhi:1824",
    "hadith:tirmidhi:1831", "hadith:tirmidhi:1839", "hadith:tirmidhi:1840",
    "hadith:tirmidhi:1842", "hadith:tirmidhi:1844", "hadith:tirmidhi:1864",
    "hadith:tirmidhi:1881", "hadith:tirmidhi:1883", "hadith:tirmidhi:1890",
    "hadith:tirmidhi:1904", "hadith:tirmidhi:200", "hadith:tirmidhi:2045",
    "hadith:tirmidhi:2109", "hadith:tirmidhi:2126", "hadith:tirmidhi:2166",
    "hadith:tirmidhi:2220", "hadith:tirmidhi:2274", "hadith:tirmidhi:2430",
    "hadith:tirmidhi:2501", "hadith:tirmidhi:2579", "hadith:tirmidhi:2735",
    "hadith:tirmidhi:2771", "hadith:tirmidhi:2796", "hadith:tirmidhi:2797",
    "hadith:tirmidhi:2812", "hadith:tirmidhi:2815", "hadith:tirmidhi:2822",
    "hadith:tirmidhi:2823", "hadith:tirmidhi:2827", "hadith:tirmidhi:2831",
    "hadith:tirmidhi:2947", "hadith:tirmidhi:31", "hadith:tirmidhi:3239",
    "hadith:tirmidhi:331", "hadith:tirmidhi:3338", "hadith:tirmidhi:3371",
    "hadith:tirmidhi:3384", "hadith:tirmidhi:3411", "hadith:tirmidhi:3486",
    "hadith:tirmidhi:3642", "hadith:tirmidhi:3650", "hadith:tirmidhi:3741",
    "hadith:tirmidhi:3765", "hadith:tirmidhi:3777", "hadith:tirmidhi:378",
    "hadith:tirmidhi:3824", "hadith:tirmidhi:3828", "hadith:tirmidhi:3944",
    "hadith:tirmidhi:3949", "hadith:tirmidhi:400", "hadith:tirmidhi:467",
    "hadith:tirmidhi:470", "hadith:tirmidhi:588", "hadith:tirmidhi:63", "hadith:tirmidhi:646",
    "hadith:tirmidhi:668", "hadith:tirmidhi:774", "hadith:tirmidhi:820", "hadith:tirmidhi:821",
    "hadith:tirmidhi:851", "hadith:tirmidhi:887", "hadith:tirmidhi:987", "hadith:tirmidhi:991",
    # A2 round 5: genuine short matns the content-mass net surfaces (cm<=3) but
    # that DELIVER a self-contained clause -- da'hu "leave him" (the Prophet's
    # reply at Tabuk, Task 11's canonical meaning-not-length keep) and 581-2.
    "hadith:muslim:274-13", "hadith:muslim:581-2",
]


def test_no_scorable_record_is_a_low_content_pointer():
    """R-A3-18 closure gate, round 5 -- the VOCABULARY-FREE backstop.

    Every scorable hadith primary with `content_mass <= K` must be an audited
    KEEP (`_CONTENT_MASS_KEEPS`), and every id in `_A2R5_CONTENT_MASS_POINTERS`
    must be unscorable. A NEW low-content scorable record -- a pointer behind
    ANY frame word, in any token order -- lands here with no exclusion to hide
    behind, and, not being in the keep list, turns this RED. A MISSING id means
    an audited keep was wrongly marked unscorable (a real hadith made
    unverifiable). This gate names no marker: it is the cure for the marker-axis
    escape pattern that defeated the prior seven closures.
    """
    from sanad_ingest.openiti import content_mass
    from sanad_ingest.audit_lists import UNSCORABLE

    conn = db.connect(str(MATERIALIZED_DB))
    rows = conn.execute(
        "SELECT id, norm_aggressive FROM records WHERE kind = 'hadith' "
        "AND unscorable_reason IS NULL AND norm_aggressive IS NOT NULL"
    ).fetchall()
    hits = sorted(r["id"] for r in rows if r["norm_aggressive"]
                  and content_mass(r["norm_aggressive"]) <= _CONTENT_MASS_K)
    assert hits == sorted(_CONTENT_MASS_KEEPS), (
        "the vocabulary-free content-mass partition changed. A NEW id is a "
        "scorable record whose matn carries <= K content tokens after "
        "scaffolding is stripped -- read it in context, pin it unscorable in "
        "audit_lists._A2R5_CONTENT_MASS_POINTERS and task-16-A2round5-audit.md "
        "if it delivers no self-contained matn, or add it to "
        "_CONTENT_MASS_KEEPS with its delivered clause named. A MISSING id "
        "means an audited keep was wrongly marked unscorable.")

    unscorable = {k for coll in UNSCORABLE.values() for k in coll}
    readmitted = [p for p in _A2R5_CONTENT_MASS_POINTERS if p not in unscorable]
    assert readmitted == [], (
        f"audited content-mass pointers no longer pinned unscorable: {readmitted}")


def test_net_b_reference_superset_surfaces_no_unaudited_pointer():
    """R-A3-18 cross-check gate, round 5 -- the reference-superset (net B).

    `find_pure_pointers(exclude_delivery=False)` is the round-4 residue sweep
    with its delivery guard REMOVED: the whole reference/deferral/chain-bearing
    population, with no "it contains qala, skip it" exclusion -- the exact
    defect of round 4. Every low-content member it surfaces (content_mass <= K)
    must already be audited: pinned unscorable, or an audited content-mass KEEP.
    A NEW one means a reference-bearing pointer slipped past both nets.
    """
    from sanad_ingest.openiti import content_mass, find_pure_pointers
    from sanad_ingest.audit_lists import UNSCORABLE

    conn = db.connect(str(MATERIALIZED_DB))
    rows = conn.execute(
        "SELECT id, norm_aggressive FROM records WHERE kind = 'hadith' "
        "AND unscorable_reason IS NULL AND norm_aggressive IS NOT NULL"
    ).fetchall()
    norms = {r["id"]: r["norm_aggressive"] for r in rows if r["norm_aggressive"]}
    nb = find_pure_pointers(norms, max_residue=10**9, exclude_delivery=False)
    unscorable = {k for coll in UNSCORABLE.values() for k in coll}
    keeps = set(_CONTENT_MASS_KEEPS)
    unaudited = sorted(
        rid for rid, _s, _r in nb
        if content_mass(norms[rid]) <= _CONTENT_MASS_K
        and rid not in keeps and rid not in unscorable)
    assert unaudited == [], (
        "the de-excluded reference-superset surfaced an un-audited low-content "
        f"pointer: {unaudited}. Read it and pin it unscorable or as a keep.")



def test_no_unaudited_near_miss_for_the_ibnmajah_compiler_marker():
    """R-A3-20's own detector, run for Ibn Majah's TWO verb+kunya markers at
    once: "قال"/"سئل"/"سمعت" against both the nominative and accusative forms
    of both al-Qattan's ("أبو/أبا الحسن") and the compiler's own ("أبو/أبا عبد
    الله") kunya, at every token gap 0-4, with `_IBNMAJAH_COMMENTARY`,
    `_IBNMAJAH_COMMENTARY_NEAR`, `_IBNMAJAH_HEARD`, and `_IBNMAJAH_FORMULA` all
    in `configured` so the sweep only reports gaps the shipped marker set does
    not already cover.

    Empty: hadith:ibnmajah:309 (the one genuine gap this sweep originally
    found, at `heard`'s own tolerance boundary) is now covered by
    `_IBNMAJAH_FORMULA`'s anchored fourth arm. A separate, wider gap-8 sweep
    (not shipped as a test -- gap 8 is wide enough to also catch ordinary
    narrative and was used only as a one-off manual check) confirmed
    hadith:ibnmajah:2082's genitive "Abu al-Hasan, mawla of Banu Nawfal" and
    nominative "Abu al-Hasan ... tahammala hadhihi" are two DIFFERENT people,
    neither al-Qattan -- a correct exclusion, not a hazard, and eval-cased
    directly as `hadith-ibnmajah-genitive-narrator-namesake-is-not-cut`.
    """
    import re

    from sanad_ingest.openiti import (
        _ARABIC, _IBNMAJAH_COMMENTARY, _IBNMAJAH_COMMENTARY_NEAR,
        _IBNMAJAH_FORMULA, _IBNMAJAH_HEARD, find_near_misses)

    configured = re.compile(
        f"{_IBNMAJAH_COMMENTARY.pattern}|{_IBNMAJAH_COMMENTARY_NEAR.pattern}"
        f"|{_IBNMAJAH_HEARD.pattern}|{_IBNMAJAH_FORMULA.pattern}")
    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل|سمعت)(?:\s+\S+){{0,4}}"
        rf"\s+(?:أبو|أبا)\s+(?:الحسن|عبد\s+الله)(?![{_ARABIC}])")
    assert find_near_misses(_real_ibnmajah_units(), configured, sweep) == []


# --- Task 15: Sunan Ibn Majah (R-A3-21) --------------------------------------
#
# Every Arabic literal below is a codepoint tuple read out of the built
# database with a one-off script, per the top-of-file convention, never typed.


def _real_ibnmajah_units():
    from sanad_ingest.lockfile import load_lockfile
    from sanad_ingest.openiti import parse_openiti
    from pathlib import Path

    sources = {s.id: s for s in load_lockfile(Path("ingest/corpus.lock.toml"))}
    locked = sources["openiti-ibnmaja-jk000141"]
    cache = Path(".corpus-cache") / (
        f"{locked.id}-{locked.format}-"
        + __import__("hashlib").sha256(locked.url.encode("utf-8")).hexdigest()[:8]
        + ".txt")
    raw = cache.read_text(encoding="utf-8")
    return parse_openiti(raw, collection="ibnmajah").units


def test_ibnmajah_record_count_and_scorability():
    r"""The measured, lockfile-pinned facts about the sixth and final hadith
    collection.

    4,341 is `expected_records` in corpus.lock.toml, the raw file's own
    numbered-unit count. 1 unscorable (hadith:ibnmajah:413, a bare "نحوه"
    pointer -- `UNSCORABLE["ibnmajah"]`), 166 cut (110 already split by the
    generic "*"-marked secondary narration before any Ibn Majah-specific
    marker exists, 56 newly split by this task's own markers).

    Ibn Majah carries TWO editorial voices, not one: a transmitter's own
    aside ("qala Abu al-Hasan [al-Qattan]", kunya "أبو الحسن") and the
    compiler's own ("qala Abu 'Abdallah[ ibn Majah]", kunya "أبو عبد الله",
    or his bare name "بن ماجة"), combined into one marker pair via `_compiler_
    commentary_markers` called twice and `|`-joined so `_split_compiler_
    commentary`'s "earliest candidate wins" rule still holds across both
    voices at once -- see openiti.py's own comment above `_IBNMAJAH_QATTAN_
    TIGHT`/`_IBNMAJAH_COMPILER_TIGHT` for the full, individually-read count
    (40 nominative/2 accusative/4 genitive for al-Qattan's voice, 29
    nominative/2 accusative/9 genitive plus 24 bare-name occurrences for Ibn
    Majah's own; every genitive occurrence, both voices, confirmed to sit
    inside `isnad_ar`, naming a different person each time -- no namesake
    ever reaches scored text). `_IBNMAJAH_FORMULA` covers "هذا حديث" (10,
    Tirmidhi's own tail-opener, recurring here at much smaller scale), the
    one-off "حدثنا أبو الحسن القطان" transmission-verb gap (3458), and a
    second one-off found only by `find_near_misses`'s own sweep, not by the
    read-through: hadith:ibnmajah:309's "سمعت محمد بن يزيد أبا عبد الله
    يقول" (Ibn Majah named in full between سمعت and his own kunya, outside
    `heard`'s token-gap tolerance).

    Sighted but NOT added, every occurrence read individually against
    `matn_ar` alone (not the joined display text): "خالفه"/"خالفهم" (3, all
    genuine narrative -- unlike Nasai, this file gives no isnad-critique use
    of the verb at all), "رفعه" (7, 6 the reward/prayer-posture idiom, 1 a
    terse unattributed note with no name to anchor a boundary on, disclosed
    not chased), "غريب"/"ضعيف"/"خطأ" bare/"الصواب"/"لم يسمع" (ordinary senses
    of common words, no editorial use in this file's occurrences). Two
    further one-off remarks by untracked individuals (hadith:342, 2497) sit
    entirely inside `addenda_ar` already, confirmed against `matn_ar` alone.

    Two hand-audited corrections beyond the marker table itself:
    `NEAR_MISS_CUT_OVERRIDE["ibnmajah"]` (hadith:ibnmajah:1385's dangling
    "qala Abu Ishaq", hadith:ibnmajah:2162's dangling "tafarrada bihi ...
    wahdahu" -- see their own dedicated tests below) and
    `NEVER_CUT["ibnmajah"]` (hadith:ibnmajah:2131 -- see its own test below).

    A pre-existing, out-of-scope defect found while auditing these cuts:
    Muslim's own file independently carries a literal "*" (this edition's
    nested-repeat marker) in three scored matns, and Tirmidhi's in one
    addendum -- both in BASE, unrelated to this task, and NOT fixed here
    because doing so would touch `_clean()`, which every one of the five
    prior collections' byte-identical proof depends on staying untouched.
    `_strip_stray_asterisk` fixes the one Ibn Majah record where `NEVER_CUT`
    would otherwise leave one behind, collection-scoped, touching nothing
    else -- see its own docstring.

    Digit width is NOT a universal OpenITI convention: this file's own
    milestones are 3 digits (`msNNN`), not the 4-digit `msNNNN` all five
    prior collections use. `_MILESTONE` widened from `ms\d{4}` to `ms\d+`
    to strip both, verified byte-identical for all five prior collections
    (see the review report for the full cross-commit proof).
    """
    conn = db.connect(DB_PATH)
    total = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='ibnmajah'"
    ).fetchone()[0]
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='ibnmajah'"
        " AND unscorable_reason IS NULL").fetchone()[0]
    unscorable = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='ibnmajah'"
        " AND unscorable_reason IS NOT NULL").fetchone()[0]
    cut = conn.execute(
        "SELECT count(*) FROM records WHERE kind='hadith' AND collection='ibnmajah'"
        " AND addenda_ar IS NOT NULL").fetchone()[0]
    # A2 round 5 (content-mass net): +1 unscorable (ibnmajah:1130, an editorial
    # back-reference "kana rasulu llah [saw] yasna'u dhalika"): 4340 -> 4339.
    assert (total, scorable, unscorable, cut) == (4341, 4339, 2, 166)

_IBNMAJAH_1_MATN = "".join(chr(c) for c in (
    0x0645, 0x0627, 0x0020, 0x0623, 0x0645, 0x0631, 0x062a, 0x0643, 0x0645, 
    0x0020, 0x0628, 0x0647, 0x0020, 0x0641, 0x062e, 0x0630, 0x0648, 0x0647, 
    0x0020, 0x0648, 0x0645, 0x0627, 0x0020, 0x0646, 0x0647, 0x064a, 0x062a, 
    0x0643, 0x0645, 0x0020, 0x0639, 0x0646, 0x0647, 0x0020, 0x0641, 0x0627, 
    0x0646, 0x062a, 0x0647, 0x0648, 0x0627, 
))


def test_ibnmajah_hadith_1_is_byte_exact():
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:ibnmajah:1")
    assert rec.text_ar == _IBNMAJAH_1_MATN
    assert rec.unscorable_reason is None



# hadith:ibnmajah:2131 -- a father asking the Prophet about a vow to sacrifice
# at Buwana; "was there an idol there? No." "Then fulfil your vow." Immediately
# followed, with no separating word, by a second complete isnad reaching the
# same report via a different chain -- whose own forward-looking chain shape
# let a BARE "qala" (with no name) count as `_split_secondary`'s own cut point,
# stranding the Prophet's actual reply ("fulfil your vow") in the addendum
# alongside an unrelated second chain. `NEVER_CUT["ibnmajah"]` keeps the whole
# unit intact; `_strip_stray_asterisk` removes the literal "*" the edition's
# own nested-repeat convention would otherwise leave sitting in scored text.
_IBNMAJAH_2131_MATN = "".join(chr(c) for c in (
    0x0623, 0x0646, 0x0020, 0x0623, 0x0628, 0x0627, 0x0647, 0x0627, 0x0020, 
    0x0644, 0x0642, 0x064a, 0x0020, 0x0627, 0x0644, 0x0646, 0x0628, 0x064a, 
    0x0020, 0x0635, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644, 0x0644, 0x0647, 
    0x0020, 0x0639, 0x0644, 0x064a, 0x0647, 0x0020, 0x0648, 0x0633, 0x0644, 
    0x0645, 0x0020, 0x0648, 0x0647, 0x064a, 0x0020, 0x0631, 0x062f, 0x064a, 
    0x0641, 0x0647, 0x0020, 0x0644, 0x0647, 0x0020, 0x0641, 0x0642, 0x0627, 
    0x0644, 0x0020, 0x0625, 0x0646, 0x064a, 0x0020, 0x0646, 0x0630, 0x0631, 
    0x062a, 0x0020, 0x0623, 0x0646, 0x0020, 0x0623, 0x0646, 0x062d, 0x0631, 
    0x0020, 0x0628, 0x0628, 0x0648, 0x0627, 0x0646, 0x0629, 0x0020, 0x0641, 
    0x0642, 0x0627, 0x0644, 0x0020, 0x0631, 0x0633, 0x0648, 0x0644, 0x0020, 
    0x0627, 0x0644, 0x0644, 0x0647, 0x0020, 0x0635, 0x0644, 0x0649, 0x0020, 
    0x0627, 0x0644, 0x0644, 0x0647, 0x0020, 0x0639, 0x0644, 0x064a, 0x0647, 
    0x0020, 0x0648, 0x0633, 0x0644, 0x0645, 0x0020, 0x0647, 0x0644, 0x0020, 
    0x0628, 0x0647, 0x0627, 0x0020, 0x0648, 0x062b, 0x0646, 0x0020, 0x0642, 
    0x0627, 0x0644, 0x0020, 0x0644, 0x0627, 0x0020, 0x0642, 0x0627, 0x0644, 
    0x0020, 0x0623, 0x0648, 0x0641, 0x0020, 0x0628, 0x0646, 0x0630, 0x0631, 
    0x0643, 0x0020, 0x062d, 0x062f, 0x062b, 0x0646, 0x0627, 0x0020, 0x0623, 
    0x0628, 0x0648, 0x0020, 0x0628, 0x0643, 0x0631, 0x0020, 0x0628, 0x0646, 
    0x0020, 0x0623, 0x0628, 0x064a, 0x0020, 0x0634, 0x064a, 0x0628, 0x0629, 
    0x0020, 0x062b, 0x0646, 0x0627, 0x0020, 0x0628, 0x0646, 0x0020, 0x062f, 
    0x0643, 0x064a, 0x0646, 0x0020, 0x0639, 0x0646, 0x0020, 0x0639, 0x0628, 
    0x062f, 0x0020, 0x0627, 0x0644, 0x0644, 0x0647, 0x0020, 0x0628, 0x0646, 
    0x0020, 0x0639, 0x0628, 0x062f, 0x0020, 0x0627, 0x0644, 0x0631, 0x062d, 
    0x0645, 0x0646, 0x0020, 0x0639, 0x0646, 0x0020, 0x064a, 0x0632, 0x064a, 
    0x062f, 0x0020, 0x0628, 0x0646, 0x0020, 0x0645, 0x0642, 0x0633, 0x0645, 
    0x0020, 0x0639, 0x0646, 0x0020, 0x0645, 0x064a, 0x0645, 0x0648, 0x0646, 
    0x0629, 0x0020, 0x0628, 0x0646, 0x062a, 0x0020, 0x0643, 0x0631, 0x062f, 
    0x0645, 0x0020, 0x0639, 0x0646, 0x0020, 0x0627, 0x0644, 0x0646, 0x0628, 
    0x064a, 0x0020, 0x0635, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644, 0x0644, 
    0x0647, 0x0020, 0x0639, 0x0644, 0x064a, 0x0647, 0x0020, 0x0648, 0x0633, 
    0x0644, 0x0645, 0x0020, 0x0628, 0x0646, 0x062d, 0x0648, 0x0647, 
))


def test_the_ibnmajah_never_cut_exception_verifies_whole():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:ibnmajah:2131")
    assert rec.text_ar == _IBNMAJAH_2131_MATN
    assert "*" not in rec.text_ar
    assert rec.addenda_ar is None
    assert rec.unscorable_reason is None
    m = verify_spans(conn, f"«{rec.text_ar}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    assert m[0].record.id == "hadith:ibnmajah:2131"



# hadith:ibnmajah:1385 -- the tawassul supplication ("O Allah, I ask You and
# turn to You through Muhammad, the Prophet of mercy ..."). `_IBNMAJAH_
# FORMULA`'s "hadha hadith" arm cuts at "hadha" but leaves "qala Abu Ishaq"
# (the narrator introducing the grading remark that follows) dangling on the
# genuine du'a -- corrected by `NEAR_MISS_CUT_OVERRIDE["ibnmajah"]`, the same
# nested-attribution shape as Abu Dawud/Tirmidhi/Nasai's own entries.
#
# hadith:ibnmajah:2162 -- a cupping-fee ruling. "qalahu Ibn Majah" ("Ibn Majah
# said IT") refers BACKWARD to "tafarrada bihi Ibn Abi 'Umar wahdahu" (an
# isnad-uniqueness remark) that precedes it -- the opposite order from every
# other "qala <compiler> ..." shape in this file -- so the marker's own
# anchor on "qalahu" leaves that remark dangling on the genuine matn.
_IBNMAJAH_1385_MATN = "".join(chr(c) for c in (
    0x0627, 0x062f, 0x0639, 0x0020, 0x0627, 0x0644, 0x0644, 0x0647, 0x0020, 
    0x0644, 0x064a, 0x0020, 0x0623, 0x0646, 0x0020, 0x064a, 0x0639, 0x0627, 
    0x0641, 0x064a, 0x0646, 0x064a, 0x0020, 0x0641, 0x0642, 0x0627, 0x0644, 
    0x0020, 0x0625, 0x0646, 0x0020, 0x0634, 0x0626, 0x062a, 0x0020, 0x0623, 
    0x062e, 0x0631, 0x062a, 0x0020, 0x0644, 0x0643, 0x0020, 0x0648, 0x0647, 
    0x0648, 0x0020, 0x062e, 0x064a, 0x0631, 0x0020, 0x0648, 0x0625, 0x0646, 
    0x0020, 0x0634, 0x0626, 0x062a, 0x0020, 0x062f, 0x0639, 0x0648, 0x062a, 
    0x0020, 0x0641, 0x0642, 0x0627, 0x0644, 0x0020, 0x0627, 0x062f, 0x0639, 
    0x0647, 0x0020, 0x0641, 0x0623, 0x0645, 0x0631, 0x0647, 0x0020, 0x0623, 
    0x0646, 0x0020, 0x064a, 0x062a, 0x0648, 0x0636, 0x0623, 0x0020, 0x0641, 
    0x064a, 0x062d, 0x0633, 0x0646, 0x0020, 0x0648, 0x0636, 0x0648, 0x0621, 
    0x0647, 0x0020, 0x0648, 0x064a, 0x0635, 0x0644, 0x064a, 0x0020, 0x0631, 
    0x0643, 0x0639, 0x062a, 0x064a, 0x0646, 0x0020, 0x0648, 0x064a, 0x062f, 
    0x0639, 0x0648, 0x0020, 0x0628, 0x0647, 0x0630, 0x0627, 0x0020, 0x0627, 
    0x0644, 0x062f, 0x0639, 0x0627, 0x0621, 0x0020, 0x0627, 0x0644, 0x0644, 
    0x0647, 0x0645, 0x0020, 0x0625, 0x0646, 0x064a, 0x0020, 0x0623, 0x0633, 
    0x0623, 0x0644, 0x0643, 0x0020, 0x0648, 0x0623, 0x062a, 0x0648, 0x062c, 
    0x0647, 0x0020, 0x0625, 0x0644, 0x064a, 0x0643, 0x0020, 0x0628, 0x0645, 
    0x062d, 0x0645, 0x062f, 0x0020, 0x0646, 0x0628, 0x064a, 0x0020, 0x0627, 
    0x0644, 0x0631, 0x062d, 0x0645, 0x0629, 0x0020, 0x064a, 0x0627, 0x0020, 
    0x0645, 0x062d, 0x0645, 0x062f, 0x0020, 0x0625, 0x0646, 0x064a, 0x0020, 
    0x0642, 0x062f, 0x0020, 0x062a, 0x0648, 0x062c, 0x0647, 0x062a, 0x0020, 
    0x0628, 0x0643, 0x0020, 0x0625, 0x0644, 0x0649, 0x0020, 0x0631, 0x0628, 
    0x064a, 0x0020, 0x0641, 0x064a, 0x0020, 0x062d, 0x0627, 0x062c, 0x062a, 
    0x064a, 0x0020, 0x0647, 0x0630, 0x0647, 0x0020, 0x0644, 0x062a, 0x0642, 
    0x0636, 0x0649, 0x0020, 0x0627, 0x0644, 0x0644, 0x0647, 0x0645, 0x0020, 
    0x0641, 0x0634, 0x0641, 0x0639, 0x0647, 0x0020, 0x0641, 0x064a, 
))
_IBNMAJAH_1385_ADDENDA = "".join(chr(c) for c in (
    0x0642, 0x0627, 0x0644, 0x0020, 0x0623, 0x0628, 0x0648, 0x0020, 0x0625, 
    0x0633, 0x062d, 0x0627, 0x0642, 0x0020, 0x0647, 0x0630, 0x0627, 0x0020, 
    0x062d, 0x062f, 0x064a, 0x062b, 0x0020, 0x0635, 0x062d, 0x064a, 0x062d, 
))
_IBNMAJAH_2162_MATN = "".join(chr(c) for c in (
    0x0623, 0x0646, 0x0020, 0x0627, 0x0644, 0x0646, 0x0628, 0x064a, 0x0020, 
    0x0635, 0x0644, 0x0649, 0x0020, 0x0627, 0x0644, 0x0644, 0x0647, 0x0020, 
    0x0639, 0x0644, 0x064a, 0x0647, 0x0020, 0x0648, 0x0633, 0x0644, 0x0645, 
    0x0020, 0x0627, 0x062d, 0x062a, 0x062c, 0x0645, 0x0020, 0x0648, 0x0623, 
    0x0639, 0x0637, 0x0627, 0x0647, 0x0020, 0x0623, 0x062c, 0x0631, 0x0647, 
))
_IBNMAJAH_2162_ADDENDA = "".join(chr(c) for c in (
    0x062a, 0x0641, 0x0631, 0x062f, 0x0020, 0x0628, 0x0647, 0x0020, 0x0628, 
    0x0646, 0x0020, 0x0623, 0x0628, 0x064a, 0x0020, 0x0639, 0x0645, 0x0631, 
    0x0020, 0x0648, 0x062d, 0x062f, 0x0647, 0x0020, 0x0642, 0x0627, 0x0644, 
    0x0647, 0x0020, 0x0628, 0x0646, 0x0020, 0x0645, 0x0627, 0x062c, 0x0629, 
))


def test_the_ibnmajah_near_miss_cut_overrides_verify():
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)

    rec = db.get_record(conn, "hadith:ibnmajah:1385")
    assert rec.text_ar == _IBNMAJAH_1385_MATN
    assert rec.addenda_ar == _IBNMAJAH_1385_ADDENDA
    m = verify_spans(conn, f"«{rec.text_ar}»")
    assert len(m) == 1
    assert m[0].verdict is Verdict.EXACT
    assert m[0].record.id == "hadith:ibnmajah:1385"

    rec2 = db.get_record(conn, "hadith:ibnmajah:2162")
    assert rec2.text_ar == _IBNMAJAH_2162_MATN
    assert rec2.addenda_ar == _IBNMAJAH_2162_ADDENDA
    m2 = verify_spans(conn, f"«{rec2.text_ar}»")
    assert len(m2) == 1
    assert m2[0].verdict is Verdict.EXACT
    assert m2[0].record.id == "hadith:ibnmajah:2162"



def test_ibnmajah_bare_pointer_is_unscorable():
    """hadith:ibnmajah:413's entire matn is the single word "نحوه" ("similarly
    to it"), referring back to 412's fuller wording two units earlier -- the
    same `_POINTER` phenomenon already on Bukhari/Tirmidhi/Nasai's own lists,
    and (measured) the identical sha256 as their own "نحوه" occurrences, since
    the digest is of the matn string alone. Read in context along with every
    other matn of 3 tokens or fewer (56 measured); the other 55 are genuine,
    complete, terse Prophetic sayings.
    """
    conn = db.connect(DB_PATH)
    rec = db.get_record(conn, "hadith:ibnmajah:413")
    assert rec.text_ar_sha256 == "da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe"
    assert rec.unscorable_reason is not None


# --- Task 16 A1: Bukhari and Muslim compiler-commentary sweep (R-A3-18) ------
#
# The two collections never swept in Tasks 12-15. Both markers are DERIVED
# from the shared `_compiler_commentary_markers` generator (Bukhari's kunya
# "أبو عبد الله", Muslim's "أبو الحسين"); Bukhari also carries al-Firabri's
# transmitter formula and Muslim the "قال مسلم" name formula. Each marker's
# full audit is in openiti.py's own comment block above its definition.


def _real_bukhari_units():
    from pathlib import Path

    from sanad_ingest.fetch import fetch_source
    from sanad_ingest.lockfile import load_lockfile
    from sanad_ingest.openiti import parse_openiti

    sources = {s.id: s for s in load_lockfile(Path("ingest/corpus.lock.toml"))}
    locked = sources["openiti-bukhari-jk000110"]
    raw = fetch_source(locked, Path(".corpus-cache"))
    return parse_openiti(raw, collection="bukhari").units


def _real_muslim_units():
    from pathlib import Path

    from sanad_ingest.fetch import fetch_source
    from sanad_ingest.lockfile import load_lockfile
    from sanad_ingest.openiti import parse_openiti

    sources = {s.id: s for s in load_lockfile(Path("ingest/corpus.lock.toml"))}
    locked = sources["openiti-muslim-jk000109"]
    raw = fetch_source(locked, Path(".corpus-cache"))
    return parse_openiti(raw, collection="muslim").units


def test_no_unaudited_near_miss_for_the_bukhari_compiler_marker():
    """R-A3-22/23's detector for al-Bukhari's own kunya + al-Firabri's
    transmitter formula: sweep "qala/su'ila/sami'tu <=4-token gap> Abu(a)
    Abdallah" -- varying BOTH token gap and grammatical case -- against the
    shipped marker set (tight/near/heard + `_BUKHARI_FORMULA`).

    The single surviving flag is hadith:bukhari:2821's VOCATIVE "يا أبا عبد
    الله" ("O Abu Abdallah") -- a Companion addressed mid-narration, genuine
    speech, correctly NOT cut (the "heard" marker requires a preceding
    "سمعت", not the vocative particle "يا"). Read in context; a permanent,
    audited exception, not a gap. hadith:bukhari:6132's accusative "حدثنا أبا
    عبد الله" is no longer a near-miss because al-Firabri's formula now matches
    that record's apparatus, so the configured set covers it.
    """
    import re

    from sanad_ingest.openiti import (
        _ARABIC, _BUKHARI_COMMENTARY, _BUKHARI_COMMENTARY_NEAR,
        _BUKHARI_FORMULA, _BUKHARI_HEARD, find_near_misses)

    configured = re.compile(
        f"{_BUKHARI_COMMENTARY.pattern}|{_BUKHARI_COMMENTARY_NEAR.pattern}"
        f"|{_BUKHARI_HEARD.pattern}|{_BUKHARI_FORMULA.pattern}")
    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل|سمعت)(?:\s+\S+){{0,4}}"
        rf"\s+(?:أبو|أبا)\s+عبد\s+الله(?![{_ARABIC}])")
    assert find_near_misses(_real_bukhari_units(), configured, sweep) == [
        "hadith:bukhari:2821"]


def test_no_unaudited_near_miss_for_the_muslim_compiler_marker():
    """The same detector for Muslim's kunya ("Abu(a) al-Husayn") + the "قال
    مسلم" name formula. Clean: every record any widening of this sweep finds
    is already matched by the configured pattern, so `find_near_misses` has
    nothing left to surface even at a four-token, both-case sweep.
    """
    import re

    from sanad_ingest.openiti import (
        _ARABIC, _MUSLIM_COMMENTARY, _MUSLIM_COMMENTARY_NEAR, _MUSLIM_FORMULA,
        _MUSLIM_HEARD, find_near_misses)

    configured = re.compile(
        f"{_MUSLIM_COMMENTARY.pattern}|{_MUSLIM_COMMENTARY_NEAR.pattern}"
        f"|{_MUSLIM_HEARD.pattern}|{_MUSLIM_FORMULA.pattern}")
    sweep = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل|سمعت)(?:\s+\S+){{0,4}}"
        rf"\s+(?:أبو|أبا)\s+الحسين(?![{_ARABIC}])")
    assert find_near_misses(_real_muslim_units(), configured, sweep) == []
