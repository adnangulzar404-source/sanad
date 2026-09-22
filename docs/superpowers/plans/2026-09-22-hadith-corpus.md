# Hadith Corpus (Stage A2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest Ṣaḥīḥ al-Bukhārī's Arabic text so `POST /api/verify` checks a quoted hadith exactly as it already checks a quoted āyah.

**Architecture:** A new mARkdown parser feeds the existing `records` table with `kind='hadith'`, storing the matn in `text_ar` and the isnād in a new `isnad_ar` column. The verification engine is unchanged — it becomes corpus-agnostic for free once the matn is what gets scored. Citation parsing gains a second, independent reference family. Three pieces of product copy that promise a Qur'an-only corpus are reworded.

**Tech Stack:** Python 3.10, SQLite + FTS5, FastAPI, Pydantic; React + Vite + TypeScript + Vitest for the frontend tasks.

**Spec:** `docs/superpowers/specs/2026-09-22-hadith-corpus-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

**Measured source facts** — all values below were measured from the actual download on 2026-09-22. Do not re-derive by guessing; re-measure if a step needs confirmation.

| Fact | Exact value |
|---|---|
| Source file | `data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed` in `github.com/OpenITI/0275AH` |
| SHA-256 (whole file, as downloaded) | `69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7` |
| Size | 5,524,762 bytes · 48,685 lines · 3,215,519 characters |
| `#META#Header#End#` offset | character 1179 |
| Numbered units (`^# <digits> `) | 7,135 |
| ... of which bāb headings | 6 |
| ... of which hadith | **7,129** ← `expected_records` |
| Hadith with no `*` boundary | 4 (numbers 2795, 6964, 6965, 6966) |
| Hadith with exactly one `*` | 7,125 |
| Hadith number range | 1 – 7124 |
| `م` (mukarrar) repeat-marked units | 5 (numbers 619, 3905, 4537, 4626, 6705 — see Task 2) |
| Number printed twice, neither `م` | 3905 |
| `### \|` kitāb lines | 100 |
| `### \|\|` bāb lines | 3,596 |
| `### \|\|\|` deeper lines | 363 |
| `~~` continuation lines | 36,360 |
| `PageV\d+P\d+` markers | 2,586 |
| `@QB@` / `@QE@` | 3,918 each (balanced) |
| `ms\d{4}` milestone markers | 2,033 |
| `\ N \` part markers | 4,657 |

**Hard rules, carried from Stage A and the spec:**

- `NEAR_THRESHOLD = 0.86`. Tier→verdict coupling is never loosened: `light`→`EXACT`, `standard`→`EXACT_ORTHOGRAPHY`, `aggressive`→`NEAR_MATCH` (never verified).
- **Never alter source text.** Markers are stripped; letters are not. The stored matn is the edition's words.
- **No gradings.** The `gradings` table stays empty. Sanad may say a wording is in Bukhari; never that a hadith is ṣaḥīḥ.
- **Arabic literals in tests are extracted from the real file, never typed.** This project has hit "character altered in transit" eleven times, once inside the test written to catch it. Task 2 creates a committed fixture sliced from the download; later tasks read from it or from the built corpus.
- Where a non-Arabic character is visually ambiguous in a regex (colon variants, tatweel, ZWNJ), write it as an explicit `\uXXXX` escape, never as a literal glyph.
- Corpus DB is opened **read-only**; the audit log lives in its own database file. Never add a writable table to the corpus.
- Python: `.venv/bin/python`, `.venv/bin/pytest` in the worktree. Frontend: `npm test -- --run` in `web/`.
- Stage A + C tests must stay green: **257 Python, 85 web** at plan start.

**The load-bearing invariant:** `text_ar` holds the **matn only**. Scoring across isnād + matn puts *innamā al-aʿmālu bi'l-niyyāt* near 0.13 against a 0.86 threshold. Task 9's first eval case exists to fail loudly if this is ever undone.

---

## File Structure

| File | Responsibility |
|---|---|
| `ingest/corpus.lock.toml` | third `[[source]]`; replaces the NOT-YET-RESOLVED note |
| `ingest/sanad_ingest/lockfile.py` | accept `format = "openiti-markdown"`, optional `commit`, `expected_records` |
| `ingest/sanad_ingest/openiti.py` | **NEW** — mARkdown → structured hadith units. Pure function; no I/O, no DB |
| `ingest/sanad_ingest/fetch.py` | commit-pinned raw URL; whole-file hash convention |
| `ingest/sanad_ingest/build.py` | dispatch on `format`; write hadith records; emit noise report |
| `api/sanad/corpus/schema.py` | `+ isnad_ar TEXT` |
| `api/sanad/corpus/models.py` | `Record.isnad_ar` |
| `api/sanad/corpus/db.py` | insert/read the new column |
| `api/sanad/verify/references.py` | `HadithReference` family, independent of the verse family |
| `api/sanad/verify/engine.py` | cross-kind reference check |
| `api/sanad/api/schemas.py` | `RecordOut.isnad_ar`, `.collection`, `.hadith_no` |
| `api/sanad/api/routes.py` | reworded `CORPUS_SCOPE` |
| `web/src/components/EvidenceCard.tsx` | isnād block in the `.data` register |
| `web/src/screens/Verify.tsx` | gradings line, once per result |
| `tests/fixtures/bukhari_sample.txt` | **NEW** — byte-exact slice of the real file |
| `eval/cases/hadith.yaml` | **NEW** — the eight spec cases |

---

## Task 1: Lockfile entry and fetch for a commit-pinned source

**Files:**
- Modify: `ingest/corpus.lock.toml` (replace the trailing NOT-YET-RESOLVED comment)
- Modify: `ingest/sanad_ingest/lockfile.py`
- Modify: `ingest/sanad_ingest/fetch.py`
- Test: `tests/ingest/test_lockfile.py`, `tests/ingest/test_fetch.py`

**Interfaces:**
- Consumes: existing `load_lockfile()`, `LockedSource`
- Produces: `LockedSource` gains `commit: str | None` and `expected_records: int | None`; `format` enum accepts `"openiti-markdown"`

- [ ] **Step 1: Write the failing test**

```python
# tests/ingest/test_lockfile.py  (append)
def test_accepts_openiti_markdown_format_with_commit_pin():
    srcs = load_lockfile(LOCKFILE_PATH)
    bukhari = [s for s in srcs if s.id == "openiti-bukhari-jk000110"]
    assert len(bukhari) == 1, "the Bukhari source must be pinned in the lockfile"
    b = bukhari[0]
    assert b.format == "openiti-markdown"
    assert b.kind == "hadith-arabic"
    assert b.license_id == "public-domain"
    assert b.expected_records == 7129
    assert b.content_sha256 == (
        "69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7"
    )

