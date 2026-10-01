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
from collections.abc import Callable
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
# Ibn Majah (Task 15): milestones in this file are THREE digits ("ms001" ..
# "ms879"), not the four ("ms0007", "ms0293", ...) every previously-shipped
# collection's cached file uses exclusively (measured: Bukhari/Muslim/
# Abu Dawud/Tirmidhi/Nasai are 100% 4-digit, 0% any other width; Ibn Majah is
# 100% 3-digit, 0% 4-digit). `ms\d{4}` -- hardcoded from the first file this
# parser ever saw -- therefore never matches a single one of Ibn Majah's 879
# milestones, and 418 of its 4,341 records carry a literal, unstripped
# "msNNN" token inside their SCORED text_ar as a direct result (measured
# against a parse with no other change) -- exactly the structural-markup-
# leaking-into-canonical-text hazard this module's own docstring says a
# docs-only parser would produce, now reproduced by a width assumption
# instead. Widened to `\d+` (any digit run), which is a strict superset for
# every already-shipped file: each one's milestones are already followed by
# a non-digit boundary, so `\d+`'s greedy match consumes exactly the same
# four digits `\d{4}` did and stops there -- re-verified by a full
# byte-identical rebuild of Bukhari/Muslim/Abu Dawud/Tirmidhi/Nasai after
# this change (see the ingest report for this task).
_MILESTONE = re.compile(r"ms\d+")
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


def _strip_stray_asterisk(matn: str) -> str:
    """Remove a literal "*" left in a (post-split) PRIMARY matn -- Ibn Majah
    only, run last, same call-site convention as `_strip_reference_numbers`.

    The "*" that opens `flush()`'s OWN isnad/matn split (`rest.split("*", 1)`)
    is always consumed there and never reaches this far. What this strips is
    a SECOND, nested "*" -- the edition's own compressed-repeat convention
    ("... 'an al-nabi ... * bi-nahwih", a second isnad printed inline, its own
    matn abbreviated to a bare pointer) -- which ordinarily lands in the
    addendum as a harmless side effect of `_split_secondary`'s cut landing
    before it, not because anything strips it. `hadith:ibnmajah:2131` is the
    one record (measured) where `NEVER_CUT["ibnmajah"]` keeps the WHOLE unit,
    nested "*" included, because the alternative -- letting `_split_secondary`
    cut at the bare "qala" it mistakes for this second chain's own opening --
    discards the primary narration's genuine punchline (see that entry's own
    comment). Ibn Majah is the only collection today where `NEVER_CUT` can
    retain a second "*": Bukhari's three `NEVER_CUT` entries measure zero
    (their addenda hold no nested repeat at all), so this is not a hook a
    future collection's own NEVER_CUT entries can assume -- each must be
    checked afresh, the same as every other guard in this file.

    Muslim's own file independently carries a literal "*" in three matns and
    Tirmidhi's in one addendum -- pre-existing in BASE, unrelated to this
    fix, and OUT OF SCOPE here: fixing them would touch `_clean()`, which
    every one of the five prior collections' byte-identity proof depends on
    staying untouched. Flagged for a future, dedicated round instead of
    silently folded into this one.
    """
    stripped = " ".join(matn.replace("*", " ").split())
    return stripped if stripped else matn


