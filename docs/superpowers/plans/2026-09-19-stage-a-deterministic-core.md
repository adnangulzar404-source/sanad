# Sanad Stage A — Deterministic Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working quotation verifier — a reproducible, checksummed Qur'an corpus plus a deterministic engine that reports whether an Arabic quotation is in that corpus verbatim — with no model, no API key, and no network at request time.

**Architecture:** An offline `sanad-ingest` CLI downloads Tanzil's Uthmani text, verifies it against a committed lockfile hash, and builds a single SQLite file with FTS5. A FastAPI service opens that file read-only and exposes `POST /api/verify`, which extracts Arabic spans from arbitrary text, matches them against the corpus through three normalization tiers, and reports a verdict per span. Every layer is pure and testable; nothing calls out to a model.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, SQLite (FTS5, `unicode61 remove_diacritics 2`), pytest, ruff, httpx, tomli, Docker.

**Spec:** `docs/superpowers/specs/2026-09-19-sanad-design.md`

## Global Constraints

- Python 3.10+ (dev machine is 3.10.12; do not use 3.11+ syntax such as `X | Y` in `isinstance`, `tomllib`, or `ExceptionGroup`).
- SQLite 3.37.2 is the floor. FTS5 with `tokenize="unicode61 remove_diacritics 2"` is verified available.
- **`records.text_ar` is canonical and is never modified.** Every normalization writes to a separate column. This is a licence condition, not a preference.
- **The Tanzil copyright block is stored verbatim** in `sources.attribution` and rendered wherever its text is shown. The file says "PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK".
- **Hash the verse payload, not the file.** The Tanzil footer embeds the current year (`Copyright (C) 2007-2026`), so a whole-file hash is unstable. Pin the SHA-256 of the 6,236 verse lines joined by `\n`.
- Verification never consults embeddings or a translation. Arabic against Arabic only.
- No `print()` in library code; use `logging`.
- Every module under `api/sanad/` must import without a database present.

### Verified constants (measured 2026-09-19, do not re-derive)

| Fact | Value |
|---|---|
| Tanzil URL | `https://tanzil.net/pub/download/index.php?quranType=uthmani&outType=txt-2&agree=true` |
| Line format | `surah|ayah|text`, UTF-8, LF |
| Verse lines | `6236` |
| Non-verse lines | 28, all beginning `#` (the copyright block) |
| Content SHA-256 | `36da55e256f54f4838b6fa1c78781734346c8d9ffde52daf5a3cbfa32626a08c` |
| Edition | Tanzil Uthmani, Version 1.1, CC BY 3.0 |

### Normalization tiers (fixed — do not redesign)

| Tier | Transform | Verdict it can produce |
|---|---|---|
| `light` | NFC; strip tatweel `U+0640`; collapse whitespace | `EXACT` |
| `standard` | light + strip `U+064B–U+065F`, `U+0670`, `U+06D6–U+06ED`; fold `آ أ إ ٱ → ا` | `EXACT_ORTHOGRAPHY` |
| `aggressive` | standard + `ى → ي`, `ة → ه`; strip non-Arabic | `NEAR_MATCH` only, always with a diff |

Alef-form folding sits in `standard` because Tanzil Uthmani uses alef wasla (`ٱ`) throughout while users type plain alef (`ا`) — that is orthography, not a textual difference. `ى/ي` and `ة/ه` can change a word, so they stay in `aggressive`, which may never report a verified match.

---

## File Structure

```
pyproject.toml                          packaging, deps, pytest + ruff config
api/sanad/__init__.py
api/sanad/arabic/normalize.py           three tiers; pure functions
api/sanad/arabic/similarity.py          levenshtein, ratio
api/sanad/corpus/schema.py              DDL as constants
api/sanad/corpus/db.py                  open, verify hash, query helpers
api/sanad/corpus/models.py              Record, Source dataclasses
api/sanad/verify/extract.py             Arabic span + quote extraction
api/sanad/verify/references.py          "2:255" / "Al-Baqarah" parsing
api/sanad/verify/engine.py              tiered match -> verdict
api/sanad/verify/claims.py              claim + risk detection
api/sanad/api/app.py                    FastAPI app factory
api/sanad/api/routes.py                 /verify /corpus /health /records
api/sanad/api/schemas.py                pydantic request/response
ingest/corpus.lock.toml                 the provenance contract
ingest/sanad_ingest/lockfile.py         parse + validate lockfile
ingest/sanad_ingest/fetch.py            download + hash check
ingest/sanad_ingest/tanzil.py           parse pipe format, split footer
ingest/sanad_ingest/build.py            construct sanad.db
ingest/sanad_ingest/cli.py              `sanad-ingest build`
eval/cases/*.yaml                       adversarial cases
eval/runner.py                          metrics + thresholds
tests/…                                 mirrors the above
```

---

### Task 1: Arabic normalization tiers

Scaffolding for the whole project folds in here, since this is the first module that needs it.

**Files:**
- Create: `pyproject.toml`
- Create: `api/sanad/__init__.py`, `api/sanad/arabic/__init__.py`
- Create: `api/sanad/arabic/normalize.py`
- Test: `tests/arabic/test_normalize.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Tier` — `Literal["light", "standard", "aggressive"]`
  - `normalize(text: str, tier: Tier) -> str`
  - `TIERS: tuple[Tier, ...]` ordered strictest-first: `("light", "standard", "aggressive")`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "sanad"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "httpx>=0.27",
    "tomli>=2.0; python_version<'3.11'",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.5"]

[project.scripts]
sanad-ingest = "sanad_ingest.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["api", "ingest"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["api", "ingest"]

[tool.ruff]
line-length = 100
target-version = "py310"
```

- [ ] **Step 2: Write the failing test**

Create `tests/arabic/test_normalize.py`:

```python
import pytest
from sanad.arabic.normalize import normalize, TIERS

BASMALA_UTHMANI = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"


def test_light_strips_tatweel_but_keeps_diacritics():
    assert normalize("بِسْـــمِ", "light") == "بِسْمِ"


def test_light_collapses_whitespace():
    assert normalize("  بِسْمِ   ٱللَّهِ  ", "light") == "بِسْمِ ٱللَّهِ"


def test_light_preserves_alef_wasla():
    assert "ٱ" in normalize(BASMALA_UTHMANI, "light")


def test_standard_strips_all_diacritics():
    out = normalize(BASMALA_UTHMANI, "standard")
    assert out == "بسم الله الرحمن الرحيم"


def test_standard_folds_alef_wasla_to_plain_alef():
    assert normalize("ٱللَّه", "standard") == "الله"


def test_standard_folds_every_alef_form():
    assert normalize("آ أ إ ٱ", "standard") == "ا ا ا ا"


def test_standard_keeps_ya_and_ta_marbuta_distinct():
    # these can change a word, so they must survive tier 2
    assert normalize("عَلَى", "standard") == "على"
    assert normalize("رَحْمَة", "standard") == "رحمه" or \
           normalize("رَحْمَة", "standard") == "رحمة"
    assert normalize("رَحْمَة", "standard").endswith("ة")


def test_aggressive_folds_alef_maqsura_and_ta_marbuta():
    assert normalize("عَلَى", "aggressive") == "علي"
    assert normalize("رَحْمَة", "aggressive") == "رحمه"


def test_aggressive_strips_latin_and_punctuation():
    assert normalize("قُلْ (Say) هُوَ", "aggressive") == "قل هو"


def test_strips_quranic_annotation_marks_at_standard():
    # U+06D6 small high ligature sad-lam-alef-ya
    assert normalize("ٱلرَّحِيمِۖ", "standard") == "الرحيم"


def test_superscript_alef_removed_at_standard():
    assert normalize("ٱلرَّحْمَٰن", "standard") == "الرحمن"


def test_normalization_is_idempotent():
    for tier in TIERS:
        once = normalize(BASMALA_UTHMANI, tier)
        assert normalize(once, tier) == once


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        normalize("x", "nonsense")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/arabic/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sanad.arabic.normalize'`

- [ ] **Step 4: Implement `api/sanad/arabic/normalize.py`**

```python
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
_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭ]")

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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/arabic/test_normalize.py -v`
Expected: PASS, 12 tests.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml api/sanad tests/arabic
git commit -m "feat(arabic): three-tier normalization with tier-appropriate folding

Alef-form folding sits at the standard tier because Tanzil Uthmani uses
alef wasla throughout while users type plain alef; that is orthography,
not a textual difference. Alef maqsura and ta marbuta folds stay at the
aggressive tier because they can change a word, and an aggressive-tier
match may never be reported as verified."
```

---

### Task 2: Similarity scoring

**Files:**
- Create: `api/sanad/arabic/similarity.py`
- Test: `tests/arabic/test_similarity.py`

**Interfaces:**
- Consumes: `sanad.arabic.normalize.normalize`, `Tier`.
- Produces:
  - `levenshtein(a: str, b: str) -> int`
  - `ratio(a: str, b: str) -> float` — `1 - dist/max(len)`, range 0.0–1.0
  - `ratio_at(a: str, b: str, tier: Tier) -> float` — normalizes both at `tier`, then `ratio`

- [ ] **Step 1: Write the failing test**

Create `tests/arabic/test_similarity.py`:

```python
from sanad.arabic.similarity import levenshtein, ratio, ratio_at


def test_levenshtein_identical_is_zero():
    assert levenshtein("كتاب", "كتاب") == 0


def test_levenshtein_single_substitution():
    assert levenshtein("كتاب", "كتاف") == 1


def test_levenshtein_empty_operand():
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3


def test_levenshtein_is_symmetric():
    assert levenshtein("قل هو الله", "قل هو اللة") == levenshtein("قل هو اللة", "قل هو الله")


def test_ratio_identical_is_one():
    assert ratio("كتاب", "كتاب") == 1.0


def test_ratio_of_two_empties_is_zero_not_nan():
    assert ratio("", "") == 0.0


def test_ratio_bounds():
    assert 0.0 <= ratio("كتاب", "شمس") <= 1.0


def test_ratio_at_standard_ignores_diacritics():
    assert ratio_at("قُلْ هُوَ ٱللَّهُ أَحَدٌ", "قل هو الله احد", "standard") == 1.0


def test_ratio_at_light_does_not_ignore_diacritics():
    assert ratio_at("قُلْ هُوَ ٱللَّهُ أَحَدٌ", "قل هو الله احد", "light") < 1.0


def test_ratio_at_detects_single_letter_mutation():
    # a real misquote must not score 1.0 at any tier
    for tier in ("light", "standard", "aggressive"):
        assert ratio_at("قل هو الله أحد", "قل هو الله أحدق", tier) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/arabic/test_similarity.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `api/sanad/arabic/similarity.py`**

```python
"""Edit distance over normalized Arabic."""
from __future__ import annotations

from .normalize import Tier, normalize


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def ratio(a: str, b: str) -> float:
    longest = max(len(a), len(b))
    if longest == 0:
        return 0.0
    return 1.0 - levenshtein(a, b) / longest


def ratio_at(a: str, b: str, tier: Tier) -> float:
    return ratio(normalize(a, tier), normalize(b, tier))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/arabic/test_similarity.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/arabic/similarity.py tests/arabic/test_similarity.py
git commit -m "feat(arabic): tier-aware Levenshtein similarity"
```

---

### Task 3: Corpus schema and database access

**Files:**
- Create: `api/sanad/corpus/__init__.py`, `schema.py`, `models.py`, `db.py`
- Test: `tests/corpus/test_schema.py`, `tests/corpus/test_db.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `schema.SCHEMA_SQL: str` — full DDL, executable via `executescript`
  - `models.Source` — dataclass: `id, kind, title, publisher, edition, url, license_id, license_url, attribution, retrieved_at, upstream_sha256, modifications`
  - `models.Record` — dataclass: `id, source_id, kind, surah, ayah, surah_name_ar, surah_name_en, text_ar, text_ar_sha256, norm_light, norm_standard, norm_aggressive, reference_display`
  - `db.connect(path: str | Path, *, read_only: bool = True) -> sqlite3.Connection`
  - `db.insert_source(conn, source: Source) -> None`
  - `db.insert_records(conn, records: Iterable[Record]) -> int`
  - `db.rebuild_fts(conn) -> None`
  - `db.iter_records(conn) -> Iterator[Record]`
  - `db.get_record(conn, record_id: str) -> Record | None`
  - `db.fts_candidates(conn, query_norm: str, limit: int = 50) -> list[Record]`
  - `db.corpus_stats(conn) -> dict[str, int]`

Only the Stage A subset of the spec's schema is created here: `sources`, `records`, `translations`, `records_fts`. `gradings`, `embeddings`, and `audit_log` are created too (empty) so Stage B needs no migration.

- [ ] **Step 1: Write the failing test**

Create `tests/corpus/test_schema.py`:

```python
import sqlite3
from sanad.corpus.schema import SCHEMA_SQL


def test_schema_executes_cleanly():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sources", "records", "translations", "gradings",
            "embeddings", "audit_log"} <= names