def test_commit_is_required_for_git_hosted_sources():
    """A branch URL is not a pin: OpenITI re-OCRs files in place."""
    srcs = load_lockfile(LOCKFILE_PATH)
    b = next(s for s in srcs if s.id == "openiti-bukhari-jk000110")
    assert b.commit and len(b.commit) == 40, "expected a full 40-char commit SHA"
    assert b.commit in b.url, "the fetched URL must embed the pinned commit"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/ingest/test_lockfile.py -k openiti -v`
Expected: FAIL — no such source id.

- [ ] **Step 3: Capture the commit SHA**

Anonymous GitHub API is rate-limited from this network. Obtain the SHA by any one of:

```bash
gh auth login && gh api \
  "repos/OpenITI/0275AH/commits?path=data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed&per_page=1" \
  --jq '.[0].sha'
```

or open the file's History on github.com and copy the latest commit SHA.

Then verify the pinned URL returns byte-identical content:

```bash
curl -sSL -o /tmp/pinned.txt \
 "https://raw.githubusercontent.com/OpenITI/0275AH/<COMMIT>/data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed"
sha256sum /tmp/pinned.txt
# MUST print 69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7
```

If the hash differs, **stop**: the file changed upstream, and both the hash and `expected_records` in Global Constraints must be re-measured before continuing.

- [ ] **Step 4: Write the lockfile entry**

Replace the `# -- NOT YET RESOLVED ---` block at the foot of `ingest/corpus.lock.toml`:

```toml
# Hadith Arabic text: Sahih al-Bukhari, OpenITI's JK000110 transcription.
#
# LEGAL BASIS: the work's own public-domain status. al-Bukhari died in 870 CE.
# NOT an OpenITI licence grant -- their website states CC BY-SA, but the data
# repository OpenITI/0275AH carries no LICENSE file and the OpenITI/OpenITI
# repo's MIT licence covers their Python tooling, not corpus text (verified
# 2026-09-22). Since Sanad is MIT, relying on a grant we cannot point to would
# hand a downstream commercial user the same problem the Pickthall entry above
# avoids. OpenITI's structural markup is parsed and discarded, so what we store
# is the public-domain text and nothing else. Attribution to them is credit,
# not licence compliance.
#
# `commit` is REQUIRED for this source and absent for the Tanzil ones. Tanzil
# publishes stable versioned exports; OpenITI is a live git repo whose files
# are re-OCRed in place, so a branch URL is not a pin.
#
# content_sha256 covers the COMPLETE RAW FILE, unlike the Tanzil entries where
# it covers the verse payload only. That exclusion exists solely because
# Tanzil's copyright block embeds the current year. This file has no volatile
# block, so hashing everything is simpler and stronger -- the #META# header is
# itself provenance worth pinning. Do not "harmonise" the two conventions.
[[source]]
id               = "openiti-bukhari-jk000110"
kind             = "hadith-arabic"
format           = "openiti-markdown"
title            = "الجامع الصحيح المختصر (Sahih al-Bukhari)"
publisher        = "OpenITI (transcription); Dar Ibn Kathir / al-Yamama, Beirut (edition)"
edition          = "al-Bugha, 3rd ed., 1407/1987; OpenITI JK000110, ara1.completed"
url              = "https://raw.githubusercontent.com/OpenITI/0275AH/<COMMIT>/data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed"
commit           = "<COMMIT>"
license_id       = "public-domain"
license_url      = "https://github.com/OpenITI/0275AH"
content_sha256   = "69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7"
expected_records = 7129
modifications    = "mARkdown structural markers parsed and discarded; no text altered"
```

- [ ] **Step 5: Extend the loader**

In `ingest/sanad_ingest/lockfile.py`, add `"openiti-markdown"` to the allowed `format` values, and add two optional fields to `LockedSource`:

```python
commit: str | None = None
expected_records: int | None = None
```

Keep `format` required with no default — that requirement is why the wrong Tanzil export was caught. `expected_lines` stays required for the two Tanzil sources and is `None` here; `expected_records` is its hadith counterpart.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/pytest tests/ingest/ -v`
Expected: PASS, including the two new tests and all pre-existing ones.

- [ ] **Step 7: Commit**

```bash
git add ingest/corpus.lock.toml ingest/sanad_ingest/lockfile.py tests/ingest/
git commit -m "feat(ingest): pin the OpenITI Bukhari source in the lockfile"
```

---

## Task 2: The mARkdown parser

The largest task. Everything downstream depends on its output being exactly right, and the measurements in Global Constraints exist so its tests assert real numbers rather than plausible ones.

**Files:**
- Create: `ingest/sanad_ingest/openiti.py`
- Create: `tests/fixtures/bukhari_sample.txt`
- Test: `tests/ingest/test_openiti.py`

**Interfaces:**
- Consumes: nothing from other tasks (pure function)
- Produces:
  ```python
  @dataclass(frozen=True)
  class HadithUnit:
      hadith_no: str        # "1", "619"; the printed al-Bugha number
      record_id: str        # "hadith:bukhari:619", "...:619-2" on repeat
      is_repeat: bool       # the 'م' mukarrar marker
      kitab_no: int
      kitab_ar: str
      bab_ar: str | None
      isnad_ar: str | None  # None when the file marks no '*' boundary
      matn_ar: str

  @dataclass(frozen=True)
  class ParsedOpeniti:
      units: list[HadithUnit]
      attribution: str      # the verbatim #META# header block
      content_sha256: str   # whole-file hash
      noisy: list[tuple[str, str]]   # (record_id, offending characters)

  def parse_openiti(raw: str) -> ParsedOpeniti: ...
  ```

- [ ] **Step 1: Build the fixture from the real file**

Do **not** type Arabic into the test. Slice it out of the download:

```bash
python3 - <<'PY'
raw = open('/tmp/bukhari.txt', encoding='utf-8').read()
i = raw.find('#META#Header#End#')
header = raw[:i + len('#META#Header#End#')]
body = raw[i + len('#META#Header#End#'):]
# first kitab marker through hadith 10, plus a known bab heading and a @QB@ unit
start = body.find('### |')
end = body.find('# 11 ')
open('tests/fixtures/bukhari_sample.txt', 'w', encoding='utf-8').write(header + body[start:end])
PY
sha256sum tests/fixtures/bukhari_sample.txt
```

Record the fixture's own SHA-256 in a comment at the top of the test file so a silent edit is detectable.

- [ ] **Step 2: Write the failing tests**

```python
# tests/ingest/test_openiti.py
from pathlib import Path
import re
import pytest
from sanad_ingest.openiti import parse_openiti, HadithUnit

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bukhari_sample.txt"
FULL = Path("/tmp/bukhari.txt")   # the real download; see Task 2 Step 1


