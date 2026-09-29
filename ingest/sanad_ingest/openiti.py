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

from . import audit_lists

_HEADER_END = "#META#Header#End#"

# Structural markers, all stripped from stored text.
_CONTINUATION = "~~"
_PAGE = re.compile(r"PageV\d+P\d+")

# Tirmidhi-only (Task 13): a second-edition page cross-reference immediately
# after a `PageV\d+P\d+` marker -- "PageV01P162 @ 164", "PageV01P229\n~~232 @
# 233", "PageV02P453 454 @", "PageV01P362 365" (bare, no "@" at all), even
# "PageV01P305 308 ms0064 @ 309" (an embedded milestone between two numbers).
# Measured: exactly 19 occurrences in the whole file, always a small number
# close to the page marker's own, NEVER a quantity in running prose (every
# one sits directly against the page marker with nothing but whitespace/"@"/
# a further milestone between them, several immediately followed by the next
# "### |||" unit boundary). Zero occurrences of this shape follow a page
# marker in Bukhari/Muslim/Abu Dawud's own cached files by the same
# measurement, but the check is scoped to `collection == "tirmidhi"` (see
# its call site in `parse_openiti`) rather than left to that coincidence,
# so the other three collections' byte-identity is never put in the same
# regex's hands. `_PAGE` itself is left untouched -- this runs on the RAW
# body text before any line is read, while the page marker is still the
# anchor, since `_clean()`'s own `_PAGE.sub(" ", s)` erases that anchor and
# leaves no way to tell an apparatus number from a genuine one afterward. A
# stray "~~" continuation prefix can fall in the MIDDLE of the apparatus
# (137's "@\n~~137"), not just between the page marker and it, so the
# optional continuation marker is threaded between every token, not just
# once at the front.
_TIRMIDHI_PAGE_XREF_UNIT = (
    r"[ \t]*(?:\n~~)?[ \t]*(?:ms\d{4}[ \t]*(?:\n~~)?[ \t]*)?@?"
    r"[ \t]*(?:\n~~)?[ \t]*\d{1,4}[ \t]*(?:\n~~)?[ \t]*@?"
)
# "(?!\d)" immediately after the page marker is load-bearing, not decoration:
# without it, `\d+P\d+`'s own greedy match backtracks to satisfy the required
# `{1,2}` repetitions below when a record has NO real apparatus at all --
# e.g. hadith:tirmidhi:30's "... mithlahu PageV01P044\n~~qala Abu 'Isa ..."
# would otherwise have its page marker's own trailing "4" peeled off and
# misread as a one-digit cross-reference, corrupting a record nowhere near
# this phenomenon. The lookahead forces the marker's digits to stay whole,
# so the repetition can only succeed against a SEPARATE, genuine digit run.
#
# The whitespace tokens are "[ \t]*", NOT "\s*": a plain "\s*" can consume a
# bare "\n" that leads into the NEXT unit's own "### |||"/"### ||" line --
# measured against 112, 126 and 231's own headings, none of which carry a
# "~~" continuation prefix -- moving that heading off column zero and making
# `_SECTION.match` blind to it, silently merging two units into one (188,
# 317, 450 cost two whole records this way before the fix). Crossing an
# actual line is only ever done through the explicit "(?:\n~~)?" alternative,
# which requires the "~~" that marks a genuine continuation.
_TIRMIDHI_PAGE_XREF = re.compile(
    rf"(PageV\d+P\d+)(?!\d)(?:{_TIRMIDHI_PAGE_XREF_UNIT}){{1,2}}")
_MILESTONE = re.compile(r"ms\d{4}")
_PART = re.compile(r"\\\s*\d+\s*\\")          # the "\ 1 \" part marker
_QURAN_MARK = re.compile(r"@QB@|@QE@")        # markers go, quoted words stay
_SECTION = re.compile(r"^###")                # ### | , ### || , ### |||
_KITAB = re.compile(r"^###\s*\|(?!\|)\s*(.*)$")
_BAB = re.compile(r"^###\s*\|\|+\s*(.*)$")
# Tirmidhi's file is the ".completed" annotation stage, not the bare "-ara1"
# Bukhari/Muslim/Abu Dawud are built from -- MEASURED to carry a structural
# difference the docs do not mention: the hadith number sits on its OWN
# "### |||" line, with the unit's content following on a separate, unnumbered
# "#" line ("### ||| 815" then "# حدثنا ..."), rather than embedded at the
# head of the content line the way Bukhari/Muslim/Abu Dawud print it ("# 1
# حدثنا ..."). Naively, "### |||" already matches `_BAB` (2-OR-MORE pipes),
# which would misfile every one of the file's 3,976 hadith-number lines as a
# bab heading whose "title" is a bare number.
#
# The two shapes are told apart by CONTENT, not pipe count, so Bukhari's own
# (pre-existing, already-shipped) use of "### |||" for a THIRD-LEVEL bab
# heading -- always wrapped in a Qur'an-quoting parenthesis or opening on
# "باب", e.g. "### ||| ( 2 باب @QB@ ... @QE@ )" -- is untouched: this pattern
# only matches when the trailing content is NOTHING but digits (an optional
# embedded milestone, e.g. "### ||| 16 ms0006"). Measured against the pinned
# files: matches all 3,976 of Tirmidhi's hadith-number lines and, checked
# separately, zero of Bukhari's 363 three-pipe lines (all of which open on
# "(" or a bare number-then-"باب", never a lone number) and zero lines in
# Muslim/Abu Dawud (which never use "###" for hadith numbering at all).
_HADITH_NUM = re.compile(r"^###\s*\|{3,}\s*(\d+)(?:\s+ms\d{4})?\s*$")
_UNIT_START = re.compile(r"^#\s")              # "^#\s" already can't match "###"
_NUMBERED = re.compile(r"^(\d+)\s+(م\s+)?(.*)$", re.DOTALL)
_LEADING_NUMBER = re.compile(r"^\d+\s+")

# A numbered unit whose text begins with "باب" is a chapter heading that the
# edition happens to number, not a narration. Six of them exist in the
# (Bukhari) file. `_KITAB_WORD` is the same idea one level up: Abu Dawud's
# file has exactly one numbered unit that is really a kitab title (Task 12;
# see the comment in `flush()` where it is used).
_BAB_WORD = "باب"
_KITAB_WORD = "كتاب"