def test_fts_table_exists_and_is_queryable():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.execute("INSERT INTO records_fts(record_id, norm_standard, norm_aggressive, translation) "
                 "VALUES ('x', 'قل هو الله احد', 'قل هو الله احد', '')")
    rows = conn.execute(
        "SELECT record_id FROM records_fts WHERE records_fts MATCH 'الله'").fetchall()
    assert rows == [("x",)]


def test_schema_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.executescript(SCHEMA_SQL)  # IF NOT EXISTS everywhere
```

Create `tests/corpus/test_db.py`:

```python
import pytest
from sanad.corpus import db
from sanad.corpus.models import Record, Source

SRC = Source(
    id="tanzil-uthmani-1.1", kind="quran-arabic", title="Tanzil Uthmani",
    publisher="Tanzil Project", edition="1.1", url="https://tanzil.net/",
    license_id="CC-BY-3.0", license_url="https://tanzil.net/docs/text_license",
    attribution="# Tanzil copyright block", retrieved_at="2026-09-19",
    upstream_sha256="deadbeef", modifications="none",
)


def _rec(rid: str, surah: int, ayah: int, text: str) -> Record:
    return Record(
        id=rid, source_id=SRC.id, kind="ayah", surah=surah, ayah=ayah,
        surah_name_ar="الإخلاص", surah_name_en="Al-Ikhlas",
        text_ar=text, text_ar_sha256="x" * 64,
        norm_light=text, norm_standard=text, norm_aggressive=text,
        reference_display=f"Al-Ikhlas {surah}:{ayah}",
    )


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db", read_only=False)
    db.insert_source(c, SRC)
    db.insert_records(c, [
        _rec("quran:112:1", 112, 1, "قل هو الله احد"),
        _rec("quran:112:2", 112, 2, "الله الصمد"),
    ])
    db.rebuild_fts(c)
    return c


def test_insert_and_get_roundtrip(conn):
    got = db.get_record(conn, "quran:112:1")
    assert got is not None
    assert got.text_ar == "قل هو الله احد"
    assert got.surah == 112


def test_get_missing_record_returns_none(conn):
    assert db.get_record(conn, "quran:999:1") is None


def test_iter_records_yields_all(conn):
    assert len(list(db.iter_records(conn))) == 2


def test_fts_candidates_finds_by_token(conn):
    hits = db.fts_candidates(conn, "الصمد")
    assert [h.id for h in hits] == ["quran:112:2"]


def test_fts_candidates_tolerates_fts_metacharacters(conn):
    # a quote containing quotes or hyphens must not raise a syntax error
    assert db.fts_candidates(conn, 'قل "هو" - الله') != []


def test_fts_candidates_empty_query_returns_empty(conn):
    assert db.fts_candidates(conn, "   ") == []


def test_corpus_stats(conn):
    stats = db.corpus_stats(conn)
    assert stats["records"] == 2
    assert stats["sources"] == 1


def test_read_only_connection_rejects_writes(tmp_path):
    p = tmp_path / "ro.db"
    db.connect(p, read_only=False).close()
    c = db.connect(p, read_only=True)
    with pytest.raises(Exception):
        c.execute("CREATE TABLE nope (x)")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/corpus -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sanad.corpus'`

- [ ] **Step 3: Implement `api/sanad/corpus/schema.py`**

```python
"""Corpus DDL. Stage A creates the full spec schema so Stage B needs no migration."""

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS sources (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL,
  title           TEXT NOT NULL,
  publisher       TEXT,
  edition         TEXT,
  url             TEXT NOT NULL,
  license_id      TEXT NOT NULL,
  license_url     TEXT,
  attribution     TEXT NOT NULL,
  retrieved_at    TEXT NOT NULL,
  upstream_sha256 TEXT NOT NULL,
  modifications   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
  id                TEXT PRIMARY KEY,
  source_id         TEXT NOT NULL REFERENCES sources(id),
  kind              TEXT NOT NULL,
  surah             INTEGER,
  ayah              INTEGER,
  surah_name_ar     TEXT,
  surah_name_en     TEXT,
  collection        TEXT,
  book_no           INTEGER,
  chapter_ar        TEXT,
  hadith_no         TEXT,
  numbering_scheme  TEXT,
  text_ar           TEXT NOT NULL,
  text_ar_sha256    TEXT NOT NULL,
  norm_light        TEXT NOT NULL,
  norm_standard     TEXT NOT NULL,
  norm_aggressive   TEXT NOT NULL,
  reference_display TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_ref ON records(surah, ayah);
CREATE INDEX IF NOT EXISTS idx_records_norm_std ON records(norm_standard);
CREATE INDEX IF NOT EXISTS idx_records_norm_light ON records(norm_light);

CREATE TABLE IF NOT EXISTS translations (
  record_id TEXT NOT NULL REFERENCES records(id),
  source_id TEXT NOT NULL REFERENCES sources(id),
  lang      TEXT NOT NULL,
  text      TEXT NOT NULL,
  PRIMARY KEY (record_id, source_id)
);

CREATE TABLE IF NOT EXISTS gradings (
  record_id    TEXT NOT NULL REFERENCES records(id),
  authority    TEXT NOT NULL,
  grade        TEXT NOT NULL,
  is_classical INTEGER NOT NULL,
  source_id    TEXT NOT NULL REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS embeddings (
  record_id TEXT PRIMARY KEY REFERENCES records(id),
  model     TEXT NOT NULL,
  dim       INTEGER NOT NULL,
  vec       BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
  id          INTEGER PRIMARY KEY,
  ts          TEXT NOT NULL,
  request_id  TEXT NOT NULL,
  stage       TEXT NOT NULL,
  verdict     TEXT NOT NULL,
  detail_json TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
  record_id UNINDEXED,
  norm_standard,
  norm_aggressive,
  translation,
  tokenize = "unicode61 remove_diacritics 2"
);
"""
```

- [ ] **Step 4: Implement `api/sanad/corpus/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    title: str
    publisher: Optional[str]
    edition: Optional[str]
    url: str
    license_id: str
    license_url: Optional[str]
    attribution: str
    retrieved_at: str
    upstream_sha256: str
    modifications: str


@dataclass(frozen=True)
class Record:
    id: str
    source_id: str
    kind: str
    text_ar: str
    text_ar_sha256: str
    norm_light: str
    norm_standard: str
    norm_aggressive: str
    reference_display: str
    surah: Optional[int] = None
    ayah: Optional[int] = None
    surah_name_ar: Optional[str] = None
    surah_name_en: Optional[str] = None
    collection: Optional[str] = None
    book_no: Optional[int] = None
    chapter_ar: Optional[str] = None
    hadith_no: Optional[str] = None
    numbering_scheme: Optional[str] = None
```

- [ ] **Step 5: Implement `api/sanad/corpus/db.py`**

```python
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .models import Record, Source
from .schema import SCHEMA_SQL

_RECORD_COLS = (
    "id", "source_id", "kind", "surah", "ayah", "surah_name_ar", "surah_name_en",
    "collection", "book_no", "chapter_ar", "hadith_no", "numbering_scheme",
    "text_ar", "text_ar_sha256", "norm_light", "norm_standard",
    "norm_aggressive", "reference_display",
)

# FTS5 treats these as syntax; a user's quote must never be parsed as a query.
_FTS_UNSAFE = re.compile(r'[^\w؀-ۿ ]', re.UNICODE)


def connect(path: str | Path, *, read_only: bool = True) -> sqlite3.Connection:
    path = Path(path)
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA_SQL)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_record(row: sqlite3.Row) -> Record:
    return Record(**{c: row[c] for c in _RECORD_COLS})


def insert_source(conn: sqlite3.Connection, source: Source) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sources (id, kind, title, publisher, edition, url,"
        " license_id, license_url, attribution, retrieved_at, upstream_sha256,"
        " modifications) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (source.id, source.kind, source.title, source.publisher, source.edition,
         source.url, source.license_id, source.license_url, source.attribution,
         source.retrieved_at, source.upstream_sha256, source.modifications),
    )
    conn.commit()


def insert_records(conn: sqlite3.Connection, records: Iterable[Record]) -> int:
    rows = [tuple(getattr(r, c) for c in _RECORD_COLS) for r in records]
    placeholders = ",".join("?" * len(_RECORD_COLS))
    conn.executemany(
        f"INSERT OR REPLACE INTO records ({','.join(_RECORD_COLS)}) "
        f"VALUES ({placeholders})", rows)
    conn.commit()
    return len(rows)


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM records_fts")
    conn.execute(
        "INSERT INTO records_fts (record_id, norm_standard, norm_aggressive, translation) "
        "SELECT r.id, r.norm_standard, r.norm_aggressive,"
        "       COALESCE((SELECT group_concat(t.text, ' ') FROM translations t"
        "                 WHERE t.record_id = r.id), '')"
        " FROM records r")
    conn.commit()


def iter_records(conn: sqlite3.Connection) -> Iterator[Record]:
    for row in conn.execute(f"SELECT {','.join(_RECORD_COLS)} FROM records"):
        yield _row_to_record(row)


def get_record(conn: sqlite3.Connection, record_id: str) -> Optional[Record]:
    row = conn.execute(
        f"SELECT {','.join(_RECORD_COLS)} FROM records WHERE id = ?",
        (record_id,)).fetchone()
    return _row_to_record(row) if row else None


def fts_candidates(conn: sqlite3.Connection, query_norm: str,
                   limit: int = 50) -> list[Record]:
    """Token-OR search. Input is sanitized: a quotation is data, never a query."""
    tokens = [t for t in _FTS_UNSAFE.sub(" ", query_norm).split() if len(t) > 1]
    if not tokens:
        return []
    match = " OR ".join(f'"{t}"' for t in tokens)
    rows = conn.execute(
        f"SELECT r.{', r.'.join(_RECORD_COLS)} FROM records_fts f"
        " JOIN records r ON r.id = f.record_id"
        " WHERE records_fts MATCH ? ORDER BY bm25(records_fts) LIMIT ?",
        (match, limit)).fetchall()
    return [_row_to_record(r) for r in rows]


def corpus_stats(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "records": conn.execute("SELECT count(*) FROM records").fetchone()[0],
        "sources": conn.execute("SELECT count(*) FROM sources").fetchone()[0],
        "translations": conn.execute("SELECT count(*) FROM translations").fetchone()[0],
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/corpus -v`
Expected: PASS, 11 tests.

- [ ] **Step 7: Commit**

```bash
git add api/sanad/corpus tests/corpus
git commit -m "feat(corpus): SQLite schema, models, and FTS5-backed access layer

Query input is sanitized before reaching MATCH so a pasted quotation
containing FTS5 metacharacters is treated as data, not as a query."
```

---

### Task 4: Lockfile — the provenance contract

**Files:**
- Create: `ingest/corpus.lock.toml`
- Create: `ingest/sanad_ingest/__init__.py`, `ingest/sanad_ingest/lockfile.py`
- Test: `tests/ingest/test_lockfile.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `LockedSource` dataclass: `id, kind, title, publisher, edition, url, license_id, license_url, content_sha256, expected_lines, modifications`
  - `load_lockfile(path: str | Path) -> list[LockedSource]`
  - `LockfileError(Exception)`

- [ ] **Step 1: Create `ingest/corpus.lock.toml`**

The `content_sha256` and `expected_lines` values below are measured, not guessed.

```toml
# Sanad corpus lockfile.
#
# Every bundled source is pinned here with a content hash. sanad-ingest refuses
# to build if a download does not match. A corpus that cannot be reproduced is
# not shipped.
#
# content_sha256 covers the VERSE PAYLOAD ONLY -- the "surah|ayah|text" lines
# joined with "\n". It deliberately excludes the trailing copyright block,
# which embeds the current year and would otherwise change the hash annually.
# The copyright block is still captured verbatim into sources.attribution.

lockfile_version = 1

[[source]]
id             = "tanzil-uthmani-1.1"
kind           = "quran-arabic"
title          = "Tanzil Qur'an Text (Uthmani)"
publisher      = "Tanzil Project"
edition        = "1.1"
url            = "https://tanzil.net/pub/download/index.php?quranType=uthmani&outType=txt-2&agree=true"
license_id     = "CC-BY-3.0"
license_url    = "https://tanzil.net/docs/text_license"
content_sha256 = "36da55e256f54f4838b6fa1c78781734346c8d9ffde52daf5a3cbfa32626a08c"
expected_lines = 6236
modifications  = "none"

# -- NOT YET RESOLVED ---------------------------------------------------------
# Qur'an translation: Tanzil is ruled out. tanzil.net/trans restricts its
# translations to non-commercial use, which is narrower than the CC BY 3.0 on
# their Arabic text. Pickthall (d. 1936) is public domain, but we need a
# transcription from a distributor that imposes no terms of its own.
# See the spec, section 14.2. Display-only layer; does not gate Stage A.
#
# Hadith Arabic matn: source not chosen. See the spec, section 14.1.
```

- [ ] **Step 2: Write the failing test**

Create `tests/ingest/test_lockfile.py`:

```python
import pytest
from sanad_ingest.lockfile import LockfileError, load_lockfile