# --- Nasai's own compiler commentary (Task 14, ruling R-A3-20) ------------
#
# Al-Nasai (kunya "أبو عبد الرحمن") appends his own voice after a matn --
# "قال أبو عبد الرحمن" measured 139 times across the file, far lower than
# Tirmidhi's 2,996 but the SAME Class-B defect (R-A3-18): fused editorial
# prose makes the genuine matn beneath it fail verification. Derived, not
# hand-written, from `_compiler_commentary_markers("أبو عبد الرحمن")`.
#
# This kunya is an extremely common one among narrators (most famously
# 'Abdullah ibn Mas'ud, but this file's own isnads also carry it for 'Abdallah
# ibn 'Umar, Abu 'Abd al-Rahman al-Sulami, al-Hubuli and al-Shami), so the
# over-cut risk the ruling calls out is real, not theoretical -- measured
# directly rather than assumed:
#
#   - Bare kunya (any case): 201 raw occurrences, 1 of which is the #META#
#     AuthorNAME line itself (outside any unit), leaving 200 in the body.
#   - Nominative "أبو عبد الرحمن": 170, of which 139 are "قال أبو عبد الرحمن"
#     (the compiler's voice, cut) and 31 are bare -- read individually, every
#     one of the 31 is either (a) already inside a tail `tight` has already
#     cut in the same unit ("قال أبو عبد الرحمن ... قال أبو عبد الرحمن
#     الأوزاعي ...", a second self-reference inside his own remark) or
#     (b) a narrator's kunya inside an isnad or inside reported speech,
#     correctly left untouched because no verb governs it.
#   - Accusative "أبا عبد الرحمن": 16 ("~~"-tolerant; a naive `\s+`-only count
#     gives 14 and undercounts for the same line-wrap reason the genitive and
#     "هذا حديث" counts below do -- found in the Task 14 fix round, R-A3-25),
#     ALL of the vocative shape "يا أبا عبد الرحمن" ("O Abu 'Abd al-Rahman")
#     addressed to 'Abdallah ibn 'Umar or another Abu 'Abd al-Rahman inside
#     genuine narration, or "أبا عبد الرحمن الحبلي" (al-Hubuli, a different
#     person, inside an isnad) -- NEVER "سمعت أبا عبد الرحمن يقول" (measured:
#     that exact verb + accusative shape occurs 0 times in this file, unlike
#     Abu Dawud's 8). No disposition changes from the recount; corrected here
#     so Task 15/16 do not inherit the naive number.
#     `heard`'s own pattern therefore matches nothing here, correctly: the
#     namesake collision is real but is resolved by verb-gating exactly as
#     Abu Dawud/al-Tayalisi's was, not by an identity check, and this is
#     recorded as measurement, not assumption.
#   - Genitive "أبي عبد الرحمن": the brief's own naive raw-text count (17)
#     undercounts, for the same reason the raw "هذا حديث" count below does --
#     a naive `\s+`-only regex does not span the source's own "~~" line-wrap
#     continuation marker, so an occurrence broken across two printed lines is
#     invisible to it. Re-measured tolerant of "~~": 19. Read individually,
#     all 19 name a narrator inside an isnad chain ("عن أبي عبد الرحمن الحبلي
#     عن ...", "عن ربيعة بن أبي عبد الرحمن عن ...") or, once
#     (hadith:nasai:1856), inside a Companion's own reported speech ("قالت
#     عائشة يغفر الله لأبي عبد الرحمن ...", 'A'isha invoking one by his kunya)
#     -- never the compiler speaking. Unlike Abu Dawud, this is NOT structural
#     luck: 1856's occurrence sits inside a unit's MATN (post-"*"), not its
#     isnad, so nothing about position alone protects it here. What protects
#     every one of the 19 is that `_compiler_commentary_markers` builds no
#     genitive pattern at all (see its own docstring) -- "أبي" is a different
#     string from the "أبو"/"أبا" every marker below requires, so none of
#     tight/near/heard/`_NASAI_FORMULA` can ever match a genitive occurrence
#     regardless of what verb or preposition precedes it. Confirmed by
#     construction and by `find_near_misses` (see the ingest report): zero of
#     the 19 are reachable even at a widened, case-varying sweep.
#   - "هذا حديث" (Tirmidhi's own grading-tail opener): the brief's raw count
#     (8) has the same "~~"-undercounting defect as the genitive above --
#     re-measured tolerant of line wraps: 11. Read individually: 6 already sit
#     inside a tail `tight` has already cut in the same unit; 1 ("وهذا حديث
#     القاسم قال * ...") is isnad-side prose before the unit's own "*" split,
#     never reaching matn at all; 3 are new and are covered by
#     `_NASAI_FORMULA` below.
#   - "وفي الباب" (Tirmidhi's other non-kunya formula): 0 occurrences,
#     measured -- Nasai's edition does not use this cross-reference formula.
#
# A further, independent sweep -- not named in the brief's own marker table,
# and NOT measured there -- found al-Nasai's single most common editorial
# formula in this edition: a terse comparative-isnad note, "خالفه/خالفهما/
# خالفهم <narrator>[, رواه/فرواه عن ...]" ("so-and-so DIFFERED from him [in
# the transmission], narrating it from ..."), noting a variant chain for the
# same hadith. This is Class-B (R-A3-18) on ~70 further records the brief's
# own table does not cover, at a higher raw count than the kunya marker
# itself (measured: "خالفه" 64, "خالفهما" 6, "خالفهم" 7 = 77 raw, tolerant of
# "~~"). It is NEVER preceded by "قال أبو عبد الرحمن" in the same breath --
# it is al-Nasai's own voice by convention throughout the book, not by an
# explicit self-naming each time, exactly like Tirmidhi's own elliptical
# "qala hadha hadith" continuations. Left unhandled, quoting the genuine matn
# of any of these ~70 records reproduces R-A3-18 exactly: the fused
# isnad-critique tail makes the stored `text_ar` narration-plus-commentary,
# not the narration.
#
# Read individually, all 77 raw occurrences but one are the tail-position
# critique shape, immediately followed by a narrator's name: `hadith:
# nasai:3047` is the ONE genuine exception -- "... وإن رسول الله صلى الله
# عليه وسلم خالفهم ثم أفاض قبل أن تطلع الشمس" ("... and the Messenger of
# Allah DIFFERED FROM THEM [the pre-Islamic practice] and hastened [the
# descent from Muzdalifah] before sunrise") is genuine narrative describing
# the Prophet's OWN act, using the same verb form for an entirely different
# sense ("differed from [a practice]" vs. "differed from him [in narrating
# it]") -- "خالفهم" here is followed by "ثم" (a narrative connective), never a
# narrator's name, so cutting here would truncate the hadith's own point
# (that he acted before sunrise, unlike the Jahiliyya) into addenda. On
# `COMMENTARY_NEVER_CUT["nasai"]`, read and excluded by hand, exactly the
# over-cut risk this task's raised bar calls for. A second false match was
# found and fixed by construction, not by an exception: "قيل ... ولا تخالفه
# في نفسها ومالها" (hadith:nasai:3231, "she does not DISOBEY him") is a
# different word ("تخالفه", imperfect + object pronoun) that a boundary-free
# substring search would wrongly match inside; `_NASAI_FORMULA` requires the
# same `(?<![{_ARABIC}])`/`(?![{_ARABIC}])` word-boundary discipline every
# other marker in this file already uses, so it is never reached.
#
# Two further formula phrases, each measured to add exactly ONE further
# record beyond the kunya marker and the "خالف*" family above:
#   - "هذا خطأ" ("this is an error", 22 raw occurrences) -- 21 already sit
#     inside an existing cut tail; the 22nd, hadith:nasai:4088, is new
#     ("... فهو شهيد هذا خطأ والصواب حديث سعير بن الخمس").
#   - "والصواب" ("and the correct [version] is", 21 raw occurrences) -- 20
#     already cut (mostly the same tails "هذا خطأ" already covers); included
#     for the same reason "هذا خطأ" is, as a second, independent anchor on
#     the same self-correcting remark, in case a future edit ever separates
#     them. Redundant with "هذا خطأ" on every record measured today (4088 is
#     the only new record either phrase reaches, and "هذا خطأ" precedes
#     "والصواب" in it, so `_NASAI_FORMULA`'s "earliest match wins" rule finds
#     the same boundary regardless of which is present). Always fused as one
#     word ("والصواب"), never a separate "فالصواب" (measured: 0), so unlike
#     "خالفه" it needs no optional `[وف]?` proclitic of its own.
#
# --- Fix round 1 (R-A3-25): the rest of the comparative-isnad family --------
#
# An independent review of this task found that "خالفه" is one VERB of a
# whole family al-Nasai uses with identical syntax -- critique verb (+
# optional `[وف]?` proclitic) immediately followed by a narrator's name, in
# the tail position after a complete matn -- and that shipping only "خالفه"
# left ~100 further occurrences of sibling verbs fused into scored text. Each
# member below was found by sweeping every record's matn AS IT STOOD
# immediately before this function ran (instrumented directly, not
# regenerated from the shipped DB, so isnad-side and already-cut occurrences
# are correctly invisible), then reading every single occurrence in context --
# not a sample -- because several of these verbs have a genuine narrative
# sense ("he RAISED his hands", "he SENT a messenger", "Allah RAISES him a
# degree") that looks identical to the critique sense out of context and a
# blind verb match would over-cut the entire remainder of the matn, not just
# a local remark (`_split_compiler_commentary` cuts from the earliest match to
# the end of the string).
#
#   - "وافقه"/"وافقهما" ("so-and-so AGREED with him [on the isnad]", the
#     positive mirror of "خالفه"): 7 raw occurrences, ALL tail-critique, no
#     exceptions. Fixes hadith:nasai:3899 directly: cutting at "وافقه" (which
#     precedes "وخالفه" in that record's matn, so "earliest match wins" finds
#     it first) moves BOTH "وافقه مالك بن أنس على إسناده" and "وخالفه في
#     لفظه" into addenda together -- the report's original claim that the
#     first phrase was genuine matn was wrong; it is al-Nasai's own isnad
#     note, not Rafi' ibn Khadij's ruling.
#   - "تابعه" ("so-and-so CORROBORATED him"): 8 raw occurrences, ALL
#     tail-critique. One (5677) already sits inside a tail "قال أبو عبد
#     الرحمن" cuts earlier in the same matn, so adding this arm changes
#     nothing there; confirmed by reading it.
#   - "أرسله" ("so-and-so transmitted it MURSAL"): 18 occurrences in scored
#     matn (19 raw; the 19th sits isnad-side, already unreachable). 13 are
#     tail-critique and cut cleanly (fixes hadith:nasai:1614 and 2127
#     directly, both named by the review). 4 are genuine narrative and are on
#     `COMMENTARY_NEVER_CUT["nasai"]`: 164 ("فأرسله إلى بسرة" -- 'Urwa SENT a
#     messenger to Busra), 938 (the Prophet's own speech "أرسله يا عمر" --
#     "LET HIM GO, Umar"), 1526 ("ثم أرسله" -- Allah SENDING down rain), 4723
#     ("فعفا عنه فأرسله" -- he pardoned and RELEASED him). One
#     (hadith:nasai:3892) cuts correctly at "فأرسله" but leaves a second,
#     also-editorial clause ("وروى الزهري الكلام الأول عن سعيد", describing a
#     different narrator's variant route) dangling on the primary; corrected
#     via `NEAR_MISS_CUT_OVERRIDE["nasai"]`, the same mechanism as the two
#     entries below.
#   - "رفعه" ("so-and-so RAISED it [attributed it] MARFU'"): 11 records. 2 are
#     clean tail-critique cuts. 3 need `NEAR_MISS_CUT_OVERRIDE` for a dangling
#     nested attribution left in front of the verb (751 "قال يحيى", 2054 "قال
#     وحدثنا أبو عثمان مرارا", 3901 "رواه يحيى بن سعيد عن حنظلة بن قيس"). 6 are
#     genuine narrative and are on `COMMENTARY_NEVER_CUT["nasai"]`: 1092
#     ("وإذا رفعه فليرفعهما" -- RAISING the hands out of prostration, named by
#     the review), 1139 ("إلا رفعه الله بها درجة", twice in the same matn --
#     Allah RAISING him a degree), 3144 (same "رفعه الله به درجة" reward
#     idiom), 4878/4879 ("فرفعه إلى النبي" -- BRINGING a thief before the
#     Prophet), 5694 ("فرفعه إلى فيه", twice -- RAISING a cup to one's mouth).
#   - "وقفه" ("so-and-so STOPPED it MAWQUF"): 3 raw occurrences, ALL clean
#     tail-critique.
#   - "أوقفه" (the same sense, causative form): 2 raw occurrences. 1
#     (hadith:nasai:1702) is a clean tail-critique cut. 1 (hadith:nasai:4067,
#     named by the review) is genuine narrative -- "حتى أوقفه على النبي" (he
#     made the pardoned man STAND before the Prophet, part of the Fath Makka
#     story) -- and is on `COMMENTARY_NEVER_CUT["nasai"]`.
#   - "أسنده" ("so-and-so gave it a full chain"): 1 raw occurrence
#     (hadith:nasai:4076), already inside a tail "قال أبو عبد الرحمن" cuts
#     earlier in the same matn; adding this arm changes nothing there,
#     confirmed by reading it, but it is added for completeness and so a
#     future occurrence without a preceding kunya marker is covered too.
#   - Bare classification tags "مرسل"/"موقوفا" (the tag alone, no verb): 22/2
#     raw occurrences. Most already sit inside an existing "قال أبو عبد
#     الرحمن" tail. 5 are new clean cuts, including the review's flagship
#     example hadith:nasai:4129 ("لا ترجعوا بعدي كفارا مرسل" -- the primary
#     becomes the famous "do not return to disbelief after me" hadith, with
#     "مرسل" the whole addendum). 1 (hadith:nasai:4903) is genuine narrative --
#     "في غزوة الفتح مرسل ففزع قومها ..." -- "مرسل" sits MID-matn, not at the
#     tail, describing the isnad status of only the opening clause of a
#     composite report that continues for ~600 further characters of the
#     famous Makhzumiyya-thief story; on `COMMENTARY_NEVER_CUT["nasai"]`. 1
#     (hadith:nasai:1792, "موقوفا") needs `NEAR_MISS_CUT_OVERRIDE` for a
#     dangling "رواه حميد بن عبد الرحمن بن عوف" attribution. 1
#     (hadith:nasai:1738) has NO genuine matn at all -- its entire text is
#     "مرسل وقد رواه عطاء بن السائب عن سعيد بن عبد الرحمن بن أبزي عن أبيه", a
#     transmission-route note with no Prophetic or Companion content -- moved
#     to `UNSCORABLE["nasai"]` instead of cut, the same disposition already
#     given to its structural siblings 1788/2114/2115/4952/5194 (missed by the
#     original UNSCORABLE audit because nothing before this fix round swept
#     for it; found by the same measurement, not a separate review comment).
#   - "هذا الصواب" ("THIS is the correct one", distinct from "والصواب" above):
#     of 38 raw "الصواب" occurrences, only 2 (hadith:nasai:4128, 4912) are new,
#     clean tail cuts with no preceding kunya marker. Deliberately NOT
#     generalised to bare "الصواب": six records (1240, 1242, 1244, 1245, 1246,
#     1247) use "الصواب" inside genuine Prophetic speech about doubt during
#     prayer ("فليتحر الذي يرى أنه الصواب" -- "let him seek out what he judges
#     correct") with no "هذا" in front, and every one was read to confirm a
#     bare pattern would have destroyed them.
#   - "لم يسمع"/"لم يسمعه" ("so-and-so did NOT HEAR it [from so-and-so]"): the
#     gap the original submission deferred as "the" known gap turned out to be
#     one member of this larger family, not a special case, so it is in scope
#     now. 27 raw occurrences. Most sit inside an existing "قال أبو عبد
#     الرحمن" tail. Read individually, the survivors split into:
#       - 2 clean tail cuts (4971, 4972 -- "ليس على خائن ولا منتهب ولا مختلس
#         قطع" + "لم يسمعه سفيان/بن جريج أيضا من أبي الزبير"; 4971 is named by
#         the review as resolving EXACT to `tirmidhi:1448` today).
#       - 5 needing `NEAR_MISS_CUT_OVERRIDE` for a dangling name or clause in
#         front of the verb (2926 "عروة"، 3844 "وقيل إن الزبير", 3872 "ومما
#         يدل على أن طاوسا", 3880 "وفي رواية همام بن يحيى كالدليل على أن
#         عطاء", 3895 "أيوب").
#       - 1 more needing the same override, found by this sweep but NOT in the
#         review's 7-record list (hadith:nasai:1541 -- "قال أبو بكر بن السني
#         الزهري سمع من بن عمر حديثين ولم يسمع هذا منه"; "أبو بكر بن السني"
#         here is al-Nasai's own transmitter relaying the report, a different
#         person from "أبو عبد الرحمن" al-Nasai himself, so `tight` never
#         fires and this record's dangling attribution was otherwise
#         invisible) -- an example of the ruling's own instruction to keep
#         measuring past the named list, not stop at it.
#       - 2 confirmed genuine narrative, first-person, NOT the third-person
#         critique shape, and placed on `COMMENTARY_NEVER_CUT["nasai"]`: 906
#         ("فلم يسمعنا قراءة بسم الله") was already out of `_NASAI_FORMULA`'s
#         reach entirely (no bare-verb arm existed before this fix round) and
#         needs no entry; 1612 ("فلم يسمع لنا حسا" -- part of the 'Ali and
#         Fatima night-prayer story) now falls inside the widened family and
#         gets the entry.
#     hadith:nasai:3461 is unaffected: its only "لم يسمع" match ("الحسن لم
#     يسمع من أبي هريرة شيئا") sits after an existing "قال أبو عبد الرحمن"
#     that already cuts earlier in the same matn (the record's OWN "لم أسمعه",
#     a different, first-person verb form this family does not match, stays
#     in the primary as it always has); reading it confirmed the boundary is
#     unchanged by this fix round.
#   - "لم يرفعه" ("so-and-so did NOT raise/attribute it MARFU'"), the negated
#     counterpart of "رفعه" -- found only by re-reading `hadith:nasai:1806`,
#     which the review itself named as a broken record ("... بنى الله عز وجل
#     له بيتا في الجنة لم يرفعه حصين وأدخل بين عنبسة وبين المسيب ذكوان") but
#     whose tail no arm of the family covered, since "يرفعه" (imperfect) is a
#     different word from "رفعه" (perfect), not a proclitic variant of it --
#     exactly the kind of sibling the ruling's own instruction to keep
#     measuring past the named list was written for. 7 raw occurrences.
#       - 2 clean tail cuts: hadith:nasai:1806 (fixes the review's own
#         example directly) and hadith:nasai:3900 (after a
#         `NEAR_MISS_CUT_OVERRIDE` for the dangling "رواه سفيان الثوري رضي
#         الله عنه عن ربيعة" attribution in front of the verb).
#       - 1 (hadith:nasai:3492, "... فذكر نحوه ولم يذكر زيد بن أرقم ولم
#         يرفعه") cuts to a primary that is STILL a bare cross-reference
#         ("three men shared in a state of purity, and he narrated something
#         LIKE IT, and Zayd ibn Arqam did not mention [it]") with no
#         standalone quotable content of its own -- moved to
#         `UNSCORABLE["nasai"]` rather than left scored as a "cut" record,
#         the same disposition as its structural sibling hadith:nasai:2232.
#       - 2 (hadith:nasai:4098, 4360) already sit in `UNSCORABLE["nasai"]` as
#         genuine pointers ("بهذا الإسناد مثله"/"نحوه") with "ولم يرفعه"
#         appended; their sha256 pins are updated for the same reason
#         2232/2295/2412/4787's were above -- the disposition is unchanged,
#         only the pinned string is shorter now that "ولم يرفعه" moves to
#         `addenda_ar`.
#       - 1 (hadith:nasai:5183) is already inside an existing "خالفه" tail
#         that cuts earlier in the same matn; adding this arm changes nothing
#         there, confirmed by reading it.
#       - 1 (hadith:nasai:400) sits inside the tail this record's own
#         dedicated hand-fix already isolates into `addenda_ar` (see
#         `_fix_nasai_400_isnad_matn_split` below); unaffected by this arm.
#
# `_split_compiler_commentary`'s own "earliest candidate wins, but an empty
# head means try the next one" rule (see its own comment) matters for exactly
# one record in this whole fix round: hadith:nasai:5194 opens directly on the
# bare "مرسل" tag ("مرسل قال أبو عبد الرحمن والمراسيل أشبه بالصواب ..."),
# which is now the earliest candidate and would otherwise abort the cut
# entirely, discarding the perfectly good, later "قال أبو عبد الرحمن" boundary
# this record has always been correctly cut at.
#
# `_NASAI_FORMULA`'s first draft omitted the optional `[وف]?` proclitic on
# the "خالفه" arm, on the (wrong) assumption that a verb beginning a fresh
# clause would never be crossed by the conjunction's own compulsory boundary
# check. A full re-sweep of the built matns (never trust the count that
# justified the pattern -- read what it actually produced) found
# hadith:nasai:3899 uncut: "... وافقه مالك بن أنس على إسناده وخالفه في لفظه"
# -- "وخالفه" ("and he differed from him") is the fused conjunction + verb,
# and `(?<![{_ARABIC}])` correctly refused to match with an Arabic letter
# ("و") immediately in front, exactly as designed -- the marker itself needed
# the same `[وف]?` optional proclitic every other verb-initial marker in this
# file already carries (`_ABUDAWUD_COMMENTARY`, `_TIRMIDHI_COMMENTARY`,
# `_compiler_commentary_markers`'s own `tight`/`near`/`heard`). Fixed below;
# 3899 now cuts correctly, leaving "... وافقه مالك بن أنس على إسناده" as
# genuine matn and "وخالفه في لفظه" in addenda.
#
# Two dangling-attribution corrections, the same nested-attribution shape
# `NEAR_MISS_CUT_OVERRIDE` already exists for (Abu Dawud's 4129/1234,
# Tirmidhi's 2239), applied here via `NEAR_MISS_CUT_OVERRIDE["nasai"]`:
#   - hadith:nasai:5583 ("... كل مسكر حرام وكل مسكر خمر قال الحسين قال أحمد
#     وهذا حديث صحيح"): after the formula cuts at "وهذا حديث صحيح", "قال
#     الحسين قال أحمد" (a sub-narrator relaying Ahmad ibn Hanbal's own grading
#     remark, not al-Nasai's voice) is left dangling on the genuine Prophetic
#     saying.
#   - hadith:nasai:5707 ("... قد خلل ومما يدل على صحة هذا حديث السائب"): the
#     formula's "هذا حديث" arm cuts at "هذا", but "هذا" is the grammatical
#     subject of the PRECEDING clause ("and among what indicates the
#     correctness of THIS is..."), not the start of the remark -- the remark
#     itself begins 4 tokens earlier, at "ومما".
#
# `_split_secondary`'s own audit for Nasai (a separate mechanism from the
# kunya markers above -- it cuts a SECOND narration embedded inside a matn
# whose leading isnad the source's own "*" already removed, not al-Nasai's
# editorial voice). Instrumented directly: every call that actually returned
# an addendum was captured while parsing the real file. Result: 26 records
# (77, 101, 362, 478, 618, 633, 675, 1231, 1287, 1991, 1993, 2208, 2329, 2847,
# 2966, 3367, 3422, 3455, 3811, 3918, 3919, 4070, 4521, 4532, 4729, 5110),
# each read by hand at its exact boundary. Every primary ends on a complete
# clause and every addendum opens a fresh attribution ("qala X akhbarani/
# haddathani Y ..."), never a mid-sentence truncation -- no over-cut found, so
# `NEVER_CUT["nasai"]` has no entries (matching Muslim/Abu Dawud/Tirmidhi,
# which also needed none; only Bukhari's original 3 remain in that dict).
_NASAI_COMMENTARY, _NASAI_COMMENTARY_NEAR, _NASAI_HEARD = \
    _compiler_commentary_markers("أبو عبد الرحمن")

