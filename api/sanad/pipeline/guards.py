# api/sanad/pipeline/guards.py — Stage 4: the deterministic safety gate between
# Claude's stage-3 output and publication (spec §5). Every guard here is
# load-bearing: this is the structural reason fabricated citations, Arabic
# leaking out of Claude's mouth, and false certainty claims cannot ship.
#
# Fix round 1 (task-8-review.md): the grading and unanimity guards had three
# confirmed bypasses — hyphenated grading terms (C1), an exact-string-only
# collection-title exemption (C2), ASCII-only unanimity matching that missed
# the diacritic form the brief itself names (I1) — and four of five guards
# gave generic detail strings instead of naming the offending value (I2).
# See task-8-report.md "Fix round 1" for the full record and the mutation
# test that confirms these fixes actually bite.
from __future__ import annotations

import re
import unicodedata

from .types import GuardResult, Selection

# Arabic blocks, written as explicit escapes and compiled once. PRINT the
# compiled pattern during review (see sanad-character-transit-defect): a wrong
# combining-mark range is invisible on screen.
#   ؀-ۿ Arabic, ݐ-ݿ Supplement,
#   ﭐ-﷿ Arabic Presentation Forms-A, ﹰ-﻿ Forms-B,
#   U+0870-U+08FF Arabic Extended-A/B (fix round 1, ruling f) — Uthmani
#   Qur'anic annotation marks; without this range a fragment consisting only
#   of an annotation mark (no base letter) could slip through undetected.
#   Written via chr() rather than typed glyphs, per sanad-character-transit-
#   defect: this exact block is Quranic annotation marks, the highest-risk
#   place in the whole file to have a silently-wrong codepoint.
_ARABIC = re.compile(
    "[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿" + chr(0x0870) + "-" + chr(0x08FF) + "]")

SUMMARY_MAX_WORDS = 80
FRAMING_MAX_WORDS = 25

# Fix round 1, ruling d (resolves I1): the brief itself writes this term as
# "ijmāʿ" (a-macron + ayin), but a plain ASCII "ijma" alternative never
# matched it — a character-in-transit defect (see sanad-character-transit-
# defect). _fold_diacritics() below normalizes the text being searched so
# "ijma" matches "ijmā"/"ijmāʿ" alike. Phrasings added in fix round 1:
# "consensus among scholars", "have all agreed", and "no disagreement" was
# generalized from the brief's exact "there is no disagreement" so it also
# catches "no disagreement among...". The original three phrasings are
# otherwise unchanged.
_UNANIMITY = re.compile(
    r"\b(ijma|unanimous(ly)?|all scholars agree|no disagreement|"
    r"scholarly consensus|consensus of the scholars|"
    r"consensus among scholars|have all agreed)\b",
    re.IGNORECASE)

# Ayin/hamza transliteration glyphs stripped by _fold_diacritics, written as
# explicit \uXXXX escapes (not typed glyphs) per sanad-character-transit-
# defect: U+02BF MODIFIER LETTER LEFT HALF RING (ayin), U+02BB MODIFIER
# LETTER TURNED COMMA (ayin, alt), U+02BE MODIFIER LETTER RIGHT HALF RING
# (hamza), U+2019 RIGHT SINGLE QUOTATION MARK (curly apostrophe), plus the
# ASCII straight apostrophe.
_TRANSLIT_MARKS = re.compile(
    "[" + chr(0x02BF) + chr(0x02BB) + chr(0x02BE) + chr(0x2019) + "']")


def _fold_diacritics(s: str) -> str:
    """NFKD-decompose and drop combining marks plus ayin/hamza
    transliteration glyphs, so 'ijmā'/'ijmāʿ' fold to the ASCII 'ijma' the
    pattern above matches. Scoped to the unanimity check only — the other
    guards don't need it, and folding indiscriminately elsewhere would blur
    real Arabic-script detection."""
    decomposed = unicodedata.normalize("NFKD", s)
    no_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _TRANSLIT_MARKS.sub("", no_marks)


# The grading guard is PARTIAL by design (spec §5). 'hasan'/'munkar' are
# deliberately NOT here — too collision-prone as a narrator-name substring,
# left to stage 5. "matrook" added in fix round 1 (ruling f) as an alt
# spelling of "matruk".
GRADING_TERMS = ("sahih", "saheeh", "صحيح",  # صحيح
                 "daif", "da'if", "daeef", "ضعيف",  # ضعيف
                 "mawdu", "mawdoo", "موضوع",  # موضوع
                 "matruk", "matrook")

# Fix round 1, ruling b (resolves C2): the exemption is now which *collection
# name tokens* pair with "sahih" to form a title citation, matched by the
# tolerant regex below ("sahih <name>", "sahih al <name>", "sahih of [the]
# <name>") — not three fixed exact strings, which false-blocked "Sahih
# Bukhari" (no "al-"), "the Sahih of Bukhari", and "Sahih al-Bukhaari" (alt
# spelling). COLLECTION_TITLES keeps its name from the original interface but
# now holds collection-name tokens rather than full exact phrases.
COLLECTION_TITLES = ("bukhari", "bukhaari", "muslim")

