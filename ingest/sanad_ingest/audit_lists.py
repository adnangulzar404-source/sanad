"""Per-collection audit lists and tuning constants for the OpenITI parser.

Moved out of `openiti.py` so the parser is collection-agnostic: each entry
below is a judgement made by hand about one specific edition's printed text,
pinned to it by digest, and keyed under the collection it was read for.
Porting to a new collection means re-measuring the tuning constants and
re-reading the candidates, not reusing these values -- see the comments
inline.
"""
from __future__ import annotations

# --- tuning constants, measured per edition ---------------------------------

# Attribution must sit within this many characters of the verb. MEASURED, not
# chosen by taste: 25 is the largest distance a one-to-three-token attribution
# ever spans in this file (the observed range is 8..24).
ATTRIBUTION_WINDOW = 25

# No single cut may move more than this much text. The edition sometimes
# breaks off mid-narration for a sub-narrator's aside and then RESUMES the
# same story -- 2581 (Hudaybiyya), 2782 (Heraclius), 2880 (Khubayb) -- so the
# text behind the marker is matn, not an addendum. Those three are the only
# cuts on this file that would exceed 1,000 characters, and all three were
# read by hand. This is a cap on blast radius, not a claim about Arabic: a
# rule this simple does not get to move a kilobyte on its own say-so.
#
# THE NUMBER IS EDITION-SPECIFIC AND MUST BE RE-MEASURED PER EDITION. On this
# file the distribution has a clean gap: the largest genuine addendum the rule
# cuts is 869 characters, the next three candidates are 1,001 / 3,406 / 4,279
# and all three are interrupted narrations rather than addenda. 1,000 sits in
# that gap. Nothing guarantees Muslim or the Sunan have a gap in the same
# place -- or a gap at all -- so porting this parser means re-running that
# measurement and reading the candidates above the cap by hand, not reusing
# this constant.
MAX_ADDENDUM = 1000

# --- do-not-cut audit --------------------------------------------------------

# THERE IS DELIBERATELY NO MINIMUM PRIMARY LENGTH HERE.
#
# Round 5 tried one -- 32 characters, measured from the only gap in the lower
# quartile of the cut-primary distribution (18 19 20 20 21 21 22 25 25 | 32 32
# 33 34 ...) -- and it was removed the same round, because the measurement
# that justified the gap also showed the rule cannot work. Length does not
# separate a stub from a short hadith in EITHER direction: "la tuki fa-yuka
# 'alayki" (1366) is eighteen characters and a complete saying of the Prophet,
# while 632's "the Prophet passed by a man" is thirty-two and names nothing.
# A floor at 32 refused nine correct cuts -- every one of them read in the raw
# source, every one a genuine matn followed by a fresh full chain -- and still
# did not reach the two records it was introduced for.
#
# The same question was settled for the pointer records in R13 and has the
# same answer here: what is quotable is a judgement about meaning, so it is
# made by hand, one record at a time, and recorded in `_NEVER_CUT` below.
#
# Records where the cut is textually correct -- the edition really does print
# a short primary and then a second chain -- but the primary it leaves is a
# content-free narrative opener: it names no act, no ruling and no speech, so
# the entire narration lives in the addendum. Scoring such a primary is the
# `_UNSCORABLE` defect in a new costume: "the Prophet passed by a man" is an
# everyday sentence of hadith literature, present verbatim in many narrations
# across many collections, and answering it with EXACT 1.0 / Sahih al-Bukhari
# 632 fabricates a citation out of a commonplace.
#
# The remedy is to leave the record UNCUT, not to mark it unscorable: the
# hadith itself is perfectly quotable, and an `unscorable_reason` would take
# its full printed text out of the corpus too. Uncut, the record has exactly
# one representation -- the whole printed text -- which still verifies, while
# the opener on its own no longer does.
#
# An AUDIT, like `_UNSCORABLE`: a closed list of records read in the source,
# keyed to the sha256 of the uncut matn so a changed text stops the build
# rather than inheriting a judgement made about a different string. The scan
# that produced it is in the round-5 report -- every cut primary ranked by how
# many tokens it holds outside the honorific frame ("the Prophet", "may God
# bless him and grant him peace", "from", "that"). These two rank first and
# second on all 395 with one and two content words; the third (466, "the
# Prophet interlaced his fingers") names a specific act and was ruled genuine.
_STUB_OPENER = ("narrative opener: the primary matn names no act, ruling or "
                "speech of its own, the narration itself beginning in the "
                "appended second chain")

# The second kind of bad cut, found by the whole-branch review rather than by
# the round-5 scan, and invisible to it: unit 4575 sits under the bab
# "fa-kana qaba qawsayni aw adna", and the edition prints the AYAH the chapter
# comments on and then the narration about it. The cut fires at the second
# chain, which is a defensible boundary, and leaves a primary matn that is
# nothing but Qur'an 53:9-10 -- so Sanad stamped "Sahih al-Bukhari 4575" on
# two verses of scripture, and told a reader who quoted them and cited
# "(53:9)" that their reference was wrong.
#
# Round 5's scan ranked cut primaries by how many tokens they hold outside the
# honorific frame, looking for stubs. A primary made of scripture is dense
# with content words and ranks at the very bottom of that list: the metric was
# built to find emptiness and cannot see this. The corpus-wide invariant in
# `materialize._reject_wholly_quranic_representations` is what closes the class;
# this entry corrects the one record.
_QURANIC_PRIMARY = ("Qur'anic primary: the cut leaves a matn that is nothing "
                    "but the ayah the chapter comments on, the narration that "
                    "makes the unit a hadith beginning in the appended chain")

NEVER_CUT: dict[str, dict[str, tuple[str, str]]] = {
    "bukhari": {
        # "The Prophet passed by a man." The man praying two rak'as after the
        # iqama, and the Prophet's "the dawn prayer in four?", are the addendum.
        "hadith:bukhari:632":
            ("7ec7ade079723e6da94065206461a9c5f530cb9dc4eddcdd37f22f1af4c32908",
             _STUB_OPENER),
        # "The Prophet had a she-camel." Al-'Adba' being outrun, and "God raises
        # nothing of this world without lowering it", are the addendum.
        "hadith:bukhari:6136":
            ("50bdf6cc60a370e998897b39f17dc707af23d4022a52e45aa33a82998d54821f",
             _STUB_OPENER),
        # "So he was at a distance of two bow-lengths or nearer, and revealed to
        # His servant what He revealed" -- Qur'an 53:9-10, verbatim. Ibn Mas'ud's
        # report that the Prophet saw Gabriel with six hundred wings is the
        # addendum, and is the whole of what makes this unit a narration.
        "hadith:bukhari:4575":
            ("86e0300ecb069cd2cd368656cfe256e667974b1ca965e3a7cd61a4b3ea0eab03",
             _QURANIC_PRIMARY),
    },
}

# --- matns that are editorial apparatus, not quotable text -----------------
#
# Where a narration repeats one already given in full, this edition prints a
# pointer instead of the text: "bi-hadha" ("with this"), "mithlahu" ("the like
# of it"), "nahwahu" ("something like it"). The source marks the isnad/matn
# boundary exactly as it does everywhere else, so the pointer lands in the
# scored text and Sanad answered the everyday Arabic phrase "bi-hadha" with
# EXACT 1.0, Sahih al-Bukhari 1379 -- inventing a hadith citation out of a
# commonplace, which is the precise failure this product exists to prevent.
#
# The list below is an AUDIT, not a heuristic. Length is emphatically not the
# rule: "al-harb khud'a" (war is deceit, 2866) is 10 characters and genuine,
# and Qur'anic records go down to 2. Three scans over all 7,129 units produced
# the candidates -- every matn of 9 characters or less (14 records, all
# apparatus); every matn whose every token is pointer or deferral vocabulary
# at any length (13 records, 11 of them already in the first set); and every
# matn holding a standalone "ha" chain-transfer mark (1 record, 237). Every
# matn up to 24 characters (92 records) and every matn containing a deferral
# phrase at any length (32 records) was then read in the source and
# classified. 17 are listed here; everything else was ruled genuine, record by
# record, in .superpowers/sdd/2026-09-22-hadith-corpus/task-4-fix-3-report.md.
#
# The value is a (sha256-of-matn, reason) pair. Pinning the text is what makes
# the entry an audit rather than a standing verdict on a number: the
# classification was made by reading one specific string, and if a future
# edition prints something else under that number the build stops and the
# record gets read again.

_POINTER = ("editorial back-reference: the matn is a pointer to a narration "
            "printed in full elsewhere, not a text")
_DEFERRAL = ("editorial abridgement: the matn breaks off and defers to the "
             "full narration printed elsewhere")
_INCIPIT = ("editorial abridgement: the edition prints the opening word in "
            "place of the narration")
_TAHWIL = ("chain-transfer fragment: the matn is a subordinate clause ending "
           "at the tahwil mark, the narration itself following in the addendum")