_NASAI_FORMULA = re.compile(
    rf"(?<![{_ARABIC}])[وف]?(?:خالفه(?:ما|م)?|وافقه(?:ما)?|تابعه|أرسله|رفعه|"
    rf"وقفه|أوقفه|أسنده|مرسل|موقوفا|هذا\s+خطأ|هذا\s+حديث|هذا\s+الصواب|"
    rf"لم\s+يسمع(?:ه)?|لم\s+يرفعه|مختصر|لم\s+يذكر|رواه|روى|"
    rf"اختلف\s+(?:على|عليه(?:ما)?))"
    rf"(?![{_ARABIC}])"
    rf"|(?<![{_ARABIC}])والصواب(?![{_ARABIC}])"
    rf"|(?<![{_ARABIC}])[وف]?اللفظ\s+ل"
    rf"|(?<![{_ARABIC}])غير\s+محفوظ(?![{_ARABIC}])")

# --- Ibn Majah's compiler AND transmitter commentary (Task 15, R-A3-21) ----
#
# TWO voices, not one, need splitting out of this file -- the brief's own
# inventory measured only the transmitter's. Ibn Majah's own remark is a
# DIFFERENT defect the inventory never checked for.
#
# 1. Abu al-Hasan (ibn Salama) al-Qattan -- the Sunan's primary TRANSMITTER
#    from Ibn Majah (the same role Abu Ali al-Lu'lu'i plays for Abu Dawud) --
#    remarks after a matn to record an ALTERNATE chain for the same report
#    ("... قال أبو الحسن [بن سلمة/القطان] حدثنا/ثنا/أخبرنا ... فذكر نحوه
#    [بإسناده]", "he mentioned it similarly, with this chain"). Kunya "أبو
#    الحسن", derived from `_compiler_commentary_markers`, not hand-written.
#    Measured wrap-tolerant (the raw, naive count undercounts for the same
#    "~~" line-wrap reason Nasai's did -- see Task 14's own R-A3-25/26 -- so
#    every count here is read from the PARSED, already-joined unit text, not
#    a bare `grep`): nominative 40 (33 immediately after قال/سئل, the
#    brief's own count; 7 recovered only by reading across a wrap), of which
#    4 (321, 413, 596, 649) sit entirely inside `isnad_ar` -- this record's
#    own "*" boundary falls AFTER the remark, so it is carried as part of
#    the NEXT report's isnad and never reaches scored text_ar by placement
#    alone, the same structural luck that protects Abu Dawud's genitive --
#    and 2 are not governed by قال/سئل at all (2082 "لقد تحمل أبو الحسن هذا
#    صخرة عظيمة على عنقه", praise for HIS OWN hadith-bearing, no verb;
#    3458 "حدثنا أبو الحسن القطان ...", see `_IBNMAJAH_FORMULA` below). The
#    remaining 34 are read individually and are every one a clean
#    alternate-chain remark. Accusative 2, both "سمعت أبا الحسن [الطنافسي]
#    يقول" -- 2051 names a DIFFERENT Abu al-Hasan (Ali ibn Muhammad
#    al-Tanafisi, one of Ibn Majah's own teachers, not al-Qattan); still
#    correctly cut, since the rule targets "someone's reported remark fused
#    onto the matn", not "specifically al-Qattan's remark". Genitive 4, all
#    inside `isnad_ar`, all a DIFFERENT narrator ("... مولى بني نوفل", "X ibن
#    أبي الحسن" twice, "الحسن بن أبي الحسن البراد") -- never reachable
#    regardless, both because `_compiler_commentary_markers` builds no
#    genitive pattern at all (see its own docstring) and because isnad_ar is
#    never scored -- checked individually per record, not assumed from Abu
#    Dawud's precedent.
#
# 2. Ibn Majah's OWN voice -- Muhammad ibn Yazid, kunya "Abu 'Abdallah"
#    (#META# 010.AuthorNAME: "محمد بن يزيد أبو عبدالله القزويني") -- grading
#    and attribution remarks ("هذا حديث غريب", "لم يحدث به إلا ...", word
#    glosses). This is the "OTHER editorial formula" the brief asked to be
#    measured for: its own inventory checked only "قال أبو عبد الرحمن"
#    (al-Nasai's kunya, to rule out a collision) and never checked Ibn
#    Majah's OWN kunya, which happens to share its first word with
#    al-Nasai's ("أبو عبد ...") but is a different person and a different
#    defect -- the COMPILER's own voice, not a narrator collision. Reached
#    two ways: his kunya ("قال أبو عبد الله[ بن ماجة]", nominative 29 raw --
#    19 immediately after قال, 7 of those explicitly followed by "بن
#    ماجة"/"يعني بن ماجة" confirming the identification; 1 (2835) inside
#    isnad_ar, harmless by the same placement rule as above; the remaining 9
#    are bare narrator kunyas inside isnads -- "Abu 'Abdallah al-Aghurr",
#    "al-Ash'ari", "al-Alhani", each a DIFFERENT person, correctly untouched
#    since no verb governs them; accusative 2 -- "سمعت محمد بن يزيد أبا عبد
#    الله يقول" (309, the transmitter reporting having heard IBN MAJAH
#    HIMSELF, named in full -- `heard`'s own token-gap does not reach past
#    the inserted name, a genuine miss `find_near_misses` caught; given its
#    own anchored arm in `_IBNMAJAH_FORMULA` below, not a widening of the
#    shared generator) and "يا أبا عبد الله" (4159, VOCATIVE, addressed
#    to a Companion mid-narration -- correctly untouched, `heard` requires a
#    preceding "سمعت", not a bare vocative); genitive 9, all inside
#    isnad_ar, all different narrators, unreachable for the same two reasons
#    as above) -- OR his own NAME, "بن ماجة" (does not decline through
#    `_kunya_case_forms`, so it needs its own pattern below, not a reuse of
#    `_compiler_commentary_markers`): 24 raw occurrences, 8 already sit right
#    after a kunya occurrence the pattern above already cuts in the same
#    unit ("قال أبو عبد الله بن ماجة ...", "... يعني بن ماجة ..."), the other
#    16 -- "قال بن ماجة" (13), "قاله بن ماجة" (2, a different conjugation,
#    "he said IT"), "قال محمد بن ماجة" (1, his name in full) -- read
#    individually below and every one a genuinely editorial remark, correctly
#    excluded from the matn. One of the two "قاله بن ماجة" occurrences,
#    hadith:ibnmajah:2162, has "قاله" ("he said IT") referring BACKWARD to an
#    isnad-uniqueness remark ("تفرد به بن أبي عمر وحده") that precedes it --
#    the opposite order from every other "qala <compiler> ..." shape in this
#    file -- so the marker's own cut at "قاله" leaves that remark dangling on
#    the genuine matn; corrected by `NEAR_MISS_CUT_OVERRIDE["ibnmajah"]`. The
#    other 15 need no such correction.
#
# `هذا حديث` (Tirmidhi's own grading-tail opener) recurs here too, at a much
# smaller scale and a different construction: 10 occurrences, 3 already
# inside a tail one of the two markers above already cuts in the same unit;
# the other 7 are almost always "هذا حديث <name>" ("this is so-and-so's
# version/recension" -- naming WHOSE wording a combined chain follows, not a
# grading term) rather than Tirmidhi's "هذا حديث <grading term>"; once,
# 1385, it IS a grading term ("هذا حديث صحيح", attributed to "أبو إسحاق", a
# third narrator) -- the marker's own cut is at "هذا", correct as far as it
# goes, but leaves "قال أبو إسحاق" (the narrator introducing that grading
# remark) dangling on the genuine matn; corrected by a second, later cut via
# `NEAR_MISS_CUT_OVERRIDE["ibnmajah"]`, the same one-hop nested-attribution
# shape as Abu Dawud/Tirmidhi/Nasai's own entries. The other 6 of the 7 need
# no such correction and are a clean, unconditional tail boundary as read --
# added as its own arm since nothing in this
# file ever uses "هذا حديث" inside genuine narrative.
#
# Sighted but NOT added -- each is genuine narrative on every SCORED
# (`matn_ar`, not the joined display text) occurrence, measured record by
# record, not assumed:
#   - "خالفه"/"خالفهم" (3, matn-scored): all three are "لا يضرهم من خالفهم"
#     (10, 3952 -- the famous "a group of my nation will remain triumphant
#     on the truth, UNHARMED BY THOSE WHO OPPOSE THEM" hadith) or "فخالفهم
#     رسول الله" (3022 -- the Prophet's own act of differing from a
#     pre-Islamic practice) -- the SAME genuine-narrative sense Nasai's own
#     single exception (hadith:nasai:3047) established for this verb, here
#     the ONLY sense present, not an exception to a formula. No entry added;
#     unlike Nasai, this file gives no isnad-critique use of the verb at
#     all.
#   - "رفعه" (7): 6 are the "Allah RAISES him a degree" reward idiom or
#     raising/lowering the head in prayer or bringing a prophecy about, the
#     identical idiom class Nasai's own `COMMENTARY_NEVER_CUT` covers; one
#     (3491, "وأنهى أمتي عن الكي رفعه") is a terse, unattributed isnad note
#     with no narrator's name to anchor a boundary on (unlike Nasai's own
#     "رفعه <name>" shape) -- left as four residual characters on an
#     otherwise-genuine matn, a measured, disclosed judgement call: it risks
#     neither a false EXACT nor a NOT_FOUND, so it is not the class this
#     ruling exists to close.
#   - "غريب" bare (1, "كن في الدنيا كأنك غريب" -- be a STRANGER in this
#     world), "ضعيف" (4, a WEAK, oppressed man), "خطأ" bare (2, killed/died
#     BY MISTAKE, legal terminology), "الصواب" (2, "let him seek out what is
#     nearest to being CORRECT" during prayer -- the identical doctrinal
#     content Nasai's own 1240-1247 exceptions already established for this
#     word), "لم يسمع" (1, "he saw the WOMEN HAD NOT HEARD [the sermon]") --
#     every one read, every one an ordinary sense of a common word in the
#     only occurrences this file has, never editorial.
#
# Two further one-off remarks by OTHER named individuals -- neither tracked
# voice -- were found ("قال محمد بن يحيى وهو الصواب ...", hadith:342; "قال
# أبو عاصم ... مرسل ...", hadith:2497) but BOTH sit entirely inside
# `addenda_ar` already: the source's own "*" already isolates a full
# alternate chain there, and these remarks are INSIDE that already-cut
# secondary narration -- confirmed by checking `matn_ar` alone, not the
# joined display text used for the sweeps above. No action needed and none
# is taken. A remark naming neither tracked voice and landing in the SCORED
# primary would be the same "known ceiling" R-A3-23 already accepted for Abu
# Dawud's bare "قلت" self-reference -- not chased here for the same reason.
# (Softened, task-16 A5: this was originally written as "and measurement
# found none to exist," which overclaims. The Task 15 review found ONE shape
# that IS exactly this -- a third-party gloss, e.g. "قال علي الطنافسي يعني
# ..." (hadith:ibnmajah:2427) -- naming neither tracked voice and sitting in
# scored text. It is not unique to Ibn Majah: the same "قال X يعني" gloss
# shape sits in scored text_ar across all six collections, measured causing
# no false verdict in any of them. It is a shared, pre-existing ceiling of
# this splitter, not something particular to the two voices tracked here,
# and not chased for the same reason the bare "قلت" ceiling above is not.)
_IBNMAJAH_QATTAN_TIGHT, _IBNMAJAH_QATTAN_NEAR, _IBNMAJAH_QATTAN_HEARD = \
    _compiler_commentary_markers("أبو الحسن")
