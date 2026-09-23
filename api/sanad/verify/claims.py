"""Claim detection and risk routing.

These are intentionally conservative pattern rules, not a classifier. A false
positive costs a caution label; a false negative can route a personal ruling
to a machine. The asymmetry is deliberate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class RiskCode(str, Enum):
    GENERAL = "GENERAL"
    DISPUTED = "DISPUTED"
    HIGH_RISK = "HIGH_RISK"
    PERSONAL_RULING = "PERSONAL_RULING"


@dataclass(frozen=True)
class Claim:
    kind: str
    label: str
    note: str


# Apostrophe character class for ijma/nasa'i/shafi'i matches:
# U+0027 APOSTROPHE (straight) and U+2019 RIGHT SINGLE QUOTATION MARK (curly)
_APOSTROPHES = "['’]"


_CLAIM_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "unanimity",
        re.compile(
            "\\b(ijma" + _APOSTROPHES + "?|unanimous(ly)?|all scholars agree|"
            "every scholar agrees|consensus of the scholars)\\b",
            re.IGNORECASE,
        ),
        "Unanimity claimed",
        (
            "A claim of consensus requires named evidence. Sanad will not accept it "
            "from model memory."
        ),
    ),
    (
        "legal_conclusion",
        re.compile(
            r"\b(therefore|thus|hence)\b[^.]{0,80}\b(islam|shariah|sharia)\b"
            r"[^.]{0,40}\b(requires?|forbids?|obliges?|mandates?|prohibits?)\b",
            re.IGNORECASE,
        ),
        "Legal conclusion beyond the quoted text",
        (
            "A valid quotation does not license a modern legal conclusion. Marked as "
            "interpretation."
        ),
    ),
    (
        "hadith_unverifiable",
        re.compile(
            "\\b(bukhari|muslim|tirmidhi|abu dawud|nasa" + _APOSTROPHES + "?i|ibn majah)\\s*"
            "[#no.]*\\s*\\d+|\\bhadith\\b",
            re.IGNORECASE,
        ),
        "Hadith citation",
        # This note used to read "No licensed Hadith edition is bundled in this
        # corpus. Treat as unverified." That was true until Sahih al-Bukhari
        # was ingested and is now false: it was being printed beside a hadith
        # this corpus had just verified word for word, contradicting Sanad's
        # own result. What is still true, and is what a reader needs, is the
        # scope limit and the refusal to grade -- the same two points the
        # corpus-scope caveat makes, said about the citation in front of them.
        (
            "This corpus contains Sahih al-Bukhari and no other collection, so a "
            "citation of any other source cannot be checked here. Sanad compares "
            "wording against a printed edition; it does not grade authenticity."
        ),
    ),
]

# First-person marker: direct references to asker
_FIRST_PERSON = re.compile(r"\b(I|me|my|mine)\b|for me\b", re.IGNORECASE)

# Normative marker: asking whether something is lawful/required/wrong
_NORMATIVE = re.compile(
    r"\b(permissible|permitted|allowed|okay|ok|alright|lawful|unlawful|halal|"
    r"haram|forbidden|can|could|sin(?:ful|ning|s)?|wrong|must|obliged|obligated|"
    r"required|have to|need to|should|valid|count|counts|ruling|obligation|rights|"
    r"compliant)\b",
    re.IGNORECASE,
)

# Faith crisis / apostasy phrases (first-person triggers PERSONAL, otherwise HIGH_RISK)
# Verb inflections: believ(e/es/ing), los(e/es/t/ing), leav(e/es/ing), becom(e/es/ing)
# Negations: don't, doesn't, do not, does not, no longer, not anymore, anymore
# Self-description: atheist, agnostic, apostate, ex-muslim
_FAITH_CRISIS = re.compile(
    r"\b(?:leav(?:e|es|ing)|leaving|left)\s+(?:islam|the\s+faith)|"
    r"(?:becom(?:e|es|ing)|becoming)\s+(?:an\s+)?(?:atheist|agnostic)|"
    r"(?:believ(?:e|es|ing)|believe)\s+(?:no\s+longer|not\s+anymore|anymore|not\s+in\s+islam)|"
    r"(?:don|does)n't\s+believe|"
    r"(?:do(?:es)?\s+)?not\s+believe|no\s+longer\s+believ(?:e|es)|"
    r"(?:los(?:e|es|t|ing)|lost)\s+(?:my\s+)?faith|"
    r"convert\s+away|renounce|ex-?muslim|apostate",
    re.IGNORECASE,
)

# Explicit personal circumstance phrases: sufficient alone to mark as personal
# Matches: "my situation", "in my case", "someone in my position", etc.
_PERSONAL_CIRCUMSTANCE = re.compile(
    r"\b(my|a|someone)\s+\w{0,15}?"
    r"(situation|position|case|circumstances|predicament)"
    r"|\bin\s+(my|a)\s+(situation|case|circumstances|position)",
    re.IGNORECASE,
)

# Explicit personal topics (belt and braces backup)
_PERSONAL_TOPICS = re.compile(
    r"\b(can i|should i|may i|am i allowed|is it haram for me|is it halal for me|"
    r"my (wife|husband|ex-wife|ex-husband|marriage|divorce|inheritance|loan|debt|"
    r"brother|sister|cousin|mother|father|parents|aunt|uncle|son|daughter|in-laws|"
    r"fiance)|"
    r"divorced me|give me a fatwa|he\s+can|she\s+can|he\s+could|she\s+could)\b",
    re.IGNORECASE,
)


# Personal ruling: (first-person + normative) OR circumstance phrase OR explicit topic
# OR faith crisis with first-person framing
def _is_personal_ruling(text: str) -> bool:
    # Arm 1: Conjunction — first-person marker AND normative marker
    has_first_person = _FIRST_PERSON.search(text) is not None
    has_normative = _NORMATIVE.search(text) is not None
    conjunction = has_first_person and has_normative

    # Arm 2: Personal circumstance phrases alone are sufficient
    has_circumstance = _PERSONAL_CIRCUMSTANCE.search(text) is not None

    # Arm 3: Explicit personal topics catch unambiguous cases
    has_explicit_topic = _PERSONAL_TOPICS.search(text) is not None

    # Arm 4: Faith crisis with first-person framing
    has_faith_crisis = _FAITH_CRISIS.search(text) is not None
    faith_crisis_personal = has_faith_crisis and has_first_person

    return conjunction or has_circumstance or has_explicit_topic or faith_crisis_personal

_HIGH_RISK = re.compile(
    r"\b(apostasy|apostate|takfir|stoning|amputation|jihad|"
    r"child marriage|slavery|honou?r killing)\b|"
    r"(?:leav(?:e|es|ing)|leaving|left)\s+(?:islam|the\s+faith)|"
    r"(?:becom(?:e|es|ing)|becoming)\s+(?:an\s+)?(?:atheist|agnostic)|"
    r"(?:believ(?:e|es|ing)|believe)\s+(?:no\s+longer|not\s+anymore|anymore|not\s+in\s+islam)|"
    r"(?:don|does)n't\s+believe|"
    r"(?:do(?:es)?\s+)?not\s+believe|no\s+longer\s+believ(?:e|es)|"
    r"(?:los(?:e|es|t|ing)|lost)\s+(?:my\s+)?faith|"
    r"convert\s+away|renounce|ex-?muslim",
    re.IGNORECASE,
)

_DISPUTED = re.compile(
    "\\b(madhha?bs?|madhabs?|mazha?bs?|hanafi|maliki|shafi" + _APOSTROPHES + "?i|"
    "hanbali|difference of opinion|scholars differ|ikhtilaf)\\b",
    re.IGNORECASE,
)


def detect_claims(text: str) -> list[Claim]:
    return [Claim(kind, label, note)
            for kind, pattern, label, note in _CLAIM_RULES
            if pattern.search(text)]


def route_risk(text: str) -> RiskCode:
    # order matters: a personal framing changes who should answer, so it wins
    if _is_personal_ruling(text):
        return RiskCode.PERSONAL_RULING
    if _HIGH_RISK.search(text):
        return RiskCode.HIGH_RISK
    if _DISPUTED.search(text):
        return RiskCode.DISPUTED
    return RiskCode.GENERAL


def requires_handoff(code: RiskCode) -> bool:
    return code in (RiskCode.PERSONAL_RULING, RiskCode.HIGH_RISK)
