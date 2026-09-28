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
    """"al-harb khud'a" is printed, byte-identically, four times across three
    collections (Bukhari 2866; Muslim 1739, 1740; Abu Dawud 2636). Task 12
    added the fourth copy, and with it the FIRST case anywhere in this corpus
    of the tie-break's "lowest id wins" rule choosing a non-Bukhari winner:
    the full id "hadith:abudawud:2636" sorts before "hadith:bukhari:2866"
    lexicographically ("a" < "b"), so Abu Dawud is now the disclosed match
    and the other three are surfaced in `also_at`. Verified, not assumed --
    read directly from `verify_spans`'s own tie-break output.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_AL_HARB_KHUDA}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    assert matches[0].record.id == "hadith:abudawud:2636"
    assert matches[0].also_at == [
        "hadith:bukhari:2866", "hadith:muslim:1739", "hadith:muslim:1740",
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
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, text_ar, addenda_ar FROM records"
        " WHERE addenda_ar IS NOT NULL AND unscorable_reason IS NULL").fetchall()
    assert len(rows) == 1346
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
    """
    conn = db.connect(DB_PATH)
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE unscorable_reason IS NULL").fetchone()[0]
    variants = conn.execute("SELECT count(*) FROM record_variants").fetchone()[0]
    indexed = conn.execute("SELECT count(*) FROM records_fts").fetchone()[0]
    assert (scorable, variants, indexed) == (25222, 1387, 26609)


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
    assert len(reps) == 20373, "the sweep stopped covering what it was written for"
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
    """
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT r.id, count(v.record_id) AS n FROM records r"
        " LEFT JOIN record_variants v ON v.record_id = r.id"
        " WHERE r.unscorable_reason IS NOT NULL GROUP BY r.id").fetchall()
    assert len(rows) == 877
    assert {r["id"]: r["n"] for r in rows if r["n"]} == {
        "hadith:bukhari:237": 1,
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
    assert len(reps) == 20373, len(reps)

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
    assert (total, scorable, unscorable, cut) == (7460, 6739, 721, 122)


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
    assert (total, scorable, unscorable, cut) == (5274, 5135, 139, 873)


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
# _AL_HARB_KHUDA above: Sahih Muslim prints this saying too (1739, 1740), and
# Task 12 found a fourth copy at Abu Dawud 2636.
def test_a_genuine_short_hadith_shared_across_collections_still_verifies():
    """Bukhari 2866, Muslim 1739/1740, and (Task 12) Abu Dawud 2636 all print
    the same three words.

    The tie-break rule ("lowest id wins, the rest are disclosed") was proven
    within one collection (383 and 774, both Bukhari); Task 11 exercised it
    firing ACROSS collections for the first time (Bukhari won the tie then).
    Task 12 changed WHICH collection wins, without changing the rule: Abu
    Dawud's full id sorts first lexicographically ("hadith:abudawud:..." <
    "hadith:bukhari:..."), so it is the winner now and the other three move
    into `also_at`. See `test_a_famous_short_hadith_still_verifies_exactly`
    above for the same fact asserted the other direction.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_AL_HARB_KHUDA}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    assert matches[0].record.id == "hadith:abudawud:2636"
    assert matches[0].also_at == [
        "hadith:bukhari:2866", "hadith:muslim:1739", "hadith:muslim:1740",
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