_IBNMAJAH_COMPILER_TIGHT, _IBNMAJAH_COMPILER_NEAR, _IBNMAJAH_COMPILER_HEARD = \
    _compiler_commentary_markers("أبو عبد الله")

# Combining two collections' worth of markers with a bare "|" (rather than
# giving Ibn Majah two independent split passes) keeps `_split_compiler_
# commentary`'s own "earliest candidate wins" rule working across BOTH
# voices at once: `re.Pattern.search` already returns the leftmost match of
# an alternation, so a record where the transmitter's remark precedes the
# compiler's own (or vice versa) is still cut at whichever comes first,
# exactly as the single-voice collections already are.
_IBNMAJAH_COMMENTARY = re.compile(
    rf"(?:{_IBNMAJAH_QATTAN_TIGHT.pattern})|(?:{_IBNMAJAH_COMPILER_TIGHT.pattern})")
_IBNMAJAH_COMMENTARY_NEAR = re.compile(
    rf"(?:{_IBNMAJAH_QATTAN_NEAR.pattern})|(?:{_IBNMAJAH_COMPILER_NEAR.pattern})")
_IBNMAJAH_HEARD = re.compile(
    rf"(?:{_IBNMAJAH_QATTAN_HEARD.pattern})|(?:{_IBNMAJAH_COMPILER_HEARD.pattern})")

# hadith:ibnmajah:3458's "حدثنا أبو الحسن القطان ثنا إبراهيم بن نصر ..." is
# the ONE occurrence in the whole file (measured across isnad_ar and
# matn+addenda both) where al-Qattan's remark is introduced by a
# transmission verb (حدثنا/ثنا/أخبرنا/أنبأنا/حدثناه) instead of قال/سئل --
# `_compiler_commentary_markers`'s own tight/near never reach it, and widening
# that SHARED generator's verb set would change abudawud/tirmidhi/nasai's
# byte-identical output for a single Ibn Majah record. Anchored on the exact
# phrase, not the bare verb set, because "حدثنا" alone opens the vast
# majority of this file's own isnad chains and a bare verb+kunya pattern
# would false-positive on every one of them.
#
# hadith:ibnmajah:309's "سمعت محمد بن يزيد أبا عبد الله يقول سمعت أحمد بن عبد
# الرحمن المخزومي يقول ..." -- found by `find_near_misses`'s own sweep, not
# by the read-through above -- is the ONE occurrence (measured: `grep -c`
# against the raw file) where Ibn Majah's own name, "محمد بن يزيد", is
# inserted in apposition between "سمعت" and his kunya "أبا عبد الله": the
# transmitter naming him in full before the kunya that identifies him. This
# sits outside `_compiler_commentary_markers`'s own token-gap tolerance for
# `heard`, and widening that SHARED generator's gap would reach past the
# genuine narrative on abudawud/tirmidhi/nasai's records too. Anchored on the
# exact phrase for the same reason as 3458's "حدثنا أبو الحسن القطان" above --
# a single record, not a general verb-plus-name shape. Left uncorrected, the
# primary matn would run on through an entire further discussion comparing
# this hadith against 'A'isha's contradicting report ("... yabulu qa'idan
# ... a'lamu bihadha minha ...") -- a different, and differently attested,
# report, not this hadith's own wording.
_IBNMAJAH_FORMULA = re.compile(
    rf"(?<![{_ARABIC}])هذا\s+حديث(?![{_ARABIC}])"
    rf"|(?<![{_ARABIC}])قال(?:ه)?\s+(?:محمد\s+)?بن\s+ماجة(?![{_ARABIC}])"
    rf"|(?<![{_ARABIC}])حدثنا\s+أبو\s+الحسن\s+القطان(?![{_ARABIC}])"
    rf"|(?<![{_ARABIC}])سمعت\s+محمد\s+بن\s+يزيد\s+أبا\s+عبد\s+الله(?![{_ARABIC}])")

