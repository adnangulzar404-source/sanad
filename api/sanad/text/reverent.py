# api/sanad/text/reverent.py -- the reverent-naming transform (spec
# 2026-09-26). Applied ONLY to English prose the app displays: model-authored
# Ask `summary`/`framing` (after the stage-4 guards have passed) and, by hand,
# our own static UI copy. It is NEVER applied to canonical corpus text
# (record.text_ar, translation_en/Pickthall, isnad_ar) -- altering the printed
# edition or the translation would break the verbatim-source guarantee this
# project rests on (spec I2).
#
# The honorific glyphs are Arabic. They are FIXED constants added by the app,
# never model output and never scripture, so they are the one documented
# exception to "no Arabic in prose" (the guards run before this on pure-English
# prose). Per sanad-character-transit-defect they are built from chr() escapes,
# never typed glyphs, and printed in the tests -- an honorific with a
# silently-wrong codepoint is exactly the defect that memory exists to catch.
from __future__ import annotations

import re

# ﷺ  U+FDFA ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM
SALLALLAHU = chr(0xFDFA)
# عليه السلام  "alayhi as-salam" -- ع ل ي ه (space) ا ل س ل ا م
ALAYHI_SALAM = "".join(chr(c) for c in (
    0x0639, 0x0644, 0x064A, 0x0647, 0x20,
    0x0627, 0x0644, 0x0633, 0x0644, 0x0627, 0x0645))

# Muhammad and its common English spellings -> ﷺ. Handled separately from the
# other prophets because it takes a different honorific.
_MUHAMMAD = ("Muhammad", "Muhammed", "Mohammed", "Mohammad")

# Every other prophet named in the Qur'an, each with its common English and
# transliterated spellings -> عليه السلام. Ordered longest-first within the
# module's use so a longer name is tried before a shorter substring name
# (e.g. matching is whole-word anyway, but this keeps intent clear). Adding a
# spelling later is a one-line change. Companions (رضي الله عنه) are out of
# scope by request -- prophets only.
_PROPHETS = (
    "Adam", "Noah", "Nuh", "Abraham", "Ibrahim", "Ishmael", "Ismail",
    "Isaac", "Ishaq", "Jacob", "Yaqub", "Joseph", "Yusuf", "Moses", "Musa",
    "Aaron", "Harun", "David", "Dawud", "Solomon", "Sulayman", "Job", "Ayyub",
    "Jonah", "Yunus", "Jesus", "Isa", "Zachariah", "Zakariya", "John", "Yahya",
    "Lot", "Lut", "Hud", "Salih", "Shuayb", "Idris", "Enoch", "Dhul-Kifl",
    "Elijah", "Ilyas", "Elisha", "Alyasa",
)

# Divine name: only CAPITALISED "God" (and possessive "God's") -> "Allah".
# Lowercase "god" is deliberately left alone -- "a false god" must never become
# "a false Allah". The model is also instructed to write "Allah"; this pass is
# the safety net for the divine-name case, not a blunt find/replace.
_GOD = re.compile(r"\bGod\b")


def _honorific_sub(names: tuple[str, ...], glyph: str, text: str) -> str:
    """Append a space + `glyph` after each whole-word occurrence of any name in
    `names`, unless it is a possessive (`Name's`) or the glyph already follows
    (idempotent)."""
    # (?!['’])       -> not a possessive apostrophe (straight or curly)
    # (?!\s*<glyph>) -> the honorific is not already present, so re-running is
    #                   a no-op. The lookahead keys off the glyph's first
    #                   character, not the inserted space.
    lead = re.escape(glyph[0])
    alternation = "|".join(re.escape(n) for n in names)
    pattern = re.compile(
        r"\b(" + alternation + r")\b(?!['’])(?!\s*" + lead + r")")
    return pattern.sub(lambda m: m.group(1) + " " + glyph, text)


def reverent(text: str) -> str:
    """Idempotent reverent-naming transform for English prose. See module docstring
    for the boundary: prose only, never canonical record fields."""
    if not text:
        return text
    text = _GOD.sub("Allah", text)
    text = _honorific_sub(_MUHAMMAD, SALLALLAHU, text)
    text = _honorific_sub(_PROPHETS, ALAYHI_SALAM, text)
    return text
