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
from pathlib import Path

from sanad.corpus import db

DB_PATH = Path("data/sanad-quran.db")

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
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    matches = verify_spans(conn, f"«{_AL_HARB_KHUDA}»")
    assert len(matches) == 1
    assert matches[0].verdict is Verdict.EXACT
    assert matches[0].record.id == "hadith:bukhari:2866"


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
    """The corpus-wide form of the test above: all 391 of them.

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
    """
    from sanad.verify.engine import Verdict, verify_spans
    conn = db.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, text_ar, addenda_ar FROM records"
        " WHERE addenda_ar IS NOT NULL AND unscorable_reason IS NULL").fetchall()
    assert len(rows) == 391
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
    """13,740 = 13,348 scorable records + 392 full-text representations.

    Asserted as three numbers that have to add up, not as one total: a record
    dropping out of the index while a variant row appears would keep the
    total right.
    """
    conn = db.connect(DB_PATH)
    scorable = conn.execute(
        "SELECT count(*) FROM records WHERE unscorable_reason IS NULL").fetchone()[0]
    variants = conn.execute("SELECT count(*) FROM record_variants").fetchone()[0]
    indexed = conn.execute("SELECT count(*) FROM records_fts").fetchone()[0]
    assert (scorable, variants, indexed) == (13348, 392, 13740)


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
    scorable representations was wholly Qur'anic, and it is the record now on
    the do-not-cut audit. The expected answer is zero.
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
    assert len(reps) == 7504, "the sweep stopped covering what it was written for"
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
