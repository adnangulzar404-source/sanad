# api/sanad/pipeline/guards.py — Stage 4: the deterministic safety gate between
# Claude's stage-3 output and publication (spec §5). Every guard here is
# load-bearing: this is the structural reason fabricated citations, Arabic
# leaking out of Claude's mouth, and false certainty claims cannot ship.
from __future__ import annotations

import re

from .types import GuardResult, Selection

# Arabic blocks, written as explicit escapes and compiled once. PRINT the
# compiled pattern during review (see sanad-character-transit-defect): a wrong
# combining-mark range is invisible on screen.
#   ؀-ۿ Arabic, ݐ-ݿ Supplement,
#   ﭐ-﷿ Arabic Presentation Forms-A, ﹰ-﻿ Forms-B
_ARABIC = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

SUMMARY_MAX_WORDS = 80
FRAMING_MAX_WORDS = 25

_UNANIMITY = re.compile(
    r"\b(ijma'?|unanimous(ly)?|all scholars agree|there is no disagreement|"
    r"scholarly consensus|consensus of the scholars)\b", re.IGNORECASE)

# The grading guard is PARTIAL by design (spec §5). Block a grading term only
# where it is not part of a collection title and not adjacent to a name
# particle. 'hasan'/'munkar' are deliberately NOT here.
GRADING_TERMS = ("sahih", "saheeh", "صحيح",  # صحيح
                 "daif", "da'if", "daeef", "ضعيف",  # ضعيف
                 "mawdu", "mawdoo", "موضوع",  # موضوع
                 "matruk")
COLLECTION_TITLES = ("sahih al-bukhari", "sahih muslim", "sahih al bukhari")
NAME_PARTICLES = ("ibn", "bin", "al-", "abu")


def contains_arabic(s: str) -> bool:
    return _ARABIC.search(s) is not None


def word_count(s: str) -> int:
    return len(s.split())


def _grading_offends(text: str) -> bool:
    low = text.lower()
    stripped = low
    for title in COLLECTION_TITLES:              # remove legitimate titles first
        stripped = stripped.replace(title, " ")
    for m in re.finditer(r"[\w'\-؀-ۿ]+", stripped):
        tok = m.group(0)
        if tok not in GRADING_TERMS:
            continue
        before = stripped[:m.start()].rstrip().split()
        prev = before[-1] if before else ""
        if any(prev.startswith(p) or prev == p.rstrip("-") for p in NAME_PARTICLES):
            continue                              # e.g. "al-hasan" style adjacency
        return True
    return False


def check(selection: Selection, candidate_ids: set[str]) -> list[GuardResult]:
    prose = [selection.summary] + [i.framing for i in selection.items]
    joined = " ".join(prose)

    stray = [i.record_id for i in selection.items if i.record_id not in candidate_ids]
    len_ok = (word_count(selection.summary) <= SUMMARY_MAX_WORDS
              and all(word_count(i.framing) <= FRAMING_MAX_WORDS
                      for i in selection.items))

    return [
        GuardResult("cited_id_in_candidates", not stray,
                    "" if not stray else f"ids outside candidate set: {stray}"),
        GuardResult("no_arabic_in_prose", not any(contains_arabic(p) for p in prose),
                    "" if not any(contains_arabic(p) for p in prose)
                    else "Arabic script in generated prose"),
        GuardResult("length_bounds", len_ok,
                    "" if len_ok else "summary >80 or a framing >25 words"),
        GuardResult("no_unanimity", _UNANIMITY.search(joined) is None,
                    "" if _UNANIMITY.search(joined) is None else "unanimity claimed"),
        GuardResult("no_grading", not _grading_offends(joined),
                    "" if not _grading_offends(joined) else "grading vocabulary used"),
    ]