# --- al-Bukhari's own compiler commentary (Task 16 A1, ruling R-A3-18) ------
#
# Al-Bukhari (kunya "أبو عبد الله" -- #META# 010.AuthorNAME: "محمد بن إسماعيل
# أبو عبدالله البخاري الجعفي") appends his OWN editorial voice after a matn
# with no structural marker, the same R-A3-18 defect first found in Abu Dawud
# and swept from four collections in Tasks 12-15; Bukhari and Muslim were the
# two never swept. Verb+kunya, so DERIVED from the shared
# `_compiler_commentary_markers` generator (kunya "أبو عبد الله"), never
# hand-written -- the exact construction Ibn Majah's OWN compiler voice uses
# too (Muhammad ibn Yazid's kunya is also "أبو عبد الله"): a different person,
# a different collection, keyed separately, so no collision.
#
# Measured against the parsed matn_ar of all 7,129 units (the SCORED field,
# not the joined display text):
#   - NOMINATIVE "قال/سئل أبو عبد الله" (the `tight` marker): 90 occurrences,
#     EVERY ONE read in context (see task-16 report) -- al-Bukhari's own
#     post-matn gloss ("يعني ..."), grammatical/lexical explanation, corrob-
#     orating chain ("تابعه ..."/"وزاد ..."/"قال بن عيينة ..."), or narrator
#     identification. Not one is a narrator named Abu Abdallah delivering
#     hadith content: the kunya is used for narrators elsewhere in this file
#     ONLY in the genitive (isnad) or the vocative, never as a nominative
#     "قال" subject at a matn's tail. The head before every one is a complete
#     Prophetic/Companion matn clause.
#   - `near` (one-token gap) and `heard` ("سمعت أبا عبد الله"): 0 each -- no
#     record needs them; they are inert fallbacks, kept only because the
#     shared generator builds them.
#   - ACCUSATIVE "أبا عبد الله": 2, BOTH the vocative "يا أبا عبد الله" (363,
#     2821 -- a Companion addressed mid-narration), genuine narrative,
#     correctly untouched (`heard` requires a preceding "سمعت", not "يا").
#   - GENITIVE "أبي عبد الله": 1, "عن أبي عبد الله عن قبيصة" (3263) -- a
#     narrator in an isnad, correctly untouched (the generator builds no
#     genitive pattern, R-A3-23).
#
# Two ungoverned nominatives are deliberately left in the scored matn, both
# the same "known ceiling" R-A3-23 accepted for a bare "قلت" self-reference:
#   - hadith:bukhari:112 "... القتل أو الفيل شك أبو عبد الله وسلط عليهم ..." --
#     "Abu Abdallah [al-Bukhari] was uncertain [which word]", a three-word
#     aside in the MIDDLE of the narration, not a tail; the verb is "شك", not
#     "قال"/"سئل", so it is never matched, and this record is cut at its own
#     genuine later "قال أبو عبد الله" tail regardless.
#   - hadith:bukhari:2569 "... وأصح عندي قاله أبو عبد الله": al-Bukhari's own
#     verdict closing a long block of variant-chain collation ("قال شعبة عن
#     مغيرة ...", "وقال إسحاق ..."). The compiler's voice here is remark-FIRST
#     ("قاله" = "he said IT", the attribution trailing the remark), so a cut
#     anchored on it would move only "قاله أبو عبد الله" and leave the whole
#     apparatus on the primary -- the wrong direction. The apparatus itself is
#     introduced by narrator-attributed variant chains ("قال شعبة عن ..."),
#     the bare "قال <name>" shape `_apply_cut_override`'s own docstring and
#     al-Nasai's carried residue both refuse a generic fix for. Disclosed, not
#     patched, and reported to Task 16's own residue pass -- see the report.
#
# One transmitter formula IS added, `_BUKHARI_FORMULA` below: al-Bukhari's
# apparatus is often a CHAIN -- "[genuine matn] قال الفربري قال أبو جعفر [بن
# أبي حاتم] قال أبو عبد الله ..." -- where Muhammad ibn Yusuf al-Firabri (the
# Sahih's own primary transmitter, the same role al-Lu'lu'i plays for Abu
# Dawud and al-Qattan for Ibn Majah, R-A3-21) relays al-Bukhari's remark. The
# kunya marker alone cuts only at the LAST link ("قال أبو عبد الله") and
# leaves "قال الفربري قال أبو جعفر ..." fused on the scored primary -- exactly
# the "cut at the earliest genuine boundary, not the first a single pattern
# finds" failure R-A3-19 warns of. Measured: it is a genuine false NEGATIVE,
# hadith:bukhari:2322's own matn scoring 0.839 (< 0.86) against its own stored
# text before this arm was added. "قال الفربري" occurs in matn_ar exactly 3
# times (2322, 2343, 6132), EVERY ONE the transmitter's tail apparatus, never
# a hadith narrator (al-Firabri is three generations past the Prophet and
# appears in no isnad). "قال أبو جعفر" is deliberately NOT added: it occurs
# twice in matn, once as this apparatus (2322, already reached via the earlier
# "قال الفربري") and once (5128) as a GENUINE narrator (Abu Ja'far al-Baqir)
# delivering hadith content -- the bare "قال <name>" hazard a generic cut is
# refused for.
_BUKHARI_COMMENTARY, _BUKHARI_COMMENTARY_NEAR, _BUKHARI_HEARD = \
    _compiler_commentary_markers("أبو عبد الله")
_BUKHARI_FORMULA = re.compile(rf"(?<![{_ARABIC}])قال\s+الفربري(?![{_ARABIC}])")

# --- Muslim's own compiler commentary (Task 16 A1, ruling R-A3-18) ----------
#
# Muslim ibn al-Hajjaj (kunya "أبو الحسين" -- #META# 010.AuthorNAME: "مسلم بن
# الحجاج أبو الحسين القشيري النيسابوري") interjects his own voice far less
# often than the four Sunan compilers, and almost always by NAME ("قال مسلم"),
# not by kunya. Measured against the parsed matn_ar of all 7,460 units:
#   - NAME "قال مسلم" (`_MUSLIM_FORMULA`, the collection-specific `extra`
#     arm): 24 occurrences, EVERY ONE read in context (see task-16 report) --
#     narrator identification ("قال مسلم أبو جمرة اسمه نصر بن عمران ..."),
#     alternate-chain note ("قال مسلم ورواه الأشجعي ..."), Muslim's own
#     transmission note ("قال مسلم قرأت على عيسى بن حماد ..."), or his own
#     uncertainty/correction ("قال مسلم لا أدري ...", "قال مسلم أخطأ ..."). Not
#     one is a narrator named Muslim delivering hadith content. Anchored on the
#     BARE "قال مسلم" with no و/ف proclitic on purpose: the one proclitic
#     occurrence, "فقال مسلم" at hadith:muslim:404-2, sits in the MIDDLE of an
#     isnad-critique dialogue ("قال أبو إسحاق قال أبو بكر ... فقال مسلم تريد
#     أحفظ من سليمان فقال له أبو بكر ..."), where a cut at "فقال مسلم" would
#     strand "قال أبو إسحاق قال أبو بكر ..." on the primary -- the same bare
#     "قال <name>" dialogue shape a generic fix is refused for; disclosed, not
#     cut. The lookahead "(?![ARABIC])" keeps "مسلم" a whole word (never
#     "مسلمة"/"المسلمين"/"مسلمون").
#   - NOMINATIVE kunya "قال أبو الحسين" (the shared generator's `tight`): 2
#     (711, 1647-2), both "قال أبو الحسين مسلم ..." -- Muslim naming himself by
#     kunya AND name, correcting a chain, unambiguously his own voice.
#   - `near`/`heard`: 0 each. ACCUSATIVE/GENITIVE kunya in matn_ar: 0 each --
#     no narrator-collision to guard against, unlike Bukhari's file.
_MUSLIM_COMMENTARY, _MUSLIM_COMMENTARY_NEAR, _MUSLIM_HEARD = \
    _compiler_commentary_markers("أبو الحسين")
_MUSLIM_FORMULA = re.compile(rf"(?<![{_ARABIC}])قال\s+مسلم(?![{_ARABIC}])")


_COMPILER_MARKERS: dict[
    str, tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str],
               re.Pattern[str] | None]
] = {
    # Bukhari (Task 16 A1): kunya markers PLUS al-Firabri's transmitter
    # formula (`_BUKHARI_FORMULA`), which marks the earlier boundary of the
    # apparatus chain the kunya alone under-cuts.
    "bukhari": (_BUKHARI_COMMENTARY, _BUKHARI_COMMENTARY_NEAR,
                _BUKHARI_HEARD, _BUKHARI_FORMULA),
    # Muslim (Task 16 A1): kunya markers PLUS the "قال مسلم" name formula.
    "muslim": (_MUSLIM_COMMENTARY, _MUSLIM_COMMENTARY_NEAR,
               _MUSLIM_HEARD, _MUSLIM_FORMULA),
    # Byte-identical to the pre-Task-13 tuple used at Abu Dawud's own call
    # site: same three patterns, same objects, no fourth (non-kunya) formula.
    "abudawud": (_ABUDAWUD_COMMENTARY, _ABUDAWUD_COMMENTARY_NEAR,
                 _ABUDAWUD_HEARD, None),
    "tirmidhi": (_TIRMIDHI_COMMENTARY, _TIRMIDHI_COMMENTARY_NEAR,
                 _TIRMIDHI_HEARD, _TIRMIDHI_FORMULA),
    "nasai": (_NASAI_COMMENTARY, _NASAI_COMMENTARY_NEAR, _NASAI_HEARD,
              _NASAI_FORMULA),
    "ibnmajah": (_IBNMAJAH_COMMENTARY, _IBNMAJAH_COMMENTARY_NEAR,
                 _IBNMAJAH_HEARD, _IBNMAJAH_FORMULA),
}


