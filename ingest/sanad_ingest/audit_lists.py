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
}