# Fix round 2, ruling g: the round-1 exemption above matched a bare
# collection name with nothing after it, which let a REAL grading claim
# hide in a punctuation-free run-on ("sahih Bukhari has documented
# similarly" — "sahih" governs nothing here, "Bukhari" starts a new clause
# with no comma). A citation is exempt only if the collection name is
# followed by a TITLE BOUNDARY: a hadith number (optionally after
# whitespace), end-of-clause punctuation/closing quote, end-of-string, or an
# "and"/"or" connector into another collection name. A verb or other word
# continuing the sentence is not a boundary, so the exemption doesn't apply
# and the grading term gets tokenized and blocked. Quote characters are
# built via chr() rather than typed glyphs, per sanad-character-transit-
# defect.
_QUOTE_CHARS = "\"'" + chr(0x2019) + chr(0x201D)  # straight ", straight ', curly ', curly "
_TITLE_BOUNDARY = (
    r"(?=\s*\d"                                      # a hadith number
    r"|[.,;:)" + _QUOTE_CHARS + r"]"                  # end-of-clause punctuation / closing quote
    r"|\s*$"                                          # end of string (optional trailing space)
    r"|\s+(?:and|or)\s+(?:al\s+|of\s+(?:the\s+)?)?(?:"
    + "|".join(COLLECTION_TITLES) + r")\b"            # connector into another title
    r")"
)
_COLLECTION_TITLE_RE = re.compile(
    r"\bsahih\b(?:\s+(?:al\s+|of\s+(?:the\s+)?))?\s*(?:"
    + "|".join(COLLECTION_TITLES) + r")\b" + _TITLE_BOUNDARY)

# Fix round 1, ruling c (resolves I3): the original NAME_PARTICLES adjacency
# exemption is dropped entirely, and the constant removed — it protected no
# real name ("hasan" is excluded from GRADING_TERMS above by name, not
# exempted via adjacency) and it only created false negatives ("Abu Sahih",
# "Ibn Daif" both used to pass). The collection-title regex above is now the
# guard's only exemption. A rare standalone "al-Sahih" with no nearby
# collection name will still block — accepted residual (ruling b), not a bug.


def contains_arabic(s: str) -> bool:
    return _ARABIC.search(s) is not None


def word_count(s: str) -> int:
    return len(s.split())


def _grading_matches(text: str) -> list[str]:
    """Return every grading term found in `text` that is not part of a
    collection-title citation. Empty list means the guard passes.

    Fix round 1, ruling a (resolves C1): hyphens are normalized to spaces
    before tokenizing. The original tokenizer's character class included a
    bare hyphen, so "al-sahih"/"non-sahih"/"quasi-daif" were captured as ONE
    token that never equals a bare GRADING_TERMS entry and so was silently
    skipped — and hyphenated transliteration of the Arabic definite article
    is a standard convention, not an exotic adversarial input.
    """
    low = text.lower().replace("-", " ")
    low = re.sub(r"\s+", " ", low)
    low = _COLLECTION_TITLE_RE.sub(" ", low)   # strip legitimate titles first
    return [m.group(0) for m in re.finditer(r"[\w']+", low)
            if m.group(0) in GRADING_TERMS]


def _prose_sources(selection: Selection) -> list[tuple[str, str]]:
    """(label, text) pairs for every piece of Claude-generated prose, so
    guard details can name exactly which one offended (fix round 1,
    ruling e)."""
    return [("summary", selection.summary)] + [
        (f"framing for {item.record_id}", item.framing) for item in selection.items]


def check(selection: Selection, candidate_ids: set[str]) -> list[GuardResult]:
    sources = _prose_sources(selection)
    joined = " ".join(text for _, text in sources)

    stray = [i.record_id for i in selection.items if i.record_id not in candidate_ids]

    arabic_offenders = [label for label, text in sources if contains_arabic(text)]

    length_offenders = []
    summary_wc = word_count(selection.summary)
    if summary_wc > SUMMARY_MAX_WORDS:
        length_offenders.append(f"summary is {summary_wc} words (max {SUMMARY_MAX_WORDS})")
    for item in selection.items:
        wc = word_count(item.framing)
        if wc > FRAMING_MAX_WORDS:
            length_offenders.append(
                f"framing for {item.record_id} is {wc} words (max {FRAMING_MAX_WORDS})")

    unanimity_match = _UNANIMITY.search(_fold_diacritics(joined))
    grading_matches = _grading_matches(joined)

    return [
        GuardResult("cited_id_in_candidates", not stray,
                    "" if not stray else f"ids outside candidate set: {stray}"),
        GuardResult("no_arabic_in_prose", not arabic_offenders,
                    "" if not arabic_offenders
                    else f"Arabic script found in: {', '.join(arabic_offenders)}"),
        GuardResult("length_bounds", not length_offenders,
                    "" if not length_offenders else "; ".join(length_offenders)),
        GuardResult("no_unanimity", unanimity_match is None,
                    "" if unanimity_match is None
                    else f"unanimity phrase matched: '{unanimity_match.group(0)}'"),
        GuardResult("no_grading", not grading_matches,
                    "" if not grading_matches
                    else f"grading term(s) matched: {', '.join(sorted(set(grading_matches)))}"),
    ]