# Sahih Muslim's OpenITI file marks EVERY kitab/bab heading with a single
# "#", not Bukhari's "###": measured against the pinned Muslim file, 1,392
# lines start "# | 1" and 0 start "###|"; measured against the pinned
# Bukhari file, the reverse (4,060 "###" lines, 0 "# |" lines beyond the
# file's own "######OpenITI#" marker). "1" is a constant here, not a nesting
# depth -- every one of the 1,392 lines has it, unlike Bukhari's pipe count,
# which is how kitab and bab tell themselves apart there. Before this was
# recognised, `_UNIT_START` matched these lines too (single "#") and
# `_NUMBERED` did not (they start "|", not a digit), so every one fell into
# the "verse inside a numbered unit" continuation guard below and was glued
# onto whichever hadith happened to be open -- 1,353 of Muslim's 7,460 units
# (measured) carried a swallowed heading fragment in their scored matn, and
# kitab_no/kitab_ar/bab_ar stayed at their initial values for the entire
# collection, because a heading line was never once recognised as one.
_HASH_PIPE = re.compile(r"^#\s*\|\s*1\s*(.*)$")

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

# A narrator's name here is one to three tokens -- "Wuhayb", "Abu Mu'awiya",
# "Sa'id ibn Zayd", "Abu Abdullah". Four or more is not a name, it is speech
# that happens to contain "qala".
_MAX_NAME_TOKENS = 3

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
                       allow_particle: bool, attribution_window: int,
                       min_name: int = 1) -> int | None:
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
    if verb_start - start > attribution_window:
        return None
    return start


def _audited_never_cut(record_id: str, matn: str,
                       never_cut: dict[str, tuple[str, str]]) -> bool:
    """Is this record on the hand-read do-not-cut list, for THIS text?

    Same contract as `_unscorable_reason`: the entry records a judgement about
    one specific string, so a matn that no longer hashes to the audited one
    stops the build instead of inheriting the judgement.
    """
    audited = never_cut.get(record_id)
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


def _split_secondary(matn: str, record_id: str, attribution_window: int,
                     max_addendum: int,
                     never_cut: dict[str, tuple[str, str]]
                     ) -> tuple[str, str | None]:
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
    if _audited_never_cut(record_id, matn, never_cut):
        return matn, None
    for verb in _VERB.finditer(matn):
        forward = _opens_a_chain(matn[verb.end():].split())
        # The backward signal on its own still counts: "wa-qala Sa'id ibn
        # Zayd haddathana Abd al-Aziz idha arada an yadkhula" (142) is a
        # one-link chain, so nothing follows the verb to recognise.
        start = _attribution_start(matn, verb.start(), _PLAIN_ATTRIBUTION,
                                   False, attribution_window)
        if forward:
            # A bare "qala" with no name is an attribution here too, because
            # the chain behind the verb already settled the question.
            start = _attribution_start(matn, verb.start(), _ATTRIBUTION,
                                       True, attribution_window,
                                       min_name=0) or start
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
        if len(matn) - cut > max_addendum:
            return matn, None
        # No length floor on what is left behind -- see the note above
        # `_NEVER_CUT`. A short primary is not evidence of a bad cut.
        return matn[:cut].rstrip(), matn[cut:]
    return matn, None


def _apply_cut_override(matn: str, addenda: str | None, record_id: str,
                        cut_override: dict[str, tuple[str, int]]
                        ) -> tuple[str, str | None]:
    """Hand-corrected boundary for a `_split_secondary` cut that left a
    dangling attribution fragment on the primary matn.

    `_attribution_start`'s single-level backward walk sometimes finds an
    INNER "qala <name>" attribution but misses an OUTER one immediately
    preceding it -- nested reported speech ("Zayd said: [Hussein said: Amr
    told me ...]"), where only the inner bracket is recognised and the outer
    "qala Zayd" is left stranded at the end of the primary. A one-hop
    recursive extension of the backward walk was tried and rejected: it
    correctly reattaches the nine records below, but ALSO fires on 454
    ("... wa-qala ightasilu kulla wahid 'ala hida", a genuine wording-variant
    note) and 3988 ("qala 'Uthman al-Ghatafani makan al-Ghatifi", a genuine
    name-correction note) -- both end on a token sequence that is
    structurally identical to a nested attribution but is, on a reading of
    the sentence, complete narrative content in its own right. No heuristic
    tried told the two shapes apart; each of the entries below was read by
    hand instead, against its own addendum, one at a time.

    The value is (sha256-of-the-uncorrected-primary, count-of-trailing-
    tokens-to-move). Moving whole tokens, not a character offset, means the
    fix is expressed as arithmetic on `_split_secondary`'s own output rather
    than as a retyped string -- nothing here is hand-copied Arabic.
    """
    override = cut_override.get(record_id)
    if override is None:
        return matn, addenda
    digest, n_tokens = override
    if hashlib.sha256(matn.encode("utf-8")).hexdigest() != digest:
        raise ValueError(
            f"{record_id} is on the cut-override audit list, but its primary "
            "matn is no longer the text that was audited. The override "
            "corrects a judgement about one specific string; it must not be "
            "carried over to a new one. Read the record and its addendum "
            "again, decide the boundary afresh, and update or remove the "
            "entry.")
    if addenda is None:
        raise ValueError(
            f"{record_id} is on the cut-override audit list, which corrects "
            "a _split_secondary cut, but this record has no addendum to "
            "correct against.")
    tokens = matn.split()
    if n_tokens < 1 or n_tokens >= len(tokens):
        raise ValueError(
            f"{record_id}'s cut-override would move {n_tokens} of "
            f"{len(tokens)} primary tokens -- not a boundary correction.")
    moved = " ".join(tokens[-n_tokens:])
    return " ".join(tokens[:-n_tokens]), f"{moved} {addenda}"


