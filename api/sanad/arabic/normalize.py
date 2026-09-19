"""Three-tier Arabic normalization.

Canonical text is never passed through these functions destructively — callers
store the result in a separate column. See the spec, section 6.

The tier that produced a match determines how a verdict is reported, so the
boundaries between tiers are a correctness concern: folding too aggressively
at a low tier makes a genuine misquote look verified.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

Tier = Literal["light", "standard", "aggressive"]
TIERS: tuple[Tier, ...] = ("light", "standard", "aggressive")

TATWEEL = "\u0640"  # ARABIC TATWEEL

# Harakat + small Qur'anic marks (U+064B-U+065F), superscript alef (U+0670),
# and Qur'anic annotation/pause marks (U+06D6-U+06ED). These three ranges are
# disjoint and deliberately EXCLUDE U+0660-U+066F (Arabic-Indic digits,
# ARABIC PERCENT SIGN, DECIMAL SEPARATOR, THOUSANDS SEPARATOR, FIVE POINTED
# STAR, and the real letters U+066E ARABIC LETTER DOTLESS BEH / U+066F
# ARABIC LETTER DOTLESS QAF), none of which are diacritics. Spec section 6
# enumerates these three sets. Written as \u escapes, not literal combining
# marks, because combining marks are invisible/indistinguishable in a diff.
_DIACRITICS = re.compile("[\u064B-\u065F\u0670\u06D6-\u06ED]")

# Alef wasla and the hamza-bearing alefs. Pure orthography -> folded at tier 2.
# Source characters are escaped (not visually self-evident); the fold target,
# plain alef, is a plain standalone letter and stays literal.
_ALEF_FORMS = str.maketrans({
    "\u0622": "ا",  # ARABIC LETTER ALEF WITH MADDA ABOVE -> ALEF
    "\u0623": "ا",  # ARABIC LETTER ALEF WITH HAMZA ABOVE -> ALEF
    "\u0625": "ا",  # ARABIC LETTER ALEF WITH HAMZA BELOW -> ALEF
    "\u0671": "ا",  # ARABIC LETTER ALEF WASLA -> ALEF
})

# These can change a word, so they are tier 3 only. Source letters are escaped
# because alef maqsura/yeh and teh marbuta/heh are near-indistinguishable on
# screen; the plain target letters (yeh, heh) are visually unambiguous and
# stay literal.
_LOSSY_FOLDS = str.maketrans({
    "\u0649": "ي",  # ARABIC LETTER ALEF MAKSURA -> YEH
    "\u0629": "ه",  # ARABIC LETTER TEH MARBUTA -> HEH
})

# Arabic block (U+0600-U+06FF), plus space. Everything else goes at tier 3.
_NON_ARABIC = re.compile(r"[^\u0600-\u06FF ]")

_WS = re.compile(r"\s+")


def normalize(text: str, tier: Tier) -> str:
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}; expected one of {TIERS}")

    out = unicodedata.normalize("NFC", text).replace(TATWEEL, "")
    out = _WS.sub(" ", out).strip()
    if tier == "light":
        return out

    out = _DIACRITICS.sub("", out)
    out = out.translate(_ALEF_FORMS)
    out = _WS.sub(" ", out).strip()
    if tier == "standard":
        return out

    out = out.translate(_LOSSY_FOLDS)
    out = _NON_ARABIC.sub(" ", out)
    return _WS.sub(" ", out).strip()