@pytest.fixture(scope="module")
def sample():
    return parse_openiti(FIXTURE.read_text(encoding="utf-8"))


def test_extracts_the_meta_header_verbatim(sample):
    assert "#META# 045.EdYEAR" in sample.attribution
    assert "1407 - 1987" in sample.attribution
    assert "#META#Header#End#" in sample.attribution


def test_first_hadith_splits_isnad_from_matn(sample):
    first = sample.units[0]
    assert first.hadith_no == "1"
    assert first.record_id == "hadith:bukhari:1"
    # The isnad ends at the '*'; the matn begins with the famous words.
    # Both strings are compared against the FILE, never against typed Arabic.
    raw = FIXTURE.read_text(encoding="utf-8")
    unit = raw[raw.index("# 1 "):raw.index("# 2 ")]
    unit = unit.replace("~~", "").replace("\n", " ")
    unit = re.sub(r"PageV\d+P\d+", "", unit)
    expect_isnad, expect_matn = unit[len("# 1 "):].split("*", 1)
    assert first.isnad_ar == " ".join(expect_isnad.split())
    assert first.matn_ar == " ".join(expect_matn.split())


def test_matn_carries_no_structural_markers(sample):
    for u in sample.units:
        for marker in ("~~", "@QB@", "@QE@", "*", "PageV"):
            assert marker not in u.matn_ar, f"{marker} leaked into {u.record_id}"
        assert not re.search(r"ms\d{4}", u.matn_ar)
        assert not re.search(r"\\\s*\d+\s*\\", u.matn_ar)


def test_quranic_quotation_text_survives_marker_stripping(sample):
    """@QB@...@QE@ markers go; the words between them stay."""
    raw = FIXTURE.read_text(encoding="utf-8")
    inner = re.search(r"@QB@(.+?)@QE@", raw, re.S)
    assert inner, "fixture must contain at least one Qur'anic quotation"
    words = " ".join(inner.group(1).replace("~~", "").split())
    joined = " ".join(u.matn_ar for u in sample.units) + " ".join(
        u.isnad_ar or "" for u in sample.units
    )
    assert words[:30] in joined


def test_bab_headings_are_not_records(sample):
    for u in sample.units:
        assert not u.matn_ar.lstrip().startswith("باب")


# --- whole-file assertions: these are the measured facts from the plan ---

@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_full_file_yields_the_measured_record_count():
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    assert len(parsed.units) == 7129


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_every_record_id_is_unique():
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    ids = [u.record_id for u in parsed.units]
    assert len(set(ids)) == len(ids), "record ids must be unique"


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_the_four_unmarked_hadith_keep_all_text_as_matn():
    """2795, 6964-6966 carry no '*'. Guessing a boundary would invent a chain."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    unmarked = [u for u in parsed.units if u.isnad_ar is None]
    assert sorted(u.hadith_no for u in unmarked) == ["2795", "6964", "6965", "6966"]
    for u in unmarked:
        assert u.matn_ar.strip()


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_repeat_marked_units_are_distinct_records():
    """619 م is a different narration from 619 -- 25 degrees vs 27."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    six19 = [u for u in parsed.units if u.hadith_no == "619"]
    assert len(six19) == 2
    assert len({u.record_id for u in six19}) == 2
    assert sum(u.is_repeat for u in six19) == 1
    assert six19[0].matn_ar != six19[1].matn_ar


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_collision_without_a_repeat_marker_still_gets_distinct_ids():
    """3905 is printed twice, neither marked م -- an edition artifact."""
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    both = [u for u in parsed.units if u.hadith_no == "3905"]
    assert len(both) == 2
    assert both[0].record_id != both[1].record_id


@pytest.mark.skipif(not FULL.exists(), reason="full download not present")
def test_content_hash_matches_the_pinned_value():
    parsed = parse_openiti(FULL.read_text(encoding="utf-8"))
    assert parsed.content_sha256 == (
        "69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7"
    )
