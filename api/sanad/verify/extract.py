"""Pull candidate quotations out of free text.

Two strategies: explicitly wrapped quotes (several quotation conventions,
including the ornate parentheses used for Qur'anic text), and bare runs of
Arabic script. A wrapped quote also matches the bare-run pattern, so overlaps
are resolved in favour of the wrapped span.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..arabic.normalize import normalize

# Openers: « (U+00AB), " (U+201C), " (U+0022), 『 (U+300E), 【 (U+3010),
#          ﴿ (U+FD3F)
# Closers: » (U+00BB), " (U+201D), " (U+0022), 』 (U+300F), 】 (U+3011),
#          ﴾ (U+FD3E)
_OPENERS = '«“"『【﴿'  # « " " 『 【 ﴿
_CLOSERS = '»”"』】﴾'  # » " " 』 】 ﴾
_WRAPPED = re.compile(
    f"[{re.escape(_OPENERS)}]"
    f"([^{re.escape(_CLOSERS)}]{{1,}})"
    f"[{re.escape(_CLOSERS)}]"
)
_ARABIC_RUN = re.compile(r"[؀-ۿ][؀-ۿ\s]{6,}")


@dataclass(frozen=True)
class Span:
    text: str
    start: int
    end: int
    kind: str


# How much Arabic, after aggressive normalization and with spaces removed, a
# span must carry before it counts as a quotation at all.
#
# The two numbers differ because the evidence differs. Someone who typed
# quotation marks has told you they are quoting, so two letters is enough --
# a wrapped «الله» is a quotation of a word. A bare run of Arabic has said
# nothing about itself, and at two letters would drag in every stray word in
# a sentence, so it has to be long enough that a run is unlikely to be
# anything else.
MIN_WRAPPED_CHARS = 2
MIN_RUN_CHARS = 6
_FLOOR_BY_KIND = {"wrapped": MIN_WRAPPED_CHARS, "arabic-run": MIN_RUN_CHARS}


def minimum_chars(kind: str) -> int:
    """The floor for a span of `kind`, as one answer in one place.

    `engine._is_only_a_citation` asks the same question this module answers
    -- "would what is left still have been a span?" -- and used to answer it
    with its own copy of the two numbers, so the floor lived in two files
    that had no way of disagreeing out loud. A third span kind would have
    silently taken the run floor in both; here it raises instead.
    """
    try:
        return _FLOOR_BY_KIND[kind]
    except KeyError:
        raise ValueError(
            f"no minimum is defined for span kind {kind!r}; a new kind needs "
            f"a judgement about how much Arabic makes it a quotation, not a "
            f"default") from None


def extract_spans(text: str) -> list[Span]:
    found: list[Span] = []

    for m in _WRAPPED.finditer(text):
        inner = m.group(1)
        offset = m.start(1)
        stripped = inner.strip()
        lead = len(inner) - len(inner.lstrip())
        found.append(Span(stripped, offset + lead, offset + lead + len(stripped),
                          "wrapped"))

    for m in _ARABIC_RUN.finditer(text):
        raw = m.group(0)
        stripped = raw.strip()
        lead = len(raw) - len(raw.lstrip())
        found.append(Span(stripped, m.start() + lead,
                          m.start() + lead + len(stripped), "arabic-run"))

    # keep only spans with enough Arabic to be a quotation
    found = [s for s in found
             if len(normalize(s.text, "aggressive").replace(" ", ""))
             >= minimum_chars(s.kind)]

    # wrapped wins over an overlapping bare run
    found.sort(key=lambda s: (s.start, s.kind != "wrapped"))
    kept: list[Span] = []
    for span in found:
        if any(span.start < k.end and k.start < span.end for k in kept):
            continue
        kept.append(span)
    return kept