def _split_compiler_commentary(
    matn: str, addenda: str | None, tight: re.Pattern[str],
    near: re.Pattern[str], extra: re.Pattern[str] | None = None, *,
    record_id: str | None = None,
    never_cut: dict[str, tuple[str, str]] | None = None,
) -> tuple[str, str | None]:
    """Cut a collection's own compiler commentary from a matn, appending it
    to whatever addendum `_split_secondary` already found (or starting one).

    `tight`/`near` are the (verb, kunya) pair `_compiler_commentary_markers`
    built for this collection; `extra`, when given, is a further,
    collection-specific formula that marks the SAME kind of boundary without
    naming the compiler at all (Tirmidhi's "وفي الباب"/"هذا حديث", Nasai's
    "خالفه"/"هذا خطأ"/"والصواب" -- see `_TIRMIDHI_FORMULA`/`_NASAI_FORMULA`).
    Between `tight` and `extra` the EARLIEST match wins, per the ruling's
    instruction to cut at the earliest genuine boundary, not merely the first
    one a single pattern happens to find; `near` is tried only as a fallback
    when NEITHER of those finds anything, preserving the "tight first, widen
    only if the tight search truly finds nothing" discipline `near` was built
    for.

    `record_id`/`never_cut` are a hand-read do-not-cut audit exactly like
    `_split_secondary`'s own (`_audited_never_cut`), but keyed to the matn as
    it stands at THIS call site, not the earlier one -- see
    `audit_lists.COMMENTARY_NEVER_CUT`'s own docstring for why it is a
    separate dict rather than a reuse of `NEVER_CUT`. Needed for `extra`
    formulas built from a general shape ("خالفه <name>" reads as "so-and-so
    differed from him [in transmission]" on every measured occurrence but
    one, hadith:nasai:3047, where the same verb form is genuine narrative
    describing the Prophet's own act) rather than a name that never occurs in
    ordinary speech.

    Cuts on what FOLLOWS the marker, not what precedes it -- the compiler's
    remark is itself the secondary material, exactly as a fresh narration's
    isnad is. Never invents a cut: if no marker is present, the matn and
    addendum returned are the ones passed in, unchanged.
    """
    if (record_id is not None and never_cut
            and _audited_never_cut(record_id, matn, never_cut)):
        return matn, addenda
    candidates = sorted(
        (m for m in (tight.search(matn), extra.search(matn) if extra else None)
         if m is not None),
        key=lambda m: m.start())
    # Try the earliest candidate first, but an empty head is a reason to try
    # the NEXT one, not to give up on the record entirely (R-A3-25, Task 14
    # fix round): Nasai's bare classification tags ("مرسل"/"موقوفا") are the
    # first thing this file's marker table ever puts at a matn's own
    # position 0 -- hadith:nasai:5194 opens "مرسل قال أبو عبد الرحمن
    # والمراسيل أشبه بالصواب ..." and, with "مرسل" now in `extra`, the
    # earliest candidate is that position-0 match, which must be rejected --
    # but `tight`'s own later match ("قال أبو عبد الرحمن") is still a
    # perfectly good boundary and must not be abandoned just because a
    # different, earlier candidate happened to fail the head check first.
    # Measured: for every marker that predates this fix round (Abu Dawud's,
    # Tirmidhi's, and Nasai's own "خالفه"/"هذا خطأ"/"هذا حديث"/"والصواب"), no
    # record's matn ever opens directly on the marker, so this loop is a
    # strict no-op for all of them -- it changes behaviour only for the new
    # bare-tag arms that can legitimately sit at position 0.
    m = None
    for cand in candidates:
        if matn[: cand.start()].rstrip():
            m = cand
            break
    if m is None:
        near_m = near.search(matn)
        if near_m is not None and matn[: near_m.start()].rstrip():
            m = near_m
    if m is None:
        return matn, addenda
    head = matn[: m.start()].rstrip()
    tail = matn[m.start() :]
    return head, tail if addenda is None else f"{tail} {addenda}"


# --- hadith:nasai:400's own isnad/matn boundary (Task 14 fix round, R-A3-25
# item 5) -----------------------------------------------------------------
#
# The source's own "*" marks the FIRST isnad/matn boundary (see the
# secondary-narration section above), but here it lands after a SECOND
# narrator's discussion of the hadith, not after the hadith itself: "... عن
# أبي هريرة قال لا يبولن أحدكم في الماء الدائم الذي لا يجري ثم يغتسل منه قال
# سفيان قالوا لهشام يعني بن حسان أن أيوب إنما ينتهي بهذا الحديث إلى أبي هريرة
# فقال * إن أيوب لو استطاع أن لا يرفع حديثا لم يرفعه" -- Sufyan relaying that
# others asked Hisham (ibn Hassan) whether Ayyub always traces this hadith
# back to Abu Hurayrah, and Hisham's reply ("if Ayyub could avoid raising a
# hadith [to the Prophet], he would not raise it") is what the source's own
# mark isolates. The genuine, famous matn -- "do not urinate in standing
# water, then wash from it" -- sits BEFORE the "*", inside what the base
# split treats as `isnad_ar`, so 100% of the scored `text_ar` was Hisham's
# remark about Ayyub, not the hadith.
#
# `_ATTRIBUTION`'s own boundary discipline (used unmodified, not a new
# pattern) finds this isnad's 4 "qala" attributions by construction: the 1st
# is the chain's own "Qutayba SAID: Sufyan narrated to us ..."; the 2nd is
# "'an Abi Hurayrah QALA" -- Abu Hurayrah's own attribution, where the
# genuine matn actually begins; the 3rd is "QALA Sufyan", which opens the
# narrator-to-narrator discussion that belongs in `addenda_ar`; the 4th is
# the source's own "fa-qala" immediately before its "*". Splitting on the
# 2nd and 3rd recovers the correct boundary the source's single "*" could
# not express on its own.
#
# A corpus-wide sweep for the two idioms unique to this exact remark ("لو
# استطاع" / "ينتهي بهذا الحديث") found ONE occurrence total -- this record.
# A widened, non-idiom-specific heuristic (a "*" preceded by a nested
# "qala ... fa-qala" discussion) surfaced 5 further raw candidates; every one
# read in context has the genuine matn correctly AFTER its own "*" already
# (the "qala X, Y said ..." shape is ordinary narrated dialogue there, not
# editorial discussion) or is an artefact of scanning across a record
# boundary, not a second instance of this defect. A fully exhaustive,
# non-idiom-anchored sweep of every "*" boundary in the file is a Task 16
# item (out-of-scope observation 2), not repeated here.
_NASAI_400_ISNAD_SHA256 = (
    "bbad24ad0dd214d4e5ed97942d8a81039a2b7de9de02fbff6b45a790721fa2fe")


def _fix_nasai_400_isnad_matn_split(
    isnad: str | None, matn: str, addenda: str | None, record_id: str
) -> tuple[str | None, str, str | None]:
    """No-op for every record except hadith:nasai:400 (verified by sha256 of
    its ORIGINAL, unsplit isnad). See the comment above `_ATTRIBUTION`'s use
    here for why this one record needs a hand-derived boundary rather than
    the source's own "*".
    """
    if record_id != "hadith:nasai:400" or isnad is None:
        return isnad, matn, addenda
    digest = hashlib.sha256(isnad.encode("utf-8")).hexdigest()
    if digest != _NASAI_400_ISNAD_SHA256:
        raise ValueError(
            "hadith:nasai:400 is on the isnad/matn split-boundary override "
            "list, but its isnad is no longer the text that was audited. "
            "Read the record in the source, decide the boundary again, and "
            "update or remove the override.")
    attributions = list(_ATTRIBUTION.finditer(isnad))
    new_isnad = isnad[: attributions[1].end()].rstrip()
    new_matn = isnad[attributions[1].end() : attributions[2].start()].strip()
    tail_from_isnad = isnad[attributions[2].start() :].strip()
    new_addenda = f"{tail_from_isnad} {matn}" if addenda is None \
        else f"{tail_from_isnad} {matn} {addenda}"
    return new_isnad, new_matn, new_addenda


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


def find_prefix_collisions(
    norms: dict[str, str], *, max_dropped: int = 8, min_head_tokens: int = 3
) -> list[tuple[str, int, str]]:
    """Fix round 2's own vocabulary-free false-negative detector (R-A3-27).

    `find_near_misses` above only widens a parameter of a marker someone
    already configured -- it can never find a formula nobody named. This
    function names nothing: for every record's `norm_standard`, it drops 1
    to `max_dropped` trailing TOKENS and checks whether what remains is
    byte-identical to some OTHER record's COMPLETE `norm_standard`, anywhere
    in the corpus. A hit means "this record's head, once you delete a short
    tail, is a hadith some other record already states in full" -- exactly
    the shape of a fused editorial tail the marker tables in this file are
    built to cut, found by a structural property (a duplicated head) rather
    than by recognising any particular Arabic word.

    Deliberately DB-agnostic and collection-agnostic, unlike `find_near_
    misses` (which takes in-memory `HadithUnit`s from a single collection's
    parse): the corpus-wide comparison this needs -- one record's head
    against every OTHER record's complete text, hadith or Qur'an, any
    collection -- only exists in `norm_standard`, a column `materialize.py`
    populates from the built DB, not in anything a single collection's
    parser holds while it runs. `norms` is therefore keyed by record id
    across the WHOLE corpus, supplied by the caller (a DB query), not
    derived here.

    A LOWER BOUND, not a completeness proof: a genuine fused tail is only
    findable this way if some OTHER record happens to preserve the same
    head in full elsewhere in the corpus. A unique hadith whose only copy
    carries a fused editorial tail, with no parallel narration anywhere
    else, produces no collision and is invisible to this function --
    exactly as it was invisible to the review that first measured this
    fix round's six shapes by other means (direct reading, not this
    detector, is what closed the family; this detector is what discovered
    that a family existed in the first place).

    Raw output is NOISY and needs a human pass, not a bare emptiness
    assertion: the majority of collisions in a hadith corpus are the
    ordinary, correctly-scored feature of multiple narrations of the same
    report agreeing on a shared head and differing only at the edges (see
    `tests/ingest/test_real_corpus.py`'s own gate, keyed to a pinned,
    hand-read residue list for al-Nasai -- the only collection this fix
    round audited -- not to "zero hits"). `min_head_tokens` guards against
    matching on a handful of common opening words shared by unrelated
    reports (e.g. "قال رسول الله صلى الله عليه وسلم") with no real
    provenance content.
    """
    index: dict[str, str] = {}
    for record_id, norm in norms.items():
        index.setdefault(norm, record_id)
    hits: list[tuple[str, int, str]] = []
    for record_id, norm in norms.items():
        tokens = norm.split()
        for dropped in range(1, min(max_dropped, len(tokens) - min_head_tokens) + 1):
            head = " ".join(tokens[:-dropped])
            if len(head) < 1:
                continue
            other = index.get(head)
            if other is not None and other != record_id:
                hits.append((record_id, dropped, other))
                break
    return sorted(hits)


