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

TATWEEL = "ـ"

# Harakat, superscript alef, and Qur'anic annotation marks.
_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭ]")

# Alef wasla and the hamza-bearing alefs. Pure orthography -> folded at tier 2.
_ALEF_FORMS = str.maketrans({"آ": "ا", "أ": "ا",
                             "إ": "ا", "ٱ": "ا"})

# These can change a word, so they are tier 3 only.
_LOSSY_FOLDS = str.maketrans({"ى": "ي", "ة": "ه"})

# Arabic block, plus space. Everything else goes at tier 3.
_NON_ARABIC = re.compile(r"[^؀-ۿ ]")

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