# Muslim-specific reasons (Task 11). Sahih Muslim's editorial convention groups
# parallel chains under a repeated back-reference far more densely than
# Bukhari's: reading every matn of 30 characters or fewer (403 distinct
# strings across 902 records) found 240 distinct pointer/deferral/attribution
# strings covering 726 records -- roughly 40x Bukhari's 17-entry list by
# count, though the SAME three reasons (_POINTER, _DEFERRAL, and the two new
# ones below) cover it; nothing Muslim-specific needed inventing except these
# two. Every one of the 240 strings was read for meaning, not matched by a
# length or frequency rule: genuine short hadith at this length (e.g. "al-harb
# khud'a", "al-'ayn haqq", the Prophet's two-word "da'hu" reply at 274) sit in
# the SAME length band as the apparatus and are deliberately left off this
# list. The 31-60 character band was scanned for the same vocabulary as a
# spot check (459 further distinct candidate strings, overwhelmingly the same
# small set of templates with a different narrator's name substituted) but was
# NOT individually read and is NOT included here -- see the task-11 report for
# the residual-risk note this leaves for a follow-up pass.
_ATTRIBUTION_NOTE = ("attribution note: the matn answers a question about "
                      "whether the narration is raised to the Prophet "
                      "(marfu') rather than reporting his words")
_TRUNCATED_STUB = ("truncated narrative frame: the reported speech is the "
                    "punchline of an earlier, separately-numbered unit and "
                    "the source ends the record here, with nothing following "
                    "to reattach")