# --- Abu Dawud's own compiler commentary ------------------------------------
#
# Abu Dawud al-Sijistani appends his own remarks directly after a hadith's
# matn -- "qala Abu Dawud ..." ("Abu Dawud said: ..."), "su'ila Abu Dawud
# ..." ("Abu Dawud was asked: ...") -- with NO structural marker separating
# it from the narration, unlike a secondary narration's fresh isnad. Measured
# against the pinned file: 806 matns carry the marker (qala|su'ila, with an
# optional wa-/fa- proclitic, immediately in front of "Abu Dawud"), 793 of
# them with no addendum at all -- the commentary simply fused into the scored
# matn. Quoting the genuine narration alone then falls below the verification
# threshold, because the stored text is narration-plus-commentary, not the
# narration.
#
# Scoped to the abudawud collection ONLY: Bukhari and Muslim's editions were
# built and audited without this marker (Task 16 measures and fixes their
# own, lower-rate instances of the same phenomenon separately), and this
# function is never called for them.
#
# No NEVER_CUT exceptions were needed. The one narrator who is himself named
# "Abu Dawud" (al-Tayalisi) appears in this file as "haddathana/thana Abu
# Dawud", never as "qala/su'ila Abu Dawud" -- checked by requiring the verb
# immediately precede the name, and independently confirmed: the file's one
# "qala Abu Dawud" inside a chain (401) sits in the isnad half of the unit,
# before the "*" split, and never reaches matn at all. The one instance where
# the marker is immediately followed by a narration verb (228, "qala Abu
# Dawud: thana al-Hasan ibn Ali al-Wasiti") was read in context: it is still
# the compiler, in his own voice, introducing a further route -- a routine
# move in his commentary -- not a narrator link.
# R-A3-23 (Task 12 fix round 3): the marker above only ever recognised the
# compiler's kunya in the NOMINATIVE ("Abu Dawud" as grammatical subject of
# "qala"/"su'ila"). An independent adversarial re-review found two further
# records where the compiler is quoted in the ACCUSATIVE instead -- "sami'tu
# ABA Dawud yaqulu ..." ("I heard Abu Dawud say ...", he is the object of
# "I heard", not the subject of "he said") -- which no nominative-only marker
# could ever match. Measuring all three grammatical cases of "Abu Dawud"
# against the pinned file (and, for the controller's own cross-check, of
# "Abu 'Isa"/al-Tirmidhi, "Abu 'Abd al-Rahman"/al-Nasa'i, and "Abu
# al-Hasan"/Ibn Majah -- Tasks 13-15's own compiler kunyas, out of scope to
# fix here but sharing the exact same grammar) gives one completely regular
# rule, not three collections' worth of ad-hoc name strings:
#
#   - "qala"/"su'ila" + NOMINATIVE kunya (he is the subject) -- the compiler
#     speaking in his own voice -- IS commentary, and is cut.
#   - "sami'tu" + ... + ACCUSATIVE kunya (he is the object of "I heard") --
#     someone else reporting having heard the compiler say something -- is
#     STILL commentary (the fused text is editorial apparatus either way),
#     and is cut.
#   - "'an"/"min" + GENITIVE kunya -- he is named as a narrator INSIDE an
#     isnad, not as the compiler speaking -- must NEVER be cut. Confirmed by
#     reading every genitive occurrence in the file: two are the `#META#`
#     book title ("Sunan Abi Dawud"), outside any unit entirely, and the one
#     inside a unit (record 507, "... 'an Abi Dawud ...") sits in `isnad_ar`
#     itself, before the "*" split -- isnad text is never scored in the
#     first place, so there is nothing to guard here beyond not inventing a
#     genitive pattern that would reach in and cut it. This is exactly why a
#     case-blind widening of the marker would be actively dangerous: nothing
#     about the SHAPE of "<preposition> + kunya" tells qala/su'ila's subject
#     apart from an isnad's own narrator reference except the case ending.
#
# `_kunya_case_forms`/`_compiler_commentary_markers` build all three
# collections' markers from this one rule and their own nominative kunya
# (Arabic's "five nouns", الأسماء الخمسة, decline "abu" the same way no
# matter what follows it: nominative "أبو", accusative "أبا", genitive
# "أبي"), so Tasks 13-15 read this table once and derive a correct marker
# from their own kunya, instead of each hand-writing a regex and inheriting
# a fresh case-blind blind spot the way this one did.


def _kunya_case_forms(nominative: str) -> tuple[str, str, str]:
    """(nominative, accusative, genitive) forms of a kunya-headed compiler
    name, e.g. "أبو داود" -> ("أبو داود", "أبا داود", "أبي داود")."""
    assert nominative.startswith("أبو "), nominative
    rest = nominative[len("أبو ") :]
    return nominative, f"أبا {rest}", f"أبي {rest}"


def _compiler_commentary_markers(
    kunya_nom: str,
) -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    """(tight, near-fallback, heard) marker set for one collection's kunya.

    `tight`/`near` cover "qala"/"su'ila" + NOMINATIVE, `near` tolerating one
    intervening token (R-A3-22) as a FALLBACK only, tried when `tight` finds
    no match anywhere in the matn -- never a replacement for it or an
    alternation joined into one pattern. Records 1741/3596 both read "...
    qala QALA Abu Dawud ..." (an outer, plain reported-speech "qala"
    immediately followed by the genuine marker's own inner "qala"); a single
    widened regex used as the primary search would let `re.search`'s
    leftmost-match rule jump to the OUTER "qala" instead (satisfying a
    one-token gap by treating the inner "qala" as the filler token) and pull
    an extra genuine word out of the narration -- an over-cut. `tight` alone
    already finds the correct, inner occurrence in both, so trying it first
    and only falling back when it finds nothing keeps those two records
    byte-for-byte unchanged.

    `heard` covers "sami'tu" + ACCUSATIVE, tight (no gap tolerance): every
    measured occurrence in the pinned Abu Dawud file has the kunya
    immediately after "sami'tu", so there is no correctness reason to widen
    it, per the same "read what each additional match actually is, don't
    blanket-widen" discipline as `near`.

    No genitive pattern exists here, deliberately: see the comment above.
    """
    nom, acc, _gen = _kunya_case_forms(kunya_nom)
    tight = re.compile(rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل)\s+{nom}(?![{_ARABIC}])")
    near = re.compile(
        rf"(?<![{_ARABIC}])[وف]?(?:قال|سئل)\s+\S+\s+{nom}(?![{_ARABIC}])")
    heard = re.compile(rf"(?<![{_ARABIC}])[وف]?سمعت\s+{acc}(?![{_ARABIC}])")
    return tight, near, heard


_ABUDAWUD_COMMENTARY, _ABUDAWUD_COMMENTARY_NEAR, _ABUDAWUD_HEARD = \
    _compiler_commentary_markers("أبو داود")

# Known ceiling (R-A3-23, deliberately not fixed here): a bare "qultu" ("I
# said") self-reference compiler remark -- one that never names "Abu Dawud"
# at all -- is structurally invisible to any name-based marker, this table
# included. Left as-is on the coordinator's explicit instruction; pinned to
# Task 16's corpus-wide sweep, which is where a construction not anchored on
# a name belongs.

