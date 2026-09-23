"""What this corpus is, stated once.

The wording is R22, chosen deliberately: it names the collections that are
ABSENT rather than saying "only", because a reader who does not know the field
cannot otherwise tell that Sahih al-Bukhari is a small slice of the hadith
literature. Absence from this corpus is not evidence about a text, and the
caveat has to say so in as many words -- `NOT_FOUND` on a hadith is a statement
about this database, never about the narration.

It lives here, not in the API layer, because it is a fact about the corpus and
is asserted by things that have no business importing FastAPI -- the evaluation
harness among them. `sanad.api.routes` re-exports it under its original name.
"""
from __future__ import annotations

CORPUS_SCOPE = (
    "This corpus contains the Qur'an and Sahih al-Bukhari. It does not "
    "contain Sahih Muslim, the four Sunan, or any other collection, so "
    "absence from this corpus does not establish that a quotation is "
    "fabricated."
)