REAL = "ingest/corpus.lock.toml"


def test_loads_the_real_lockfile():
    sources = load_lockfile(REAL)
    assert len(sources) == 1
    s = sources[0]
    assert s.id == "tanzil-uthmani-1.1"
    assert s.expected_lines == 6236
    assert s.license_id == "CC-BY-3.0"
    assert len(s.content_sha256) == 64


def test_rejects_missing_required_field(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('lockfile_version = 1\n[[source]]\nid = "x"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="missing"):
        load_lockfile(p)


def test_rejects_malformed_sha256(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id="x"\nkind="quran-arabic"\ntitle="t"\nurl="u"\n'
        'license_id="CC-BY-3.0"\ncontent_sha256="nothex"\n'
        'expected_lines=1\nmodifications="none"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="sha256"):
        load_lockfile(p)


def test_rejects_unknown_lockfile_version(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text("lockfile_version = 99\n", encoding="utf-8")
    with pytest.raises(LockfileError, match="version"):
        load_lockfile(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(LockfileError, match="not found"):
        load_lockfile(tmp_path / "nope.toml")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/ingest/test_lockfile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sanad_ingest'`

- [ ] **Step 4: Implement `ingest/sanad_ingest/lockfile.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

SUPPORTED_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED = ("id", "kind", "title", "url", "license_id",
             "content_sha256", "expected_lines", "modifications")


class LockfileError(Exception):
    pass


@dataclass(frozen=True)
class LockedSource:
    id: str
    kind: str
    title: str
    url: str
    license_id: str
    content_sha256: str
    expected_lines: int
    modifications: str
    publisher: Optional[str] = None
    edition: Optional[str] = None
    license_url: Optional[str] = None


def load_lockfile(path: str | Path) -> list[LockedSource]:
    path = Path(path)
    if not path.is_file():
        raise LockfileError(f"lockfile not found: {path}")

    data = tomllib.loads(path.read_text(encoding="utf-8"))

    version = data.get("lockfile_version")
    if version != SUPPORTED_VERSION:
        raise LockfileError(
            f"unsupported lockfile version {version!r}; expected {SUPPORTED_VERSION}")

    out: list[LockedSource] = []
    for entry in data.get("source", []):
        missing = [f for f in _REQUIRED if f not in entry]
        if missing:
            raise LockfileError(
                f"source {entry.get('id', '<unnamed>')!r} missing: {', '.join(missing)}")
        if not _SHA256.match(entry["content_sha256"]):
            raise LockfileError(
                f"source {entry['id']!r} has a malformed sha256")
        out.append(LockedSource(**{k: entry.get(k) for k in
                                   list(_REQUIRED) + ["publisher", "edition", "license_url"]}))
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/ingest/test_lockfile.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add ingest/corpus.lock.toml ingest/sanad_ingest tests/ingest
git commit -m "feat(ingest): corpus lockfile with measured Tanzil content hash

content_sha256 covers the verse payload only. Tanzil's trailing copyright
block embeds the current year, so hashing the whole file would break every
January. The block is still captured verbatim for attribution."
```

---

### Task 5: Tanzil parser

**Files:**
- Create: `ingest/sanad_ingest/tanzil.py`
- Create: `tests/fixtures/tanzil_excerpt.txt`
- Test: `tests/ingest/test_tanzil.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ParsedTanzil` dataclass: `verses: list[tuple[int, int, str]]`, `attribution: str`, `content_sha256: str`
  - `parse_tanzil(raw: str) -> ParsedTanzil`
  - `TanzilParseError(Exception)`

- [ ] **Step 1: Create the fixture `tests/fixtures/tanzil_excerpt.txt`**

Byte-for-byte in the real file's shape: verse lines, then a `#` copyright block.

```text
1|1|بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ
1|2|ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ
112|1|قُلْ هُوَ ٱللَّهُ أَحَدٌ
112|2|ٱللَّهُ ٱلصَّمَدُ

# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK
#====================================================================
#
#  Tanzil Quran Text (Uthmani, Version 1.1)
#  Copyright (C) 2007-2026 Tanzil Project
#  License: Creative Commons Attribution 3.0
#
```

- [ ] **Step 2: Write the failing test**

Create `tests/ingest/test_tanzil.py`:

```python
import hashlib
from pathlib import Path

import pytest
from sanad_ingest.tanzil import TanzilParseError, parse_tanzil

FIXTURE = Path("tests/fixtures/tanzil_excerpt.txt")


@pytest.fixture()
def parsed():
    return parse_tanzil(FIXTURE.read_text(encoding="utf-8"))


def test_extracts_every_verse(parsed):
    assert len(parsed.verses) == 4


def test_verse_tuple_shape(parsed):
    surah, ayah, text = parsed.verses[0]
    assert (surah, ayah) == (1, 1)
    assert text.startswith("بِسْمِ")


def test_pipe_inside_text_is_not_a_delimiter():
    p = parse_tanzil("2|1|alpha|beta\n")
    assert p.verses == [(2, 1, "alpha|beta")]


def test_attribution_captures_the_copyright_block(parsed):
    assert "PLEASE DO NOT REMOVE" in parsed.attribution
    assert "Creative Commons Attribution 3.0" in parsed.attribution


def test_attribution_excludes_verse_lines(parsed):
    assert "بِسْمِ" not in parsed.attribution


def test_content_hash_covers_verses_only(parsed):
    payload = "\n".join(f"{s}|{a}|{t}" for s, a, t in parsed.verses)
    assert parsed.content_sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_content_hash_is_stable_across_copyright_year_change():
    base = "1|1|نص\n\n# Copyright (C) 2007-2026 Tanzil Project\n"
    later = "1|1|نص\n\n# Copyright (C) 2007-2031 Tanzil Project\n"
    assert parse_tanzil(base).content_sha256 == parse_tanzil(later).content_sha256


def test_empty_input_raises():
    with pytest.raises(TanzilParseError, match="no verse"):
        parse_tanzil("# only a comment\n")


def test_malformed_verse_line_raises():
    with pytest.raises(TanzilParseError, match="line 2"):
        parse_tanzil("1|1|ok\nnot-a-verse-line\n")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/ingest/test_tanzil.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement `ingest/sanad_ingest/tanzil.py`**

```python
"""Parser for Tanzil's "text with aya numbers" export.

Format, verified 2026-09-19: UTF-8, LF, one verse per line as
"surah|ayah|text", followed by a 28-line copyright block whose lines begin
with "#". The block embeds the current year, so it is excluded from the
content hash but captured verbatim for attribution.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_VERSE = re.compile(r"^(\d{1,3})\|(\d{1,3})\|(.*)$")


class TanzilParseError(Exception):
    pass


@dataclass(frozen=True)
class ParsedTanzil:
    verses: list[tuple[int, int, str]]
    attribution: str
    content_sha256: str


def parse_tanzil(raw: str) -> ParsedTanzil:
    verses: list[tuple[int, int, str]] = []
    notice: list[str] = []

    for lineno, line in enumerate(raw.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            notice.append(stripped)
            continue
        m = _VERSE.match(line)
        if not m:
            raise TanzilParseError(f"unrecognized content at line {lineno}: {line[:40]!r}")
        # split on the first two pipes only; the text may legitimately contain one
        verses.append((int(m.group(1)), int(m.group(2)), m.group(3).strip()))

    if not verses:
        raise TanzilParseError("no verse lines found in input")

    payload = "\n".join(f"{s}|{a}|{t}" for s, a, t in verses)
    return ParsedTanzil(
        verses=verses,
        attribution="\n".join(notice),
        content_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/ingest/test_tanzil.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 6: Commit**

```bash
git add ingest/sanad_ingest/tanzil.py tests/ingest/test_tanzil.py tests/fixtures
git commit -m "feat(ingest): Tanzil pipe-format parser with year-stable content hash"
```

---

### Task 6: Fetch with hash verification, and the build CLI

**Files:**
- Create: `ingest/sanad_ingest/fetch.py`, `build.py`, `cli.py`
- Create: `api/sanad/corpus/surahs.py`
- Test: `tests/ingest/test_fetch.py`, `tests/ingest/test_build.py`

**Interfaces:**
- Consumes: `load_lockfile`, `LockedSource`, `parse_tanzil`, `db.*`, `normalize`.
- Produces:
  - `fetch.fetch_source(src: LockedSource, cache_dir: Path) -> str` — returns raw text; caches
  - `fetch.HashMismatch(Exception)`
  - `build.build_corpus(lockfile: Path, out_db: Path, cache_dir: Path) -> dict[str, int]`
  - `surahs.SURAH_NAMES: dict[int, tuple[str, str]]` — `{number: (arabic, english)}`
  - `cli.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Create `api/sanad/corpus/surahs.py`**

Surah names are metadata, not scripture — they are not in the Tanzil file and
cannot be derived from it, so the table is written out in full. Copy verbatim:

```python
"""Surah names. Metadata, not scripture: these are not part of the Tanzil text,
so they are not covered by its licence and are not checksummed with it."""

SURAH_NAMES: dict[int, tuple[str, str]] = {
    1: ("الفاتحة", "Al-Fatihah"),      2: ("البقرة", "Al-Baqarah"),
    3: ("آل عمران", "Aal-E-Imran"),    4: ("النساء", "An-Nisa"),
    5: ("المائدة", "Al-Maidah"),       6: ("الأنعام", "Al-Anam"),
    7: ("الأعراف", "Al-Araf"),         8: ("الأنفال", "Al-Anfal"),
    9: ("التوبة", "At-Tawbah"),       10: ("يونس", "Yunus"),
   11: ("هود", "Hud"),                12: ("يوسف", "Yusuf"),
   13: ("الرعد", "Ar-Rad"),           14: ("إبراهيم", "Ibrahim"),
   15: ("الحجر", "Al-Hijr"),          16: ("النحل", "An-Nahl"),
   17: ("الإسراء", "Al-Isra"),        18: ("الكهف", "Al-Kahf"),
   19: ("مريم", "Maryam"),            20: ("طه", "Taha"),
   21: ("الأنبياء", "Al-Anbiya"),     22: ("الحج", "Al-Hajj"),
   23: ("المؤمنون", "Al-Muminun"),    24: ("النور", "An-Nur"),
   25: ("الفرقان", "Al-Furqan"),      26: ("الشعراء", "Ash-Shuara"),
   27: ("النمل", "An-Naml"),          28: ("القصص", "Al-Qasas"),
   29: ("العنكبوت", "Al-Ankabut"),    30: ("الروم", "Ar-Rum"),
   31: ("لقمان", "Luqman"),           32: ("السجدة", "As-Sajdah"),
   33: ("الأحزاب", "Al-Ahzab"),       34: ("سبأ", "Saba"),
   35: ("فاطر", "Fatir"),             36: ("يس", "Ya-Sin"),
   37: ("الصافات", "As-Saffat"),      38: ("ص", "Sad"),
   39: ("الزمر", "Az-Zumar"),         40: ("غافر", "Ghafir"),
   41: ("فصلت", "Fussilat"),          42: ("الشورى", "Ash-Shura"),
   43: ("الزخرف", "Az-Zukhruf"),      44: ("الدخان", "Ad-Dukhan"),
   45: ("الجاثية", "Al-Jathiyah"),    46: ("الأحقاف", "Al-Ahqaf"),
   47: ("محمد", "Muhammad"),          48: ("الفتح", "Al-Fath"),
   49: ("الحجرات", "Al-Hujurat"),     50: ("ق", "Qaf"),
   51: ("الذاريات", "Adh-Dhariyat"),  52: ("الطور", "At-Tur"),
   53: ("النجم", "An-Najm"),          54: ("القمر", "Al-Qamar"),
   55: ("الرحمن", "Ar-Rahman"),       56: ("الواقعة", "Al-Waqiah"),
   57: ("الحديد", "Al-Hadid"),        58: ("المجادلة", "Al-Mujadila"),
   59: ("الحشر", "Al-Hashr"),         60: ("الممتحنة", "Al-Mumtahanah"),
   61: ("الصف", "As-Saff"),           62: ("الجمعة", "Al-Jumuah"),
   63: ("المنافقون", "Al-Munafiqun"), 64: ("التغابن", "At-Taghabun"),
   65: ("الطلاق", "At-Talaq"),        66: ("التحريم", "At-Tahrim"),
   67: ("الملك", "Al-Mulk"),          68: ("القلم", "Al-Qalam"),
   69: ("الحاقة", "Al-Haqqah"),       70: ("المعارج", "Al-Maarij"),
   71: ("نوح", "Nuh"),                72: ("الجن", "Al-Jinn"),
   73: ("المزمل", "Al-Muzzammil"),    74: ("المدثر", "Al-Muddaththir"),
   75: ("القيامة", "Al-Qiyamah"),     76: ("الإنسان", "Al-Insan"),
   77: ("المرسلات", "Al-Mursalat"),   78: ("النبأ", "An-Naba"),
   79: ("النازعات", "An-Naziat"),     80: ("عبس", "Abasa"),
   81: ("التكوير", "At-Takwir"),      82: ("الانفطار", "Al-Infitar"),
   83: ("المطففين", "Al-Mutaffifin"), 84: ("الانشقاق", "Al-Inshiqaq"),
   85: ("البروج", "Al-Buruj"),        86: ("الطارق", "At-Tariq"),
   87: ("الأعلى", "Al-Ala"),          88: ("الغاشية", "Al-Ghashiyah"),
   89: ("الفجر", "Al-Fajr"),          90: ("البلد", "Al-Balad"),
   91: ("الشمس", "Ash-Shams"),        92: ("الليل", "Al-Layl"),
   93: ("الضحى", "Ad-Duha"),          94: ("الشرح", "Ash-Sharh"),
   95: ("التين", "At-Tin"),           96: ("العلق", "Al-Alaq"),
   97: ("القدر", "Al-Qadr"),          98: ("البينة", "Al-Bayyinah"),
   99: ("الزلزلة", "Az-Zalzalah"),   100: ("العاديات", "Al-Adiyat"),
  101: ("القارعة", "Al-Qariah"),     102: ("التكاثر", "At-Takathur"),
  103: ("العصر", "Al-Asr"),          104: ("الهمزة", "Al-Humazah"),
  105: ("الفيل", "Al-Fil"),          106: ("قريش", "Quraysh"),
  107: ("الماعون", "Al-Maun"),       108: ("الكوثر", "Al-Kawthar"),
  109: ("الكافرون", "Al-Kafirun"),   110: ("النصر", "An-Nasr"),
  111: ("المسد", "Al-Masad"),        112: ("الإخلاص", "Al-Ikhlas"),
  113: ("الفلق", "Al-Falaq"),        114: ("الناس", "An-Nas"),
}

assert len(SURAH_NAMES) == 114, f"expected 114 surahs, got {len(SURAH_NAMES)}"


def surah_name(number: int) -> tuple[str, str]:
    try:
        return SURAH_NAMES[number]
    except KeyError:
        raise KeyError(f"surah {number} not in SURAH_NAMES (expected 1-114)") from None
```

- [ ] **Step 2: Write the failing tests**

Create `tests/ingest/test_fetch.py`:

```python
import pytest
from sanad_ingest.fetch import HashMismatch, fetch_source
from sanad_ingest.lockfile import LockedSource

RAW = "1|1|نص\n\n# Copyright (C) 2007-2026 Tanzil Project\n"
# sha256 of the verse payload "1|1|نص"
import hashlib
GOOD = hashlib.sha256("1|1|نص".encode("utf-8")).hexdigest()


def _src(sha: str) -> LockedSource:
    return LockedSource(
        id="t", kind="quran-arabic", title="T", url="https://example.invalid/q",
        license_id="CC-BY-3.0", content_sha256=sha, expected_lines=1,
        modifications="none")


def test_uses_cache_and_returns_raw_text(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "t.txt").write_text(RAW, encoding="utf-8")
    monkeypatch.setattr("sanad_ingest.fetch._download",
                        lambda url: pytest.fail("must not download when cached"))
    assert fetch_source(_src(GOOD), cache) == RAW


def test_downloads_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    assert fetch_source(_src(GOOD), tmp_path) == RAW
    assert (tmp_path / "t.txt").is_file()


def test_hash_mismatch_raises_and_does_not_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    with pytest.raises(HashMismatch, match="t"):
        fetch_source(_src("0" * 64), tmp_path)
    assert not (tmp_path / "t.txt").exists()


def test_line_count_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    src = LockedSource(
        id="t", kind="quran-arabic", title="T", url="https://example.invalid/q",
        license_id="CC-BY-3.0", content_sha256=GOOD, expected_lines=6236,
        modifications="none")
    with pytest.raises(HashMismatch, match="6236"):
        fetch_source(src, tmp_path)
```

Create `tests/ingest/test_build.py`:

```python
import hashlib
from pathlib import Path

import pytest
from sanad.corpus import db
from sanad_ingest.build import build_corpus

FIXTURE = Path("tests/fixtures/tanzil_excerpt.txt")


@pytest.fixture()
def built(tmp_path, monkeypatch):
    raw = FIXTURE.read_text(encoding="utf-8")
    payload = "\n".join(
        l for l in raw.split("\n") if l.strip() and not l.strip().startswith("#"))
    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    lock = tmp_path / "corpus.lock.toml"
    lock.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id = "tanzil-uthmani-1.1"\nkind = "quran-arabic"\n'
        'title = "Tanzil Uthmani"\npublisher = "Tanzil Project"\n'
        'edition = "1.1"\nurl = "https://example.invalid/q"\n'
        'license_id = "CC-BY-3.0"\nlicense_url = "https://tanzil.net/docs/text_license"\n'
        f'content_sha256 = "{sha}"\nexpected_lines = 4\nmodifications = "none"\n',
        encoding="utf-8")

    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: raw)
    out = tmp_path / "sanad.db"
    stats = build_corpus(lock, out, tmp_path / "cache")
    return out, stats


def test_builds_expected_record_count(built):
    _, stats = built
    assert stats["records"] == 4


def test_canonical_text_is_stored_unmodified(built):
    out, _ = built
    conn = db.connect(out)
    rec = db.get_record(conn, "quran:112:1")
    assert rec.text_ar == "قُلْ هُوَ ٱللَّهُ أَحَدٌ"  # diacritics and wasla intact


def test_normalized_columns_are_populated(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.norm_standard == "قل هو الله احد"
    assert rec.norm_light != rec.norm_standard


def test_text_checksum_is_of_canonical_text(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.text_ar_sha256 == hashlib.sha256(rec.text_ar.encode("utf-8")).hexdigest()


def test_attribution_block_is_stored_verbatim(built):
    out, _ = built
    row = db.connect(out).execute(
        "SELECT attribution FROM sources WHERE id='tanzil-uthmani-1.1'").fetchone()
    assert "PLEASE DO NOT REMOVE" in row["attribution"]


def test_reference_display_uses_surah_name(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.reference_display == "Al-Ikhlas 112:1"


def test_fts_is_populated(built):
    out, _ = built
    assert db.fts_candidates(db.connect(out), "الصمد") != []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/ingest/test_fetch.py tests/ingest/test_build.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement `ingest/sanad_ingest/fetch.py`**

```python
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import httpx

from .lockfile import LockedSource
from .tanzil import parse_tanzil

log = logging.getLogger(__name__)


class HashMismatch(Exception):
    pass


def _download(url: str) -> str:
    resp = httpx.get(url, follow_redirects=True, timeout=120.0)
    resp.raise_for_status()
    return resp.text


def fetch_source(src: LockedSource, cache_dir: Path) -> str:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{src.id}.txt"

    raw = cached.read_text(encoding="utf-8") if cached.is_file() else _download(src.url)

    parsed = parse_tanzil(raw)
    if len(parsed.verses) != src.expected_lines:
        raise HashMismatch(
            f"{src.id}: expected {src.expected_lines} verse lines, "
            f"got {len(parsed.verses)}")
    if parsed.content_sha256 != src.content_sha256:
        raise HashMismatch(
            f"{src.id}: content sha256 mismatch\n"
            f"  lockfile: {src.content_sha256}\n"
            f"  download: {parsed.content_sha256}\n"
            "Upstream changed, or the download is corrupt. Do not update the "
            "lockfile without reviewing the diff.")

    if not cached.is_file():
        cached.write_text(raw, encoding="utf-8")
    log.info("verified %s (%d verses)", src.id, len(parsed.verses))
    return raw
```

- [ ] **Step 5: Implement `ingest/sanad_ingest/build.py`**

```python
from __future__ import annotations

import datetime as _dt
import hashlib
import logging
from pathlib import Path

from sanad.arabic.normalize import normalize
from sanad.corpus import db
from sanad.corpus.models import Record, Source
from sanad.corpus.surahs import surah_name

from .fetch import fetch_source
from .lockfile import load_lockfile
from .tanzil import parse_tanzil

log = logging.getLogger(__name__)


def build_corpus(lockfile: Path, out_db: Path, cache_dir: Path) -> dict[str, int]:
    out_db = Path(out_db)
    if out_db.exists():
        out_db.unlink()

    conn = db.connect(out_db, read_only=False)
    today = _dt.date.today().isoformat()

    for locked in load_lockfile(lockfile):
        if locked.kind != "quran-arabic":
            log.warning("skipping %s: kind %r not handled in Stage A",
                        locked.id, locked.kind)
            continue

        raw = fetch_source(locked, cache_dir)
        parsed = parse_tanzil(raw)

        db.insert_source(conn, Source(
            id=locked.id, kind=locked.kind, title=locked.title,
            publisher=locked.publisher, edition=locked.edition, url=locked.url,
            license_id=locked.license_id, license_url=locked.license_url,
            attribution=parsed.attribution, retrieved_at=today,
            upstream_sha256=parsed.content_sha256,
            modifications=locked.modifications,
        ))

        records = []
        for surah, ayah, text in parsed.verses:
            name_ar, name_en = surah_name(surah)
            records.append(Record(
                id=f"quran:{surah}:{ayah}", source_id=locked.id, kind="ayah",
                surah=surah, ayah=ayah, surah_name_ar=name_ar, surah_name_en=name_en,
                text_ar=text,
                text_ar_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                norm_light=normalize(text, "light"),
                norm_standard=normalize(text, "standard"),
                norm_aggressive=normalize(text, "aggressive"),
                reference_display=f"{name_en} {surah}:{ayah}",
            ))
        db.insert_records(conn, records)
        log.info("inserted %d records from %s", len(records), locked.id)

    db.rebuild_fts(conn)
    stats = db.corpus_stats(conn)
    conn.close()
    return stats
```

- [ ] **Step 6: Implement `ingest/sanad_ingest/cli.py`**

```python
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from .build import build_corpus
from .fetch import HashMismatch
from .lockfile import LockfileError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sanad-ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="build the corpus database")
    b.add_argument("--lockfile", type=Path, default=Path("ingest/corpus.lock.toml"))
    b.add_argument("--out", type=Path, default=Path("data/sanad.db"))
    b.add_argument("--cache", type=Path, default=Path(".corpus-cache"))
    b.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s")

    try:
        stats = build_corpus(args.lockfile, args.out, args.cache)
    except (LockfileError, HashMismatch) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(f"built {args.out}")
    print(f"  records      {stats['records']}")
    print(f"  sources      {stats['sources']}")
    print(f"  db sha256    {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/ingest -v`
Expected: PASS, 18 tests total across the ingest suite.

- [ ] **Step 8: Build the real corpus and verify it end to end**

```bash
pip install -e ".[dev]"
sanad-ingest build --out data/sanad-quran.db -v
```

Expected: `records 6236`, `sources 1`, and a db sha256. If the content hash does not match the lockfile the command exits 1 — that is correct behaviour, not a bug to work around.

- [ ] **Step 9: Commit**

```bash
git add ingest api/sanad/corpus/surahs.py tests/ingest data/sanad-quran.db
git commit -m "feat(ingest): hash-verified fetch, corpus builder, and sanad-ingest CLI

Build refuses to proceed on a content-hash or verse-count mismatch. The
6,236-verse Qur'an database is committed so the repo is clone-and-run."
```

---

### Task 7: Quote and Arabic span extraction

**Files:**
- Create: `api/sanad/verify/__init__.py`, `api/sanad/verify/extract.py`
- Test: `tests/verify/test_extract.py`

**Interfaces:**
- Consumes: `sanad.arabic.normalize.normalize`.
- Produces:
  - `Span` dataclass: `text: str`, `start: int`, `end: int`, `kind: str` (`"wrapped"` or `"arabic-run"`)
  - `extract_spans(text: str, min_arabic_chars: int = 8) -> list[Span]`

- [ ] **Step 1: Write the failing test**

Create `tests/verify/test_extract.py`:

```python
from sanad.verify.extract import extract_spans


def test_extracts_guillemet_quote():
    spans = extract_spans('He said «قُلْ هُوَ ٱللَّهُ أَحَدٌ» today.')
    assert any(s.kind == "wrapped" and "قُلْ" in s.text for s in spans)


def test_extracts_curly_quote():
    spans = extract_spans('“قُلْ هُوَ ٱللَّهُ أَحَدٌ”')
    assert len(spans) >= 1


def test_extracts_ornate_parenthesis():
    spans = extract_spans('﴿قُلْ هُوَ ٱللَّهُ أَحَدٌ﴾')
    assert len(spans) >= 1


def test_extracts_bare_arabic_run():
    spans = extract_spans("Islam teaches إِنَّا أَعْطَيْنَاكَ ٱلْكَوْثَرَ in this surah.")
    assert any("أَعْطَيْنَٰ" in s.text or "أَعْطَيْنَا" in s.text for s in spans)


def test_offsets_point_into_the_original_text():
    text = "before قُلْ هُوَ ٱللَّهُ أَحَدٌ after"
    span = extract_spans(text)[0]
    assert text[span.start:span.end].strip() == span.text


def test_ignores_short_arabic_fragments():
    assert extract_spans("the word الله alone") == []


def test_deduplicates_overlapping_extractions():
    # a wrapped quote also matches the bare-Arabic pattern; only one span
    spans = extract_spans('«قُلْ هُوَ ٱللَّهُ أَحَدٌ»')
    assert len(spans) == 1


def test_returns_empty_for_pure_latin():
    assert extract_spans("no arabic here at all") == []


def test_handles_multiple_distinct_quotes():
    text = "«قُلْ هُوَ ٱللَّهُ أَحَدٌ» and «ٱللَّهُ ٱلصَّمَدُ»"
    assert len(extract_spans(text)) == 2


def test_spans_are_sorted_by_position():
    text = "«ٱللَّهُ ٱلصَّمَدُ» then «قُلْ هُوَ ٱللَّهُ أَحَدٌ»"
    spans = extract_spans(text)
    assert spans == sorted(spans, key=lambda s: s.start)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/verify/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `api/sanad/verify/extract.py`**

```python
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

_WRAPPED = re.compile(r"[«“\"『【﴿]([^»”\"』】﴾]{4,})[»”\"』】﴾]")
_ARABIC_RUN = re.compile(r"[؀-ۿ][؀-ۿ\s]{6,}")


@dataclass(frozen=True)
class Span:
    text: str
    start: int
    end: int
    kind: str


def extract_spans(text: str, min_arabic_chars: int = 8) -> list[Span]:
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
             if len(normalize(s.text, "aggressive").replace(" ", "")) >= min_arabic_chars]

    # wrapped wins over an overlapping bare run
    found.sort(key=lambda s: (s.start, s.kind != "wrapped"))
    kept: list[Span] = []
    for span in found:
        if any(span.start < k.end and k.start < span.end for k in kept):
            continue
        kept.append(span)
    return kept
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/verify/test_extract.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/verify tests/verify
git commit -m "feat(verify): quotation and Arabic-run span extraction"
```

---

### Task 8: Reference parsing

**Files:**
- Create: `api/sanad/verify/references.py`
- Generate: `api/sanad/verify/ayah_counts.py` (Step 4 — derived from the corpus, never hand-typed)
- Test: `tests/verify/test_references.py`

**Interfaces:**
- Consumes: `sanad.corpus.surahs.SURAH_NAMES`, `sanad.corpus.surahs.surah_name`.
- Produces:
  - `Reference` dataclass: `surah: int`, `ayah: int | None`, `raw: str`, `start: int`
  - `parse_references(text: str) -> list[Reference]`
  - `nearest_reference(refs: list[Reference], position: int, window: int = 180) -> Reference | None`

- [ ] **Step 1: Write the failing test**

Create `tests/verify/test_references.py`:

```python
from sanad.verify.references import Reference, nearest_reference, parse_references


def test_parses_numeric_reference():
    refs = parse_references("see 2:255 for this")
    assert (refs[0].surah, refs[0].ayah) == (2, 255)


def test_parses_named_surah_with_numbers():
    refs = parse_references("Al-Baqarah 2:255")
    assert (refs[0].surah, refs[0].ayah) == (2, 255)


def test_parses_bare_surah_name():
    refs = parse_references("as stated in Al-Ikhlas")
    assert refs[0].surah == 112
    assert refs[0].ayah is None


def test_surah_name_spelling_variants():
    for spelling in ("Al-Fatihah", "al fatiha", "AL-FATIHA"):
        assert parse_references(spelling)[0].surah == 1


def test_records_position_in_text():
    text = "aaaa 112:1 bbbb"
    assert parse_references(text)[0].start == text.index("112:1")


def test_ignores_out_of_range_surah():
    assert parse_references("999:1") == []


def test_ignores_out_of_range_ayah():
    # Al-Fatihah has 7 verses; 300 is impossible
    assert parse_references("1:300") == []


def test_no_reference_returns_empty():
    assert parse_references("no citation here") == []


def test_nearest_reference_picks_closest():
    refs = [Reference(2, 255, "2:255", 0), Reference(112, 1, "112:1", 500)]
    assert nearest_reference(refs, 480).surah == 112


def test_nearest_reference_respects_window():
    refs = [Reference(2, 255, "2:255", 0)]
    assert nearest_reference(refs, 5000, window=180) is None


def test_nearest_reference_on_empty_list():
    assert nearest_reference([], 0) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/verify/test_references.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `api/sanad/verify/references.py`**

```python
"""Find Qur'an references in prose: "2:255", "Al-Baqarah 2:255", "Al-Ikhlas"."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from ..corpus.surahs import SURAH_NAMES

# Verses per surah. Generated from the built corpus by the step below -- never
# typed by hand, so it cannot disagree with the text we actually shipped.
from .ayah_counts import AYAH_COUNTS  # noqa: E402

_NUMERIC = re.compile(r"\b(\d{1,3})\s*[:：]\s*(\d{1,3})\b")

# A bare English word is only treated as a surah name if it carries the "al-"
# article or is reasonably long. Without this, "Sad" (38), "Hud" (11), "Nuh"
# (71) and "Qaf" (50) would fire on ordinary English prose.
_MIN_BARE_NAME = 5

_NAME_CANDIDATE = re.compile(r"\b(?:al[-\s]?)?[A-Za-z]{3,}\b", re.I)


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def _spelling_variants(english_name: str) -> set[str]:
    """Accept Fatiha/Fatihah, Baqara/Baqarah, with or without the article."""
    base = _slug(english_name)
    out = {base}
    if base.endswith("h"):
        out.add(base[:-1])
    for prefix in ("al", "ad", "adh", "an", "ar", "as", "ash", "at", "az"):
        if base.startswith(prefix):
            stem = base[len(prefix):]
            if len(stem) >= 3:
                out.add(stem)
                if stem.endswith("h"):
                    out.add(stem[:-1])
    return out


_NAME_TO_SURAH: dict[str, int] = {}
for _num, (_ar, _en) in SURAH_NAMES.items():
    for _variant in _spelling_variants(_en):
        _NAME_TO_SURAH.setdefault(_variant, _num)


@dataclass(frozen=True)
class Reference:
    surah: int
    ayah: Optional[int]
    raw: str
    start: int


def _valid(surah: int, ayah: Optional[int]) -> bool:
    if surah not in AYAH_COUNTS:
        return False
    return ayah is None or 1 <= ayah <= AYAH_COUNTS[surah]


def parse_references(text: str) -> list[Reference]:
    refs: list[Reference] = []
    claimed: list[tuple[int, int]] = []

    for m in _NUMERIC.finditer(text):
        surah, ayah = int(m.group(1)), int(m.group(2))
        if _valid(surah, ayah):
            refs.append(Reference(surah, ayah, m.group(0), m.start()))
            claimed.append((m.start(), m.end()))

    for m in _NAME_CANDIDATE.finditer(text):
        slug = _slug(m.group(0))
        num = _NAME_TO_SURAH.get(slug)
        if num is None:
            continue
        if not slug.startswith("al") and len(slug) < _MIN_BARE_NAME:
            continue  # "sad", "hud", "nuh", "qaf" as ordinary English words
        # a named surah adjacent to a numeric ref we already captured is a duplicate
        if any(abs(m.start() - s) < 24 for s, _e in claimed):
            continue
        refs.append(Reference(num, None, m.group(0), m.start()))

    return sorted(refs, key=lambda r: r.start)


def nearest_reference(refs: list[Reference], position: int,
                      window: int = 180) -> Optional[Reference]:
    candidates = [r for r in refs if abs(r.start - position) <= window]
    if not candidates:
        return None
    return min(candidates, key=lambda r: abs(r.start - position))
```

- [ ] **Step 4: Generate `api/sanad/verify/ayah_counts.py` from the built corpus**

Deriving this from the shipped database rather than typing it means the
validator can never disagree with the text actually in the corpus.

```bash
python - <<'PY'
from pathlib import Path
from sanad.corpus import db

conn = db.connect("data/sanad-quran.db")
rows = conn.execute(
    "SELECT surah, max(ayah) FROM records WHERE kind='ayah' "
    "GROUP BY surah ORDER BY surah").fetchall()
counts = {int(s): int(a) for s, a in rows}
assert len(counts) == 114, f"expected 114 surahs, got {len(counts)}"
assert sum(counts.values()) == 6236, f"expected 6236 ayat, got {sum(counts.values())}"

lines = ['"""Verses per surah. GENERATED from data/sanad-quran.db -- do not edit.',
         '',
         'Regenerate with the snippet in the Stage A plan, Task 8 Step 4.',
         '"""',
         '',
         "AYAH_COUNTS: dict[int, int] = {"]
for i in range(0, 114, 6):
    chunk = [f"{n}: {counts[n]}," for n in range(i + 1, min(i + 7, 115))]
    lines.append("    " + " ".join(chunk))
lines += ["}", "",
          'assert len(AYAH_COUNTS) == 114',
          'assert sum(AYAH_COUNTS.values()) == 6236', ""]
Path("api/sanad/verify/ayah_counts.py").write_text("\n".join(lines), encoding="utf-8")
print("wrote api/sanad/verify/ayah_counts.py")
PY
```

Expected: the two asserts pass and the file is written. If either assert fails,
the corpus build is wrong — fix that before continuing, do not edit around it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/verify/test_references.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 6: Commit**

```bash
git add api/sanad/verify/references.py api/sanad/verify/ayah_counts.py \
        tests/verify/test_references.py
git commit -m "feat(verify): reference parsing with range validation

Ayah counts are derived from the built corpus, so an impossible citation
like 1:300 is rejected rather than silently treated as a mismatch."
```

---

### Task 9: The verification engine

This is the core of Stage A. The verdict taxonomy and its tier coupling come straight from the spec's section 6.

**Files:**
- Create: `api/sanad/verify/engine.py`
- Test: `tests/verify/test_engine.py`

**Interfaces:**
- Consumes: `normalize`, `ratio_at`, `db.fts_candidates`, `db.iter_records`, `extract_spans`, `parse_references`, `nearest_reference`.
- Produces:
  - `Verdict` — str enum: `EXACT`, `EXACT_ORTHOGRAPHY`, `NEAR_MATCH`, `WRONG_REFERENCE`, `NOT_FOUND`
  - `Match` dataclass: `span: Span`, `verdict: Verdict`, `record: Record | None`, `tier: Tier | None`, `score: float`, `given_reference: Reference | None`, `diff: list[tuple[str, str]] | None`
  - `verify_spans(conn, text: str) -> list[Match]`
  - `NEAR_THRESHOLD: float = 0.86`

- [ ] **Step 1: Write the failing test**

Create `tests/verify/test_engine.py`:

```python
import pytest
from sanad.corpus import db
from sanad.verify.engine import Verdict, verify_spans

IKHLAS_1 = "قُلْ هُوَ ٱللَّهُ أَحَدٌ"
KAWTHAR_1 = "إِنَّا أَعْطَيْنَٰكَ ٱلْكَوْثَرَ"


@pytest.fixture(scope="module")
def conn():
    return db.connect("data/sanad-quran.db")


def _only(matches):
    assert len(matches) == 1, f"expected one span, got {len(matches)}"
    return matches[0]


def test_verbatim_quote_is_exact(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}»"))
    assert m.verdict is Verdict.EXACT
    assert m.record.id == "quran:112:1"
    assert m.tier == "light"


def test_undiacritized_quote_is_exact_orthography(conn):
    m = _only(verify_spans(conn, "«قل هو الله احد»"))
    assert m.verdict is Verdict.EXACT_ORTHOGRAPHY
    assert m.record.id == "quran:112:1"
    assert m.tier == "standard"


def test_plain_alef_instead_of_wasla_is_still_exact_orthography(conn):
    # the single most common real-world variation
    m = _only(verify_spans(conn, "«قُلْ هُوَ اللَّهُ أَحَدٌ»"))
    assert m.verdict is Verdict.EXACT_ORTHOGRAPHY


def test_single_letter_mutation_is_near_match_not_exact(conn):
    m = _only(verify_spans(conn, "«قل هو الله احدق»"))
    assert m.verdict is Verdict.NEAR_MATCH
    assert m.diff is not None


def test_near_match_never_reports_as_verified(conn):
    m = _only(verify_spans(conn, "«قل هو الله احدق»"))
    assert m.verdict not in (Verdict.EXACT, Verdict.EXACT_ORTHOGRAPHY)


def test_correct_text_wrong_surah_is_wrong_reference(conn):
    m = _only(verify_spans(conn, f"The Qur'an says «{IKHLAS_1}» (Al-Baqarah 2:255)."))
    assert m.verdict is Verdict.WRONG_REFERENCE
    assert m.record.id == "quran:112:1"
    assert m.given_reference.surah == 2


def test_correct_text_correct_reference_is_exact(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (Al-Ikhlas 112:1)"))
    assert m.verdict is Verdict.EXACT


def test_correct_text_wrong_ayah_is_wrong_reference(conn):
    m = _only(verify_spans(conn, f"«{IKHLAS_1}» (112:4)"))
    assert m.verdict is Verdict.WRONG_REFERENCE


def test_fabricated_arabic_is_not_found(conn):
    m = _only(verify_spans(conn, "«هذا كلام مخترع تماما وليس من القران الكريم»"))
    assert m.verdict is Verdict.NOT_FOUND
    assert m.record is None


def test_multiple_spans_are_all_classified(conn):
    matches = verify_spans(conn, f"«{IKHLAS_1}» and «{KAWTHAR_1}»")
    assert len(matches) == 2
    assert all(m.verdict is Verdict.EXACT for m in matches)


def test_no_arabic_returns_no_matches(conn):
    assert verify_spans(conn, "There is no Arabic in this sentence.") == []


def test_ayat_al_kursi_long_verse_matches(conn):
    kursi = db.get_record(conn, "quran:2:255").text_ar
    m = _only(verify_spans(conn, f"«{kursi}»"))
    assert m.verdict is Verdict.EXACT


def test_diff_is_populated_only_for_near_match(conn):
    assert _only(verify_spans(conn, f"«{IKHLAS_1}»")).diff is None
    assert _only(verify_spans(conn, "«قل هو الله احدق»")).diff is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/verify/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `api/sanad/verify/engine.py`**

```python
"""Deterministic quotation verification.

The tier at which a span matches determines its verdict. This coupling is the
point: an aggressive-tier fold can turn a genuine misquote into a string that
equals a real verse, so an aggressive-tier hit may never be reported as
verified. See the spec, section 6.
"""
from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..arabic.normalize import Tier, normalize
from ..arabic.similarity import ratio
from ..corpus import db
from ..corpus.models import Record
from .extract import Span, extract_spans
from .references import Reference, nearest_reference, parse_references

NEAR_THRESHOLD = 0.86
CANDIDATE_LIMIT = 50


class Verdict(str, Enum):
    EXACT = "EXACT"
    EXACT_ORTHOGRAPHY = "EXACT_ORTHOGRAPHY"
    NEAR_MATCH = "NEAR_MATCH"
    WRONG_REFERENCE = "WRONG_REFERENCE"
    NOT_FOUND = "NOT_FOUND"


_TIER_VERDICT: dict[Tier, Verdict] = {
    "light": Verdict.EXACT,
    "standard": Verdict.EXACT_ORTHOGRAPHY,
    "aggressive": Verdict.NEAR_MATCH,
}

_NORM_COLUMN: dict[Tier, str] = {
    "light": "norm_light",
    "standard": "norm_standard",
    "aggressive": "norm_aggressive",
}


@dataclass(frozen=True)
class Match:
    span: Span
    verdict: Verdict
    record: Optional[Record]
    tier: Optional[Tier]
    score: float
    given_reference: Optional[Reference] = None
    diff: Optional[list[tuple[str, str]]] = None


def _exact_at_tier(conn: sqlite3.Connection, text: str, tier: Tier) -> Optional[Record]:
    needle = normalize(text, tier)
    if not needle:
        return None
    row = conn.execute(
        f"SELECT id FROM records WHERE {_NORM_COLUMN[tier]} = ? LIMIT 1",
        (needle,)).fetchone()
    return db.get_record(conn, row["id"]) if row else None


def _best_fuzzy(conn: sqlite3.Connection, text: str) -> tuple[Optional[Record], float]:
    needle = normalize(text, "aggressive")
    if not needle:
        return None, 0.0
    best: Optional[Record] = None
    best_score = 0.0
    for cand in db.fts_candidates(conn, needle, CANDIDATE_LIMIT):
        score = ratio(needle, cand.norm_aggressive)
        if score > best_score:
            best, best_score = cand, score
    return best, best_score


def _build_diff(quoted: str, canonical: str) -> list[tuple[str, str]]:
    """Character-level opcodes over the standard-tier forms, for display."""
    a, b = normalize(quoted, "standard"), normalize(canonical, "standard")
    out: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            out.append(("equal", a[i1:i2]))
        elif tag == "delete":
            out.append(("quoted-only", a[i1:i2]))
        elif tag == "insert":
            out.append(("corpus-only", b[j1:j2]))
        else:
            out.append(("quoted-only", a[i1:i2]))
            out.append(("corpus-only", b[j1:j2]))
    return out


def _classify(conn: sqlite3.Connection, span: Span,
              refs: list[Reference]) -> Match:
    given = nearest_reference(refs, span.start)

    for tier in ("light", "standard"):
        rec = _exact_at_tier(conn, span.text, tier)  # type: ignore[arg-type]
        if rec is None:
            continue
        verdict = _TIER_VERDICT[tier]  # type: ignore[index]
        if given and _reference_conflicts(given, rec):
            return Match(span, Verdict.WRONG_REFERENCE, rec, tier, 1.0, given)
        return Match(span, verdict, rec, tier, 1.0, given)  # type: ignore[arg-type]

    rec, score = _best_fuzzy(conn, span.text)
    if rec is not None and score >= 1.0:
        # matches only after lossy folding -> never "verified"
        if given and _reference_conflicts(given, rec):
            return Match(span, Verdict.WRONG_REFERENCE, rec, "aggressive", score, given,
                         _build_diff(span.text, rec.text_ar))
        return Match(span, Verdict.NEAR_MATCH, rec, "aggressive", score, given,
                     _build_diff(span.text, rec.text_ar))

    if rec is not None and score >= NEAR_THRESHOLD:
        return Match(span, Verdict.NEAR_MATCH, rec, "aggressive", score, given,
                     _build_diff(span.text, rec.text_ar))

    return Match(span, Verdict.NOT_FOUND, None, None, score, given)


def _reference_conflicts(given: Reference, rec: Record) -> bool:
    if given.surah != rec.surah:
        return True
    return given.ayah is not None and given.ayah != rec.ayah


def verify_spans(conn: sqlite3.Connection, text: str) -> list[Match]:
    refs = parse_references(text)
    return [_classify(conn, span, refs) for span in extract_spans(text)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/verify/test_engine.py -v`
Expected: PASS, 13 tests.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/verify/engine.py tests/verify/test_engine.py
git commit -m "feat(verify): tiered matching engine with verdict taxonomy

The tier at which a span matches determines its verdict. An aggressive-tier
match can never report as verified, because lossy folding can make a genuine
misquote equal a real verse."
```

---

### Task 10: Claim detection and risk routing

**Files:**
- Create: `api/sanad/verify/claims.py`
- Test: `tests/verify/test_claims.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `Claim` dataclass: `kind: str`, `label: str`, `note: str`
  - `RiskCode` — str enum: `GENERAL`, `DISPUTED`, `HIGH_RISK`, `PERSONAL_RULING`
  - `detect_claims(text: str) -> list[Claim]`
  - `route_risk(text: str) -> RiskCode`
  - `requires_handoff(code: RiskCode) -> bool`

- [ ] **Step 1: Write the failing test**

Create `tests/verify/test_claims.py`:

```python
from sanad.verify.claims import (Claim, RiskCode, detect_claims,
                                 requires_handoff, route_risk)


def test_detects_unanimity_claim():
    kinds = {c.kind for c in detect_claims("All scholars agree this is obligatory.")}
    assert "unanimity" in kinds


def test_detects_ijma_spelling():
    assert "unanimity" in {c.kind for c in detect_claims("There is ijma on this.")}


def test_detects_hadith_citation_without_edition():
    assert "hadith_unverifiable" in {c.kind for c in detect_claims("Bukhari 99999 says...")}


def test_detects_legal_conclusion():
    claims = detect_claims("Therefore Islam requires every convert to follow one school.")
    assert "legal_conclusion" in {c.kind for c in claims}


def test_clean_text_yields_no_claims():
    assert detect_claims("This surah has four verses.") == []


def test_personal_question_routes_to_handoff():
    assert route_risk("Can I marry my cousin?") is RiskCode.PERSONAL_RULING
    assert route_risk("Should I divorce my wife?") is RiskCode.PERSONAL_RULING


def test_high_risk_topic_routes_to_handoff():
    assert route_risk("Explain the ruling on apostasy and takfir.") is RiskCode.HIGH_RISK


def test_disputed_topic_is_flagged_but_not_handoff():
    assert route_risk("What do the four madhhabs say about this?") is RiskCode.DISPUTED
    assert requires_handoff(RiskCode.DISPUTED) is False


def test_general_question_is_general():
    assert route_risk("How many verses are in Al-Ikhlas?") is RiskCode.GENERAL


def test_personal_outranks_high_risk():
    # a personal framing must win, because it changes who should answer
    assert route_risk("Should I divorce my wife over apostasy?") is RiskCode.PERSONAL_RULING


def test_handoff_required_for_personal_and_high_risk():
    assert requires_handoff(RiskCode.PERSONAL_RULING) is True
    assert requires_handoff(RiskCode.HIGH_RISK) is True
    assert requires_handoff(RiskCode.GENERAL) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/verify/test_claims.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `api/sanad/verify/claims.py`**

```python
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
    ("unanimity",
     re.compile(r"\b(ijma[’']?|unanimous(ly)?|all scholars agree|"
                r"every scholar agrees|consensus of the scholars)\b", re.I),
     "Unanimity claimed",
     "A claim of consensus requires named evidence. Sanad will not accept it "
     "from model memory."),
    ("legal_conclusion",
     re.compile(r"\b(therefore|thus|hence)\b[^.]{0,80}\b(islam|shariah|sharia)\b"
                r"[^.]{0,40}\b(requires?|forbids?|obliges?|mandates?|prohibits?)\b", re.I),
     "Legal conclusion beyond the quoted text",
     "A valid quotation does not license a modern legal conclusion. Marked as "
     "interpretation."),
    ("hadith_unverifiable",
     re.compile(r"\b(bukhari|muslim|tirmidhi|abu dawud|nasa[’']?i|ibn majah)\s*"
                r"[#no.]*\s*\d+|\bhadith\b", re.I),
     "Hadith citation",
     "No licensed Hadith edition is bundled in this corpus. Treat as unverified."),
]

_PERSONAL = re.compile(
    r"\b(can i|should i|may i|am i allowed|is it haram for me|is it halal for me|"
    r"my (wife|husband|marriage|divorce|inheritance|loan|debt|mother|father)|"
    r"divorced me|give me a fatwa)\b", re.I)

_HIGH_RISK = re.compile(
    r"\b(apostasy|apostate|takfir|stoning|amputation|jihad|"
    r"child marriage|slavery|honou?r killing)\b", re.I)

_DISPUTED = re.compile(
    r"\b(madhhab|madhab|mazhab|hanafi|maliki|shafi[’']?i|hanbali|"
    r"difference of opinion|scholars differ|ikhtilaf)\b", re.I)


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/verify/test_claims.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/verify/claims.py tests/verify/test_claims.py
git commit -m "feat(verify): claim detection and risk routing

Personal framing outranks topic risk, because it changes who should answer
rather than how carefully."
```

---

### Task 11: The HTTP API

**Files:**
- Create: `api/sanad/api/__init__.py`, `schemas.py`, `routes.py`, `app.py`
- Create: `api/sanad/settings.py`
- Test: `tests/api/test_routes.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `settings.resolve_db_path() -> Path` — `SANAD_DB` env, else `data/sanad.db`, else `data/sanad-quran.db`
  - `app.create_app() -> FastAPI`
  - Routes: `POST /api/verify`, `GET /api/records/{record_id}`, `GET /api/search`, `GET /api/corpus`, `GET /api/health`

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_routes.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sanad.api.app import create_app

IKHLAS_1 = "قُلْ هُوَ ٱللَّهُ أَحَدٌ"


@pytest.fixture(scope="module")
def client(monkeypatch_module=None):
    return TestClient(create_app())


def test_health_reports_corpus_loaded(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["records"] == 6236


def test_corpus_manifest_exposes_license_and_attribution(client):
    body = client.get("/api/corpus").json()
    src = body["sources"][0]
    assert src["license_id"] == "CC-BY-3.0"
    assert "PLEASE DO NOT REMOVE" in src["attribution"]
    assert len(body["db_sha256"]) == 64


def test_verify_exact_quote(client):
    r = client.post("/api/verify", json={"text": f"«{IKHLAS_1}»"})
    assert r.status_code == 200
    body = r.json()
    assert body["quotations"][0]["verdict"] == "EXACT"
    assert body["quotations"][0]["record"]["reference_display"] == "Al-Ikhlas 112:1"


def test_verify_wrong_reference(client):
    r = client.post("/api/verify",
                    json={"text": f"«{IKHLAS_1}» (Al-Baqarah 2:255)"})
    assert r.json()["quotations"][0]["verdict"] == "WRONG_REFERENCE"


def test_verify_reports_claims_and_risk(client):
    r = client.post("/api/verify",
                    json={"text": "All scholars agree. Can I marry my cousin?"})
    body = r.json()
    assert "unanimity" in {c["kind"] for c in body["claims"]}
    assert body["risk"] == "PERSONAL_RULING"
    assert body["requires_handoff"] is True


def test_verify_empty_text_is_rejected(client):
    assert client.post("/api/verify", json={"text": "   "}).status_code == 422


def test_verify_oversized_text_is_rejected(client):
    assert client.post("/api/verify",
                       json={"text": "x" * 60_000}).status_code == 422


def test_get_record_returns_provenance(client):
    body = client.get("/api/records/quran:112:1").json()
    assert body["text_ar"] == IKHLAS_1
    assert len(body["text_ar_sha256"]) == 64
    assert body["source"]["license_id"] == "CC-BY-3.0"


def test_get_missing_record_404(client):
    assert client.get("/api/records/quran:999:1").status_code == 404


def test_search_finds_by_arabic_token(client):
    body = client.get("/api/search", params={"q": "الصمد"}).json()
    assert "quran:112:2" in {r["id"] for r in body["results"]}


def test_search_blank_query_is_rejected(client):
    assert client.get("/api/search", params={"q": "  "}).status_code == 422


def test_search_respects_limit(client):
    body = client.get("/api/search", params={"q": "الله", "limit": 3}).json()
    assert len(body["results"]) <= 3


def test_verify_does_not_echo_text_into_audit_log(client):
    # the spec forbids storing user text
    client.post("/api/verify", json={"text": f"«{IKHLAS_1}» secret phrase"})
    from sanad.api.app import _conn_for_tests
    rows = _conn_for_tests().execute("SELECT detail_json FROM audit_log").fetchall()
    assert all("secret phrase" not in r[0] for r in rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/api -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `api/sanad/settings.py`**

```python
from __future__ import annotations

import hashlib
import os
from pathlib import Path


class CorpusNotFound(Exception):
    pass


def resolve_db_path() -> Path:
    override = os.environ.get("SANAD_DB")
    if override:
        p = Path(override)
        if not p.is_file():
            raise CorpusNotFound(f"SANAD_DB points at a missing file: {p}")
        return p
    for candidate in (Path("data/sanad.db"), Path("data/sanad-quran.db")):
        if candidate.is_file():
            return candidate
    raise CorpusNotFound(
        "no corpus found. Run: sanad-ingest build --out data/sanad-quran.db")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
```

- [ ] **Step 4: Implement `api/sanad/api/schemas.py`**

```python
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class VerifyRequest(BaseModel):
    text: str = Field(..., max_length=50_000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class RecordOut(BaseModel):
    id: str
    reference_display: str
    text_ar: str
    text_ar_sha256: str
    surah: Optional[int] = None
    ayah: Optional[int] = None


class QuotationOut(BaseModel):
    quoted_text: str
    start: int
    end: int
    verdict: str
    tier: Optional[str]
    score: float
    record: Optional[RecordOut]
    given_reference: Optional[str]
    diff: Optional[list[tuple[str, str]]]


class ClaimOut(BaseModel):
    kind: str
    label: str
    note: str


class VerifyResponse(BaseModel):
    quotations: list[QuotationOut]
    claims: list[ClaimOut]
    risk: str
    requires_handoff: bool
    overall: str
    corpus_scope: str
```

- [ ] **Step 5: Implement `api/sanad/api/routes.py`**

```python
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..arabic.normalize import normalize
from ..corpus import db
from ..verify.claims import detect_claims, requires_handoff, route_risk
from ..verify.engine import Verdict, verify_spans
from .schemas import (ClaimOut, QuotationOut, RecordOut, VerifyRequest,
                      VerifyResponse)

router = APIRouter(prefix="/api")

CORPUS_SCOPE = (
    "This corpus contains the Qur'an only. Absence of a quotation from this "
    "corpus does not establish that it is fabricated."
)


def _conn(request: Request) -> sqlite3.Connection:
    return request.app.state.conn


def _overall(quotations: list[QuotationOut], claims: list[ClaimOut],
             handoff: bool) -> str:
    if handoff:
        return "handoff"
    if not quotations and not claims:
        return "insufficient_span"
    bad = {Verdict.NOT_FOUND.value, Verdict.WRONG_REFERENCE.value,
           Verdict.NEAR_MATCH.value}
    if any(q.verdict in bad for q in quotations) or claims:
        return "needs_review"
    return "grounded"


@router.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest, request: Request) -> VerifyResponse:
    conn = _conn(request)
    matches = verify_spans(conn, payload.text)

    quotations = [
        QuotationOut(
            quoted_text=m.span.text, start=m.span.start, end=m.span.end,
            verdict=m.verdict.value, tier=m.tier, score=round(m.score, 4),
            record=RecordOut(
                id=m.record.id, reference_display=m.record.reference_display,
                text_ar=m.record.text_ar, text_ar_sha256=m.record.text_ar_sha256,
                surah=m.record.surah, ayah=m.record.ayah) if m.record else None,
            given_reference=m.given_reference.raw if m.given_reference else None,
            diff=m.diff,
        )
        for m in matches
    ]
    claims = [ClaimOut(kind=c.kind, label=c.label, note=c.note)
              for c in detect_claims(payload.text)]
    risk = route_risk(payload.text)
    handoff = requires_handoff(risk)

    # Audit: verdicts and record ids only. User text is never stored.
    conn.execute(
        "INSERT INTO audit_log (ts, request_id, stage, verdict, detail_json) "
        "VALUES (?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), str(uuid.uuid4()), "verify",
         risk.value,
         json.dumps({"verdicts": [q.verdict for q in quotations],
                     "record_ids": [q.record.id for q in quotations if q.record],
                     "claim_kinds": [c.kind for c in claims]})),
    )
    conn.commit()

    return VerifyResponse(
        quotations=quotations, claims=claims, risk=risk.value,
        requires_handoff=handoff,
        overall=_overall(quotations, claims, handoff),
        corpus_scope=CORPUS_SCOPE,
    )


@router.get("/records/{record_id}")
def get_record(record_id: str, request: Request) -> dict:
    conn = _conn(request)
    rec = db.get_record(conn, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no record {record_id!r}")
    src = conn.execute("SELECT * FROM sources WHERE id = ?",
                       (rec.source_id,)).fetchone()
    return {
        "id": rec.id, "reference_display": rec.reference_display,
        "text_ar": rec.text_ar, "text_ar_sha256": rec.text_ar_sha256,
        "surah": rec.surah, "ayah": rec.ayah,
        "surah_name_ar": rec.surah_name_ar, "surah_name_en": rec.surah_name_en,
        "source": dict(src) if src else None,
    }


@router.get("/search")
def search(q: str, request: Request, limit: int = 20) -> dict:
    """Corpus browse. Spec section 9. Lexical only -- no embeddings in Stage A."""
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank")
    limit = max(1, min(limit, 100))
    hits = db.fts_candidates(_conn(request), normalize(q, "aggressive"), limit)
    return {
        "query": q,
        "count": len(hits),
        "results": [
            {"id": r.id, "reference_display": r.reference_display,
             "text_ar": r.text_ar, "surah": r.surah, "ayah": r.ayah}
            for r in hits
        ],
    }


@router.get("/corpus")
def corpus(request: Request) -> dict:
    conn = _conn(request)
    return {
        "db_sha256": request.app.state.db_sha256,
        "db_path": str(request.app.state.db_path),
        "stats": db.corpus_stats(conn),
        "scope": CORPUS_SCOPE,
        "sources": [dict(r) for r in conn.execute("SELECT * FROM sources")],
    }


@router.get("/health")
def health(request: Request) -> dict:
    stats = db.corpus_stats(_conn(request))
    return {"status": "ok", "records": stats["records"],
            "sources": stats["sources"]}
```

- [ ] **Step 6: Implement `api/sanad/api/app.py`**

```python
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..corpus import db
from ..settings import file_sha256, resolve_db_path
from .routes import router

log = logging.getLogger(__name__)
_APP: FastAPI | None = None


def create_app() -> FastAPI:
    global _APP
    app = FastAPI(title="Sanad", version="0.1.0",
                  description="Evidence-first verification of Islamic textual claims.")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
        allow_headers=["*"])

    path = resolve_db_path()
    # audit_log is written, so the connection cannot be read-only
    app.state.conn = db.connect(path, read_only=False)
    app.state.db_path = path
    app.state.db_sha256 = file_sha256(path)
    log.info("corpus %s sha256=%s", path, app.state.db_sha256)

    app.include_router(router)
    _APP = app
    return app


def _conn_for_tests():
    """Test hook: the live connection, for asserting on audit_log contents."""
    assert _APP is not None, "create_app() has not run"
    return _APP.state.conn
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/api -v`
Expected: PASS, 13 tests.

- [ ] **Step 8: Verify the service runs**

```bash
uvicorn sanad.api.app:create_app --factory --port 8000 &
sleep 3
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/verify \
  -H 'content-type: application/json' \
  -d '{"text":"«قُلْ هُوَ ٱللَّهُ أَحَدٌ» (Al-Baqarah 2:255)"}' | head -40
kill %1
```

Expected: health reports 6236 records; verify reports `WRONG_REFERENCE`.

- [ ] **Step 9: Commit**

```bash
git add api/sanad/api api/sanad/settings.py tests/api
git commit -m "feat(api): verify, records, corpus manifest, and health endpoints

The audit log records verdicts and record ids only; user text is never
stored, per the no-user-data constraint."
```

---

### Task 12: Evaluation harness with a false-verification gate

**Files:**
- Create: `eval/cases/quran_exact.yaml`, `quran_mutations.yaml`, `quran_references.yaml`, `fabrications.yaml`, `claims_and_risk.yaml`
- Create: `eval/runner.py`
- Test: `tests/eval/test_runner.py`

**Interfaces:**
- Consumes: `verify_spans`, `Verdict`, `route_risk`, `detect_claims`, `db.connect`.
- Produces:
  - `Case` dataclass: `id, text, expect_verdict, expect_record, expect_risk, rationale`
  - `load_cases(directory: Path) -> list[Case]`
  - `Metrics` dataclass: `total, passed, false_verifications, failures: list[str], by_verdict: dict[str, int]`
  - `run_eval(conn, cases) -> Metrics`
  - `main(argv) -> int` — exits 1 if `false_verifications > 0`

- [ ] **Step 1: Create `eval/cases/quran_exact.yaml`**

```yaml
- id: exact-ikhlas-1
  text: "«قُلْ هُوَ ٱللَّهُ أَحَدٌ»"
  expect_verdict: EXACT
  expect_record: quran:112:1
  rationale: Verbatim Uthmani text, no reference given.

- id: exact-with-correct-reference
  text: "The Qur'an says «قُلْ هُوَ ٱللَّهُ أَحَدٌ» (Al-Ikhlas 112:1)."
  expect_verdict: EXACT
  expect_record: quran:112:1
  rationale: Verbatim text with a matching reference.

- id: undiacritized-is-orthography-only
  text: "«قل هو الله احد»"
  expect_verdict: EXACT_ORTHOGRAPHY
  expect_record: quran:112:1
  rationale: Diacritics removed; the letters are unchanged.

- id: plain-alef-for-wasla
  text: "«قُلْ هُوَ اللَّهُ أَحَدٌ»"
  expect_verdict: EXACT_ORTHOGRAPHY
  expect_record: quran:112:1
  rationale: Plain alef for alef wasla is the commonest real-world variation.
```

- [ ] **Step 2: Create `eval/cases/quran_mutations.yaml`**

```yaml
- id: mutation-appended-letter
  text: "«قل هو الله احدق»"
  expect_verdict: NEAR_MATCH
  expect_record: quran:112:1
  rationale: One letter appended. Must never report as verified.

- id: mutation-substituted-letter
  text: "«قل هو اللة احد»"
  expect_verdict: NEAR_MATCH
  expect_record: quran:112:1
  rationale: Ta marbuta substituted into the divine name. Tier-3 fold only.

- id: mutation-dropped-word
  text: "«قل هو احد»"
  expect_verdict: NEAR_MATCH
  expect_record: quran:112:1
  rationale: A word removed. Similar enough to locate, not to verify.

- id: mutation-word-order-swapped
  text: "«هو قل الله احد»"
  expect_verdict: NEAR_MATCH
  expect_record: quran:112:1
  rationale: Reordering changes meaning and must not verify.
```

- [ ] **Step 3: Create `eval/cases/quran_references.yaml`**

```yaml
- id: wrong-surah
  text: "«قُلْ هُوَ ٱللَّهُ أَحَدٌ» (Al-Baqarah 2:255)"
  expect_verdict: WRONG_REFERENCE
  expect_record: quran:112:1
  rationale: Text is genuine; the citation points at a different surah.

- id: wrong-ayah-same-surah
  text: "«قُلْ هُوَ ٱللَّهُ أَحَدٌ» (112:4)"
  expect_verdict: WRONG_REFERENCE
  expect_record: quran:112:1
  rationale: Right surah, wrong verse.

- id: kursi-cited-as-ikhlas
  text: "«ٱللَّهُ ٱلصَّمَدُ» (Ayat al-Kursi 2:255)"
  expect_verdict: WRONG_REFERENCE
  expect_record: quran:112:2
  rationale: A frequently mis-cited pairing.
```

- [ ] **Step 4: Create `eval/cases/fabrications.yaml`**

```yaml
- id: invented-arabic
  text: "«هذا كلام مخترع تماما وليس من القران الكريم ابدا»"
  expect_verdict: NOT_FOUND
  expect_record: null
  rationale: Grammatical Arabic that is not scripture.

- id: fabricated-hadith-english
  text: "A hadith in Bukhari 99999 says \"The best among you invents new worship.\""
  expect_verdict: null
  expect_claim: hadith_unverifiable
  rationale: >
    No Arabic span to verify. Must surface a claim flag rather than silence,
    and must not assert fabrication, since no Hadith corpus is bundled.

- id: quran-like-but-not-quran
  text: "«وَلَقَدْ خَلَقْنَا ٱلْحَاسُوبَ مِنْ طِينٍ»"
  expect_verdict: NOT_FOUND
  expect_record: null
  rationale: Qur'anic register and cadence, invented content.
```

- [ ] **Step 5: Create `eval/cases/claims_and_risk.yaml`**

```yaml
- id: personal-ruling-routes-to-handoff
  text: "Can I marry my cousin?"
  expect_risk: PERSONAL_RULING
  rationale: A personal question must reach a qualified person, not a machine.

- id: unanimity-claim-flagged
  text: "All scholars agree that this practice is obligatory."
  expect_claim: unanimity
  rationale: Consensus claims require named evidence.

- id: legal-conclusion-beyond-text
  text: "«قُلْ هُوَ ٱللَّهُ أَحَدٌ» Therefore Islam requires every convert to follow one school."
  expect_verdict: EXACT
  expect_record: quran:112:1
  expect_claim: legal_conclusion
  rationale: >
    The quotation is genuine and the conclusion does not follow from it. Both
    facts must be reported together.

- id: high-risk-topic
  text: "Explain the ruling on apostasy."
  expect_risk: HIGH_RISK
  rationale: Routes to handoff regardless of evidence quality.

- id: general-question-is-general
  text: "How many verses does Al-Ikhlas have?"
  expect_risk: GENERAL
  rationale: Baseline; must not over-trigger the router.
```

- [ ] **Step 6: Write the failing test**

Create `tests/eval/test_runner.py`:

```python
from pathlib import Path

from eval.runner import load_cases, run_eval
from sanad.corpus import db

CASES = Path("eval/cases")


def test_loads_every_case_file():
    cases = load_cases(CASES)
    assert len(cases) >= 19
    assert len({c.id for c in cases}) == len(cases), "case ids must be unique"


def test_full_suite_passes():
    metrics = run_eval(db.connect("data/sanad-quran.db"), load_cases(CASES))
    assert metrics.failures == [], f"failing cases: {metrics.failures}"


def test_no_false_verifications():
    metrics = run_eval(db.connect("data/sanad-quran.db"), load_cases(CASES))
    assert metrics.false_verifications == 0


def test_a_mutation_case_is_never_verified():
    conn = db.connect("data/sanad-quran.db")
    cases = [c for c in load_cases(CASES) if c.id.startswith("mutation-")]
    assert cases
    metrics = run_eval(conn, cases)
    assert metrics.false_verifications == 0
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `python -m pytest tests/eval -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.runner'`

- [ ] **Step 8: Implement `eval/runner.py`**

```python
"""Adversarial evaluation harness.

False verification -- reporting a misquote as EXACT or EXACT_ORTHOGRAPHY -- is
the one metric that gates CI. Everything else is tracked and reported.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from sanad.corpus import db
from sanad.verify.claims import detect_claims, route_risk
from sanad.verify.engine import Verdict, verify_spans

VERIFIED = {Verdict.EXACT.value, Verdict.EXACT_ORTHOGRAPHY.value}


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    rationale: str
    expect_verdict: Optional[str] = None
    expect_record: Optional[str] = None
    expect_claim: Optional[str] = None
    expect_risk: Optional[str] = None


@dataclass
class Metrics:
    total: int = 0
    passed: int = 0
    false_verifications: int = 0
    failures: list[str] = field(default_factory=list)
    by_verdict: dict[str, int] = field(default_factory=dict)


def load_cases(directory: Path) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(Path(directory).glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            cases.append(Case(**raw))
    return cases


def run_eval(conn, cases: list[Case]) -> Metrics:
    m = Metrics(total=len(cases))

    for case in cases:
        problems: list[str] = []
        matches = verify_spans(conn, case.text)
        top = matches[0] if matches else None
        verdict = top.verdict.value if top else None

        if verdict:
            m.by_verdict[verdict] = m.by_verdict.get(verdict, 0) + 1

        # The gate: a case whose expectation is not a verified verdict must
        # never actually produce one.
        if case.expect_verdict not in VERIFIED and verdict in VERIFIED:
            m.false_verifications += 1
            problems.append(
                f"FALSE VERIFICATION: expected {case.expect_verdict}, got {verdict}")

        if case.expect_verdict is not None and verdict != case.expect_verdict:
            problems.append(f"verdict: expected {case.expect_verdict}, got {verdict}")

        if case.expect_record is not None:
            got = top.record.id if top and top.record else None
            if got != case.expect_record:
                problems.append(f"record: expected {case.expect_record}, got {got}")

        if case.expect_claim is not None:
            kinds = {c.kind for c in detect_claims(case.text)}
            if case.expect_claim not in kinds:
                problems.append(f"claim: expected {case.expect_claim}, got {sorted(kinds)}")

        if case.expect_risk is not None:
            got_risk = route_risk(case.text).value
            if got_risk != case.expect_risk:
                problems.append(f"risk: expected {case.expect_risk}, got {got_risk}")

        if problems:
            m.failures.append(f"{case.id}: " + "; ".join(problems))
        else:
            m.passed += 1

    return m


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sanad-eval")
    parser.add_argument("--cases", type=Path, default=Path("eval/cases"))
    parser.add_argument("--db", type=Path, default=Path("data/sanad-quran.db"))
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    m = run_eval(db.connect(args.db), cases)

    print(f"cases               {m.total}")
    print(f"passed              {m.passed}")
    print(f"failed              {len(m.failures)}")
    print(f"false verifications {m.false_verifications}")
    print("verdict distribution:")
    for verdict, count in sorted(m.by_verdict.items()):
        print(f"  {verdict:<20} {count}")

    for failure in m.failures:
        print(f"  FAIL {failure}", file=sys.stderr)

    if m.false_verifications:
        print("\nGATE FAILED: a misquote was reported as verified.", file=sys.stderr)
        return 1
    return 1 if m.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create an empty `eval/__init__.py` so `from eval.runner import ...` resolves.

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -m pytest tests/eval -v && python eval/runner.py`
Expected: tests PASS; runner prints `false verifications 0` and exits 0.

- [ ] **Step 10: Commit**

```bash
git add eval tests/eval
git commit -m "feat(eval): adversarial suite gating on false-verification rate

Reporting a misquote as verified is the one failure that fails CI. Other
metrics are reported but do not gate."
```

---

### Task 13: CI, Docker, and documentation

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `Dockerfile`, `.dockerignore`
- Modify: `README.md` (replace the placeholder URL and the "what is included" section)
- Modify: `REPO_STATUS.md` (tick the boxes Stage A actually completes)

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - name: Install
        run: pip install -e ".[dev]"
      - name: Lint
        run: ruff check api ingest eval
      - name: Unit tests
        run: pytest -v --cov=sanad --cov=sanad_ingest
      - name: Adversarial evaluation gate
        run: python eval/runner.py
      - name: Verify the committed corpus matches the lockfile
        run: |
          sanad-ingest build --out /tmp/rebuilt.db
          python - <<'PY'
          from sanad.corpus import db
          a = db.corpus_stats(db.connect("data/sanad-quran.db"))
          b = db.corpus_stats(db.connect("/tmp/rebuilt.db"))
          assert a == b, f"committed corpus differs from a fresh build: {a} != {b}"
          print("corpus reproducible:", a)
          PY
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml ./
COPY api ./api
COPY ingest ./ingest
COPY eval ./eval

RUN pip install --no-cache-dir -e "."

# Build the corpus at image build time so the container needs no network.
RUN sanad-ingest build --out data/sanad-quran.db

ENV SANAD_DB=/app/data/sanad-quran.db
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://localhost:8000/api/health').status_code==200 else 1)"

CMD ["uvicorn", "sanad.api.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create `.dockerignore`**

```text
.git
.github
.corpus-cache
__pycache__
*.pyc
.pytest_cache
.ruff_cache
htmlcov
web/node_modules
```

- [ ] **Step 4: Update `README.md`**

Replace the `YOUR-USERNAME` placeholder on line 11 with the real Pages URL, and replace the "Run locally" and "What is included" sections:

```markdown
## Live demo

`https://adnangulzar404-source.github.io/sanad/`

## Run locally

```bash
pip install -e ".[dev]"
sanad-ingest build --out data/sanad-quran.db     # verifies against the lockfile
uvicorn sanad.api.app:create_app --factory --port 8000
```

Or with Docker, which builds the corpus into the image:

```bash
docker build -t sanad . && docker run -p 8000:8000 sanad
```

## What is included

Stage A — the deterministic core:

- The full Tanzil Uthmani Qur'an, 6,236 verses, verified against a committed
  content hash at build time
- Three-tier Arabic normalization, with the matching tier reported so an
  orthographic variant is never conflated with a textual one
- Verdicts: exact, exact-with-orthographic-variance, near match with a
  character diff, wrong reference, not found
- Claim detection and risk routing, with personal questions directed to a
  qualified person
- `POST /api/verify` — deterministic, no model, no API key
- `GET /api/corpus` — the provenance manifest: sources, licences, hashes
- An adversarial evaluation suite that fails CI if any misquote is reported
  as verified

Not yet included: Hadith (no licence-cleared source yet — see
`docs/superpowers/specs/2026-09-19-sanad-design.md` §14.1), translations
(§14.2), and the Ask pipeline (Stage B).

## Attribution

Qur'an text from the [Tanzil Project](https://tanzil.net), used verbatim under
Creative Commons Attribution 3.0. The full copyright notice is stored in the
corpus database and served at `GET /api/corpus`.
```

- [ ] **Step 5: Update `REPO_STATUS.md`**

```markdown
# Repository status

## Current status

- [x] Static prototype
- [x] Pages workflow
- [x] Source accumulator
- [x] Licensing notes
- [x] Roadmap
- [x] Git remote configured
- [x] Full Tanzil import, hash-verified
- [x] Deterministic verification API
- [x] Adversarial evaluation gate in CI
- [ ] Licensed Hadith subset — blocked, see spec §14.1
- [ ] Licence-cleared translation — blocked, see spec §14.2
- [ ] Ask pipeline — Stage B
- [ ] React frontend — Stage C
```

- [ ] **Step 6: Run the whole suite and the linter**

```bash
ruff check api ingest eval
python -m pytest -v
python eval/runner.py
docker build -t sanad . && docker run --rm -d -p 8000:8000 --name sanad-test sanad
sleep 8 && curl -s localhost:8000/api/health && docker rm -f sanad-test
```

Expected: ruff clean, all tests pass, eval gate exits 0, container health returns 6236 records.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/ci.yml Dockerfile .dockerignore README.md REPO_STATUS.md
git commit -m "ci: test, lint, eval gate, and corpus-reproducibility check

CI rebuilds the corpus from the lockfile and asserts it matches the committed
database, so a drifted or hand-edited corpus cannot merge."
```

---

## Stage A Definition of Done

- [ ] `pytest` green; every module has tests
- [ ] `ruff check api ingest eval` clean
- [ ] `python eval/runner.py` exits 0 with `false verifications 0`
- [ ] `sanad-ingest build` produces 6,236 records and matches the lockfile hash
- [ ] CI rebuilds the corpus and confirms it matches the committed database
- [ ] `docker run` serves `/api/health` with no network access
- [ ] `GET /api/corpus` returns the Tanzil attribution block verbatim
- [ ] `records.text_ar` is byte-identical to Tanzil's for a sampled 20 verses
- [ ] README no longer contains `YOUR-USERNAME`

## Deliberately deferred, with reasons

**To Stage B:** embeddings, vector search, RRF fusion, the generator and
auditor, SSE streaming, the adjudicator. The `embeddings` and `audit_log`
tables are created empty in Stage A so Stage B needs no migration.

**To Stage C:** the React frontend. `index.html` stays at the repository root
and keeps serving the Phase 0 demo on Pages until then.

**Spec §5.3 release-asset distribution is not built in Stage A.** The whole
point of that machinery — GitHub Releases, boot-time download, hash-verify on
startup — is the 100 MB file limit, and a Qur'an-only corpus is roughly 5 MB.
It is committed directly, which is strictly better: `git clone` gives you a
working verifier with no network. The release pipeline becomes necessary the
moment Hadith lands and the database crosses 100 MB. `settings.resolve_db_path`
already prefers `data/sanad.db` over `data/sanad-quran.db`, so the download
step slots in ahead of the fallback without touching anything else.

**Spec §14.1 (Hadith source) and §14.2 (translation source) remain open.**
Neither blocks Stage A. The `translations` and `gradings` tables exist and are
empty; `build_corpus` already logs and skips any lockfile source whose `kind`
it does not handle, so adding a cleared source is a lockfile entry plus one
parser, not a refactor.