# --- Tirmidhi's own compiler commentary (Task 13, ruling R-A3-19) ----------
#
# Al-Tirmidhi (kunya "أبو عيسى") appends his own voice after a matn at ROUGHLY
# FOUR TIMES Abu Dawud's rate -- "قال أبو عيسى" measured 3,064 times across
# the file's 3,976 units (Abu Dawud's whole marker set: 806). The verb+kunya
# construction is exactly the one `_compiler_commentary_markers` already
# builds, so `_TIRMIDHI_COMMENTARY`/`_TIRMIDHI_COMMENTARY_NEAR`/
# `_TIRMIDHI_HEARD` are DERIVED from it -- kunya "أبو عيسى" -- not hand-written.
# The genitive form ("أبي عيسى") -- the case `_compiler_commentary_markers`
# deliberately builds no pattern for -- occurs 0 times in this file (measured
# directly against the raw text), so there is not even a live narrator
# reference for that absence to matter for here, unlike Abu Dawud's file.
#
# Two further formulas are Tirmidhi's OWN, not Abu Dawud's, and are NOT of the
# (verb, kunya) shape at all, so no amount of widening the table above could
# ever reach them:
#
#   - "وفي الباب عن ..." ("and on this topic, [there are hadith] from ...") --
#     Abu Isa's own cross-reference formula, closing almost every bab with a
#     list of other Companions who narrate on the same topic. Measured against
#     every one of its 1,178 unit-level occurrences: 1,177 are followed
#     immediately by "عن" (a name list) and the 1,178th ("وفي الباب ما يقوى
#     قولهم") is still Abu Isa's own discussion, not narration -- there is no
#     occurrence anywhere in the file of "الباب" ("the door/chapter") used in
#     its literal, narrative sense directly after "وفي". It OFTEN precedes
#     "قال أبو عيسى" in the same tail (733 of 1,178 units measured), so cutting
#     only at the kunya marker would leave this formula, and everything after
#     it, inside the scored matn -- exactly the failure mode the ruling warns
#     against.
#   - "هذا حديث ..." ("this hadith is ...") -- opens Abu Isa's classical
#     grading verdict (R-A3-2's "حسن صحيح غريب" tails). Measured: of 2,711
#     unit-level occurrences, the very next word is a closed set of 24 grading
#     terms (حسن 2,128, غريب 363, صحيح 102, لا/ليس/مرسل/ضعيف/منكر/... the rest)
#     -- never an ordinary narrative word -- so the phrase is safe to treat as
#     its own unconditional boundary, not merely a fallback for when the kunya
#     marker is absent. 431 of the 2,711 have no earlier "قال أبو عيسى"/
#     "وفي الباب" in the same unit at all.
#   - "وفي الحديث قصة[ طويلة]" ("and in the hadith there is a [long] story") --
#     Abu Isa's own note that the printed matn is an abridgement of a longer
#     narration. Measured 18 unit-level occurrences, ALL at the tail of the
#     unit, ALL following either genuine narrative matn (e.g. 1408, 1636,
#     1904, 3716) or an already-pointer-class remainder (836, 1599); never
#     mid-narrative. Distinguished from the unrelated, non-cutting phrase
#     "فذكر القصة في الحديث" (2667, "and he mentioned the story in the
#     hadith", different word order, appears mid-sentence describing an
#     action, not an aside about the text itself) by anchoring on the exact
#     "وفي الحديث قصة" order.
#   - "وهذا أصح[ من حديث ...]" ("and this [report/chain] is more accurate
#     [than the hadith of ...]") -- a bare isnad-comparison verdict, never
#     part of the Prophet's own reported speech. Measured 18 unit-level
#     occurrences; most already sit inside an already-pointer-class
#     remainder ("نحوه ... وهذا أصح"), harmless either way, but two (1771
#     "he forbade predator hides", 1778 "she walked with one sandal") follow
#     GENUINE narrative matn with no other marker present -- exactly the
#     fused-commentary defect this ruling exists to close, caught only
#     because this phrase was measured on its own rather than assumed to
#     appear solely inside the pointer combinations that motivated finding
#     it. Never mid-narrative in any of the 18.
#
# Both formulas are regularly introduced by a BARE "قال" with no kunya
# repeated -- an elliptical continuation ("قال وفي الباب ...", "قال هذا حديث
# ...", "قال وهذا حديث ...") referring back to the Abu Isa already named
# earlier in the same tail, or standing with no "قال" at all directly after
# the matn ends (asyndeton; e.g. "... فهو عاهر هذا حديث حسن صحيح"). Measured:
# of the 431 "هذا حديث" occurrences with no earlier kunya marker, 336 are
# introduced by this bare "قال" and 95 are asyndetic. `_TIRMIDHI_FORMULA`
# therefore makes the "قال" OPTIONAL AND PART OF THE SAME MATCH: when present,
# the match (and so the cut point) starts AT "قال", not at the formula word,
# so the bare attribution is carried into addenda with its formula rather than
# left dangling on the primary -- the same "cut on what follows" discipline as
# every other marker in this file, applied here to an attribution word instead
# of a name.
_TIRMIDHI_FORMULA = re.compile(
    rf"(?<![{_ARABIC}])(?:قال\s+)?"
    rf"(?:وفي\s+الباب|[وف]?هذا\s+حديث|وفي\s+الحديث\s+قصة(?:\s+طويلة)?|"
    rf"وهذا\s+أصح)"
    rf"(?![{_ARABIC}])")

_TIRMIDHI_COMMENTARY, _TIRMIDHI_COMMENTARY_NEAR, _TIRMIDHI_HEARD = \
    _compiler_commentary_markers("أبو عيسى")

# Reference-number apparatus unique to this file, e.g. "... زرتك [1053]" --
# measured 1,588 raw occurrences, ALL of shape "[<digits>]", never any other
# bracketed content, and never appearing in Bukhari/Muslim/Abu Dawud's own
# cached files (0 occurrences in each). This is Shakir's own cross-reference
# footnote number (the bracketed digit is close to, but rarely exactly, the
# unit's own printed hadith number -- e.g. hadith 48 ends "... [47]" -- ruling
# out a simple "matches its own number" explanation), not part of the
# classical text and not itself explanatory prose worth preserving in
# `addenda_ar` the way genuine commentary is -- a bare number in brackets
# means nothing to a reader without Shakir's own footnote text, which this
# transcription does not carry. Treated as structural apparatus and stripped,
# the same disposition as a milestone or page marker, NOT folded into
# `_clean()` (see `_strip_reference_numbers`'s own docstring for why the
# timing matters).
_TIRMIDHI_REF_NUMBER = re.compile(r"\[\d+\]")


