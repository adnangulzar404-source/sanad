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


def extract_spans(
    text: str, *, min_wrapped_chars: int = 2, min_run_chars: int = 6
) -> list[Span]:
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
             >= (min_wrapped_chars if s.kind == "wrapped" else min_run_chars)]

    # wrapped wins over an overlapping bare run
    found.sort(key=lambda s: (s.start, s.kind != "wrapped"))
    kept: list[Span] = []
    for span in found:
        if any(span.start < k.end and k.start < span.end for k in kept):
            continue
        kept.append(span)
    return kept
