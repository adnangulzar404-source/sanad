from __future__ import annotations


def rrf_fuse(ranked_lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal-rank fusion. Score = sum over lists of 1/(k + rank), rank 0-based.

    k=60 is the conventional RRF constant; it damps the contribution of deep
    ranks so a top-1 in one list is not overwhelmed by a long tail in another.
    """
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, rid in enumerate(lst):
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda t: (-t[1], t[0]))
