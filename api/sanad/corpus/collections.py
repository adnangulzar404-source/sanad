"""English display titles for hadith collections -- the single source of
truth (Stage A3 controller ruling R-A3-16).

Moved here from `ingest.sanad_ingest.build._COLLECTION_TITLE`: `ingest`
depends on `api` (`build.py` does `from sanad.corpus import db`), so the map
has to live on the api side for `corpus.scope.corpus_scope` to read it
without `api` importing from `ingest` -- a dependency direction this project
does not allow.

Plain ASCII, hamza/'ayn dropped -- the house style already used for surah
names (`surah_name_en` renders "Al-Fatihah", "An-Nisa", ...; see
`sanad.corpus.surahs`). Only "bukhari" -> "Sahih al-Bukhari" is shipped as of
this task; the other five are dormant until their own Stage A3 sources are
ingested, but the titles are fixed now so a future addition is a lockfile
edit, not a code change.
"""
from __future__ import annotations

COLLECTION_TITLES = {
    "bukhari": "Sahih al-Bukhari",
    "muslim": "Sahih Muslim",
    "abudawud": "Sunan Abi Dawud",
    "tirmidhi": "Jami at-Tirmidhi",
    "nasai": "Sunan an-Nasai",
    "ibnmajah": "Sunan Ibn Majah",
}

# Canonical Kutub al-Sittah order. `corpus.scope.corpus_scope` lists whichever
# of these are actually present in this order, regardless of ingest order.
COLLECTION_ORDER = ("bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah")