# --- Whole-string pure-pointer detector (Task 16 A2 round 3, R-A3-18 class) ---
#
# The false-EXACT back-reference class escaped THREE closures, each on the axis
# the previous fix held fixed: A2's duplicate-string grouping keyed on identical
# WHOLE strings (missed unique singletons); the C0 round keyed on the LEADING
# particle (missed the construction when it sat mid-string). This detector is
# POSITION-INDEPENDENT by construction: it never looks at the first token, the
# string length, or whether two records share a string. It asks a structural
# question of the WHOLE token bag -- "once every reference/pointer/chain/name
# token is removed, is there any NARRATION left?" -- and a back-reference that
# moved to the middle, got a new leading particle, or is a one-off singleton
# answers that question identically to one at the front.
#
# All sets are in NORM_AGGRESSIVE form (alef forms -> alef, alef-maqsura -> yeh,
# teh-marbuta -> heh, diacritics and non-Arabic stripped, tatweel removed), so
# the caller passes `norm_aggressive` (the column materialize already derives),
# the same way `find_prefix_collisions` takes `norm_standard`. Matching on the
# folded form means an orthographic variant of a pointer word cannot dodge the
# sweep, which is the whole point of not re-introducing a brittle literal list.

# A reference to ANOTHER narration: the record points at a hadith/riwaya given
# elsewhere, or at a chain, rather than reporting anything itself.
_PP_REF_NOUN = frozenset((
    "حديث", "حديثه", "حديثها", "حديثهم", "حديثهما", "حديثي", "حديثهن", "حديثك",
    "روايه", "روايته", "روايتهما", "روايتهم", "روايتها", "الحديث", "الحديثين",
    "وحديث",
))
_PP_CHAIN = frozenset((
    "اسناد", "الاسناد", "باسناد", "باسناده", "باسنادهما", "باسناديهما",
    "الاسنادين", "بالاسنادين", "بالاسناد", "باسنادهم", "باسنادي", "باسنادهن",
    "اسناده", "اسنادهما", "اسنادهم", "باسنادينا",
))
# Standalone pointer pronouns ("the like of it", "its meaning") -- always a
# back-reference on their own, unlike bare "mithl"/"nahw" which can be matn
# ("the likeness of the believer ...").
_PP_PTR_PRON = frozenset((
    "مثله", "بمثله", "نحوه", "بنحوه", "بمعناه", "معناه", "بمعناهما", "مثلها",
    "نحوها", "بمثلها", "بنحوها", "مثلهما", "نحوهما", "بمثلهما", "معناهما",
    "نحوهم", "بمثلهم", "ومعناه", "ونحوه", "ومثله",
))
# Comparison particles -- only an anchor when bound directly to a reference noun
# ("mithl HADITH X"); on their own they are ordinary matn.
_PP_PTR_CMP = frozenset((
    "مثل", "بمثل", "نحو", "بنحو", "بمعني", "معني", "كمعني", "ومعني", "وبمعني",
    "ونحو", "ومثل",
))
# Pure connective / demonstrative / chain-glue carrying no narration, plus the
# bare isnad-frame nouns ("rasul Allah", "al-nabi") and transmission verbs
# ("sami'a", "rafa'a") that frame WHO narrated rather than WHAT -- so a record
# that is nothing but "'an al-nabi [saw] ... bi-mithl hadith X" or "sami'a
# rasul Allah ... bi-mithlihi" reduces to a bare frame (empty residue), while a
# record that also states an ACT or OBJECT keeps that word in the residue. A
# genuine matn carries more than the frame, so these stay above the threshold.
_PP_GLUE = frozenset((
    "في", "هذا", "هذه", "بهذا", "بهذه", "ذلك", "كذلك", "جميعا", "كليهما",
    "كلاهما", "كلتيهما", "معا", "سواء", "بينهما", "كلها", "كله", "ايضا",
    "فيهما",
    # isnad-frame nouns
    "رسول", "رسوله", "النبي", "نبي", "الله",
    # bare transmission / hearing / raising verbs (frame, not content)
    "سمع", "سمعت", "رفع", "رفعه", "يرفع", "يرفعان", "رفعا",
))
# Tokens that INTRODUCE a narrator-name chain (the next token is a name).
_PP_INTRO = frozenset((
    "عن", "وعن", "بن", "وبن", "ابن", "وابن", "حديث", "حديثه", "حديثها",
    "حديثهم", "حديثهما", "روايه", "روايته", "روايتهما", "وحديث",
))
# A2 round 5 (Task 16): the speech-FRAME verbs. For the vocabulary-free
# content-mass measure (`content_mass` below), a frame verb introduces WHO
# spoke, not WHAT, so "qala <narrator-name>" / "sami'tu <narrator>" with
# nothing delivered after it is scaffold -- it must absorb a following name
# exactly like `_PP_INTRO` does, so a pure pointer wrapped in a frame
# ("bi-hadha l-isnad mithlahu wa-qala sami'tu rasula llah") reduces to EMPTY
# content, whatever frame word it hid behind. This is deliberately the SAME
# token family the round-4 sweep EXCLUDED as `_PP_DELIVERS`; the round-5 cure
# is NOT to add a qala exception but to stop keying the detector on this word
# at all -- content_mass counts what is LEFT, which for a genuine delivered
# "qala: <words>" is the words (high mass) and for a frame-only pointer is
# nothing (mass 0). It keys on no marker, so it catches a pointer regardless
# of which frame it uses. NOT used by `find_pure_pointers`, whose residue
# deliberately KEEPS these so a real "wa-zada Y" stays scorable.
_PP_FRAME_INTRO = frozenset((
    "قال", "قالا", "قالوا", "قالت", "قلت", "يقول", "تقول", "فقال", "وقال",
    "وقالا", "وقالت", "فقالت", "فقالوا", "وقالوا", "قالها", "سمعت", "سمع",
))
# Name-chain connectors (joins the next token onto the running name chain).
_PP_CONNECTOR = frozenset((
    "و", "بن", "وبن", "ابن", "وابن", "عن", "وعن", "ابي", "وابي", "ابو",
    "وابو", "ام", "وام", "بنت", "وبنت",
))
# Compound-name heads ("abd Allah", "abu Hurayra"): the following token is still
# part of the SAME name, so absorption must not stop after the first token.
_PP_NAME_HEAD = frozenset((
    "عبد", "عبيد", "ابو", "ابي", "ام", "ابن", "بن", "ذو", "وعبد", "وعبيد",
    "وابو", "وابي", "وابن", "وبن",
))
# Wording markers that STOP name absorption and count as residue, so a genuine
# added clause stays in the residue rather than being swallowed as a "name".
# This is deliberately BROAD (it includes deferral/frame/omission verbs like
# "fa-dhakara"/"sami'a"/"laysa"), because its only job here is to end a name
# chain -- it must NOT be used to pre-exclude a record from the sweep (a
# deferral or omission record is exactly what the sweep is hunting). The
# narrower `_PP_DELIVERS` below is what decides "this one genuinely quotes/adds
# words of its own, keep it scorable".
_PP_WDM = frozenset((
    "قال", "قالا", "قالوا", "قالت", "قلت", "يقول", "تقول", "فقال", "وقال",
    "وقالا", "وقالت", "فقالت", "فقالوا", "وقالوا",
    "زاد", "زادوا", "وزاد", "يزيد", "وزادوا", "فزاد", "زادا",
    "غير", "الا", "ليس", "وليس", "لم", "ولم", "وفيه", "فيه", "وفي", "وفيها",
    "رايت", "كان", "جعل", "فجعل", "يعني", "انه", "اني", "انها",
    "انهم", "يقل", "يذكر", "يذكرا", "يذكروا", "يشك", "قالها", "وانه", "فذكر",
    "ذكر",
))
# Genuine wording-DELIVERY markers: the record quotes speech ("qala ..."),
# adds words ("zada ..."), or states a difference ("ghayra anna ...", "illa
# anna ..."). A record carrying one of these delivers matn of its own and is
# NOT a pure pointer, so the sweep excludes it outright. Deliberately NARROW:
# deferral verbs ("dhakara", "saqa"), hearing/frame verbs ("sami'a", "kana"),
# glosses ("ya'ni") and omission notes ("laysa", "lam yadhkur") are NOT here --
# those ARE the pure-pointer shapes. (Three records -- muslim:2821-2, 2880-2,
# 2036-2 -- use "zada"/"qala" for a CHAIN addition or a dangling attribution,
# not a matn word; the sweep cannot tell, so those are added to UNSCORABLE by
# hand, documented there, not surfaced here.)
_PP_DELIVERS = frozenset((
    "قال", "قالا", "قالوا", "قالت", "قلت", "يقول", "تقول", "فقال", "وقال",
    "وقالا", "وقالت", "فقالت", "فقالوا", "وقالوا", "قالها",
    "زاد", "زادوا", "وزاد", "يزيد", "وزادوا", "فزاد", "زادا",
    "غير", "الا",
))
# Section-break artifact: a basmala that leaked onto the end of a pointer record
# when the next kitab opens (e.g. muslim:997-6). Canonical text, never altered,
# but it is not narration -- stripped only for THIS audit's residue test.
_PP_BASMALA = frozenset(("بسم", "الله", "الرحمن", "الرحيم"))
# The honorific formula, in norm_aggressive form, treated as an isnad frame
# rather than matn for the residue test (so "'an al-nabi [saw] bi-mithl hadith
# X" reduces to a bare frame, not a four-token residue).
_PP_HONORIFIC = re.compile(r"صلي الله عليه وسلم")