```

- [ ] **Step 3: Run to verify they fail**

Run: `.venv/bin/pytest tests/ingest/test_openiti.py -v`
Expected: FAIL — `ModuleNotFoundError: sanad_ingest.openiti`.

- [ ] **Step 4: Implement the parser**

```python
"""OpenITI mARkdown -> hadith units.

Pure function: text in, structure out. No network, no database, no file I/O.

The marker inventory below was measured against the pinned file on 2026-09-22,
not taken from OpenITI's documentation -- the file contains marker forms the
docs do not mention (ms####, backslash part markers), and a parser written from
the docs alone would have leaked them into stored text.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_HEADER_END = "#META#Header#End#"

# Structural markers, all stripped from stored text.
_CONTINUATION = "~~"
_PAGE = re.compile(r"PageV\d+P\d+")
_MILESTONE = re.compile(r"ms\d{4}")
_PART = re.compile(r"\\\s*\d+\s*\\")          # the "\ 1 \" part marker
_QURAN_MARK = re.compile(r"@QB@|@QE@")        # markers go, quoted words stay
_SECTION = re.compile(r"^###")                # ### | , ### || , ### |||
_KITAB = re.compile(r"^###\s*\|(?!\|)\s*(.*)$")
_BAB = re.compile(r"^###\s*\|\|+\s*(.*)$")
_UNIT_START = re.compile(r"^#\s(?!##)")
_NUMBERED = re.compile(r"^(\d+)\s+(م\s+)?(.*)$", re.S)

# A numbered unit whose text begins with "باب" is a chapter heading that the
# edition happens to number, not a narration. Six of them exist in the file.
_BAB_WORD = "باب"

# Everything outside these ranges is flagged (never corrected) as OCR noise.
_ALLOWED = re.compile(r"[؀-ۿ\s]")


@dataclass(frozen=True)
class HadithUnit:
    hadith_no: str
    record_id: str
    is_repeat: bool
    kitab_no: int
    kitab_ar: str
    bab_ar: str | None
    isnad_ar: str | None
    matn_ar: str


@dataclass(frozen=True)
class ParsedOpeniti:
    units: list[HadithUnit]
    attribution: str
    content_sha256: str
    noisy: list[tuple[str, str]]


def _clean(s: str) -> str:
    """Strip every structural marker; never touch letters."""
    s = _PAGE.sub(" ", s)
    s = _MILESTONE.sub(" ", s)
    s = _PART.sub(" ", s)
    s = _QURAN_MARK.sub(" ", s)
    return " ".join(s.split())


def parse_openiti(raw: str) -> ParsedOpeniti:
    end = raw.find(_HEADER_END)
    if end == -1:
        raise ValueError("no #META#Header#End# marker: not an OpenITI mARkdown file")
    attribution = raw[: end + len(_HEADER_END)]
    body = raw[end + len(_HEADER_END) :]

    units: list[HadithUnit] = []
    seen: dict[str, int] = {}
    kitab_no, kitab_ar, bab_ar = 0, "", None
    buf: list[str] | None = None

    def flush() -> None:
        nonlocal buf
        if buf is None:
            return
        text, buf = " ".join(buf), None
        m = _NUMBERED.match(text)
        if not m:
            return
        number, repeat, rest = m.group(1), bool(m.group(2)), m.group(3)
        rest_clean = _clean(rest)
        if rest_clean.startswith(_BAB_WORD):
            return  # numbered chapter heading, not a narration

        if "*" in rest:
            isnad_raw, matn_raw = rest.split("*", 1)
            isnad, matn = _clean(isnad_raw), _clean(matn_raw)
        else:
            # The file marks no boundary. Keep everything as matn rather than
            # guessing where a chain ends -- inventing an isnad is worse than
            # admitting the source does not mark one.
            isnad, matn = None, rest_clean

        seen[number] = seen.get(number, 0) + 1
        suffix = "" if seen[number] == 1 else f"-{seen[number]}"
        units.append(
            HadithUnit(
                hadith_no=number,
                record_id=f"hadith:bukhari:{number}{suffix}",
                is_repeat=repeat,
                kitab_no=kitab_no,
                kitab_ar=kitab_ar,
                bab_ar=bab_ar,
                isnad_ar=isnad,
                matn_ar=matn,
            )
        )

    for line in body.splitlines():
        if line.startswith(_CONTINUATION):
            if buf is not None:
                buf.append(line[len(_CONTINUATION) :])
            continue
        if _SECTION.match(line):
            flush()
            if (k := _KITAB.match(line)) is not None:
                kitab_no += 1
                kitab_ar, bab_ar = _clean(k.group(1)), None
            elif (b := _BAB.match(line)) is not None:
                bab_ar = _clean(b.group(1)) or None
            continue
        if _UNIT_START.match(line):
            flush()
            buf = [line[2:]]
            continue
        if buf is not None:
            buf.append(line)
    flush()

    noisy = []
    for u in units:
        bad = "".join(sorted({c for c in u.matn_ar if not _ALLOWED.match(c)}))
        if bad:
            noisy.append((u.record_id, bad))

    return ParsedOpeniti(
        units=units,
        attribution=attribution,
        content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        noisy=noisy,
    )
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/pytest tests/ingest/test_openiti.py -v`
Expected: PASS, all of them. `test_full_file_yields_the_measured_record_count` must print exactly 7129 — if it does not, **stop and re-measure** rather than adjusting the assertion.

- [ ] **Step 6: Confirm the tests can actually fail**

Mutation check, because this project has shipped tests that could not fail. Temporarily change `_clean` to skip `_PART.sub`, re-run, and confirm `test_matn_carries_no_structural_markers` fails. Revert.

Run: `.venv/bin/pytest tests/ingest/test_openiti.py -v`
Expected: PASS again after reverting.

- [ ] **Step 7: Commit**

```bash
git add ingest/sanad_ingest/openiti.py tests/ingest/test_openiti.py tests/fixtures/bukhari_sample.txt
git commit -m "feat(ingest): parse OpenITI mARkdown into isnad/matn hadith units"
```

---

## Task 3: Schema and model gain `isnad_ar`

**Files:**
- Modify: `api/sanad/corpus/schema.py`, `api/sanad/corpus/models.py`, `api/sanad/corpus/db.py`
- Test: `tests/corpus/test_db.py`

**Interfaces:**
- Consumes: `Record` from Task 0 (existing)
- Produces: `Record.isnad_ar: str | None`; `records.isnad_ar` column readable via `get_record`

- [ ] **Step 1: Write the failing test**

```python
# tests/corpus/test_db.py  (append)
def test_round_trips_a_hadith_record_with_its_isnad(tmp_path):
    conn = connect(tmp_path / "c.db", read_only=False)
    conn.executescript(SCHEMA_SQL)
    insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    rec = Record(
        id="hadith:bukhari:1",
        source_id="openiti-bukhari-jk000110",
        kind="hadith",
        collection="bukhari",
        hadith_no="1",
        numbering_scheme="bugha-1987",
        text_ar="MATN",
        isnad_ar="ISNAD",
        text_ar_sha256="x" * 64,
        norm_light="MATN", norm_standard="MATN", norm_aggressive="MATN",
        reference_display="Sahih al-Bukhari 1",
    )
    insert_records(conn, [rec])
    got = get_record(conn, "hadith:bukhari:1")
    assert got.isnad_ar == "ISNAD"
    assert got.text_ar == "MATN"
    assert got.surah is None and got.ayah is None


def test_quran_records_have_no_isnad(tmp_path):
    conn = connect(tmp_path / "c.db", read_only=False)
    conn.executescript(SCHEMA_SQL)
    insert_source(conn, _a_source())
    insert_records(conn, [_an_ayah(id="quran:112:1")])
    assert get_record(conn, "quran:112:1").isnad_ar is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/corpus/test_db.py -k isnad -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'isnad_ar'`.

- [ ] **Step 3: Add the column and field**

In `api/sanad/corpus/schema.py`, inside `CREATE TABLE records`, immediately after `bismillah TEXT,`:

```sql
  isnad_ar          TEXT,
```

In `api/sanad/corpus/models.py`, on `Record`, after `bismillah`:

```python
    # The narrator chain, for hadith records. Stored but never scored: see the
    # Stage A2 spec §7. Scoring across isnad + matn puts a short, famous matn
    # near 0.13 against a 0.86 threshold.
    isnad_ar: str | None = None
```

Add `isnad_ar` to the column list and row-mapping in `db.py`'s `insert_records` and `get_record`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/corpus/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/corpus/ tests/corpus/
git commit -m "feat(corpus): store the isnad alongside the matn"
```

---

## Task 4: Build the corpus

**Files:**
- Modify: `ingest/sanad_ingest/build.py`, `ingest/sanad_ingest/fetch.py`
- Create: `docs/hadith-noise-report.md` (generated artifact, committed for review)
- Test: `tests/ingest/test_build.py`

**Interfaces:**
- Consumes: `parse_openiti`, `ParsedOpeniti`, `HadithUnit` (Task 2); `Record.isnad_ar` (Task 3)
- Produces: a corpus DB containing 6,236 āyāt + 7,129 hadith; new corpus SHA-256

- [ ] **Step 1: Write the failing test**

```python
# tests/ingest/test_build.py  (append)
def test_builds_hadith_records_with_matn_as_the_scored_text(tmp_path):
    db = tmp_path / "corpus.db"
    build_corpus(db, only_sources=["openiti-bukhari-jk000110"])
    conn = connect(db, read_only=True)
    n = conn.execute("SELECT count(*) FROM records WHERE kind='hadith'").fetchone()[0]
    assert n == 7129
    row = conn.execute(
        "SELECT text_ar, isnad_ar, norm_standard FROM records WHERE id='hadith:bukhari:1'"
    ).fetchone()
    matn, isnad, norm = row
    assert isnad and len(isnad) > 100, "the chain must be stored"
    assert len(matn) < len(isnad), "hadith 1's matn is shorter than its chain"
    assert "حدثنا" not in matn, "narration verbs belong to the isnad, not the matn"
    assert norm and "حدثنا" not in norm, "normalized text derives from the matn only"


def test_fts_does_not_index_the_isnad(tmp_path):
    db = tmp_path / "corpus.db"
    build_corpus(db, only_sources=["openiti-bukhari-jk000110"])
    conn = connect(db, read_only=True)
    # A narrator name unique to hadith 1's chain must not retrieve it.
    hits = conn.execute(
        "SELECT count(*) FROM records_fts WHERE records_fts MATCH ?", ("الحميدي",)
    ).fetchone()[0]
    assert hits == 0, "the isnad must not be searchable text"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/ingest/test_build.py -k hadith -v`
Expected: FAIL — the format dispatch has no `openiti-markdown` branch.

- [ ] **Step 3: Implement the build branch**

In `build.py`, dispatch on `source.format`. For `"openiti-markdown"`, map each `HadithUnit` to a `Record`:

```python
from .openiti import parse_openiti

def _hadith_records(parsed, source):
    out = []
    for u in parsed.units:
        # text_ar is the MATN. This single line is the whole of spec §7.
        text = u.matn_ar
        out.append(Record(
            id=u.record_id,
            source_id=source.id,
            kind="hadith",
            collection="bukhari",
            book_no=u.kitab_no,
            chapter_ar=u.bab_ar,
            hadith_no=u.hadith_no,
            numbering_scheme="bugha-1987",
            text_ar=text,
            isnad_ar=u.isnad_ar,
            text_ar_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            norm_light=normalize(text, "light"),
            norm_standard=normalize(text, "standard"),
            norm_aggressive=normalize(text, "aggressive"),
            reference_display=f"Sahih al-Bukhari {u.hadith_no}",
        ))
    return out
```

Enforce `expected_records` exactly as `expected_lines` is enforced for Tanzil: mismatch aborts the build.

`rebuild_fts` must insert `norm_standard` and `norm_aggressive` only — never `isnad_ar`.

- [ ] **Step 4: Write the noise report**

After ingest, write `parsed.noisy` to `docs/hadith-noise-report.md`: one row per flagged record with its id and offending characters, plus a header stating that **no text was altered** and that the report exists so corrupt records are not chosen as eval cases.

- [ ] **Step 5: Build the real corpus and record its hash**

```bash
.venv/bin/python -m sanad_ingest.cli build
sha256sum data/sanad-quran.db
.venv/bin/python -c "
import sqlite3;c=sqlite3.connect('data/sanad-quran.db')
print(c.execute('select kind,count(*) from records group by kind').fetchall())"
```

Expected: `[('ayah', 6236), ('hadith', 7129)]`. Update the corpus SHA-256 wherever it is asserted — `grep -rn` for the old hash first; several tests and docs carry it.

- [ ] **Step 6: Run the full Python suite**

Run: `.venv/bin/pytest -q`
Expected: PASS. Investigate any Qur'an-side failure as a real regression, not as an expected consequence.

- [ ] **Step 7: Commit**

```bash
git add ingest/ tests/ingest/ docs/hadith-noise-report.md data/sanad-quran.db
git commit -m "feat(ingest): build Bukhari into the corpus, matn as the scored text"
```

---

## Task 5: Hadith citation parsing

**Files:**
- Modify: `api/sanad/verify/references.py`
- Test: `tests/verify/test_references.py`

**Interfaces:**
- Consumes: nothing new
- Produces:
  ```python
  @dataclass(frozen=True)
  class HadithReference:
      collection: str      # "bukhari"
      hadith_no: str
      raw: str
      start: int

  AnyReference = Reference | HadithReference
  def parse_references(text: str) -> list[AnyReference]: ...
  def nearest_reference(refs, position, window=180) -> AnyReference | None: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/verify/test_references.py  (append)
import pytest
from sanad.verify.references import parse_references, HadithReference, Reference

@pytest.mark.parametrize("text,number", [
    ("Bukhari 1", "1"),
    ("Sahih al-Bukhari, no. 1", "1"),
    ("al-Bukhari, Book 1, Hadith 1", "1"),
    ("Sahih Bukhari 7124", "7124"),
])
def test_parses_hadith_citations(text, number):
    refs = [r for r in parse_references(text) if isinstance(r, HadithReference)]
    assert len(refs) == 1
    assert refs[0].collection == "bukhari"
    assert refs[0].hadith_no == number


def test_bare_collection_name_is_not_a_reference():
    """'Bukhari' names a collection, not a text -- same rule as bare 'Maryam'."""
    assert not [r for r in parse_references("as Bukhari reports") 
                if isinstance(r, HadithReference)]


def test_collection_name_governs_a_colon_pair():
    """'Bukhari 1:1' is kitab 1 hadith 1, never surah 1 ayah 1."""
    refs = parse_references("Bukhari 1:1")
    assert not any(isinstance(r, Reference) for r in refs)
    assert any(isinstance(r, HadithReference) for r in refs)


def test_a_plain_verse_citation_is_still_a_verse():
    refs = parse_references("Al-Baqarah 2:255")
    assert any(isinstance(r, Reference) and r.surah == 2 and r.ayah == 255 
               for r in refs)
    assert not any(isinstance(r, HadithReference) for r in refs)


def test_out_of_range_number_does_not_fall_back_to_a_verse_reading():
    refs = parse_references("Bukhari 99999")
    assert not any(isinstance(r, Reference) for r in refs)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/verify/test_references.py -k hadith -v`
Expected: FAIL — `ImportError: cannot import name 'HadithReference'`.

- [ ] **Step 3: Implement**

Add to `references.py`:

```python
# Collection names that mark a following number as a hadith citation. Bare
# names are rejected by requiring the number, mirroring the surah-name rule:
# a spurious reference produces an actively wrong WRONG_REFERENCE, whereas a
# missed one only downgrades to a correct plain match.
_COLLECTIONS = {
    "bukhari": "bukhari",
    "albukhari": "bukhari",
    "sahihbukhari": "bukhari",
    "sahihalbukhari": "bukhari",
}

_HADITH_CITE = re.compile(
    r"\b(?:sahih\s+)?(?:al[-\s]?)?bukhari\b"
    r"(?:\s*,)?\s*"
    r"(?:(?:book|kitab)\s*\d{1,3}\s*,?\s*)?"
    r"(?:(?:hadith|hadeeth|no\.?|number|#)\s*)?"
    r"(\d{1,4})"
    r"(?:\s*[:：]\s*(\d{1,4}))?",
    re.IGNORECASE,
)
MAX_HADITH_NO = 7124
```

In `parse_references`, run `_HADITH_CITE` **first** and record its spans as claimed, so the verse-numeric pass skips text already consumed by a hadith citation — that is what makes `Bukhari 1:1` resolve as a hadith. When the optional second group is present, the pair is kitāb:hadith and the **second** group is the hadith number. Reject numbers above `MAX_HADITH_NO` without falling back to a verse reading.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/verify/ -v`
Expected: PASS, including all pre-existing verse-reference tests.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/verify/references.py tests/verify/test_references.py
git commit -m "feat(verify): parse Bukhari citations as their own reference family"
```

---

## Task 6: Cross-kind reference checking in the engine

**Files:**
- Modify: `api/sanad/verify/engine.py`
- Test: `tests/verify/test_engine.py`

**Interfaces:**
- Consumes: `HadithReference`, `AnyReference` (Task 5); hadith records (Task 4)
- Produces: no new names; `verify_spans` returns `WRONG_REFERENCE` on a kind mismatch

- [ ] **Step 1: Write the failing test**

```python
# tests/verify/test_engine.py  (append)
def test_a_hadith_quoted_and_correctly_cited_verifies(corpus):
    matn = corpus.execute(
        "SELECT text_ar FROM records WHERE id='hadith:bukhari:1'"
    ).fetchone()[0]
    out = verify_spans(corpus, f"«{matn}» (Bukhari 1)")
    assert out[0].verdict is Verdict.EXACT


def test_an_ayah_cited_as_bukhari_is_a_wrong_reference(corpus):
    ayah = corpus.execute(
        "SELECT text_ar FROM records WHERE id='quran:112:1'"
    ).fetchone()[0]
    out = verify_spans(corpus, f"«{ayah}» (Bukhari 1)")
    assert out[0].verdict is Verdict.WRONG_REFERENCE


def test_a_hadith_cited_as_a_verse_is_a_wrong_reference(corpus):
    matn = corpus.execute(
        "SELECT text_ar FROM records WHERE id='hadith:bukhari:1'"
    ).fetchone()[0]
    out = verify_spans(corpus, f"«{matn}» (Al-Baqarah 2:255)")
    assert out[0].verdict is Verdict.WRONG_REFERENCE


def test_the_famous_short_matn_verifies_on_its_own(corpus):
    """The §7 canary. Fails the moment anyone stores isnad+matn in text_ar."""
    matn = corpus.execute(
        "SELECT text_ar FROM records WHERE id='hadith:bukhari:1'"
    ).fetchone()[0]
    out = verify_spans(corpus, f"«{matn}»")
    assert out[0].verdict is Verdict.EXACT
    assert out[0].record.id == "hadith:bukhari:1"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/verify/test_engine.py -k hadith -v`
Expected: FAIL — an āyah cited as Bukhari currently verifies EXACT, ignoring the reference.

- [ ] **Step 3: Implement**

In the reference-comparison branch of `verify_spans`, compare kinds before comparing values:

```python
# A reference of the wrong kind is wrong, not absent. Mis-attributing an ayah
# to Bukhari is a common real-world error and a useful verdict.
if isinstance(ref, HadithReference):
    if match.record.kind != "hadith" or match.record.hadith_no != ref.hadith_no:
        return Verdict.WRONG_REFERENCE
else:
    if match.record.kind != "ayah":
        return Verdict.WRONG_REFERENCE
    ...existing surah/ayah comparison...
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/verify/engine.py tests/verify/test_engine.py
git commit -m "feat(verify): treat a cross-kind citation as a wrong reference"
```

---

## Task 7: API surface and the reworded corpus scope

**Files:**
- Modify: `api/sanad/api/schemas.py`, `api/sanad/api/routes.py`
- Test: `tests/api/test_routes.py`

**Interfaces:**
- Consumes: `Record.isnad_ar`, hadith records
- Produces: `RecordOut` gains `isnad_ar`, `collection`, `hadith_no`; `CORPUS_SCOPE` reworded

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_routes.py  (append)
def test_corpus_scope_names_both_corpora(client):
    r = client.post("/api/verify", json={"text": "hello"}).json()
    scope = r["corpus_scope"]
    assert "Bukhari" in scope
    assert "Qur'an" in scope
    assert "only" not in scope.lower().split("Bukhari")[0]
    assert "does not establish that it is fabricated" in scope


def test_a_verified_hadith_exposes_its_isnad(client, corpus):
    matn = corpus.execute(
        "SELECT text_ar FROM records WHERE id='hadith:bukhari:1'"
    ).fetchone()[0]
    q = client.post("/api/verify", json={"text": f"«{matn}»"}).json()["quotations"][0]
    assert q["record"]["isnad_ar"]
    assert q["record"]["collection"] == "bukhari"
    assert q["record"]["hadith_no"] == "1"


def test_no_grading_is_ever_returned(client, corpus):
    matn = corpus.execute(
        "SELECT text_ar FROM records WHERE id='hadith:bukhari:1'"
    ).fetchone()[0]
    body = client.post("/api/verify", json={"text": f"«{matn}»"}).text.lower()
    for word in ("sahih\"", "da'if", "daif", "grading", "authentic"):
        assert word not in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/api/test_routes.py -k "scope or isnad or grading" -v`
Expected: FAIL — scope still says "the Qur'an only".

- [ ] **Step 3: Implement**

`routes.py`, replacing the constant at roughly line 31:

```python
CORPUS_SCOPE = (
    "This corpus contains the Qur'an and Sahih al-Bukhari. Absence of a "
    "quotation here does not establish that it is fabricated -- it may be "
    "authentic and simply outside what Sanad currently checks."
)
```

Add the three fields to `RecordOut` in `schemas.py`, all optional, and populate them in both routes that build a `RecordOut`.

- [ ] **Step 4: Update the four test files carrying the old literal**

`grep -rln "corpus contains the Qur'an only"` and update each occurrence to the new string.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/ tests/
git commit -m "feat(api): expose the isnad and name Bukhari in the corpus scope"
```

---

## Task 8: Frontend — isnād display and the gradings line

**Files:**
- Modify: `web/src/components/EvidenceCard.tsx`, `web/src/screens/Verify.tsx`, `web/src/api/types.ts` (regenerated)
- Test: `web/tests/components/EvidenceCard.test.tsx`, `web/tests/screens/Verify.test.tsx`

**Interfaces:**
- Consumes: `RecordOut.isnad_ar`, `.collection`, `.hadith_no` (Task 7)
- Produces: no new exports

- [ ] **Step 1: Regenerate the API client**

```bash
cd web && npm run generate:api && git diff --stat src/api/types.ts
```

`types.ts` is generated — never hand-edit it. CI fails on drift.

- [ ] **Step 2: Write the failing tests**

```tsx
// web/tests/components/EvidenceCard.test.tsx  (append)
const hadith = q({
  record: { id: "hadith:bukhari:1", reference_display: "Sahih al-Bukhari 1",
            text_ar: "MATN", text_ar_sha256: "abc", isnad_ar: "CHAIN OF NARRATORS",
            collection: "bukhari", hadith_no: "1",
            translation_en: null, translation_disclaimer: null },
});

it("shows the isnad for a hadith, in the apparatus register", () => {
  render(<EvidenceCard quotation={hadith} corpusScope={SCOPE} />);
  const el = screen.getByTestId("isnad");
  expect(el).toHaveTextContent("CHAIN OF NARRATORS");
  expect(el.className).toContain("data");
});

it("shows no isnad block for an ayah", () => {
  render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
  expect(screen.queryByTestId("isnad")).toBeNull();
});
```

```tsx
// web/tests/screens/Verify.test.tsx  (append)
it("states once that it does not grade authenticity, when a hadith is shown", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
    ...verified,
    quotations: [
      { ...verified.quotations[0], record: { id: "hadith:bukhari:1",
        reference_display: "Sahih al-Bukhari 1", text_ar: "M1", text_ar_sha256: "a",
        isnad_ar: "C1", collection: "bukhari", hadith_no: "1",
        translation_en: null, translation_disclaimer: null } },
      { ...verified.quotations[0], record: { id: "hadith:bukhari:2",
        reference_display: "Sahih al-Bukhari 2", text_ar: "M2", text_ar_sha256: "b",
        isnad_ar: "C2", collection: "bukhari", hadith_no: "2",
        translation_en: null, translation_disclaimer: null } },
    ],
  })));
  const user = userEvent.setup();
  render(<Verify />);
  await user.type(screen.getByRole("textbox"), "two hadith");
  await user.click(screen.getByRole("button", { name: /verify/i }));
  await waitFor(() => expect(screen.getAllByTestId("isnad")).toHaveLength(2));
  expect(screen.getAllByTestId("no-grading")).toHaveLength(1);
  expect(screen.getByTestId("no-grading")).toHaveTextContent(/does not grade authenticity/i);
});

it("shows no gradings line when only ayat are shown", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(verified)));
  const user = userEvent.setup();
  render(<Verify />);
  await user.type(screen.getByRole("textbox"), "an ayah");
  await user.click(screen.getByRole("button", { name: /verify/i }));
  await waitFor(() => expect(screen.getByText(/^Verified$/)).toBeInTheDocument());
  expect(screen.queryByTestId("no-grading")).toBeNull();
});
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd web && npm test -- --run`
Expected: FAIL — no `isnad` or `no-grading` testids.

- [ ] **Step 4: Implement**

In `EvidenceCard.tsx`, after the matn/translation block:

```tsx
{rec?.isnad_ar && (
  <p data-testid="isnad" className="data"
     style={{ margin: "0.5rem 0 0", lineHeight: 1.7 }} dir="rtl">
    {rec.isnad_ar}
  </p>
)}
```

In `Verify.tsx`, beside the translation disclaimer added earlier — same once-per-result pattern:

```tsx
{result.quotations.some((q) => q.record?.collection) && (
  <p data-testid="no-grading" className="data" style={{ marginBlockStart: "0.5rem" }}>
    Sanad confirms wording against this printed edition. It does not grade
    authenticity (ṣaḥīḥ/ḍaʿīf); that requires a scholarly source.
  </p>
)}
```

- [ ] **Step 5: Run tests**

Run: `cd web && npm test -- --run`
Expected: PASS — 89 tests.

- [ ] **Step 6: Commit**

```bash
git add web/
git commit -m "feat(web): show the isnad, and say plainly that Sanad does not grade"
```

---

## Task 9: Evaluation cases

**Files:**
- Create: `eval/cases/hadith.yaml`
- Modify: `eval/runner.py` if the existing case schema lacks a field these need
- Test: `tests/eval/test_cases.py`

**Interfaces:**
- Consumes: the built corpus, `verify_spans`, `route_risk`
- Produces: eight cases under the existing zero-false-verification CI gate

- [ ] **Step 1: Select the case texts from the real corpus**

Every Arabic string in the YAML is copied out of the built database, never typed:

```bash
.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect('file:data/sanad-quran.db?mode=ro', uri=True)
for rid in ('hadith:bukhari:1', 'hadith:bukhari:2', 'quran:112:1'):
    print(rid, '::', c.execute(
        'select text_ar from records where id=?', (rid,)).fetchone()[0])
PY
```

Cross-check each chosen id against `docs/hadith-noise-report.md` and pick a different record if it is flagged.

- [ ] **Step 2: Write the cases**

```yaml
# eval/cases/hadith.yaml
# Adversarial cases for the Bukhari layer. Same gate as every other file:
# zero false verifications, no exceptions. A false EXACT on a hadith is worse
# than on an ayah -- the reader has no memorised text to catch it with.

- id: hadith-famous-matn-bare
  # THE CANARY for spec §7. Fails the moment isnad+matn is stored in text_ar.
  text: "<matn of hadith:bukhari:1, pasted from the corpus>"
  expect_verdict: EXACT
  expect_record: hadith:bukhari:1

- id: hadith-with-quranic-quotation
  # Verifies that stripping @QB@ markers did not strip the words between them.
  text: "<matn of a hadith containing a Qur'anic quotation>"
  expect_verdict: EXACT

- id: hadith-right-text-wrong-number
  text: "<matn of hadith:bukhari:1> (Bukhari 4321)"
  expect_verdict: WRONG_REFERENCE

- id: hadith-authentic-elsewhere-absent-here
  # A sound hadith found in Muslim but not Bukhari. Must NOT read as an
  # accusation: the reworded scope caveat is the point of this case.
  text: "<matn of a hadith in Muslim only>"
  expect_verdict: NOT_FOUND
  expect_scope_caveat: true

- id: hadith-fabricated
  text: "<a hadith in circulation with no chain, e.g. 'seek knowledge even unto China'>"
  expect_verdict: NOT_FOUND

- id: hadith-in-personal-ruling-question
  text: "Can I divorce my wife this way? <matn of hadith:bukhari:1>"
  expect_risk: PERSONAL_RULING
  expect_handoff: true
  expect_no_verdict: true

- id: ayah-cited-as-bukhari
  text: "<text of quran:112:1> (Bukhari 1)"
  expect_verdict: WRONG_REFERENCE

- id: hadith-quoted-with-its-isnad
  # Realistic copy-paste from a website. Outcome is MEASURED, not assumed:
  # a long chain prefix drags the score down. Whatever it does, it must not
  # near-match onto a DIFFERENT hadith. Record the result in the ledger.
  text: "<isnad + matn of hadith:bukhari:1 as one string>"
  expect_not_verdict: NEAR_MATCH_TO_OTHER_RECORD
```

- [ ] **Step 3: Run the eval suite**

Run: `.venv/bin/pytest tests/eval/ -v && .venv/bin/python -m eval.runner`
Expected: PASS, **zero false verifications**.

For `hadith-quoted-with-its-isnad`, record the measured verdict in the SDD ledger with its score. If it comes out `NOT_FOUND`, that is an acceptable, documented limitation — it must not be "fixed" by lowering `NEAR_THRESHOLD`, which would trade a missed match for false verifications across the whole corpus.

- [ ] **Step 4: Commit**

```bash
git add eval/ tests/eval/
git commit -m "test(eval): adversarial Bukhari cases under the zero-false-verification gate"
```

---

## Task 10: Documentation and final verification

**Files:**
- Modify: `docs/SOURCES.md`, `README.md`
- Test: full suite

- [ ] **Step 1: Record the licensing basis in `docs/SOURCES.md`**

Reproduce spec §4.2 in full: the public-domain basis, the verified absence of a `LICENSE` file in `OpenITI/0275AH` as of 2026-09-22, why attribution is credit rather than compliance, and the pinned commit and hash.

- [ ] **Step 2: Update `README.md`**

Corpus description, record counts (6,236 āyāt + 7,129 hadith), the new corpus SHA-256, and an explicit statement that Sanad does not grade hadith authenticity.

- [ ] **Step 3: Full verification**

```bash
.venv/bin/pytest -q                     # expect 257 + new, all passing
cd web && npm test -- --run             # expect 89
cd web && npm run build                 # must succeed
git diff --exit-code web/src/api/types.ts   # generated client must be current
```

- [ ] **Step 4: Verify the corpus is reproducible**

```bash
.venv/bin/python -m sanad_ingest.cli build --out /tmp/rebuild.db
.venv/bin/python - <<'PY'
import sqlite3, hashlib
def sig(p):
    c = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    rows = c.execute('select id, text_ar_sha256 from records order by id').fetchall()
    return hashlib.sha256(repr(rows).encode()).hexdigest()
print(sig('data/sanad-quran.db'))
print(sig('/tmp/rebuild.db'))
PY
```

Both signatures must match. This compares every record's text hash, not just counts — counts alone would pass even if every verse had changed.

- [ ] **Step 5: Commit**

```bash
git add docs/ README.md
git commit -m "docs: record the Bukhari source, its basis, and the new corpus hash"
```

---

## Self-Review

**Spec coverage.** §4 lockfile → Task 1. §5 parser → Task 2. §6 schema → Task 3. §7 matn-only matching → Tasks 2, 4, 6, 9 (canary). §8 citations → Task 5. §9.1 caveat → Task 7. §9.2 isnād → Task 8. §9.3 gradings → Tasks 7, 8. §9.4 API → Tasks 7, 8. §10 OCR noise → Tasks 2, 4. §11 eval → Task 9. §12 files → all. §15 open items → Task 1 (commit SHA), Task 4 (`expected_records`, now measured at 7,129).

**Deviations from the spec, all discovered by measuring the real file and none requiring a spec change:**

1. **`### |||` exists** (363 lines). The spec's table lists only two section depths. Task 2 treats any `||`-or-deeper as a bāb.
2. **`ms\d{4}` and `\ N \` markers exist** (2,033 and 4,657). Absent from the spec's table; both are stripped in Task 2. A parser written from the spec alone would have leaked them into stored text.
3. **`hadith_no` is not unique.** The spec's `hadith:bukhari:<n>` id would have collided on six records. Task 2 appends an occurrence ordinal. This is the Stage A duplicate-verse problem in a new form.
4. **`م` (mukarrar) units are genuinely different narrations** — 619 says 27 degrees, 619 م says 25. Stored as distinct records.
5. **Four hadith carry no `*`.** The spec's "keep everything as matn" rule was written for this and is correct; the count is now known.
6. **Six numbered units are bāb headings, not hadith.** Filtered by the `باب` prefix, giving 7,129 rather than 7,135.

**Placeholder scan.** The only `<...>` placeholders are the commit SHA (Task 1 Step 3 shows exactly how to obtain and verify it) and the Arabic case texts in Task 9 (Step 1 shows exactly how to extract them, and typing them by hand is forbidden by the Global Constraints).

**Type consistency.** `HadithUnit`/`ParsedOpeniti` (Task 2) are consumed with the same field names in Task 4. `Record.isnad_ar` (Task 3) is used in Tasks 4, 7. `HadithReference.hadith_no` is a `str` in Tasks 5, 6 and matches `Record.hadith_no`'s `TEXT` column. `record_id` (Task 2) becomes `Record.id` (Task 4).