def _strip_reference_numbers(matn: str) -> str:
    """Remove Tirmidhi's own bracketed cross-reference numbers from a
    (post-split) PRIMARY matn -- never from `addenda_ar`, and never before the
    unit's own empty-matn fallback check in `flush()` has already run.

    Ordering is load-bearing: `hadith:tirmidhi:162`'s matn, after the
    generic "*" split, is the bare four characters "[161]" -- a genuine
    editorial pointer ("see hadith 161"), not damage. If bracket-stripping
    ran inside `_clean()` (i.e. before `flush()`'s own `if not matn:` check),
    162's matn would go from a non-empty string to an empty one at exactly
    the point that check is testing, and its fallback branch -- built for a
    different case entirely, "the source marks no boundary at all" -- would
    then substitute the record's own ISNAD as its matn. Running this step
    afterward, on the already-resolved matn, means 162 instead reaches this
    function with matn="[161]".

    NEVER RETURNS EMPTY: `build._hadith_records` treats an empty `text_ar` as
    an unconditional hard error regardless of `unscorable_reason` -- it is a
    guard against a DIFFERENT hazard (a parsing regression silently shipping
    a blank scored string) and does not know this stripping step exists. A
    record whose entire matn is nothing but a bracket -- 162 and 3615-2, both
    measured -- keeps its bracket, exactly like Bukhari's own bare "bi-hadha"
    pointer keeps its four characters: the text is still apparatus, not
    prose, and is still hand-pinned in `UNSCORABLE["tirmidhi"]`, but it is
    the UNSTRIPPED bracket that gets pinned, not an empty string.

    Only the PRIMARY matn is stripped, not `addenda_ar`: the two records
    where this number already sits inside `_TIRMIDHI_COMMENTARY`'s own cut
    tail (1204, 2824-2, both measured) keep their bracket, byte-exact, as
    part of the preserved commentary -- exactly like every other character
    `_split_compiler_commentary` moves into addenda.
    """
    stripped = " ".join(_TIRMIDHI_REF_NUMBER.sub(" ", matn).split())
    return stripped if stripped else matn


_COMPILER_MARKERS: dict[
    str, tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str],
               re.Pattern[str] | None]
] = {
    # Byte-identical to the pre-Task-13 tuple used at Abu Dawud's own call
    # site: same three patterns, same objects, no fourth (non-kunya) formula.
    "abudawud": (_ABUDAWUD_COMMENTARY, _ABUDAWUD_COMMENTARY_NEAR,
                 _ABUDAWUD_HEARD, None),
    "tirmidhi": (_TIRMIDHI_COMMENTARY, _TIRMIDHI_COMMENTARY_NEAR,
                 _TIRMIDHI_HEARD, _TIRMIDHI_FORMULA),
}


def _split_compiler_commentary(
    matn: str, addenda: str | None, tight: re.Pattern[str],
    near: re.Pattern[str], extra: re.Pattern[str] | None = None,
) -> tuple[str, str | None]:
    """Cut a collection's own compiler commentary from a matn, appending it
    to whatever addendum `_split_secondary` already found (or starting one).

    `tight`/`near` are the (verb, kunya) pair `_compiler_commentary_markers`
    built for this collection; `extra`, when given, is a further,
    collection-specific formula that marks the SAME kind of boundary without
    naming the compiler at all (Tirmidhi's "وفي الباب"/"هذا حديث" -- see
    `_TIRMIDHI_FORMULA`). Between `tight` and `extra` the EARLIEST match wins,
    per the ruling's instruction to cut at the earliest genuine boundary, not
    merely the first one a single pattern happens to find; `near` is tried
    only as a fallback when NEITHER of those finds anything, preserving the
    "tight first, widen only if the tight search truly finds nothing"
    discipline `near` was built for.

    Cuts on what FOLLOWS the marker, not what precedes it -- the compiler's
    remark is itself the secondary material, exactly as a fresh narration's
    isnad is. Never invents a cut: if no marker is present, the matn and
    addendum returned are the ones passed in, unchanged.
    """
    candidates = [m for m in (tight.search(matn),
                               extra.search(matn) if extra else None)
                  if m is not None]
    m = min(candidates, key=lambda m: m.start()) if candidates else None
    if m is None:
        m = near.search(matn)
    if m is None:
        return matn, addenda
    head = matn[: m.start()].rstrip()
    if not head:
        # Measured: no record's matn opens directly on the marker (every one
        # of the 806 Abu Dawud instances, and every Tirmidhi one, has genuine
        # narrative in front of it). Guarded anyway, on the same principle as
        # _split_secondary's one-word guard: an empty scored text is worse
        # than the fused-commentary bug this function exists to fix.
        return matn, addenda
    tail = matn[m.start() :]
    return head, tail if addenda is None else f"{tail} {addenda}"


def _split_heard_commentary(matn: str, addenda: str | None,
                            heard: re.Pattern[str]
                            ) -> tuple[str, str | None]:
    """Cut the "sami'tu ... ACCUSATIVE-kunya" shape of a collection's own
    commentary (R-A3-23) -- someone reporting having heard the compiler say
    something, which is still editorial apparatus fused onto the matn, not
    narration. `heard` is the collection's own marker from
    `_compiler_commentary_markers`.

    Run AFTER `_split_lului_commentary` in `flush()` (Abu Dawud only), not
    before: of Abu Dawud's 8 accusative occurrences, 6 are immediately
    preceded by "qala Abu Ali" ("... qala Abu Ali sami'tu Aba Dawud yaqulu
    ...") and are already cut, correctly, at that EARLIER position by
    `_split_lului_commentary`'s own marker before this function ever runs --
    running this one first would instead cut at the later "sami'tu" and
    leave "qala Abu Ali" stranded on the primary, the exact dangling-
    attribution defect `CUT_OVERRIDE` exists to fix elsewhere. By the time
    this function's search runs, those 6 already have "sami'tu ..." inside
    their addendum, so it is a no-op for them, not a second cut.

    Abu Dawud's remaining 2 (1234, 1854) have no earlier marker at all and are
    cut here directly. 1854's cut is complete on its own. 1234's is not:
    "qala Uthman 'an 'Abd Allah ibn Muhammad ibn 'Amr ibn 'Ali sami'tu Aba
    Dawud yaqulu ..." leaves "qala Uthman 'an ... 'Ali" dangling on the
    primary the same way 4129 did in fix round 2 -- corrected the same way,
    by a second hand-audited entry in `NEAR_MISS_CUT_OVERRIDE`, applied after
    this function returns. Tirmidhi's own accusative form ("أبا عيسى") occurs
    exactly once in the file (measured) and is not reached by this function
    at all -- see the near-miss detector's own findings.
    """
    m = heard.search(matn)
    if m is None:
        return matn, addenda
    head = matn[: m.start()].rstrip()
    if not head:
        return matn, addenda
    tail = matn[m.start() :]
    return head, tail if addenda is None else f"{tail} {addenda}"