def _pp_anchored(tokens: list[str]) -> bool:
    """True if the token bag references another narration anywhere in it."""
    s = set(tokens)
    if s & _PP_REF_NOUN or s & _PP_CHAIN or s & _PP_PTR_PRON:
        return True
    # a bare comparison particle counts only when bound to a reference noun.
    for i, t in enumerate(tokens[:-1]):
        if t in _PP_PTR_CMP and tokens[i + 1] in _PP_REF_NOUN:
            return True
    return False


def content_mass(norm_aggressive: str) -> int:
    """A2 round 5 (Task 16): VOCABULARY-FREE content mass. The number of content
    tokens left in `norm_aggressive` after stripping ONLY non-matn scaffolding:
    honorific, basmala, leaked isnad/chain (`'an NAME`, `haddathana NAME`), the
    reference/pointer/deferral vocabulary, AND a speech frame that delivers
    nothing after it (`qala <narrator>`, `sami'tu <narrator> yaqul`). A pure
    pointer -- which defers instead of delivering -- carries almost no content
    whatever marker it hides behind, so it reduces to ~0; a genuine delivered
    "qala: <words>" / "zada: <words>" keeps its words and scores high.

    This is the PRIMARY net of round 5. It is the round-3/4 residue sweep with
    the escape removed TWICE over: (a) it does NOT exclude a record for carrying
    a delivery marker (the round-4 `_PP_DELIVERS` guard, which hid every pointer
    wrapped in a qala/yaqul frame), and (b) it absorbs a name after a frame verb
    (`_PP_FRAME_INTRO`), so "qala <narrator>" is scaffold, not content. It keys
    on NO marker word and NO position, which is the whole point: the seven prior
    closures each narrowed a filter and the next pointer walked through the
    exclusion. Content mass has no exclusion to walk through.

    Distinct from `find_pure_pointers`/`_pp_residue`, which KEEP frame verbs so a
    genuine "wa-zada Y" stays scorable there; here that job is done by keeping
    the WORDS after the frame, not the frame token.
    """
    tokens = _PP_HONORIFIC.sub(" ", norm_aggressive).split()
    if set(tokens) >= _PP_BASMALA:
        tokens = [t for t in tokens if t not in _PP_BASMALA]
    content: list[str] = []
    mode = "normal"
    for t in tokens:
        if t in _PP_FRAME_INTRO:
            mode = "expect_name"
            continue
        if mode == "expect_name":
            mode = "expect_name" if t in _PP_NAME_HEAD else "after_name"
            continue
        if mode == "after_name":
            if t in _PP_CONNECTOR:
                mode = "expect_name"
                continue
            mode = "normal"
        if t in _PP_WDM:
            mode = "normal"
            continue
        if t in _PP_INTRO:
            mode = "expect_name"
            continue
        if (t in _PP_REF_NOUN or t in _PP_CHAIN or t in _PP_PTR_PRON
                or t in _PP_PTR_CMP or t in _PP_GLUE):
            mode = "normal"
            continue
        content.append(t)
        mode = "normal"
    return len(content)



# A2 read sweep (Task 16): the bounded population P that was read by hand. The
# rulings over it (tests/ingest/data/pointer_sweep_rulings.tsv) are what keep
# pointers out of the index; content_mass only defines P. This is the ONE
# definition of P -- the gate in tests/ingest/test_real_corpus.py recomputes P
# with it, so changing it means re-reading whatever enters P.
POINTER_SWEEP_MAX_MASS = 7
_POINTER_SWEEP_REF = _PP_REF_NOUN | _PP_CHAIN | _PP_PTR_PRON | frozenset((
    "بهذا", "بذلك", "فذكر", "يذكر", "يذكرا", "يذكروا", "يقل",
))


def in_pointer_sweep_population(norm_aggressive: str) -> bool:
    """True if a scorable record belongs to the read-sweep population P:
    content_mass <= 7, or any reference/omission token in its token bag."""
    return (content_mass(norm_aggressive) <= POINTER_SWEEP_MAX_MASS
            or bool(set(norm_aggressive.split()) & _POINTER_SWEEP_REF))

def _pp_residue(norm_aggressive: str) -> list[str]:
    """Remove every reference/pointer/chain/name/honorific/basmala token and
    return what is LEFT. An empty (or near-empty) residue means the whole
    record is scaffold -- a pure pointer. A wording-delivery marker (and the
    words after it) stays in the residue, which is how a genuine "wa-zada Y"
    addition keeps itself scorable.

    Name absorption is BOUNDED (a short "<name> (bn|'an|...) <name>" chain,
    honouring compound heads like "'abd Allah") and STOPS at a wording-delivery
    marker, so it can never swallow a real added-matn clause the way an
    unbounded "absorb until scaffold" rule would.
    """
    tokens = _PP_HONORIFIC.sub(" ", norm_aggressive).split()
    if set(tokens) >= _PP_BASMALA:
        tokens = [t for t in tokens if t not in _PP_BASMALA]
    residue: list[str] = []
    mode = "normal"
    for t in tokens:
        if t in _PP_WDM:
            residue.append(t)
            mode = "normal"
            continue
        if mode == "expect_name":
            mode = "expect_name" if t in _PP_NAME_HEAD else "after_name"
            continue
        if mode == "after_name":
            if t in _PP_CONNECTOR:
                mode = "expect_name"
                continue
            mode = "normal"  # fall through to classify t below
        if t in _PP_INTRO:
            mode = "expect_name"
            continue
        if (t in _PP_REF_NOUN or t in _PP_CHAIN or t in _PP_PTR_PRON
                or t in _PP_PTR_CMP or t in _PP_GLUE):
            mode = "normal"
            continue
        residue.append(t)
        mode = "normal"
    return residue


def find_pure_pointers(
    norms: dict[str, str], *, max_residue: int = 2, exclude_delivery: bool = True
) -> list[tuple[str, int, tuple[str, ...]]]:
    """Corpus-wide, position-independent sweep for scorable records whose matn
    is pure back-reference / structural-pointer / chain-meta / deferral scaffold
    with no narration of its own -- the R-A3-18 false-EXACT class (see the big
    comment block above for why the prior three closures leaked).

    `norms` maps record id -> `norm_aggressive` (the caller supplies it, keyed
    across the whole corpus, exactly as `find_prefix_collisions` takes
    `norm_standard`); the caller is expected to pass ONLY scorable hadith
    primaries, since an already-`UNSCORABLE` record is not what this sweep is
    hunting. Returns `(record_id, residue_size, residue_tokens)` for every
    record that (a) references another narration anywhere in its token bag and
    (b) carries no wording-delivery marker, with the non-scaffold residue no
    larger than `max_residue`.

    Like `find_prefix_collisions`, this is an AUDIT, not a filter: a non-empty
    result is NOT automatically unscorable. Every hit must be read BOTH ways --
    a residue of a genuine report clause ("naha 'an al-wisal", "min katama
    ghallan fa-innahu mithluhu") is a KEEP, and over-marking one of those as
    unscorable makes a real hadith unverifiable. The call site therefore pins
    the audited KEEP residue (see `tests/ingest/test_real_corpus.py`), not an
    emptiness assertion: the convergence proof is "the sweep comes back holding
    ONLY the hand-read justified KEEPs", not "the sweep comes back empty".

    `exclude_delivery` (A2 round 5): the round-3/4 default (True) drops any
    record carrying a `_PP_DELIVERS` marker, to protect a genuine "wa-zada Y".
    That guard was the round-4 escape -- a pointer wrapped in a qala/yaqul frame
    walked through it. The round-5 secondary net (net B) calls this with
    `exclude_delivery=False` to see the WHOLE reference-bearing population with
    no delivery exclusion; the content-free members it then surfaces are the
    same ones `content_mass` catches vocabulary-free, which is the cross-check.
    """
    hits: list[tuple[str, int, tuple[str, ...]]] = []
    for record_id, norm in norms.items():
        tokens = _PP_HONORIFIC.sub(" ", norm).split()
        if not _pp_anchored(tokens):
            continue
        if exclude_delivery and set(tokens) & _PP_DELIVERS:
            continue
        residue = _pp_residue(norm)
        if len(residue) <= max_residue:
            hits.append((record_id, len(residue), tuple(residue)))
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
    collection: str,
    max_addendum: int = audit_lists.MAX_ADDENDUM,
    attribution_window: int = audit_lists.ATTRIBUTION_WINDOW,
    never_cut: dict[str, tuple[str, str]] | None = None,
    unscorable: dict[str, tuple[str, str]] | None = None,
    cut_override: dict[str, tuple[str, int]] | None = None,
    lului_never_cut: dict[str, tuple[str, str]] | None = None,
    near_miss_cut_override: dict[str, tuple[str, int]] | None = None,
    commentary_never_cut: dict[str, tuple[str, str]] | None = None,
    on_presplit: Callable[[str, str | None, str], None] | None = None,
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
    if commentary_never_cut is None:
        commentary_never_cut = audit_lists.COMMENTARY_NEVER_CUT.get(
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

        # R-A3-28's byte-conservation invariant needs a snapshot of `isnad`/
        # `matn` exactly here -- already `_clean`-ed, but before ANY of the
        # split functions below (`_split_secondary`, `_apply_cut_override`,
        # `_split_compiler_commentary`, `_split_lului_commentary`,
        # `_split_heard_commentary`, `_fix_nasai_400_isnad_matn_split`) has
        # had a chance to move or drop a single byte. A test comparing THIS
        # tuple to the unit's final isnad_ar/matn_ar/addenda_ar is therefore
        # independent of every one of those functions' own internal logic --
        # exactly the discipline `_NASAI_400_ISNAD_SHA256`'s own bug escaped,
        # because the only existing guard (the row-for-row guard) compares
        # committed output to freshly-rebuilt output, and a bug shared by
        # both is invisible to it. `on_presplit` is `None` outside tests.
        if on_presplit is not None:
            on_presplit(record_id, isnad, matn)

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
                matn, addenda, tight, near, extra,
                record_id=record_id, never_cut=commentary_never_cut)
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
            if collection == "ibnmajah":
                # See `_strip_stray_asterisk`'s own comment: a `NEVER_CUT`
                # entry can retain a nested "*" this collection's edition
                # embeds; strip it from whatever the PRIMARY matn is once
                # every cut above has already happened, never from
                # `addenda_ar`.
                matn = _strip_stray_asterisk(matn)

        # hadith:nasai:400 only -- see `_fix_nasai_400_isnad_matn_split`'s own
        # comment; a no-op for every other record_id.
        isnad, matn, addenda = _fix_nasai_400_isnad_matn_split(
            isnad, matn, addenda, record_id)

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
