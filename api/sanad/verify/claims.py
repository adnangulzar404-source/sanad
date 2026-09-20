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


_CLAIM_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "unanimity",
        re.compile(
            "\\b(ijma[‘\u2019]?|unanimous(ly)?|all scholars agree|"
            "every scholar agrees|consensus of the scholars)\\b", re.IGNORECASE
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
            "\\b(bukhari|muslim|tirmidhi|abu dawud|nasa[‘’]?i|ibn majah)\\s*"
            "[#no.]*\\s*\\d+|\\bhadith\\b",
            re.IGNORECASE,
        ),
        "Hadith citation",
        "No licensed Hadith edition is bundled in this corpus. Treat as unverified.",
    ),
]

_PERSONAL = re.compile(
    r"\b(can i|should i|may i|am i allowed|is it haram for me|is it halal for me|"
    r"my (wife|husband|marriage|divorce|inheritance|loan|debt|mother|father)|"
    r"divorced me|give me a fatwa)\b", re.IGNORECASE)

_HIGH_RISK = re.compile(
    r"\b(apostasy|apostate|takfir|stoning|amputation|jihad|"
    r"child marriage|slavery|honou?r killing)\b", re.IGNORECASE)

_DISPUTED = re.compile(
    "\\b(madhha?bs?|madhabs?|mazha?bs?|hanafi|maliki|shafi[‘’]?i|hanbali|"
    "difference of opinion|scholars differ|ikhtilaf)\\b", re.IGNORECASE)


def detect_claims(text: str) -> list[Claim]:
    return [Claim(kind, label, note)
            for kind, pattern, label, note in _CLAIM_RULES
            if pattern.search(text)]


def route_risk(text: str) -> RiskCode:
    # order matters: a personal framing changes who should answer, so it wins
    if _PERSONAL.search(text):
        return RiskCode.PERSONAL_RULING
    if _HIGH_RISK.search(text):
        return RiskCode.HIGH_RISK
    if _DISPUTED.search(text):
        return RiskCode.DISPUTED
    return RiskCode.GENERAL


def requires_handoff(code: RiskCode) -> bool:
    return code in (RiskCode.PERSONAL_RULING, RiskCode.HIGH_RISK)