# --- Abu Ali al-Lu'lu'i's own voice (Task 12 fix round 2, ruling R-A3-22) ---
#
# The same defect class -- post-matn editorial prose fused into the scored
# matn, with no structural marker -- but a different speaker: Abu Ali
# al-Lu'lu'i, the primary transmitter of Abu Dawud's own Sunan, remarking
# about Abu Dawud or about an isnad. "qala Abu Ali" occurs 10 times in the
# file (read individually, not sampled):
#
#   - 7 are a plain post-matn remark with nothing genuine trailing it --
#     911, 1096, 1391, 3220, 3437, 4924, 5190 -- correctly cut by the same
#     mechanism as the compiler's own commentary.
#   - 2 already sit entirely inside an addendum some earlier cut produced
#     (3040, inside `_split_compiler_commentary`'s own tail; 5113, inside
#     `_split_secondary`'s), so this function's search over `matn` is
#     already a no-op for them -- nothing further to do.
#   - 1, hadith:abudawud:4068, is the one genuine exception, on
#     `audit_lists.LULUI_NEVER_CUT`: "qala Abu Ali al-Lu'lu'i arahu wa-'alayya
#     thawb..." sits IN THE MIDDLE of a single narration ("the Messenger of
#     Allah saw me ..."), not after it -- Abu Ali is glossing an uncertain
#     detail mid-narration, and the narration's own punchline ("why didn't
#     you give it to your family instead?") depends on the clause a naive cut
#     would discard into addenda. Read by hand; excluded, not patched around.
#
# 911's own duplicate, 894, is byte-identical apart from carrying no such
# remark -- confirming this is the same fused-commentary shape, not
# narration.
_ABUDAWUD_LULUI = re.compile(
    rf"(?<![{_ARABIC}])[وف]?قال\s+أبو\s+علي(?![{_ARABIC}])")


def _split_lului_commentary(matn: str, addenda: str | None, record_id: str,
                            never_cut: dict[str, tuple[str, str]]
                            ) -> tuple[str, str | None]:
    """Cut Abu Ali al-Lu'lu'i's own remark from a matn, same shape as
    `_split_compiler_commentary` but for a different speaker's voice, and
    honouring a dedicated do-not-cut audit list (see `_ABUDAWUD_LULUI` above)
    for the one record where the marker sits inside the narration, not after
    it.
    """
    if _audited_never_cut(record_id, matn, never_cut):
        return matn, addenda
    m = _ABUDAWUD_LULUI.search(matn)
    if m is None:
        return matn, addenda
    head = matn[: m.start()].rstrip()
    if not head:
        return matn, addenda
    tail = matn[m.start() :]
    return head, tail if addenda is None else f"{tail} {addenda}"


def full_text_from_parts(matn_ar: str, addenda_ar: str | None) -> str:
    """The string-level join `full_text` delegates to.

    Exists separately from `full_text` so that `sanad_ingest.materialize` --
    which works from DB columns, not `HadithUnit` objects, because a
    source-only DB carries no units -- can rejoin a record's primary matn and
    addendum without reconstructing a `HadithUnit` just to read two fields
    off it.
    """
    if addenda_ar is None:
        return matn_ar
    return f"{matn_ar} {addenda_ar}"


def full_text(unit: HadithUnit) -> str:
    """The unit's matn as the edition prints it: primary plus every addendum.

    The one place the two halves of a cut are rejoined, so the build and the
    reassembly test cannot disagree about the join. The single space is the
    one `_split_secondary` removed with `rstrip()`; `_clean` has already
    collapsed every whitespace run in the unit to exactly one space, so this
    restores the source byte for byte. `test_nothing_is_lost_when_an_addendum_
    is_cut_away` proves that against the raw file, not against the parser.
    """
    return full_text_from_parts(unit.matn_ar, unit.addenda_ar)


def find_near_misses(units: list["HadithUnit"], configured: re.Pattern[str],
                     sweep: re.Pattern[str]) -> list[str]:
    """Record ids whose printed text (matn and addendum rejoined, so a marker
    already cut into an addendum by an unrelated mechanism still counts) is
    matched by `sweep` but not by `configured`.

    Not a fix -- a reusable AUDIT, exactly like `NEVER_CUT`/`UNSCORABLE`/
    `CUT_OVERRIDE`: it never changes what gets cut, only surfaces candidates
    a human has not yet read. `configured` is whatever the collection's
    shipped marker actually matches today (a single pattern, or several
    joined with `|`); `sweep` is a DELIBERATELY widened variant of the same
    marker, used only for this audit, never for the real split.

    Task 12 fix round 1 shipped `_ABUDAWUD_COMMENTARY` (R-A3-18) without this
    check and missed two records where the marker needed one more token of
    slack (R-A3-22, `hadith:abudawud:4129`/`5239`) -- found by an outside
    review, not by the build. Running this per collection, per marker,
    whenever a marker is added or widened is how that class of miss gets
    caught before shipping instead of after: R-A3-22 also used it to find
    `hadith:abudawud:2237` for the `_ABUDAWUD_LULUI` marker, a narrator's
    kunya ("Abu Ali al-Hanafi") that must NOT be cut, proving the audit finds
    both shapes -- a genuine gap and a correct exclusion -- and leaves the
    judgement to the person reading the result, not to the sweep itself.

    Every call site should assert against a PINNED list of already-read
    record ids (see `tests/ingest/test_real_corpus.py`), not merely that the
    result is empty: a collection like Abu Ali's narrator name can have a
    permanent, audited non-empty result, and a silently-added new entry is
    exactly the thing this function exists to catch.
    """
    hits = []
    for u in units:
        text = full_text_from_parts(u.matn_ar, u.addenda_ar)
        if configured.search(text) is None and sweep.search(text) is not None:
            hits.append(u.record_id)
    return sorted(hits)


def _unscorable_reason(record_id: str, matn: str,
                       unscorable: dict[str, tuple[str, str]]) -> str | None:
    audited = unscorable.get(record_id)
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


def _unwrap_parens(s: str) -> str:
    """Drop exactly one layer of wrapping parens, nothing else -- used only
    for the "# | 1 ( ... )" lines `_heading_kind` rules are NOT a heading
    (see its docstring). Unlike `_strip_heading_markup`, this never strips a
    leading number: none of the measured non-heading cases carry one, and a
    genuine one (e.g. a narrated quantity) would be matn, not markup."""
    s = s.strip()
    if s.startswith("("):
        s = s[1:]
    if s.endswith(")"):
        s = s[:-1]
    return s.strip()