UNSCORABLE: dict[str, dict[str, tuple[str, str]]] = {
    "bukhari": {
        # Pointer only -- "bi-dhalika", "bi-hadha", "mithlahu", "nahwahu",
        # "bi-nahwihi". Nothing of the narration is present.
        "hadith:bukhari:127":
            ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        "hadith:bukhari:394":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        "hadith:bukhari:549":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:bukhari:557":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        "hadith:bukhari:1379":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        "hadith:bukhari:2483":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:bukhari:3457":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:bukhari:3750":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:bukhari:4540":
            ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        "hadith:bukhari:5454":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:bukhari:5837":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        # Breaks off mid-sentence into a deferral. 335 is "I witnessed Umar, and
        # Ammar said to him --" with no reported speech at all; 3801 and 3957 are
        # deferral phrases end to end ("and he mentioned the hadith of the ifk",
        # "the story was mentioned").
        "hadith:bukhari:335":
            ("6ee90378f5b44749f8eceb8ab8df58e6d111a3aff1b347170e2618cc6688002b", _DEFERRAL),
        "hadith:bukhari:3801":
            ("4b9d1fad31b2db451efc1b8da5126228579e4b4c502d598146df5dd664d6a616", _DEFERRAL),
        "hadith:bukhari:3957":
            ("ce978d7770d5c1c95852945608a5bfe28bfa168ad4fd374541dba93f42cfc4cf", _DEFERRAL),
        # One word standing for the whole narration, the part marker "\ 1 \"
        # following it immediately in the source.
        "hadith:bukhari:1915":
            ("eef9aff2b8eb9c9b7bf8b1dad3573aafc7ebd62765e1eaa436d27b43d5ec3020", _INCIPIT),
        "hadith:bukhari:3777":
            ("e8f7569bb6d6c846a67e3d7a7d8235e04ae9b9340ffd4694f0de8028de0c1295", _INCIPIT),
        # "while the Messenger of God was prostrating -- ha" : a "bayna" clause
        # with no main clause, ending on the chain-transfer mark. The narration it
        # introduces is the second chain, which is in this record's addendum.
        "hadith:bukhari:237":
            ("990234ea283424988b4c8932d69ec68bd0d99f4d0d635dab14cb919338bce0f3", _TAHWIL),
    },
    "muslim": {
        # See the module-level comment above _ATTRIBUTION_NOTE/_TRUNCATED_STUB
        # for the scan methodology and scope. sha256 values were computed
        # directly from parse_openiti(raw, collection="muslim")'s matn_ar for
        # each id (never hand-typed), the same value build.py stores as
        # text_ar before materialize hashes it -- these records have no
        # addenda, so text_ar == matn_ar.
        #
        # "rafa'ahu" (626-2): Sufyan is asked whether the narration is raised
        # to the Prophet; the matn is his one-word answer "he raised it",
        # not a report of anything the Prophet said.
        # "marra bi-rajulin min al-ansari ya'izu akhahu" (36-2): a second
        # chain for unit 36 reports only that the Prophet "passed by a man of
        # the Ansar admonishing his brother" -- the actual saying ("shyness is
        # part of faith") is unit 36's own primary matn, not repeated here,
        # and the source starts a new numbered unit immediately after. There
        # is no addendum to reattach, so this is _TRUNCATED_STUB, not a
        # NEVER_CUT candidate.
        # "ma sha'a Allah" (719-2): "... with this chain, like it, and Yazid
        # said [just the words] 'ma sha'a Allah'" -- a narrator's wording note
        # against the fuller "wa-yazidu ma sha'a Allah" ("and adds what God
        # wills") given at 719. Also, coincidentally, verbatim Qur'anic
        # phrasing (18:39): this is the record that tripped
        # materialize._reject_wholly_quranic_representations before this
        # entry existed. Listed as _POINTER on its own merits -- the wording
        # note, not the Qur'an collision, is why it is not independently
        # quotable -- with the collision noted here since it is what first
        # surfaced the record.
        # 'بهذا الإسناد مثله' (108 records)
        'hadith:muslim:90-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:120-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:276-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:307-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:381-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:442-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:445-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:447-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:463-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:596-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:656-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:672-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:673-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:707-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:710-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:715-23': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:719-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:723-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:773-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:821-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:879-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:979-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1066-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1085-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1106-10': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1190-9': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1223-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1317-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1340-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1352-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1353-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1374-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1408-10': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1446-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1460-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1539-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1542-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1543-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1548-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1554-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1556-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1568-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1575-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1582-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1588-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1599-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1622-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1635-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1640-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1643-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1672-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1676-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1684-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1690-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1691-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1696-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1706-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1707-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1713-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1767-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1839-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1842-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1857-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1872-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1890-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1896-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1933-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1934-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1957-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1960-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1969-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1979-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1979-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1987-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1988-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2003-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2064-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2068-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2069-10': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2076-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2093-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2100-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2119-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2121-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2169-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2177-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2191-7': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2195-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2199-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2210-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2321-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2344-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2395-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2398-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2444-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2444-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2447-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2486-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2549-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2597-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2602-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2623-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2741-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2798-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2877-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2947-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2959-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:3022-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        # 'بمثله' (100 records)
        'hadith:muslim:52-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:55-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:55-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:64-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:66': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:93-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:169-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:224-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:237-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:240-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:274-10': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:278-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:387-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:410-5': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:414-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:422-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:506-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:515-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:522-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:523-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:568-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:578-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:597-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:672-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:713-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:721-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:732-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:799-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:799-6': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:844-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:850-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:851-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:852-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:852-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:982-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:991-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1047-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1092-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1098-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1163-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1164-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1164-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1336-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1345-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1378-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1386-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1395-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1395-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1408-6': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1438-12': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1452-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1469-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1477-6': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1493-5': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1511-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1522-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1534-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1536-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1543-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1562-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1564-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1568-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1575-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1576-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1625-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1673-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1710-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1828-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1860-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1874-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1918-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1989-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1995-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2032-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2060-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2110-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2124-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2226-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2242-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2302-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2309-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2318-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2369-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2411-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2425-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2433-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2609-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2616-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2624-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2640-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2672-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2672-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2684-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2747-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2823': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2914-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2916-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2991-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2998-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:3002-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        # 'بهذا الإسناد' (87 records)
        'hadith:muslim:176-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:190-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:200-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:388-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:440-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:453-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:546-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:589-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:603-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:627-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:660-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:674-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:715-25': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:737-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:807-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:819-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:848-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:878-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:916-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:921-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:962-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:962-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1008-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1096-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1097-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1153-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1162-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1198-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1283-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1333-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1394-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1395-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1412-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1412-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1433-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1494-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1512-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1586-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1666-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1691-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1714-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1749-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1757-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1802-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1858-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1876-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1892-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1893-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1929-7': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1941-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1942-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1956-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1975-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2055-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2075-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2089-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2107-11': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2113-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2121-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2168-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2170-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2184-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2250-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2263-8': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2265-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2341-6': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2353-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2412-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2487-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2506-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2509-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2522-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2568-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2572-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2610-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2681-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2684-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2728-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2734-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2737-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2753-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2758-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2812-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2945-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2987-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:3019-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:3030-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        # 'بهذا الإسناد نحوه' (72 records)
        'hadith:muslim:389-7': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:412-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:430-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:432-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:436-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:537-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:538-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:539-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:663-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:688-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:694-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:695-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:884-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:884-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:940-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:971-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:989-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1024-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1053-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1073-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1082-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1290-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1341-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1376-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1456-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1456-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1474-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1476-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1495-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1504-9': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1525-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1542-6': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1543-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1547-14': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1563-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1587-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1591-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1609-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1617-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1628-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1674-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1698': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1760-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1812-8': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1840-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1844-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1878-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1938-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1954-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1954-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1977-6': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2064-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2170-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2221-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2284-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2308-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2336-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2420-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2438-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2449-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2567-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2611-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2669-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2704-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2759-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2776-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2876-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2885-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2891-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2907-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2913-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2948-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        # 'مثله' (23 records)
        'hadith:muslim:358-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:380-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:578-5': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:588-5': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:588-6': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:743-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:784-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:808-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:808-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:933-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:933-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1207-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1211-17': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1350-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1511-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1511-4': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1579-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1961-6': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2172-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2485-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2683-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2737-4': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2817': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        # 'بنحوه' (13 records)
        'hadith:muslim:207-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:559-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:651-4': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:677-9': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:1047-3': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2078-5': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2191-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2323-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2586-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2601-4': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2639-7': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2647-4': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2775-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        # 'في هذا الإسناد بمثله' (12 records)
        'hadith:muslim:631-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1001-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1129-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1132-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1157-4': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1161-5': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1201-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1916-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2234-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2389-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2920-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2938-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        # 'بنحو حديثهم' (8 records)
        'hadith:muslim:8-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:288-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:1669-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:1831-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2125-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2218-11': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2218-12': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2492-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        # 'بهذا الحديث' (8 records)
        'hadith:muslim:132-2': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:487-2': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:1017-8': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:1148-3': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:1735-2': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:2036-3': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:2639-8': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:2688-4': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        # 'في هذا الإسناد' (8 records)
        'hadith:muslim:1002-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:1441-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:1997-15': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2053-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2404-3': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2514-3': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2702-3': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2719-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        # 'نحو حديثهم' (7 records)
        'hadith:muslim:1029-3': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:1540-4': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:1550-3': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:1835-5': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:2243-4': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:2471-4': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:2652-6': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        # 'نحوه' (7 records)
        'hadith:muslim:874-2': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:895-3': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:1851-2': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2078-6': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2511-2': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2586-5': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2704-4': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        # 'بمثل حديثهم' (5 records)
        'hadith:muslim:1833-3': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:1835-6': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:2062-2': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:2085-4': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:2951-4': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        # 'بمثل حديث مالك' (4 records)
        'hadith:muslim:1349-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        'hadith:muslim:1621-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        'hadith:muslim:1664-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        'hadith:muslim:2559-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        # 'مثل ذلك' (4 records)
        'hadith:muslim:1929-9': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        'hadith:muslim:2264-2': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        'hadith:muslim:2480-3': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        'hadith:muslim:2801': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        # 'بإسناد يونس نحو حديثه' (3 records)
        'hadith:muslim:2218-7': ("b6a7660b96b1fea3e266415b4f7c6bd99978de4e581e6c09747065f64b3d0d94", _POINTER),
        'hadith:muslim:2391-2': ("b6a7660b96b1fea3e266415b4f7c6bd99978de4e581e6c09747065f64b3d0d94", _POINTER),
        'hadith:muslim:2392-2': ("b6a7660b96b1fea3e266415b4f7c6bd99978de4e581e6c09747065f64b3d0d94", _POINTER),
        # 'بذلك' (3 records)
        'hadith:muslim:356-2': ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        'hadith:muslim:2120-4': ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        'hadith:muslim:2242-3': ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        # 'بمثل هذا الحديث' (3 records)
        'hadith:muslim:13-2': ("fae02d64b5cfdd6882f14790ed860fb9eab0fc48fab0e2ece2d2db8bf29ba957", _POINTER),
        'hadith:muslim:1988-6': ("fae02d64b5cfdd6882f14790ed860fb9eab0fc48fab0e2ece2d2db8bf29ba957", _POINTER),
        'hadith:muslim:2372-3': ("fae02d64b5cfdd6882f14790ed860fb9eab0fc48fab0e2ece2d2db8bf29ba957", _POINTER),
        # 'بمثله بسم الله الرحمن الرحيم' (3 records)
        'hadith:muslim:900-2': ("7ef13e9272e4017b6ad7f5c37f8a48959a514678ee0290e347680879d5889e69", _POINTER),
        'hadith:muslim:1710-5': ("7ef13e9272e4017b6ad7f5c37f8a48959a514678ee0290e347680879d5889e69", _POINTER),
        'hadith:muslim:2064-5': ("7ef13e9272e4017b6ad7f5c37f8a48959a514678ee0290e347680879d5889e69", _POINTER),
        # 'بمثله سواء' (3 records)
        'hadith:muslim:615-2': ("52c3ae71011b05e9c595509614df1362d7ae33ac695712c5f325aa598343367a", _POINTER),
        'hadith:muslim:1835-4': ("52c3ae71011b05e9c595509614df1362d7ae33ac695712c5f325aa598343367a", _POINTER),
        'hadith:muslim:1883-2': ("52c3ae71011b05e9c595509614df1362d7ae33ac695712c5f325aa598343367a", _POINTER),
        # 'بمثله في هذا الإسناد' (3 records)
        'hadith:muslim:1126-2': ("134a6997d373b52fb12f8d40572d420befa9d50614ec5158fed3f25f95ab3183", _POINTER),
        'hadith:muslim:1684-2': ("134a6997d373b52fb12f8d40572d420befa9d50614ec5158fed3f25f95ab3183", _POINTER),
        'hadith:muslim:1943-4': ("134a6997d373b52fb12f8d40572d420befa9d50614ec5158fed3f25f95ab3183", _POINTER),
        # 'بهذا' (3 records)
        'hadith:muslim:1731-4': ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        'hadith:muslim:1807-2': ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        'hadith:muslim:2951-3': ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        # 'بهذا الإسناد سواء' (3 records)
        'hadith:muslim:942-2': ("d93d334876ddddf4049faad3d50377a6190130cf210197862e4975426d1a425e", _POINTER),
        'hadith:muslim:1449-2': ("d93d334876ddddf4049faad3d50377a6190130cf210197862e4975426d1a425e", _POINTER),
        'hadith:muslim:2373-2': ("d93d334876ddddf4049faad3d50377a6190130cf210197862e4975426d1a425e", _POINTER),
        # 'بمثل حديث أبي عوانة' (2 records)
        'hadith:muslim:1048-2': ("cf614dc38194d0f7f532b36b6050a8e5d1ee3f41fe7f93e868703526d8062488", _POINTER),
        'hadith:muslim:1717-2': ("cf614dc38194d0f7f532b36b6050a8e5d1ee3f41fe7f93e868703526d8062488", _POINTER),
        # 'بمثل حديث الليث' (2 records)
        'hadith:muslim:95-3': ("bd3d511c717ed3d79b2d9f3a84e264b1fc33b07581b6e27992225ea8ed20ad1a", _POINTER),
        'hadith:muslim:1970-2': ("bd3d511c717ed3d79b2d9f3a84e264b1fc33b07581b6e27992225ea8ed20ad1a", _POINTER),
        # 'بمثل حديث بن جريج' (2 records)
        'hadith:muslim:1670-3': ("24b422c81e27c297dabb5561411a4b911fd5ee98cef7a88e1cfa09c7cec7aa70", _POINTER),
        'hadith:muslim:2059-2': ("24b422c81e27c297dabb5561411a4b911fd5ee98cef7a88e1cfa09c7cec7aa70", _POINTER),
        # 'بمثل حديث جرير' (2 records)
        'hadith:muslim:1652-4': ("7350102d9e6ecb3748d5e68b246b27d61f87d8f92e8f38266df738f8997e521a", _POINTER),
        'hadith:muslim:2069-6': ("7350102d9e6ecb3748d5e68b246b27d61f87d8f92e8f38266df738f8997e521a", _POINTER),
        # 'بمثل حديث عبيد الله' (2 records)
        'hadith:muslim:2003-8': ("4d15c35d235ac6b6ad9b171d74af5e9ab1d53e947cd6176620a640113f41641b", _POINTER),
        'hadith:muslim:2299-4': ("4d15c35d235ac6b6ad9b171d74af5e9ab1d53e947cd6176620a640113f41641b", _POINTER),
        # 'بمثل حديث معاذ' (2 records)
        'hadith:muslim:1226-4': ("eab6b9519c8be0bbd66b98299f687d1edc697f647ba78aa64870d6c5822c5151", _POINTER),
        'hadith:muslim:1944-2': ("eab6b9519c8be0bbd66b98299f687d1edc697f647ba78aa64870d6c5822c5151", _POINTER),
        # 'بمثل معناه' (2 records)
        'hadith:muslim:649-7': ("f7714310c99793eb578a41a4f2530c07a1b78584e5c34c73eb163176612b4f82", _POINTER),
        'hadith:muslim:2242-2': ("f7714310c99793eb578a41a4f2530c07a1b78584e5c34c73eb163176612b4f82", _POINTER),
        # 'بمعنى حديث شيبان' (2 records)
        'hadith:muslim:2802-2': ("786c489e40a54d570f545b3927db6f627a5a105d97c4cc60b352038dded82020", _POINTER),
        'hadith:muslim:2848-2': ("786c489e40a54d570f545b3927db6f627a5a105d97c4cc60b352038dded82020", _POINTER),
        # 'بنحو هذا' (2 records)
        'hadith:muslim:649-12': ("2575864e26a32ba81792fb024f5b84b18de2fbf84d95d70788775c1e8f35f76a", _POINTER),
        'hadith:muslim:2088-2': ("2575864e26a32ba81792fb024f5b84b18de2fbf84d95d70788775c1e8f35f76a", _POINTER),
        # 'بهذا الإسناد بمثله' (2 records)
        'hadith:muslim:1430-2': ("4fbc5934fec81451caf8980249343b03952d4fcf24a82e372972e1b10ec696ec", _POINTER),
        'hadith:muslim:1833-2': ("4fbc5934fec81451caf8980249343b03952d4fcf24a82e372972e1b10ec696ec", _POINTER),
        # 'بهذا الإسناد مثله سواء' (2 records)
        'hadith:muslim:1337-3': ("2297df7ae3c09b93e16a83fb920f561f608908f498034ff3b0880534fb65f742", _POINTER),
        'hadith:muslim:1468-2': ("2297df7ae3c09b93e16a83fb920f561f608908f498034ff3b0880534fb65f742", _POINTER),
        # 'بهذا الإسناد نحو حديث جرير' (2 records)
        'hadith:muslim:598-2': ("5ae4d5b7e2bc76092ed5f729f23de8d411e46e5653c6d2a2d4de4c9d1554d7c1", _POINTER),
        'hadith:muslim:1639-4': ("5ae4d5b7e2bc76092ed5f729f23de8d411e46e5653c6d2a2d4de4c9d1554d7c1", _POINTER),
        # 'بهذا الإسناد نحو حديثهم' (2 records)
        'hadith:muslim:1542-8': ("b265fb4c787886fc74ded06df550146bfc3f6192fa65b155b52908a238b9dc04", _POINTER),
        'hadith:muslim:1622-3': ("b265fb4c787886fc74ded06df550146bfc3f6192fa65b155b52908a238b9dc04", _POINTER),
        # 'بهذا المعنى' (2 records)
        'hadith:muslim:1829-5': ("249aa60f3ed7e1e671c834449b283328428d364b68e7b3a664d0ead31d270082", _POINTER),
        'hadith:muslim:2098-2': ("249aa60f3ed7e1e671c834449b283328428d364b68e7b3a664d0ead31d270082", _POINTER),
        # 'فذكر مثله' (2 records)
        'hadith:muslim:1038-2': ("3ba4c7bb513d553cc6c2786b91ea02d71d14d50c44872354f8d220ae4a2391b1", _DEFERRAL),
        'hadith:muslim:1612-2': ("3ba4c7bb513d553cc6c2786b91ea02d71d14d50c44872354f8d220ae4a2391b1", _DEFERRAL),
        # 'في هذا الإسناد مثله' (2 records)
        'hadith:muslim:567-2': ("d2fed8725e4642ec46fd6d06a07d3b4d765822afec8f02dce69a410a58599971", _POINTER),
        'hadith:muslim:1709-6': ("d2fed8725e4642ec46fd6d06a07d3b4d765822afec8f02dce69a410a58599971", _POINTER),
        # 'في هذا الإسناد نحوه' (2 records)
        'hadith:muslim:1221-2': ("4eee7b48727853faddb6bc4c784a84bffaf51c679233b4296b98005b0112bb5d", _POINTER),
        'hadith:muslim:2700-2': ("4eee7b48727853faddb6bc4c784a84bffaf51c679233b4296b98005b0112bb5d", _POINTER),
        # 'مثله سواء' (2 records)
        'hadith:muslim:26-2': ("1689c6318ec9c6db4fbe987b4477218c0855c4fbae2c69e357bf7a5909856513", _POINTER),
        'hadith:muslim:2311-2': ("1689c6318ec9c6db4fbe987b4477218c0855c4fbae2c69e357bf7a5909856513", _POINTER),
        # 'نحو حديثه' (2 records)
        'hadith:muslim:2380-4': ("8e0910fb17972104067535af03d80a243856b409f4bf667a53906cd3c60199f5", _POINTER),
        'hadith:muslim:2662-3': ("8e0910fb17972104067535af03d80a243856b409f4bf667a53906cd3c60199f5", _POINTER),
        # 'إذا دخل رمضان بمثله' (1 record)
        'hadith:muslim:1079-3': ("37360a7067bbf309b4461e32b133d41517afa0d68f7efd6a223096d82d7316b8", _POINTER),
        # 'اقرؤوا القرآن بمثل حديثهما' (1 record)
        'hadith:muslim:2667-3': ("019c1733410f7212bd0c5d5923f9beeea77a080d532b3dd36f95a9d77f5cdb1b", _POINTER),
        # 'الإسناد وفي حديثه' (1 record)
        'hadith:muslim:1915-3': ("d1b3525b48073595d854834512726a3f502ac233795eeae7d9cb5e2f61dc2246", _POINTER),
        # 'الجنة والنار فذكر نحو حديثهما' (1 record)
        'hadith:muslim:2750-3': ("96321180729669565b57749a077ac24fb5d22e66e4f0e61abc25e04997256cb8", _POINTER),
        # 'الحديث نحوه' (1 record)
        'hadith:muslim:2669-3': ("680a1c893dd7ee569cbece0d5ec0aa5ec31965256c784be922b7b2e0dd504af5", _POINTER),
        # 'بإسناد الليث ومعنى حديثه' (1 record)
        'hadith:muslim:1638-2': ("bf470add99bea4d3e36f0bef97fe213f414a6eff4f9023b1ba212f2def7c1fb2", _POINTER),
        # 'بإسناد بن جريج نحو حديثه' (1 record)
        'hadith:muslim:2218-5': ("a04fce3aa5def39fd08a5b798e5058f7e4564f5726b4616ef28608e39bdda17c", _POINTER),
        # 'بإسناد جرير مثل حديثه' (1 record)
        'hadith:muslim:2570-2': ("186634dce29b22f39167ce68b76efde4f73292a03747eb1cab422a2f5196a1a7", _POINTER),
        # 'بإسناد جرير نحو حديثه' (1 record)
        'hadith:muslim:2356-2': ("ecf135060c57e426e6cd8971a7125154bcc6c72de661f60a75991442932ccf88", _POINTER),
        # 'بإسناد حديث الليث مثل روايته' (1 record)
        'hadith:muslim:1490-2': ("bc7037fa6e4c40e16f4cefd86b12614a566223de6343ce2521399693ef3c8fe1", _POINTER),
        # 'بإسناد سفيان' (1 record)
        'hadith:muslim:2020-2': ("1c017e64889ce9d0a99ac405cce3ced6d03c48f45d2bc0629804b7d526c241ca", _POINTER),
        # 'بإسناد سفيان ومعنى حديثه' (1 record)
        'hadith:muslim:2918-2': ("ff6c8ba3472db436b2e72f7bbc10c415482faf2d9552295739cb401d8c176f75", _POINTER),
        # 'بإسناد معمر كمثل حديثه' (1 record)
        'hadith:muslim:2537-2': ("4fb69bea4e4c315792773b7127156a694e8ec0e4123f89e1263a783ed79dbb4a", _POINTER),
        # 'بإسناد يونس عن الزهري سواء' (1 record)
        'hadith:muslim:2769-2': ("6db5c046e31ee155cf52a5f2e8e86c009eced77aa5f9c17b5e29f2d6e2310dad", _POINTER),
        # 'بإسناد يونس كنحو حديثه' (1 record)
        'hadith:muslim:510-2': ("2fd6c2263882a08d9866f8d937da4828cec33a53be467e649f4a7c042621d259", _POINTER),
        # 'بإسناد يونس ومعنى حديثه' (1 record)
        'hadith:muslim:1027-2': ("e0f9b3c0e593138fce6ded64c2d99ef6a7fa21d98a5e457d67f0332be0d33034", _POINTER),
        # 'بالإسنادين جميعا مثل حديث عقيل' (1 record)
        'hadith:muslim:2349-2': ("fec7f308b4d910a9f35f8731ab9e629f2b6d0842322217e3f55919a2a11542b4", _POINTER),
        # 'بالإسنادين جميعا مثله' (1 record)
        'hadith:muslim:2538-4': ("6ab6a40959f43b26fe2a4289f0d3c4ed24a26e0cb0445c41dc4ea5e682e43ab1", _POINTER),
        # 'بقصته' (1 record)
        'hadith:muslim:1480-15': ("0975e075433293873890ec59ae4134515adafcd5852ea8c75fa91cd5c6f0e76d", _POINTER),
        # 'بمثل حديث أبي الزناد سواء' (1 record)
        'hadith:muslim:2963-2': ("d30af37036f77ee1c532d73c7d7d568819479c3e874e95d0e91d26994d12345b", _POINTER),
        # 'بمثل حديث إسماعيل' (1 record)
        'hadith:muslim:1039-3': ("65123ede99e74b21edd4e606a22ac73e550e50de3cffde20ac8c4d7d7373bba9", _POINTER),
        # 'بمثل حديث إسماعيل عن أبي حيان' (1 record)
        'hadith:muslim:1831-2': ("46776ded02cc999284ce41e0b3f8e903c4d38773bfaf64d5c4c3f73ea9d4801d", _POINTER),
        # 'بمثل حديث الأعمش' (1 record)
        'hadith:muslim:2319-2': ("26628feb84a11519f023b9c64a2130f4f0cbf20bbfec204bd66f709e27f4081b", _POINTER),
        # 'بمثل حديث الربيع' (1 record)
        'hadith:muslim:216-2': ("7640805e376a9c0a4c91600b66e4fb35218dfb7f91c8b27b79e0d849dab86b9b", _POINTER),
        # 'بمثل حديث بشر وعبد العزيز' (1 record)
        'hadith:muslim:2995-4': ("37cc22647fe68227db501f4e86aac0d80d96dca2b708a524767485a6656b2f7b", _POINTER),
        # 'بمثل حديث بن علية' (1 record)
        'hadith:muslim:2834-2': ("996ab11d670f55ebee2a8d9f2dde42945f7b4474675884ccbc4deebd4d6e49e5", _POINTER),
        # 'بمثل حديث بن علية وإسناده' (1 record)
        'hadith:muslim:2427-2': ("6d3666093c1ee350c20a794ce303e422ed6c833f3abea5f5c1595680dde484fa", _POINTER),
        # 'بمثل حديث بن علية وحماد' (1 record)
        'hadith:muslim:1668-3': ("b6a6d89e1f36d84c297eb296fb27bce476f195dd9b1be5788cc1d360523054fb", _POINTER),
        # 'بمثل حديث بن عيينة' (1 record)
        'hadith:muslim:979-3': ("83fa7e937615467d19db232f71bf049befbd5112f741e38e754d330e83245f11", _POINTER),
        # 'بمثل حديث بن نمير' (1 record)
        'hadith:muslim:715-12': ("3ec9b37f3117ea087fdee181147f1b534cf709a7cbfd529d280ebaabb8af2fe7", _POINTER),
        # 'بمثل حديث بن نمير عن عبيد الله' (1 record)
        'hadith:muslim:1517-2': ("a8ad86d20574068ae1b72272258db54624eddf27ba86cf0d5498857826a1bf52", _POINTER),
        # 'بمثل حديث بن نمير وزهير' (1 record)
        'hadith:muslim:2394-2': ("b0fa44b372595fcb73067cb736268ccbca7a09877c301af323b4ca97eb0b876f", _POINTER),
        # 'بمثل حديث زهير عن هشيم' (1 record)
        'hadith:muslim:1480-10': ("7064639f468da76e84b70a22cdb8ebcf59c77295f49aea3dae067f00bcc63158", _POINTER),
        # 'بمثل حديث شعبة عن واقد' (1 record)
        'hadith:muslim:66-3': ("ee933fe60bce594dac4d9b36a38da9930daaa03a71cae2900f9948a79370e968", _POINTER),
        # 'بمثل حديث شعبة وسفيان' (1 record)
        'hadith:muslim:49-2': ("ae2ec4fd79a14adb31e452d2d08d0b8ad5e601b7c85f588aa4b76c238f947d4a", _POINTER),
        # 'بمثل حديث عبد الوهاب' (1 record)
        'hadith:muslim:1534-5': ("5af268a710b298db8b18f9bef62c56f713b962b206dc10c00ea292a2f06cbe32", _POINTER),
        # 'بمثل حديث عقيل عن الزهري' (1 record)
        'hadith:muslim:2402-2': ("f3e652f3f80ad30bc836a1cc3d83bfe60fd1d92d1ab63b7ba3e84aac51c06156", _POINTER),
        # 'بمثل حديث مالك عن زيد بن أسلم' (1 record)
        'hadith:muslim:608-2': ("3aa58f31e404204b6c4c075f3eedc9332124d76d9426d2596bd37d3a166fbc01", _POINTER),
        # 'بمثل حديث مالك عن نافع' (1 record)
        'hadith:muslim:1871-2': ("252e016940bf385b86e0aee979d4f140ccfbd1b307d505ee049880f2ef37c234", _POINTER),
        # 'بمثل حديث مالك وعبيد الله' (1 record)
        'hadith:muslim:1534-6': ("0ff916c12fa069c053e253a6429b296212d935f99b8ffbef644819223c1cb49e", _POINTER),
        # 'بمثل حديث مروان سواء' (1 record)
        'hadith:muslim:1921-2': ("2b84880fb3583cafe4b3f7822c861ccbee8d9f143e54b44abf063968ab7b3dd7", _POINTER),
        # 'بمثل حديث معمر هذا سواء' (1 record)
        'hadith:muslim:2527-6': ("19110e1194291d6cd4fa6022b055c1af85bab61afadd13b4649adae394e513d5", _POINTER),
        # 'بمثل حديث منصور والأعمش' (1 record)
        'hadith:muslim:593-4': ("9a2a5ba24738914798a0056933b14751b69f53d4b30f1f4e71d829b2c85a901b", _POINTER),
        # 'بمثل حديث هشام بن عروة' (1 record)
        'hadith:muslim:2673-3': ("a02a8cb3f67c5ecf3411f81d37d9fba87bcc30aca103398f41abbd6a11df1698", _POINTER),
        # 'بمثل حديث هشيم' (1 record)
        'hadith:muslim:693-2': ("47aa112bfabb028e82d8e8a4641dd3dd04967ebc9d645bf51bf95feee30afc9e", _POINTER),
        # 'بمثل حديث وكيع وبن نمير' (1 record)
        'hadith:muslim:2672-2': ("f01969ba175ab25ddc0d6a75f7274419d445117fb7b08d02397e0d492bac6027", _POINTER),
        # 'بمثل حديث يحيى القطان' (1 record)
        'hadith:muslim:1399-4': ("058a1e40c1a704c4c886e647e37c92af20cc8a3313f417022df5e2fde3c8ba3b", _POINTER),
        # 'بمثل حديثهما' (1 record)
        'hadith:muslim:2447-2': ("776ec6880c1b9f094c479ae77b58b3ffcf7b544a6163e71536a70b4703ed6753", _POINTER),
        # 'بمثل حديثهما ولم يذكر ضحى' (1 record)
        'hadith:muslim:2941-3': ("df5d507887f4e303f0f5baf4a0fbf14a59d8d6877607d4211a79e46d790dff03", _POINTER),
        # 'بمثل ذلك' (1 record)
        'hadith:muslim:1075-3': ("769ce066220566f0a2b9bab157034b61d51fba37d4b148d41a2b26ee7756f3b0", _POINTER),
        # 'بمثل ما حدث عروة عن عائشة' (1 record)
        'hadith:muslim:902-2': ("2b9f2cae237260d60526d7baf722f192fcae44a7232c3bb9802ab09c0d8ee2ec", _POINTER),
        # 'بمثل معنى حديث حفص بن ميسرة' (1 record)
        'hadith:muslim:2598-2': ("4091eed207cafe2de26375feffd32f068083f8deb569cc51995be234d34a92c2", _POINTER),
        # 'بمثله 5' (1 record)
        'hadith:muslim:844-3': ("5107a5a5ba4d5151019143633c78970c273b3ee5a4477bc89ad2312e236ac683", _POINTER),
        # 'بمثله غير أنه قال بدهم أو بسوء' (1 record)
        'hadith:muslim:1387-2': ("7f1a2eb4c0f696ec3b3b28cc6337cf027eebe2b1fc932c63e3e4ce521ccb837a", _POINTER),
        # 'بمثله غير أنه قال فقولوا وعليك' (1 record)
        'hadith:muslim:2164-2': ("7252d55fc7a72f3f166ad0679be1404fe3ed5603a449af0db16bea55a09de1ce", _POINTER),
        # 'بمثله غير أنه قال كان لا يدخل' (1 record)
        'hadith:muslim:1928-2': ("b5e9fa021ea658fa0489c37ce150717a65db91da797d1f1f09a55547d839f3db", _POINTER),
        # 'بمثله غير أنه قال من ضر أصابه' (1 record)
        'hadith:muslim:2680-2': ("988cff708549875e5f50c248a8a7569ea8fff210d0f5b4e284f9a36339b0d785", _POINTER),
        # 'بمثله غير أنه قال ينبعث' (1 record)
        'hadith:muslim:157-13': ("84a46f54d5cddd2bd0a80eb077f22136f9b58c24791fac27717349431f58952c", _POINTER),
        # 'بمثله في المعنى' (1 record)
        'hadith:muslim:2176-2': ("0c15a3b07eceba44af88d5770e3783c21812fba6b1b79557238213794eab1211", _POINTER),
        # 'بمثله وزاد في الصلاة' (1 record)
        'hadith:muslim:422-3': ("af9c84e8d4bd45bf5d6a1209956f5faa775dcd66fdfdfc16154033fc7703c496", _POINTER),
        # 'بمثله وزاد لا يقطعها' (1 record)
        'hadith:muslim:2826-2': ("7f70dd69ce8fe841b13fd08071b15e22812bb9e8ba82c51316eaf049a3d7e74f", _POINTER),
        # 'بمثله وزاد وأبشروا' (1 record)
        'hadith:muslim:2816-8': ("361f983f6a8409f2417f99e3c23579b6521deb987c6669f0248845d44a769f15", _POINTER),
        # 'بمثله وقال في الإناء' (1 record)
        'hadith:muslim:2028-3': ("8d1324b7a36269f725fce91966bd43e8503855173822835fde39638ebc1cff90", _POINTER),
        # 'بمثله ولم يذكر الحج' (1 record)
        'hadith:muslim:693-4': ("a8aa20ab31b1de3eb8e30d035515a428087d432286470408751a8d60f3cfdee9", _POINTER),
        # 'بمثله ولم يذكر بن عمر' (1 record)
        'hadith:muslim:2061-2': ("a11a88268f89aad417c2e0086c0a892d6cc33d7f91776308af4139aa3ebaa618", _POINTER),
        # 'بمثله ولم يذكر قول قتادة' (1 record)
        'hadith:muslim:2024-3': ("5373a09356939d868c305cebc0f3d63ab2540d2ae44023cd8dc8c765a30bf1f5", _POINTER),
        # 'بمثله ولم يقل في رمضان' (1 record)
        'hadith:muslim:1102-3': ("01ab0df5121b7f3b3ff846c105c14a3d99fe9dabf116db51c49a128ba890394c", _POINTER),
        # 'بمثله يعني حديث يحيى بن يحيى' (1 record)
        'hadith:muslim:366-2': ("1c6dca989a2d9ac6a49683cd08f8a17950ce700553885dab99690abbee534705", _POINTER),
        # 'بمعناه' (1 record)
        'hadith:muslim:2675-10': ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        # 'بمعنى حديث أبي سنان' (1 record)
        'hadith:muslim:977-2': ("535647499809b6a637382ee9348d321eba8c81a5d41d9446cc6c13e6015be3fe", _POINTER),
        # 'بمعنى حديث المقبري' (1 record)
        'hadith:muslim:1885-3': ("dc680b41fe835f5ec78199c62eedbf42f39c30da93fb5de35aab501a0eda6dc6", _POINTER),
        # 'بمعنى حديث بن عيينة' (1 record)
        'hadith:muslim:2415-2': ("893397769cc198dbbf573f24d2e0a921904feaa4192ff9eee2c974d6d333e2a0", _POINTER),
        # 'بمعنى حديث جويرية' (1 record)
        'hadith:muslim:2242-5': ("d247a7a03b2dc6e3445bd75d4e625829973b49327f271a826030be97ce5153e1", _POINTER),
        # 'بمعنى حديث سمي' (1 record)
        'hadith:muslim:409-2': ("af0a7193124c54e7bce68f10d894d418dc715986de39e5373bcfb20f2c0c3bed", _POINTER),
        # 'بمعنى حديث شعبة' (1 record)
        'hadith:muslim:2218-10': ("4cd0a9d1ea4fb4be3792987ad8f0c4bc79a5712b5d7a2f9583c6510181d2ae8a", _POINTER),
        # 'بمعنى حديث مالك' (1 record)
        'hadith:muslim:2183-2': ("e1fa631f9520e9e0d18a2f5b2ffd30bc78d9e92f2b4724fc8ff35fb498e4298f", _POINTER),
        # 'بمعنى حديث مالك عن نافع' (1 record)
        'hadith:muslim:1501-2': ("bf93899d25779821c12b677b0cefab936c65f814e82c39bd83615d383d5582b1", _POINTER),
        # 'بمعنى حديث من ذكرنا' (1 record)
        'hadith:muslim:2067-6': ("661baed1d1b2293a014afb0c43ab3a6f9371922c4fd173bfdb83c27a0e58581a", _POINTER),
        # 'بمعنى حديث نافع عن بن عمر' (1 record)
        'hadith:muslim:1851-3': ("b815118e26886a2cb5dac8ae7dc174c166da13ee896fed6854aa917b2824ee9e", _POINTER),
        # 'بمعنى حديث هشام بن عروة' (1 record)
        'hadith:muslim:2243-3': ("56c0e365ccddab02885861d720ea5f281580fa3e232e3e7032b8d13884759adc", _POINTER),
        # 'بمعنى حديث يونس عن الزهري' (1 record)
        'hadith:muslim:151-5': ("3a42c1e607c1e92f898c6dfe33748d9066509843bc707b17faf29693b986a074", _POINTER),
        # 'بمعنى حديثهم' (1 record)
        'hadith:muslim:1490-4': ("27fbf905463e3bef776c513b4a5f5da968cd4022c7337169ce3dd64d7af4ad87", _POINTER),
        # 'بمعنى حديثهما' (1 record)
        'hadith:muslim:2808-3': ("82a77373a6ea74593399f784680eea8cb7e850690823fdd6125d848618f4b0fb", _POINTER),
        # 'بنحو حديث أبي عوانة' (1 record)
        'hadith:muslim:209-3': ("82d7dc20cc94334b9c03553b1f3f9fd80a66a1f9aa46f7753b601dc673bd50d9", _POINTER),
        # 'بنحو حديث زهير' (1 record)
        'hadith:muslim:2013-2': ("d510e25bc9e86aa0ed3cf900ca4b0be4aae89f464336b5e148af3f0d1df65d81", _POINTER),
        # 'بنحو حديث مالك' (1 record)
        'hadith:muslim:2068-2': ("0e8c98e629b218befa55fb0e98ab8134aa965dd47dceb96faa33eee27c924ba5", _POINTER),
        # 'بنحو هذا أو بمثله' (1 record)
        'hadith:muslim:2468-2': ("3f83bb7f2fe693caf336ee8dd3c175108a03aa976769e59fc03e7f770aca976a", _POINTER),
        # 'بنحو هذا الحديث أيضا' (1 record)
        'hadith:muslim:963-2': ("99df1e94d46698b31a4f579130b9d6498a11bf0fbe8d42100e802b04a59e8390", _POINTER),
        # 'بهذا الإسناد بنحو رواية يونس' (1 record)
        'hadith:muslim:363-3': ("33b53263b5c26bc98175d88db893cb2aa8dff93ff59f98d336fb77151ec1d11a", _POINTER),
        # 'بهذا الإسناد بنحوه' (1 record)
        'hadith:muslim:663-2': ("131dfd1a935755e55d6761d44d73783945f8a9e6704d27277a07579d9ad2a845", _POINTER),
        # 'بهذا الإسناد كما قال مالك' (1 record)
        'hadith:muslim:723-2': ("ff743b2add2eb87f90df6a06a9aeab5f92456e122b51e0016cab58365e2c14b8", _POINTER),
        # 'بهذا الإسناد مثل حديث بن بكر' (1 record)
        'hadith:muslim:1333-8': ("5fd7c331b0c3eed6756d1a93d35020fca0aa0162bae8d6535a085f03bd30a82b", _POINTER),
        # 'بهذا الإسناد مثل حديث بن مهدي' (1 record)
        'hadith:muslim:979-7': ("01a1d2a8f3f61862416c104c8c48852b966688676821a63f1c428a123359a4a6", _POINTER),
        # 'بهذا الإسناد مثل حديث بن نمير' (1 record)
        'hadith:muslim:286-3': ("e93fc873ed5b7885890f6713e0843328b4c2c65fe0e946f1753b576f8008931b", _POINTER),
        # 'بهذا الإسناد مثل معناه' (1 record)
        'hadith:muslim:2608-2': ("47fb780242934f7b76168686d54428b7135dc56daf31ec99488e46291dd6d14b", _POINTER),
        # 'بهذا الإسناد مثله وزاد فصاعدا' (1 record)
        'hadith:muslim:394-4': ("bb8ca137a326d6c100615c4c92dbfe75f4a2558db7a7ed85e3db0fdc5eb1f980", _POINTER),
        # 'بهذا الإسناد مثله ولم يقل حق' (1 record)
        'hadith:muslim:2225-5': ("81136122d6e18547971f8a7394db19613469e26571a358cce52ed21771a5546c", _POINTER),
        # 'بهذا الإسناد نحو حديث بن عيينة' (1 record)
        'hadith:muslim:1111-6': ("088a6f38bac04b0160a2fd5b856812c932f8eb263f7de0c1fd8d055254a8f45a", _POINTER),
        # 'بهذا الإسناد نحو حديث عبثر' (1 record)
        'hadith:muslim:2685-2': ("b4b6b4d08695a4ab0ccf013bcd23f8947ae434dd137701674f89c5909f927f91", _POINTER),
        # 'بهذا الإسناد نحو حديث مالك' (1 record)
        'hadith:muslim:2327-3': ("356a9e275818cc88b76f1761eec97e6b5d6bf56b6d0a9a2bc9d4a9980bad144a", _POINTER),
        # 'بهذا الإسناد نحو حديثهما' (1 record)
        'hadith:muslim:1797-3': ("2deede7add4ae0f9d34e236a253baa055e3b0c56ea717b931dad7ab7d5590fc1", _POINTER),
        # 'بهذا الإسناد هذا الحديث' (1 record)
        'hadith:muslim:1619-2': ("5d6b53c85fa39cfd4a67e2d2fb242893c4ab5262038ccab6e3aaa76839bd962e", _POINTER),
        # 'بهذا الإسناد وزاد فأدعها' (1 record)
        'hadith:muslim:2083-3': ("f99057ae34e7bb5160e2c10483e4e31380515db165409f72313cce208b84ce02", _POINTER),
        # 'بهذا الإسناد وساق الحديث' (1 record)
        'hadith:muslim:987-4': ("e1a1d472991daff1b3a36dc22114835200572977a291202356229f22cd6df8ab", _POINTER),
        # 'بهذا الإسناد وقال حتى ترجع' (1 record)
        'hadith:muslim:1436-2': ("edd4a1e1f1aa38a884eb33ac9a93f20ca0f68418ed254aa550906cb3e45b20ae", _POINTER),
        # 'بهذا الإسناد وقال سبع غزوات' (1 record)
        'hadith:muslim:1952-3': ("521eca1bc745ad5a5d6518d34278b2ef1613fb6d08df66538793eb8ab1527688", _POINTER),
        # 'بهذا الإسناد وقال صوم شهرين' (1 record)
        'hadith:muslim:1149-4': ("f09ea2c2786b3e58d283769a418c141f9f643d72e354897398d4d6e33e80fe7a", _POINTER),
        # 'بهذا الإسناد وقال عبدا حبشيا' (1 record)
        'hadith:muslim:1838-2': ("7df75d3f5ed4088f940a7a63a0ed732b79d7d0e64597943878af93222e0fdbca", _POINTER),
        # 'بهذا الإسناد وقال ونفهت النفس' (1 record)
        'hadith:muslim:1159-9': ("5a0777490edeafc374b668c2b87feb0b1cc22bdaa546e144cda0aaf0a990bc5e", _POINTER),
        # 'بهذا الإسناد وقالا وشق ودعا' (1 record)
        'hadith:muslim:103-2': ("7d9a4fd3104b077fbddad94edbefc825524da15072df7b3edc7aca28bb58a993", _POINTER),
        # 'بهذا الإسناد ولم يذكر في السفر' (1 record)
        'hadith:muslim:2076-2': ("c3ca5f39b25df5d0e9db07d23940935337b0c756f655c941b7433b64e0b753d0", _POINTER),
        # 'بهذا الإسناد ولم يذكر وأبشروا' (1 record)
        'hadith:muslim:2818-2': ("fa95a5a09f82bde9c998d3ee8c800f2f3382b8e15c71525d854f154f84c5f430", _POINTER),
        # 'بهذا الإسناد ولم يذكر يدا بيد' (1 record)
        'hadith:muslim:1588-2': ("be1ae5026cc4568421881fca2fb26a6305c50a0e57195486e408c790629cf16c", _POINTER),
        # 'بهذا الإسناد ولم يذكروا أم كعب' (1 record)
        'hadith:muslim:964-2': ("e4aa5c86684558b72222af9f3656f9dfc786c48b67d9951c35811739016f05b1", _POINTER),
        # 'بهذا الإسناد ولم يقولا حسنا' (1 record)
        'hadith:muslim:670-3': ("1b5dcefa287d4966f25a037541363a15e5ea78929da1436aeb075e4c4a1dd974", _POINTER),
        # 'بهذا الحديث يزيد بعضهم على بعض' (1 record)
        'hadith:muslim:677-7': ("642eb78115f8f322ce8e43637bdaa39c46debbe0917a3ab1d663b75d65998528", _POINTER),
        # 'بهذا مثل حديث الليث عن نافع' (1 record)
        'hadith:muslim:1829-3': ("dd2ec52059081995aa10e20b601e116d0469429edf44faff8bd8b235df3a4f7e", _POINTER),
        # 'بهذا ولم يذكر الأجر والمغنم' (1 record)
        'hadith:muslim:1873-5': ("d55a881957ac57dafea86f93534aecbd16adb7f86102ca00c35f8ea6e21beb38", _POINTER),
        # 'بهذا ولم يذكر عن عمه ظهير' (1 record)
        'hadith:muslim:1548-6': ("845ee553a2b40f069a17ec4ab9d6433a8f62ea59af6b77ee6ba313f4898d104d", _POINTER),
        # 'بهذا ولم يقولوا أبيض قد شاب' (1 record)
        'hadith:muslim:2343-2': ("be5613763597884a0ac7fe187bdd053c5a84288c52997428d3dc29dd98678e7d", _POINTER),
        # 'بهذه القصة نحو حديث يزيد' (1 record)
        'hadith:muslim:2144-3': ("5eb1192ebd764d241567a49e263a59a19296e4856c62a51357a06f84bcad8cae", _POINTER),
        # 'حماد ولم يذكر الركعتين' (1 record)
        'hadith:muslim:875-2': ("8323cb807d2a444e54f2afe03a222eb04debdd7dcbafb3bfe26b1deb8ea8f172", _POINTER),
        # 'ذكر نحوه' (1 record)
        'hadith:muslim:411-2': ("c1efe1d128aaada4dd59dbcb80769d57de8da5623f39466e8fd948e17948a614", _DEFERRAL),
        # 'ذلك' (1 record)
        'hadith:muslim:1651-4': ("75d350ce684c85e31b4f9cd299e8a7c6f875724cbefd6c86e1fddae07a24e31b", _POINTER),
        # 'رفعه' (1 record)
        'hadith:muslim:626-2': ("fb95a9828d7585d8ec476cf8e597bb65efaef0eabe0ad303290386ad968313ac", _ATTRIBUTION_NOTE),
        # 'سألت أنسا بمثله' (1 record)
        'hadith:muslim:555-2': ("07dc0aad5c717c41caace80fcb6e3dc823b6c9e0919b1bec3f0e15a9da7e0dbc", _POINTER),
        # 'سمع أنس بن مالك يذكر ذلك' (1 record)
        'hadith:muslim:399-4': ("217f18cf7aa0728b4411cb6309abbda2d9aecad39e718a4058045331a43086ba", _DEFERRAL),
        # 'سمعت العلاء بهذا الإسناد' (1 record)
        'hadith:muslim:2761-4': ("46f528abd471e082b941de1edd1522989980ac5b8dc9bf42d5cf60324fa8eb6e", _DEFERRAL),
        # 'سمعت معمرا بهذا الإسناد' (1 record)
        'hadith:muslim:608-4': ("29611bc21b89c9ee3f862018b3f20d9519d9c709536c39c46ed8766aac0ec8ef", _DEFERRAL),
        # 'على معنى حديث صالح عن الزهري' (1 record)
        'hadith:muslim:150-6': ("cda618323a7fd613763d8eec597224b3d74a5dc2ba42d67b88fcd33425ff7da0", _POINTER),
        # 'عليك بالرفق ثم ذكر بمثله' (1 record)
        'hadith:muslim:2594-2': ("41131a7f5fa08da505f17a43cff453c32ddbe034330fb1c9f744768eda809501", _POINTER),
        # 'فذكر بمثل حديث بن علية' (1 record)
        'hadith:muslim:824-4': ("3bf208ee6d5f9606e8478858a85911f19f6775904d503ca4a3ab893e08cde720", _DEFERRAL),
        # 'فذكر بمثل حديث همام' (1 record)
        'hadith:muslim:2958-2': ("c3c9495f11c0e048c95f5d8bdef38ddc9d916a747c4c095fee1dc8e4a72abb00", _DEFERRAL),
        # 'فذكر بمعنى حديث مالك' (1 record)
        'hadith:muslim:507-2': ("8873c21a50c1f771af613db7bb213c4486c28c2b5bdecc0dec1e5cbf40e4514d", _DEFERRAL),
        # 'فذكر نحو حديث قتادة عن أنس' (1 record)
        'hadith:muslim:200-4': ("2c339423ca0070f0e05296df653068097525d0d2b1bfb8f8a1b0953f5dd2c9db", _DEFERRAL),
        # 'فذكر نحوه' (1 record)
        'hadith:muslim:521-2': ("edc5862bd004c3bef89e0e4e3c8f0e64f1fa71d9a89a676789dd728c9d23ff4a", _DEFERRAL),
        # 'فذكر نحوه ولم يقل يوم القيامة' (1 record)
        'hadith:muslim:2067-3': ("c8e5a76c863bf86b001b74a0f7a0cc72d4edddf0ca02cb3af62266c0eb39ede6", _DEFERRAL),
        # 'فذكر هذا' (1 record)
        'hadith:muslim:1094-5': ("f88da58d894bb254adb240946c307233d661d9893b7159237aeb448b9f0db303", _DEFERRAL),
        # 'فذكرا نحوه غير أنهما قالا تنقز' (1 record)
        'hadith:muslim:795-3': ("f81f5a25041bc9869ddcae1d526d738e8a6ddbeb206e8e0b483fa6ca130686c4", _DEFERRAL),
        # 'فذكروا الحديث بطوله' (1 record)
        'hadith:muslim:2577-3': ("ee40b92ca7636557d437595772b0d6aef6686ee5caa4db079b84097de244858c", _DEFERRAL),
        # 'في الحرير بمثله' (1 record)
        'hadith:muslim:2069-4': ("607b59933897dfede5c01289ebbc9dabe4015177c4b7c68a613ff74bb9592fb4", _POINTER),
        # 'في حديثه إزارا غليظا' (1 record)
        'hadith:muslim:2080-2': ("5c1e1171155a67a66e96d4e49707abdfc5a68c5490df3670722d89fb88fcc120", _POINTER),
        # 'في حديثه هذا يهودي ورائي' (1 record)
        'hadith:muslim:2921-2': ("8aaa9d6e86c8d2b96b96bb6704c276ccda320b8d7192be8c3eabcae7a66187f9", _POINTER),
        # 'في خاتم الذهب نحو حديث الليث' (1 record)
        'hadith:muslim:2091-3': ("9d96a226ab440bc807f0653bcac3790529ea7eadf1ac897a47dd199596cca5d7", _POINTER),
        # 'في روايته يعني معاوية' (1 record)
        'hadith:muslim:1225-2': ("af8e30b24855d8b9dc35e9d339f221d2329fb223228fff950c60506b6845eebb", _POINTER),
        # 'في طعام أبي طلحة نحو حديثهم' (1 record)
        'hadith:muslim:2040-9': ("00f49ab02c825d9f40ae7f6aaad4efc6ecda23e787d7c8d65a9d60697245d038", _POINTER),
        # 'في هذا الإسناد بمثل حديث هشيم' (1 record)
        'hadith:muslim:466-2': ("4a6c075eef23ca957546e3ee82944481e0f1c7e139a8cf0e39e03e3f5a3d0a34", _POINTER),
        # 'في هذا الإسناد بمعنى حديثهما' (1 record)
        'hadith:muslim:1086-3': ("988a4a13e067b9506f3366c09315c87cf3cd881684d6ac8a9ffe0983f879a5bf", _POINTER),
        # 'في هذا الإسناد في معناه' (1 record)
        'hadith:muslim:2917-2': ("60efcf3fd2ce1f80f7d1c199a1baa533210ca2145810445c6e0de504447fd290", _POINTER),
        # 'كرواية روح' (1 record)
        'hadith:muslim:2012-7': ("879e0b4b9683a4aff4ab4f9dc2a73cca6bad2b7e7171919c5b91de17e287ea75", _POINTER),
        # 'كرواية عقيل بالإسنادين جميعا' (1 record)
        'hadith:muslim:951-3': ("a9d0d6b2db226d0cd6aa5b1c4ee7b63063ab23daf2cc06424eab9ccdb0149b4f", _POINTER),
        # 'كرواية يونس بإسناده' (1 record)
        'hadith:muslim:818-3': ("702086c2c60fe1cb389b20d5b1c1142fd0d0233169a4a58aaece4e0947ea668b", _POINTER),
        # 'كنا نصلي المغرب بنحوه' (1 record)
        'hadith:muslim:637-2': ("9c2ede2775e3b3b704cce8e1d653c82065893c263d4064f4b54354d32c014dcb", _POINTER),
        # 'لكأني أنظر بمثل حديث وكيع' (1 record)
        'hadith:muslim:1190-4': ("29dd0bd472cde6316ac8975959c725489807a30327f5a36b684dd89dfde8d076", _POINTER),
        # 'ما شاء الله' (1 record)
        'hadith:muslim:719-2': ("dfd9695ee60f9294b80a2d025d6745fd2da438ed486d673f9a250f510ed46c58", _POINTER),
        # 'مثل حديث الليث عن نافع' (1 record)
        'hadith:muslim:1829-2': ("b4d98627b87929bb81a2575bb1b6f5ef9e622103141f17bbae3753f8ef51ac07", _POINTER),
        # 'مثل حديث ثابت' (1 record)
        'hadith:muslim:1809-2': ("903ab15e51987de74796fff046c23e23ec421110ca68e557a9c598a2beb09dbc", _POINTER),
        # 'مثل حديث هؤلاء عن بن عمر' (1 record)
        'hadith:muslim:2518-3': ("7ae7f5a268a5d4f113fc625cb44d571a82e145b007dd34c24e1b5182edfbacfe", _POINTER),
        # 'مثل حديث يونس' (1 record)
        'hadith:muslim:523-3': ("c2f1fc255d652607247777c9bc86809ab1882d66449378f8ffc847dffd72f0fb", _POINTER),
        # 'مثل حديثه' (1 record)
        'hadith:muslim:1710-2': ("12f33147cf153fa305d34ec6cb86d4a966cfa3bee5a27b5d6cb1328df0546eff", _POINTER),
        # 'مثله أو نحوه' (1 record)
        'hadith:muslim:1654-3': ("2a763ad27e558cac7f6e08250950c22bea6bef04c914bfd273f66ccc4bbe52fa", _POINTER),
        # 'مثله إلا أن فيه زكاة وأجرا' (1 record)
        'hadith:muslim:2602': ("74532fe35e8b75bb2413e81c1b49bcb6bd91e50f30cab919d43cb55d3491803e", _POINTER),
        # 'مثله غير أنه قال ثيابه' (1 record)
        'hadith:muslim:2085-6': ("d04968e961eade65c08a44d07085a7544c2b13d70f34bef6259e407fbd90331d", _POINTER),
        # 'مثله وقال بدل أتمها أحسنها' (1 record)
        'hadith:muslim:2287-2': ("5cd4bc7de20c182a8d97f35b7e0172f628475307df0b336d0d19ad7952db057f", _POINTER),
        # 'مثله ولم يذكر من حديد' (1 record)
        'hadith:muslim:1603-4': ("432171abe36426661f0ec2e4993504c4818564a1f41f209ab435c19d8319b853", _POINTER),
        # 'مثلي ومثل النبيين فذكر نحوه' (1 record)
        'hadith:muslim:2286-4': ("926a980d49eb9d6dd69047bec55eeafe0aa7861bcf14ef7e7d99d03d28eee6c9", _POINTER),
        # 'مر برجل من الأنصار يعظ أخاه' (1 record)
        'hadith:muslim:36-2': ("91245e01d0f3bdc558d93a52c2a108c15a8ca7934a237e94605fef271b8179f2", _TRUNCATED_STUB),
        # 'من شحم ولم يذكر الطعام' (1 record)
        'hadith:muslim:1772-3': ("b60bb8ef936f08c0152b3c3bfdc6c0906793e2fa2e3189a490479c50c4ec8c13", _POINTER),
        # 'من وحد الله ثم ذكر بمثله 9' (1 record)
        'hadith:muslim:23-2': ("549ce9fb424755f500ac19cdde5819b1509ed1bf469c0742ddf14b6cbe0fdcbe", _POINTER),
        # 'نحو حديث أيوب مرفوعا' (1 record)
        'hadith:muslim:1066-5': ("74af21104e12b429589e780dc654c3dc47d31d780a39594800f6a2abc18792f8", _POINTER),
        # 'نحو حديث الأعمش ومغيرة' (1 record)
        'hadith:muslim:2297-4': ("4bb1b854b48a27fd316af8132ad7a0e3713bcbcb1dfe5bf4f8632338357ae1a6", _POINTER),
        # 'نحو حديث الليث ويونس' (1 record)
        'hadith:muslim:2156-3': ("277889f908dbd59a3dca52b7a0ad6482d48d83bb5f7fddf7ff7851ea8595bf6b", _POINTER),
        # 'نحو حديث بن أبي عروبة' (1 record)
        'hadith:muslim:1786-2': ("3dc707cafc75d1788d0639827e0d38ce9a9047f84a89432799f70a32cc9c4652", _POINTER),
        # 'نحو حديث بن عيينة' (1 record)
        'hadith:muslim:1234-2': ("05e1cbb2d6c6e20d0af8083524fc0e6b15acae4f537e6ad99160667c86d375bf", _POINTER),
        # 'نحو حديث شيبان' (1 record)
        'hadith:muslim:2967-2': ("cd73752b46976c5a26b7af118b8f5c2fd69b32fcbeaa24ae56a382cd8899b6e7", _POINTER),
        # 'نحو حديث مالك عن نافع' (1 record)
        'hadith:muslim:1531-2': ("dd5aaa67b29632b6a95b731bf5d293c1f364bf9e292849b2403f25049281b9f0", _POINTER),
        # 'نحو حديث يعقوب عن سهيل' (1 record)
        'hadith:muslim:1014-4': ("74e2bc032e01523688167d0c0679e41794778093e94d3346d525b9db146b99b1", _POINTER),
        # 'نحو ذلك' (1 record)
        'hadith:muslim:1432-3': ("cf1f22d38f2ded3b02c6f04ec674d178a304af4ca4dafdb6c7adc37c7721b697", _POINTER),
        # 'نحو هذا' (1 record)
        'hadith:muslim:206-2': ("b2133cd31847e4d6a1dbdcf8e39425d27513e8a2c945867b902e622191a40b08", _POINTER),
        # 'نحو هذه القصة' (1 record)
        'hadith:muslim:1471-20': ("c3ea67a787ea1ff1ab863eedcb3dbc9078bf751420284f19d6f4359954a6fd62", _POINTER),
        # 'واقتص الحديث' (1 record)
        'hadith:muslim:1751': ("8355edd78515744c43cc6a8b37ab04ebe9f02eb42589aa7bbd61d18d8151daef", _DEFERRAL),
        # 'والذي نفسي بيده بمثل حديثهما' (1 record)
        'hadith:muslim:1252-3': ("76c4d05f4e3ea23198421ce9c4218b5158b73b703825d3224da782b7da84dfe9", _POINTER),
        # 'وذكر اللقمة نحو حديثهما' (1 record)
        'hadith:muslim:2033-6': ("5dc6d4cd550766342e42875d48d082a354f3edaca34d05d6f09656b891dd6f0e", _POINTER),
        # 'وساق الحديث' (1 record)
        'hadith:muslim:1751-2': ("3fb9392ed9b90344141c4b038fe5ce3f29b57822de50f91565aa7919044bb98a", _DEFERRAL),
        # 'وفي حديث وكيع قال يرفعه بمثله' (1 record)
        'hadith:muslim:278-2': ("1b0a668294b153dd021117a61f1f4a54e8495e41a11d753a4fe02f2617b71c81", _POINTER),
        # 'ولم يذكر حاد حسن الصوت' (1 record)
        'hadith:muslim:2323-6': ("6c1ab8076ebb58cf1f9820d0198a0cc1aea0a8f19040d710ae1aee6cb1963093", _POINTER),
        # 'ولم يذكر في السجود' (1 record)
        'hadith:muslim:480-6': ("c7041685d43a6271b533d163f834890c60f1165306e272a36a045a04d556d02b", _POINTER),
        # 'ولم يذكر لا كفارة لها إلا ذلك' (1 record)
        'hadith:muslim:684-2': ("cddc94e64bfe9119a24f1485a18c8773d50bbd932a2262f057f5e43e1987e301", _POINTER),
        # 'يا رسول الله بمثله' (1 record)
        'hadith:muslim:2369-2': ("ab41a99e99f93506aa7accb1ab4c4c105028149dcfd1971a47294602731441c0", _POINTER),
        # 'يا رسول الله مالك لم تحل بنحوه' (1 record)
        'hadith:muslim:1229-2': ("6eb6bcb3e91ef400cc66d2307876f7b509003245f14249d687e82d37032fe6f0", _POINTER),
        # 'يصدر الناس بنسكين فذكر الحديث' (1 record)
        'hadith:muslim:1211-19': ("7e45b0e2abcd79a670db1d6ead161b006ef2133d63d1339dc99b94ddf36031d4", _POINTER),
        # 'يعوده نحو حديث الحسن عن معقل' (1 record)
        'hadith:muslim:142-8': ("76d549465aafab4d14b57bf519e4d1e25f316d69313db4f34eab7696205eb0e4", _POINTER),
        # 'يقول فذكر بمثله' (1 record)
        'hadith:muslim:2671-3': ("dc3f8465471a490603837d07a0bf56f2d5927537d0a458f12969d573d7b876f3", _POINTER),
    },
}
