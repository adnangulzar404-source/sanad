"""OpenITI mARkdown -> hadith units.

Pure function: text in, structure out. No network, no database, no file I/O.

The marker inventory below was measured against the pinned file on 2026-09-22,
not taken from OpenITI's documentation -- the file contains marker forms the
docs do not mention (ms####, backslash part markers), and a parser written from
the docs alone would have leaked them into stored text.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_HEADER_END = "#META#Header#End#"

# Structural markers, all stripped from stored text.
_CONTINUATION = "~~"
_PAGE = re.compile(r"PageV\d+P\d+")
_MILESTONE = re.compile(r"ms\d{4}")
_PART = re.compile(r"\\\s*\d+\s*\\")          # the "\ 1 \" part marker
_QURAN_MARK = re.compile(r"@QB@|@QE@")        # markers go, quoted words stay
_SECTION = re.compile(r"^###")                # ### | , ### || , ### |||
_KITAB = re.compile(r"^###\s*\|(?!\|)\s*(.*)$")
_BAB = re.compile(r"^###\s*\|\|+\s*(.*)$")
_UNIT_START = re.compile(r"^#\s")              # "^#\s" already can't match "###"
_NUMBERED = re.compile(r"^(\d+)\s+(م\s+)?(.*)$", re.DOTALL)
_LEADING_NUMBER = re.compile(r"^\d+\s+")

# A numbered unit whose text begins with "باب" is a chapter heading that the
# edition happens to number, not a narration. Six of them exist in the file.
_BAB_WORD = "باب"

# Everything outside these ranges is flagged (never corrected) as OCR noise.
_ALLOWED = re.compile(r"[؀-ۿ\s]")

# --- secondary narrations --------------------------------------------------
#
# The al-Bugha edition appends FURTHER narrations after the primary matn --
# each with its own chain and often its own variant wording -- and marks only
# the first isnad/matn boundary with "*". Everything after that boundary was
# therefore landing in the scored text, with the trailing material a median
# 40% of the stored string.
#
# The source does mark these boundaries, just not with "*": a narration verb
# followed by CHAIN MATERIAL -- a narrator's name and then another link ("an",
# "ibn", another narration verb). What follows the verb is the signal. Round 1
# anchored on what precedes it instead (an attribution, "qala <name>"), which
# is real but rare: it found 155 boundaries and missed ~240 the edition marks
# just as plainly. The forward test also makes the counterexamples fall out
# for free rather than needing a guard each -- "he said to Bilal: TELL ME the
# deed you most hope for" (1098) and "TELL ME about faith" (50) are narration
# verbs with a preposition behind them, not a chain.
#
# Every number in the comments is from the pinned file, not an estimate; the
# full measurement is in .superpowers/sdd/2026-09-22-hadith-corpus/
# task-4-fix-2-report.md.

_NARRATION_VERBS = ("حدثنا", "حدّثنا", "حدثني", "أخبرنا", "أخبرني")
_ARABIC = "؀-ۿ"
# The wa- and fa- proclitics are part of the verb, not a reason to ignore it:
# the edition writes "...qala Shu'ayb WA-haddathani Nafi' 'an Ibn Umar..."
# (621) and "...qala Hisham FA-akhbarani abi 'an A'isha..." (3896) as single
# tokens, and round 1's lookbehind stepped straight over both.
_VERB = re.compile(
    rf"(?<![{_ARABIC}])[وف]?(?:{'|'.join(_NARRATION_VERBS)})(?![{_ARABIC}])")
_VERB_TOKEN = re.compile(rf"^[وف]?(?:{'|'.join(_NARRATION_VERBS)})$")
# The attribution that introduces an addendum. "fa-qala" counts only on the
# forward path: on its own it is far more often plain narration ("he said to
# him: tell us how the Prophet prayed", 574) than a chain marker.
_ATTRIBUTION = re.compile(rf"(?<![{_ARABIC}])[وف]?قال(?![{_ARABIC}])")
_PLAIN_ATTRIBUTION = re.compile(rf"(?<![{_ARABIC}])و?قال(?![{_ARABIC}])")
# "he said" / "she said" / "they said" / "says", with the wa- and fa- proclitics.
_SPEECH_VERB = re.compile(r"[وف]?(?:قال|قالت|قالوا|يقول|تقول)")
# "to me" / "to us" / "to him" ... -- the addressee of a speech verb.
_ADDRESSEE = re.compile(r"ل(?:ي|نا|ه|ها|هم|هن|كم|كن)")

# What a chain says after it names a narrator: "from", "son of". A narration
# verb is another link and is checked separately.
_CHAIN_LINKS = frozenset({"عن", "بن", "ابن"})

# Words that GOVERN the verb behind them, so the verb opens a clause rather
# than a chain: "I said: TELL ME something you remember" (1570), "we told him
# WHAT Anas told us" (7072), "the people did the like of THAT WHICH Salim
# reported to me" (1606). Each of the three forms rejects exactly one
# candidate on this file, and all three were found by reading every candidate
# the rule produced -- not by pattern-hunting. A relative or interrogative in
# front of the verb makes the chain behind it a complement, and cutting there
# leaves the primary ending on a dangling "the one which".
_GOVERNS_THE_VERB = frozenset({
    "قلت", "فقلت", "قلنا", "فقلنا", "سألت", "فسألت",   # "I said / I asked"
    "ما", "بما", "مما",                                  # "what / with what"
    "الذي", "التي", "الذين",                             # "that which / who"
})

# Attribution must sit within this many characters of the verb. MEASURED, not
# chosen by taste: 25 is the largest distance a one-to-three-token attribution
# ever spans in this file (the observed range is 8..24).
_ATTRIBUTION_WINDOW = 25
# A narrator's name here is one to three tokens -- "Wuhayb", "Abu Mu'awiya",
# "Sa'id ibn Zayd", "Abu Abdullah". Four or more is not a name, it is speech
# that happens to contain "qala".
_MAX_NAME_TOKENS = 3
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
_MAX_ADDENDUM = 1000

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
# `build._reject_wholly_quranic_representations` is what closes the class;
# this entry corrects the one record.
_QURANIC_PRIMARY = ("Qur'anic primary: the cut leaves a matn that is nothing "
                    "but the ayah the chapter comments on, the narration that "
                    "makes the unit a hadith beginning in the appended chain")

_NEVER_CUT: dict[str, tuple[str, str]] = {
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
}

# Tokens that cannot be part of a narrator's name. Closed word classes --
# vocatives, particles, pronouns, demonstratives, prepositions, speech verbs --
# not a list fitted to the candidates it happens to reject.
_NOT_A_NAME = frozenset({
    # vocative / interjection
    "يا", "اللهم", "ألا",
    # affirmation and negation
    "نعم", "لا", "بلى", "كلا", "ليس", "لم", "لن", "ما",
    # demonstratives
    "هذا", "هذه", "ذلك", "تلك", "ذاك", "هؤلاء", "ذا",
    # pronouns
    "هو", "هي", "هم", "هن", "أنا", "أنت", "نحن", "إياه",
    # particles and conjunctions
    "إن", "أن", "إنه", "إنها", "أنه", "أنها", "إنما", "قد", "لقد", "فقد",
    "فلقد", "ثم", "بل", "لكن", "حتى", "إذا", "إذ", "لما", "أو", "أم", "هل",
    "كيف", "أين", "متى", "لو", "لولا", "كأن", "لعل", "ليت", "فإن", "فإنه",
    "وإن",
    # prepositions and adverbs
    "في", "على", "إلى", "مع", "عند", "بعد", "قبل", "بين", "حين", "يوم", "من",
    # the edition's placeholder for an unnamed person
    "فلان", "فلانا", "فلانة", "وفلان", "وفلانا",
    # speech verbs: "qala qultu ..." is narrative, not an attribution
    "قالت", "قالوا", "فقال", "فقالت", "قلت", "فقلت", "سمعت", "يقول", "تقول",
    "كان", "كانت", "فكان",
})


def _opens_a_chain(after: list[str]) -> bool:
    """Do the tokens after a narration verb read as the start of a chain?

    A chain names its narrator and then links onward: "haddathani Nafi' 'AN
    Abdullah", "haddathana Muhammad IBN al-Muthanna", "haddathana Amr
    HADDATHANA Shu'ba". Genuine speech does not: "akhbirni bi-arja 'amal"
    ("tell me the deed you most hope for") runs straight into a
    prepositional phrase, and "akhbirni 'AN al-islam" is "tell me ABOUT
    islam" -- which is why "'an" flush against the verb, with no narrator
    named in between, is the one position where it cannot be a link.
    """
    for i, token in enumerate(after[:_MAX_NAME_TOKENS + 1]):
        if _VERB_TOKEN.match(token):
            return True
        if token in _CHAIN_LINKS:
            return not (token == "عن" and i == 0)
        if token in _NOT_A_NAME:
            return False
    return False


def _attribution_start(matn: str, verb_start: int, pattern: re.Pattern[str],
                       allow_particle: bool, min_name: int = 1) -> int | None:
    """Index of an attribution "qala <name>" introducing the verb, if any.

    Walks back over at most _MAX_NAME_TOKENS name tokens, so that the cut
    takes the attribution with the addendum it introduces rather than
    stranding it at the end of the primary.
    """
    tokens = matn[:verb_start].split()
    k = len(tokens)
    if allow_particle and k and tokens[-1] in ("و", "ف"):
        k -= 1          # "...qala Shu'ayb wa | haddathani..." -- 621, 3896
    named = 0
    while k >= 1 and named < _MAX_NAME_TOKENS and not pattern.fullmatch(tokens[k - 1]):
        if tokens[k - 1] in _NOT_A_NAME or len(tokens[k - 1]) == 1:
            return None
        k -= 1
        named += 1
    if k < 1 or named < min_name or not pattern.fullmatch(tokens[k - 1]):
        return None
    if named == 1 and tokens[k].startswith("ل"):
        # "qala li-Anas haddithni" is "he said TO Anas: tell me", not
        # "Anas said". The lam- proclitic marks an addressee.
        return None
    start = len(" ".join(tokens[:k - 1])) + (1 if k - 1 > 0 else 0)
    if verb_start - start > _ATTRIBUTION_WINDOW:
        return None
    return start


def _audited_never_cut(record_id: str, matn: str) -> bool:
    """Is this record on the hand-read do-not-cut list, for THIS text?

    Same contract as `_unscorable_reason`: the entry records a judgement about
    one specific string, so a matn that no longer hashes to the audited one
    stops the build instead of inheriting the judgement.
    """
    audited = _NEVER_CUT.get(record_id)
    if audited is None:
        return False
    digest, _reason = audited
    if hashlib.sha256(matn.encode("utf-8")).hexdigest() != digest:
        raise ValueError(
            f"{record_id} is on the do-not-cut audit list, but its matn is no "
            "longer the text that was audited. The list records a judgement "
            "about one specific string; it must not be carried over to a new "
            "one. Read the record in the source, decide again whether the cut "
            "leaves a quotable primary, and update or remove the entry.")
    return True


def _split_secondary(matn: str, record_id: str) -> tuple[str, str | None]:
    """Split a matn into (primary, addenda) at the first secondary narration.

    Returns (matn, None) unless the source marks a boundary. Never invents
    one: every guard below is a reason to leave the text alone, and leaving
    an addendum in the scored text is merely the bug we already had, while
    cutting one word too early destroys scripture.

    The addendum is not lost to scoring by being cut away: `full_text` rejoins
    it and the build stores the result as the record's second representation
    (`corpus.models.RecordVariant`), so the whole printed hadith is indexed
    too. That is what makes the guards below safe to be conservative.
    """
    if _audited_never_cut(record_id, matn):
        return matn, None
    for verb in _VERB.finditer(matn):
        forward = _opens_a_chain(matn[verb.end():].split())
        # The backward signal on its own still counts: "wa-qala Sa'id ibn
        # Zayd haddathana Abd al-Aziz idha arada an yadkhula" (142) is a
        # one-link chain, so nothing follows the verb to recognise.
        start = _attribution_start(matn, verb.start(), _PLAIN_ATTRIBUTION, False)
        if forward:
            # A bare "qala" with no name is an attribution here too, because
            # the chain behind the verb already settled the question.
            start = _attribution_start(matn, verb.start(), _ATTRIBUTION,
                                       True, min_name=0) or start
        elif start is None:
            continue

        cut = start if start is not None else verb.start()
        before = matn[:cut].split()
        if len(before) < 2:
            # 6477's matn is the single word "al-kaba'ir" in front of a second
            # chain that carries the actual hadith. A one-word scored text is
            # the empty-matn hazard wearing a hat.
            return matn, None
        if _ADDRESSEE.fullmatch(before[-1]) and _SPEECH_VERB.fullmatch(before[-2]):
            # "fa-qala li: qala Ibn Abbas ..." -- the attribution is the
            # CONTENT of the preceding speech verb, so it is inside the
            # narration. Cutting here moved 2,677 characters of hadith 4449
            # (the Musa and al-Khidr story) out of the scored text.
            return matn, None
        if before[-1] in _GOVERNS_THE_VERB:
            return matn, None
        if len(matn) - cut > _MAX_ADDENDUM:
            return matn, None
        # No length floor on what is left behind -- see the note above
        # `_NEVER_CUT`. A short primary is not evidence of a bad cut.
        return matn[:cut].rstrip(), matn[cut:]
    return matn, None


def full_text(unit: HadithUnit) -> str:
    """The unit's matn as the edition prints it: primary plus every addendum.

    The one place the two halves of a cut are rejoined, so the build and the
    reassembly test cannot disagree about the join. The single space is the
    one `_split_secondary` removed with `rstrip()`; `_clean` has already
    collapsed every whitespace run in the unit to exactly one space, so this
    restores the source byte for byte. `test_nothing_is_lost_when_an_addendum_
    is_cut_away` proves that against the raw file, not against the parser.
    """
    if unit.addenda_ar is None:
        return unit.matn_ar
    return f"{unit.matn_ar} {unit.addenda_ar}"


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

_UNSCORABLE: dict[str, tuple[str, str]] = {
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
}


def _unscorable_reason(record_id: str, matn: str) -> str | None:
    audited = _UNSCORABLE.get(record_id)
    if audited is None:
        return None
    digest, reason = audited
    if hashlib.sha256(matn.encode("utf-8")).hexdigest() != digest:
        raise ValueError(
            f"{record_id} is on the unscorable audit list, but its matn is no "
            "longer the text that was audited. The list records a judgement "
            "about one specific string; it must not be carried over to a new "
            "one. Read the record in the source, classify it again, and "
            "update or remove the entry.")
    return reason


@dataclass(frozen=True)
class HadithUnit:
    hadith_no: str
    record_id: str
    is_repeat: bool
    kitab_no: int
    kitab_ar: str
    bab_ar: str | None
    isnad_ar: str | None
    matn_ar: str
    # Further narrations the edition appends after the primary matn. Stored
    # and displayed, never scored and never indexed -- exactly like isnad_ar.
    addenda_ar: str | None
    # Why this unit's matn is not an independently quotable text, or None for
    # the 7,112 that are. Set only from the audited list above. A reason here
    # keeps the record in the corpus and out of the index.
    unscorable_reason: str | None = None


@dataclass(frozen=True)
class ParsedOpeniti:
    units: list[HadithUnit]
    attribution: str
    content_sha256: str
    noisy: list[tuple[str, str]]

    def __len__(self) -> int:
        """The record count fetch_source checks against `expected_records`.

        ParsedTanzil/ParsedTanzilXml define the same thing, so fetch_source
        can count any parsed source the same way instead of branching on
        which parser produced it.
        """
        return len(self.units)


def _clean(s: str) -> str:
    """Strip every structural marker; never touch letters.

    Order matters here: _MILESTONE must run before _PART. 15 occurrences in
    the pinned file look like "\\ 1 ms0007 \\" -- a milestone sitting inside
    a part marker's digits. If _PART ran first, its regex would not match
    across the embedded "ms0007" text, leaving the backslash-digit-backslash
    part marker unstripped once the milestone was removed afterward. A
    reviewer swapped the two lines during a check and the test suite caught
    the leak, so this ordering is load-bearing, not incidental.
    """
    s = _PAGE.sub(" ", s)
    s = _MILESTONE.sub(" ", s)
    s = _PART.sub(" ", s)
    s = _QURAN_MARK.sub(" ", s)
    return " ".join(s.split())


def _strip_heading_markup(s: str) -> str:
    """Drop the wrapping parens and leading printed number from a display
    heading -- "( 2 كتاب الإيمان )" -> "كتاب الإيمان". Cosmetic only: this
    never runs on isnad_ar/matn_ar, which carry the edition's words as-is.
    """
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    return _LEADING_NUMBER.sub("", s)


def parse_openiti(raw: str) -> ParsedOpeniti:
    end = raw.find(_HEADER_END)
    if end == -1:
        raise ValueError("no #META#Header#End# marker: not an OpenITI mARkdown file")
    attribution = raw[: end + len(_HEADER_END)]
    body = raw[end + len(_HEADER_END) :]

    units: list[HadithUnit] = []
    seen: dict[str, int] = {}
    kitab_no, kitab_ar, bab_ar = 0, "", None
    buf: list[str] | None = None

    # A "### ||" bab heading whose wrapping "(" isn't closed on its own line
    # spills the rest of its text onto following "#"-prefixed lines that look
    # exactly like anonymous narration fragments (774 of the file's 3,959 bab
    # headings do this). bab_parts/bab_balance track an in-progress heading
    # until its parens balance, a real numbered hadith starts, or a new
    # "###" section begins -- whichever comes first. The lookahead never
    # crosses into a real hadith: each candidate continuation chunk is
    # tested against _NUMBERED before being absorbed, so an actual narration
    # is never swallowed into a heading no matter how long the heading's
    # unresolved parenthesis run is.
    bab_parts: list[str] | None = None
    bab_balance = 0

    def start_bab(text: str) -> None:
        nonlocal bab_ar, bab_parts, bab_balance
        balance = text.count("(") - text.count(")")
        bab_ar = _strip_heading_markup(_clean(text)) or None
        if balance <= 0:
            bab_parts, bab_balance = None, 0
        else:
            bab_parts, bab_balance = [text], balance

    def flush() -> None:
        nonlocal buf, bab_ar, bab_parts, bab_balance
        if buf is None:
            return
        text, buf = " ".join(buf), None
        m = _NUMBERED.match(text)

        if bab_parts is not None:
            if m is None:
                # Heading continuation, not a narration -- absorb it.
                bab_parts.append(text)
                bab_balance += text.count("(") - text.count(")")
                bab_ar = _strip_heading_markup(_clean(" ".join(bab_parts))) or None
                if bab_balance <= 0:
                    bab_parts, bab_balance = None, 0
                return
            # A real numbered hadith starts here: the heading is done,
            # resolved or not (an unresolved case is a genuine missing
            # paren in the source -- roughly 25 of the 774 -- which no
            # amount of continuation-reading can close).
            bab_parts, bab_balance = None, 0

        if not m:
            return
        number, repeat, rest = m.group(1), bool(m.group(2)), m.group(3)
        rest_clean = _clean(rest)
        if rest_clean.startswith(_BAB_WORD):
            return  # numbered chapter heading, not a narration

        if "*" in rest:
            isnad_raw, matn_raw = rest.split("*", 1)
            isnad, matn = _clean(isnad_raw), _clean(matn_raw)
        else:
            isnad, matn = None, rest_clean
        if not matn:
            # Either the file marks no boundary at all (2795, 6964-6966) or it
            # puts the mark at the very end of the unit, where it separates
            # nothing (218, 1620, 5833). Same fact, same answer: keep
            # everything as matn rather than guessing where a chain ends.
            # Inventing an isnad is worse than admitting the source does not
            # mark one, and storing an empty scored text is worse than both --
            # 5833's matn is right there in the file, in front of the
            # misplaced mark.
            isnad, matn = None, _clean(rest.replace("*", " "))
        # The id is settled before the split, not after: the do-not-cut audit
        # in `_split_secondary` is keyed by record id.
        seen[number] = seen.get(number, 0) + 1
        suffix = "" if seen[number] == 1 else f"-{seen[number]}"
        record_id = f"hadith:bukhari:{number}{suffix}"

        if isnad is None:
            # No source-marked boundary anywhere in this unit, so its leading
            # chain is part of the stored matn. Every narration verb in that
            # chain opens a chain -- that is what a chain is -- and splitting
            # on the first one leaves "haddathana Musaddad" as the scored
            # text. Where the source marks nothing, nothing is cut.
            addenda = None
        else:
            matn, addenda = _split_secondary(matn, record_id)

        units.append(
            HadithUnit(
                hadith_no=number,
                record_id=record_id,
                is_repeat=repeat,
                kitab_no=kitab_no,
                kitab_ar=kitab_ar,
                bab_ar=bab_ar,
                isnad_ar=isnad,
                matn_ar=matn,
                addenda_ar=addenda,
                unscorable_reason=_unscorable_reason(record_id, matn),
            )
        )

    for line in body.splitlines():
        if line.startswith(_CONTINUATION):
            frag = line[len(_CONTINUATION) :]
            if buf is not None:
                buf.append(frag)
            elif bab_parts is not None:
                # A "~~" line can follow the "### ||" line directly, before
                # any "#"-prefixed chunk -- e.g. "( 1 باب ... صدقة الفطر" /
                # "~~فريضة )" is one heading, "فريضة" ("obligatory") being
                # the word that closes it. Dropping this line would lose
                # real words, not just markup.
                bab_parts.append(frag)
                bab_balance += frag.count("(") - frag.count(")")
                bab_ar = _strip_heading_markup(_clean(" ".join(bab_parts))) or None
                if bab_balance <= 0:
                    bab_parts, bab_balance = None, 0
            continue
        if _SECTION.match(line):
            flush()
            if bab_parts is not None:
                # A new section starts before the heading's paren closed --
                # no more continuation text is coming; keep what we have.
                bab_parts, bab_balance = None, 0
            if (k := _KITAB.match(line)) is not None:
                kitab_no += 1
                kitab_ar, bab_ar = _strip_heading_markup(_clean(k.group(1))), None
            elif (b := _BAB.match(line)) is not None:
                start_bab(b.group(1))
            continue
        if _UNIT_START.match(line):
            frag = line[2:]
            if (buf is not None and bab_parts is None
                    and _NUMBERED.match(" ".join(buf))
                    and not _NUMBERED.match(frag)):
                # A "#" line that carries no printed number is a CONTINUATION
                # of the numbered unit already open, not a new one. The
                # edition prints verse on its own "#" line -- "( la 'aysha
                # illa 'aysha l-akhira % ... )" -- and flushing here dropped
                # it on the floor, because the flushed chunk then failed
                # _NUMBERED and was discarded. That silently deleted the
                # entire matn of 3584, 4063 and 6050 and the closing verse of
                # 62 other records. Guarded three ways so no existing
                # behaviour moves: only when a numbered unit is open, only
                # when no bab heading is mid-assembly (that machinery reads
                # its own continuations through flush), and only when the
                # line is not itself a numbered unit.
                buf.append(frag)
                continue
            flush()
            buf = [frag]
            continue
        if line.strip() == "#":
            # A bare "#" closes a run of verse lines. "^#\\s" does not match it,
            # so it fell through to the plain-text branch below and left a
            # literal "#" in 6967's scored text -- flagged by the noise report
            # since the first build, and markup rather than damage.
            continue
        if buf is not None:
            buf.append(line)
    flush()

    noisy = []
    for u in units:
        bad = "".join(sorted({c for c in u.matn_ar if not _ALLOWED.match(c)}))
        if bad:
            noisy.append((u.record_id, bad))

    return ParsedOpeniti(
        units=units,
        attribution=attribution,
        content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        noisy=noisy,
    )