def _heading_kind(cleaned_content: str) -> str | None:
    """"kitab", "bab", or None if a Muslim "# | 1 ( ... )" line's content is
    not a heading at all.

    The SAME wrapper marks 1,368 kitab/bab headings and 24 lines that are
    not headings -- a narrator's aside ("qala fa-atamma lahu rasulu llahi ...
    mi'a", "he said: the Messenger of God completed it for him to a
    hundred") or a Qur'an citation ("fa-nazalat hadhihi l-aya ...") that
    continues the narration already open. The wrapper cannot tell the two
    apart -- both are "( ... )", sometimes with a leading number -- but the
    first word inside it can: every one of the 1,368 opens on "kitab" (54)
    or "bab" (1,314), and every one of the other 24 opens on ordinary prose.
    `cleaned_content` must already be `_clean`-ed, so an embedded milestone
    between the wrapper and the heading word (measured: four cases) is
    already gone. Only the OPENING side is inspected -- not "is this
    balanced" -- so a heading that spans a "~~" continuation before its
    closing paren arrives still classifies correctly from its first line.
    """
    s = cleaned_content.strip()
    if s.startswith("("):
        s = s[1:].lstrip()
    s = _LEADING_NUMBER.sub("", s, count=1)
    if s.startswith(_KITAB_WORD):
        return "kitab"
    if s.startswith(_BAB_WORD):
        return "bab"
    return None


