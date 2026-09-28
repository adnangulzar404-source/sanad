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
    """The corpus-wide form of the test above: all 579 of them.

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

    Task 12 (Sunan Abi Dawud): 391 + 120 + 68 = 579. Abu Dawud contributes 69
    cut records total (`addenda_ar IS NOT NULL`), one of which --
    hadith:abudawud:2225, the `_EDITORIAL_DISCUSSION` record -- is also on
    `UNSCORABLE["abudawud"]` and so is excluded from this scorable-only count,
    leaving 68.
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, text_ar, addenda_ar FROM records"
        " WHERE addenda_ar IS NOT NULL AND unscorable_reason IS NULL").fetchall()
    assert len(rows) == 579
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
    """25,841 = 25,258 scorable records + 583 full-text representations.

    Asserted as three numbers that have to add up, not as one total: a record
    dropping out of the index while a variant row appears would keep the
    total right.

    Task 11 (Sahih Muslim): these numbers moved from (13348, 392, 13740) when
    Muslim joined Bukhari and the Qur'an in the same committed database.
    Muslim contributes 7,460 hadith records, of which 6,739 are scorable and
    122 carry a second ("full", cut) representation -- see
    test_muslim_record_count_and_scorability below for the per-collection
    breakdown these totals are built from.

    Task 12 (Sunan Abi Dawud) moved these to (25258, 583, 25841). Abu Dawud
    contributes 5,274 hadith records, of which 5,171 are scorable and 69
    carry a second ("full", cut) representation -- see
    test_abudawud_record_count_and_scorability below for the breakdown.
    """
    conn = db.connect(DB_PATH)
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE unscorable_reason IS NULL").fetchone()[0]
    variants = conn.execute("SELECT count(*) FROM record_variants").fetchone()[0]
    indexed = conn.execute("SELECT count(*) FROM records_fts").fetchone()[0]
    assert (scorable, variants, indexed) == (25258, 583, 25841)


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

    Task 12 (Sunan Abi Dawud): the sweep now covers 19,605 representations
    (14,365 plus Abu Dawud's 5,240) and is still zero, after
    `UNSCORABLE["abudawud"]` excludes the 23 records
    `_reject_wholly_quranic_representations` flagged on the first measured
    build (22 false-positive short editorial pointers plus the one genuine
    wholly-Qur'anic report, hadith:abudawud:3979 -- see audit_lists.py's
    "abudawud" section and the task-12 report).
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
    assert len(reps) == 19605, "the sweep stopped covering what it was written for"
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

    Task 12 (Sunan Abi Dawud): 103 more excluded records joined this count.
    One of Abu Dawud's is the same shape -- "hadith:abudawud:2225"
    (`_EDITORIAL_DISCUSSION`: Abu Dawud's own numbered remark about how other
    narrators transmitted the isnad/wording differently, carrying its own
    addendum). Everything else Abu Dawud contributes is excluded whole.
    """
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT r.id, count(v.record_id) AS n FROM records r"
        " LEFT JOIN record_variants v ON v.record_id = r.id"
        " WHERE r.unscorable_reason IS NOT NULL GROUP BY r.id").fetchall()
    assert len(rows) == 841
    assert {r["id"]: r["n"] for r in rows if r["n"]} == {
        "hadith:bukhari:237": 1,
        "hadith:muslim:1915-3": 1,
        "hadith:muslim:546-3": 1,
        "hadith:abudawud:2225": 1,
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

    Task 12 (Sunan Abi Dawud) moved the representation count (14,365 to
    19,605) without moving either list: re-read in full against the built
    database, no Abu Dawud representation sits inside an ayah at either tier.
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
    assert len(reps) == 19605, len(reps)

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
    `openiti.py`'s `flush()`. 103 unscorable and 69 cut are the audit's own
    output: see audit_lists.py's "abudawud" section for what each of the 103
    is and why.
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
    assert (total, scorable, unscorable, cut) == (5274, 5171, 103, 69)


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