def parse_openiti(
    raw: str,
    *,
    collection: str = "bukhari",
    max_addendum: int = audit_lists.MAX_ADDENDUM,
    attribution_window: int = audit_lists.ATTRIBUTION_WINDOW,
    never_cut: dict[str, tuple[str, str]] | None = None,
    unscorable: dict[str, tuple[str, str]] | None = None,
    cut_override: dict[str, tuple[str, int]] | None = None,
    lului_never_cut: dict[str, tuple[str, str]] | None = None,
    near_miss_cut_override: dict[str, tuple[str, int]] | None = None,
) -> ParsedOpeniti:
    # None-then-resolve rather than a mutable dict default, and resolved
    # against `collection`: NEVER_CUT/UNSCORABLE are keyed by collection, so
    # Bukhari (whose collection is "bukhari") gets exactly the dict it always
    # got. A future collection with no audit list yet gets an empty dict
    # instead of silently inheriting Bukhari's entries -- lookups are keyed
    # by the full record id, so an unrelated collection's ids would simply
    # never match an inherited Bukhari list, but an empty dict says so
    # honestly rather than by accident.
    if never_cut is None:
        never_cut = audit_lists.NEVER_CUT.get(collection, {})
    if unscorable is None:
        unscorable = audit_lists.UNSCORABLE.get(collection, {})
    if cut_override is None:
        cut_override = audit_lists.CUT_OVERRIDE.get(collection, {})
    if lului_never_cut is None:
        lului_never_cut = audit_lists.LULUI_NEVER_CUT.get(collection, {})
    if near_miss_cut_override is None:
        near_miss_cut_override = audit_lists.NEAR_MISS_CUT_OVERRIDE.get(
            collection, {})

    end = raw.find(_HEADER_END)
    if end == -1:
        raise ValueError("no #META#Header#End# marker: not an OpenITI mARkdown file")
    attribution = raw[: end + len(_HEADER_END)]
    body = raw[end + len(_HEADER_END) :]
    if collection == "tirmidhi":
        # See `_TIRMIDHI_PAGE_XREF`'s own comment: must run before any line
        # is read, while `PageV\d+P\d+` is still present to anchor on.
        body = _TIRMIDHI_PAGE_XREF.sub(r"\1", body)

    units: list[HadithUnit] = []
    seen: dict[str, int] = {}
    kitab_no, kitab_ar, bab_ar = 0, "", None
    buf: list[str] | None = None
    # Set by `_HADITH_NUM` (Tirmidhi's ".completed" stage only -- see its own
    # comment) and consumed by the very next `_UNIT_START` line, which is
    # ALWAYS the next line in the file (measured: all 3,976 occurrences).
    # Prepending it there reproduces the exact shape `_NUMBERED` expects from
    # Bukhari/Muslim/Abu Dawud's single-line "<number> [م] <text>" convention,
    # so the rest of `flush()` -- including the repeat-marker "م" the second
    # printing of a repeated number carries on ITS OWN content line here, e.g.
    # "### ||| 815 ms0293" / "# م حدثنا ..." -- needs no further change.
    pending_number: str | None = None

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
    #
    # heading_kind tracks WHICH of kitab_ar/bab_ar an in-progress bab_parts
    # span is updating. It exists for Muslim's sake (see `_HASH_PIPE` below):
    # Bukhari's "###" marker tells kitab and bab apart by pipe count before
    # start_heading is ever called, so for Bukhari heading_kind is always
    # "bab" the moment bab_parts is non-None -- a kitab heading there is
    # still handled inline, without continuation tracking, exactly as before.
    bab_parts: list[str] | None = None
    bab_balance = 0
    heading_kind: str | None = None

    def start_heading(kind: str, text: str) -> None:
        nonlocal kitab_no, kitab_ar, bab_ar, bab_parts, bab_balance, heading_kind
        heading_kind = kind
        value = _strip_heading_markup(_clean(text)) or None
        if kind == "kitab":
            kitab_no += 1
            kitab_ar, bab_ar = value, None
        else:
            bab_ar = value
        balance = text.count("(") - text.count(")")
        if balance <= 0:
            bab_parts, bab_balance, heading_kind = None, 0, None
        else:
            bab_parts, bab_balance = [text], balance

    def absorb_heading(chunk: str) -> None:
        """Add a continuation chunk to the in-progress bab_parts span and
        recompute whichever of kitab_ar/bab_ar it is heading_kind says it is.
        Shared by the "~~"-continuation path and flush()'s "#"-prefixed one,
        so the two cannot drift into recomputing the wrong field."""
        nonlocal kitab_ar, bab_ar, bab_parts, bab_balance, heading_kind
        bab_parts.append(chunk)
        bab_balance += chunk.count("(") - chunk.count(")")
        value = _strip_heading_markup(_clean(" ".join(bab_parts))) or None
        if heading_kind == "kitab":
            kitab_ar = value
        else:
            bab_ar = value
        if bab_balance <= 0:
            bab_parts, bab_balance, heading_kind = None, 0, None

    def flush() -> None:
        nonlocal buf, bab_parts, bab_balance, heading_kind, kitab_no, kitab_ar, bab_ar
        if buf is None:
            return
        text, buf = " ".join(buf), None
        m = _NUMBERED.match(text)

        if bab_parts is not None:
            if m is None:
                # Heading continuation, not a narration -- absorb it.
                absorb_heading(text)
                return
            # A real numbered hadith starts here: the heading is done,
            # resolved or not (an unresolved case is a genuine missing
            # paren in the source -- roughly 25 of the 774 -- which no
            # amount of continuation-reading can close).
            bab_parts, bab_balance, heading_kind = None, 0, None

        if not m:
            return
        number, repeat, rest = m.group(1), bool(m.group(2)), m.group(3)
        rest_clean = _clean(rest)
        if rest_clean.startswith(_KITAB_WORD):
            # A numbered unit whose entire text is a kitab title, not a
            # narration. Every OTHER kitab heading in every pinned file
            # arrives wrapped in the "### |" (Bukhari) or "# | 1 ( ... )"
            # (Muslim/Abu Dawud) envelope, both handled elsewhere; this
            # branch exists because Abu Dawud's OWN FIRST kitab heading --
            # "# 1 كتاب الطهارة" -- carries no such wrapper, so `_NUMBERED`
            # matches it exactly like an ordinary numbered hadith. Left
            # unhandled, this mints a fabricated "hadith:abudawud:1" whose
            # entire matn is "كتاب الطهارة" ("The Book of Purification"),
            # and bumps the real first hadith to a false "-2" occurrence
            # suffix, as if it were a repeat of a hadith that never existed.
            # Measured against every pinned file: `^# \d+(\s+م)?\s+كتاب`
            # matches exactly once, in Abu Dawud's file, and zero times in
            # Bukhari's or Muslim's -- this branch is inert for both already-
            # shipped collections.
            kitab_no += 1
            kitab_ar, bab_ar = rest_clean, None
            return
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
        record_id = f"hadith:{collection}:{number}{suffix}"

        if isnad is None:
            # No source-marked boundary anywhere in this unit, so its leading
            # chain is part of the stored matn. Every narration verb in that
            # chain opens a chain -- that is what a chain is -- and splitting
            # on the first one leaves "haddathana Musaddad" as the scored
            # text. Where the source marks nothing, nothing is cut.
            addenda = None
        else:
            matn, addenda = _split_secondary(
                matn, record_id, attribution_window, max_addendum, never_cut)
        # Unconditional, even when isnad is None (Abu Dawud 208): the
        # compiler's remark can follow a matn whose own leading chain the
        # source never marked a boundary for either. `_apply_cut_override`
        # is a no-op when `record_id` is not on its (per-collection, keyed by
        # the full record id) audit list, so calling it for every collection
        # -- rather than gating it to "abudawud" -- changes nothing for
        # bukhari/muslim (whose `CUT_OVERRIDE` entries, if any, simply never
        # match a different collection's ids) and lets Tirmidhi reuse it too.
        matn, addenda = _apply_cut_override(
            matn, addenda, record_id, cut_override)
        markers = _COMPILER_MARKERS.get(collection)
        if markers is not None:
            tight, near, heard, extra = markers
            matn, addenda = _split_compiler_commentary(
                matn, addenda, tight, near, extra)
            if collection == "abudawud":
                # Al-Lu'lu'i's voice: a different speaker (Abu Dawud's own
                # transmitter), unique to this collection, run BEFORE the
                # heard-form marker below (R-A3-23): 6 of the 8 "sami'tu
                # ACC-kunya" occurrences are immediately preceded by "qala Abu
                # Ali", and must be cut at that earlier position, not the
                # later "sami'tu" -- see `_split_heard_commentary`'s own
                # docstring for why the order is load-bearing, not
                # incidental. 3040's "qala Abu Ali" already lives inside
                # `_split_compiler_commentary`'s own tail above, so by the
                # time this runs it is a no-op for that record, not a double
                # cut.
                matn, addenda = _split_lului_commentary(
                    matn, addenda, record_id, lului_never_cut)
            # R-A3-23: "sami'tu ACC-kunya", the case `tight`/`near`/`extra`
            # cannot reach (they only recognise the NOMINATIVE, or no kunya at
            # all). A no-op for Abu Dawud's 6 records `_split_lului_
            # commentary` just handled, and Tirmidhi has no occurrence of this
            # shape at all (measured: its one accusative "أبا عيسى" is never
            # preceded by "سمعت").
            matn, addenda = _split_heard_commentary(matn, addenda, heard)
            # Abu Dawud's 4129 (R-A3-22) and 1234 (R-A3-23) near-miss cuts
            # each leave a further nested "qala <name>" attribution fused
            # onto the genuine matn, past what either marker's own window
            # reaches -- a no-op for every other record, since the table
            # holds exactly these two hand-read entries.
            matn, addenda = _apply_cut_override(
                matn, addenda, record_id, near_miss_cut_override)
            if collection == "tirmidhi":
                # Shakir's own bracketed cross-reference numbers (see
                # `_strip_reference_numbers`) -- run last, on whatever the
                # PRIMARY matn is once every commentary cut above has already
                # happened, never on `addenda_ar`.
                matn = _strip_reference_numbers(matn)

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
                unscorable_reason=_unscorable_reason(record_id, matn, unscorable),
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
                absorb_heading(frag)
            continue
        if _SECTION.match(line):
            flush()
            if bab_parts is not None:
                # A new section starts before the heading's paren closed --
                # no more continuation text is coming; keep what we have.
                bab_parts, bab_balance, heading_kind = None, 0, None
            if (h := _HADITH_NUM.match(line)) is not None:
                pending_number = h.group(1)
            elif (k := _KITAB.match(line)) is not None:
                kitab_no += 1
                kitab_ar, bab_ar = _strip_heading_markup(_clean(k.group(1))), None
            elif (b := _BAB.match(line)) is not None:
                start_heading("bab", b.group(1))
            continue
        if (hp := _HASH_PIPE.match(line)) is not None:
            content = hp.group(1)
            kind = _heading_kind(_clean(content))
            if kind is None:
                # Not a heading -- a parenthesised aside that continues
                # whatever narration is already open. See _heading_kind's
                # docstring: the SAME "# | 1 ( ... )" envelope wraps both,
                # and only the word inside tells them apart.
                if buf is not None and bab_parts is None:
                    buf.append(_unwrap_parens(content))
                continue
            flush()
            if bab_parts is not None:
                bab_parts, bab_balance, heading_kind = None, 0, None
            start_heading(kind, content)
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
            if pending_number is not None:
                # Tirmidhi only (see `_HADITH_NUM`): this content line carries
                # no number of its own -- it was printed on the "### |||" line
                # just consumed -- so reattach it here, in the exact shape
                # `_NUMBERED` parses everywhere else, before this unit is
                # buffered under it. Measured: the "### |||" line is always
                # (all 3,976 times) immediately followed by exactly this kind
                # of line, so there is never a stale `pending_number` left
                # over to misattach to some LATER, unrelated unit.
                frag = f"{pending_number} {frag}"
                pending_number = None
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
