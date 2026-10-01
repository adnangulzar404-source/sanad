# Stage A3 — Five More Hadith Collections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest Ṣaḥīḥ Muslim and the four Sunan into the corpus on the same terms as Bukhari, and split the build so the committed database stays under GitHub's 100 MB per-file limit.

**Architecture:** The build gains a derivation boundary. `sanad-ingest build` writes a *source-only* SQLite file (the committed artifact); a new network-free `sanad-ingest materialize` step derives `norm_*`, `text_ar_sha256`, `record_variants`, FTS, and indexes from the source columns, and runs at Docker/Vercel build time and in a pytest fixture. `reference_display` is the one documented exception (Stage A3 ruling R-A3-6, revised into this doc 2026-10-01): it is written at BUILD time, not materialize time, because it depends on `HadithUnit.is_repeat` and a build-time occurrence counter that are not columns, so a source-only DB carries it as a genuine source column instead — see `sanad_ingest.materialize`'s module docstring and `sanad.corpus.schema`. The `bukhari`-hardcoded points in the parser and builder become per-source config; citation parsing and the corpus-scope copy generalise to N collections. Each new source is vetted per-file, measured (never guessed), and given its own hand-audited exception lists.

**Tech Stack:** Python 3.10, FastAPI, SQLite (FTS5), httpx, pytest, ruff; React/Vite/vitest for the copy changes; Docker + Vercel for deploy.

**Spec:** `docs/superpowers/specs/2026-09-27-hadith-collections-a3-design.md`

## Global Constraints

- **No gradings, any collection.** The `gradings` table stays empty; al-Tirmidhī's own gradings are out of scope this stage.
- **Byte-exact Arabic**, `content_sha256`-pinned per source; the build refuses on drift. No silent text correction.
- **Measured, never guessed:** `content_sha256`, `commit`, and `expected_records` are measured at first build and then pinned into the lockfile. No count is typed from memory.
- **Anti-fabrication display contract (I1/I2):** Arabic is shown only from server `record` objects; English is model/app prose. The `reverent` transform runs on prose only, never on canonical corpus text.
- **Reverent naming** on any new/changed English prose: "Allah" not "God", honorifics after prophets.
- **Ask model** is `claude-sonnet-4-6` (already set; do not reintroduce Opus).
- **Eval gate:** zero false verifications and zero false misattributions, no exceptions.
- **Every test must be capable of failing** — a test that never queries the corpus it asserts about is not a test.
- **Materialised DB is built, never committed;** the committed DB is source-only, except `reference_display` (R-A3-6: written at build time, not derivable from other stored columns; see the Architecture note above). Runtime opens the materialised DB read-only.
- Run all commands from the worktree; never `cd` to the original repo root. Commits end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## Review Focus

- **A source-only committed DB opened directly (bypassing materialize) returns NULL norms → every query silently misses.** Pinned by Task 5's fixture and Task 4's "build output has NULL norms" assertion.
- **A materialize run that partially completes (e.g. FTS built, indexes not) ships a half-derived DB.** Pinned by Task 2's determinism + completeness assertions (no NULL norm; FTS row count == scorable rows; every expected index present).
- **Vercel's read-only runtime: a first-run derive passes locally and fails only on deploy.** Pinned by Task 6 making derivation a *build* step and asserting the runtime path is a full DB.
- **A new collection's citation number collides with a Qur'an surah:ayah reading (e.g. `Muslim 2:255`).** Pinned by Task 9's cross-kind and collection-governs tests.
- **An editorial-pointer / incipit / wholly-Qur'anic matn in a new edition returns a false EXACT.** Pinned by each per-source ingest task's audit list + the per-collection eval cases (Tasks 11+).

---

## Task 1: Sourcing spike — Tirmidhī and Nasāʾī (and final vet of Muslim / Abū Dāwūd / Ibn Mājah)

**This is a spike, not TDD.** Its output is a findings note that decides which collections ship and pins each one's raw URL + commit. No product code.

**Files:**
- Create: `docs/superpowers/research/2026-09-27-a3-source-vetting.md`

**Interfaces:**
- Produces: for each of the five collections, either `SHIP` with `{raw_url, commit_sha, edition_meta}` or `DEFER` with the reason. Consumed by every per-source ingest task (11+) and by the scope wording (Task 10).

- [ ] **Step 1: Locate candidate OpenITI files.** For each collection, search the OpenITI `0275AH` data repo for a `JK`-prefixed `ara1.completed` file:
  - Muslim: `0261Muslim/…JK…-ara1.completed`
  - Abū Dāwūd: `0275AbuDawudSijistani/…JK000142-ara1.completed`
  - Ibn Mājah: `0273IbnMaja/…JK…-ara1.completed`
  - Tirmidhī: search `0279Tirmidhi*` folders (**unverified — may not exist in clean form**)
  - Nasāʾī: search `0303NasaiAhmadIbnShucayb*` folders (**unverified**)

  Use raw GitHub over the network (this repo already fetches OpenITI in CI). If the network blocks it from this environment, record that and mark the affected collections `DEFER (unreachable here)` — do not fabricate URLs.

- [ ] **Step 2: Vet each candidate** against the seven-criterion bar from `docs/superpowers/research/2026-09-20-hadith-source-assessment.md`: complete `#META#` header, internally consistent named printed edition, `ara1.completed` stage, no unfilled placeholder metadata, not a raw Shamela scrape, matn present, mARkdown structural markers present. Record the edition (`040.EdEDITOR`, `043.EdPUBLISHER`, `045.EdYEAR`, `041.EdNUMBER`) from each file's own header.

- [ ] **Step 3: Record the decision table** in the findings note: one row per collection with `SHIP`/`DEFER`, the raw URL, the commit SHA (the `0275AH` HEAD at retrieval), and the edition metadata. This table is the contract the ingest tasks read.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/research/2026-09-27-a3-source-vetting.md
git commit -m "spike(a3): vet OpenITI sources for Muslim + the four Sunan"
```

---

## Task 2: `materialize()` — derive everything from source columns

**Files:**
- Create: `ingest/sanad_ingest/materialize.py`
- Test: `tests/ingest/test_materialize.py`

**Interfaces:**
- Consumes: `sanad.corpus.schema.SCHEMA_SQL`, `sanad.corpus.db.rebuild_fts(conn)`, `sanad.corpus.db.corpus_fingerprint(conn)`, `sanad.arabic.normalize.normalize(text, tier)`, `sanad.ingest`-side `openiti.full_text(primary, addenda)`, `build._reference_display` (moved here in Task 8 — until then, import from `build`).
- Produces: `materialize(src_path: str, out_path: str) -> dict` (returns `corpus_stats`); raises `MaterializeError` on any completeness failure.

- [ ] **Step 1: Write the failing test — materialize reproduces the committed DB's derived content**

```python
# tests/ingest/test_materialize.py
import sqlite3
from sanad.corpus import db
from sanad_ingest.materialize import materialize

COMMITTED = "data/sanad-quran.db"  # still full at this point in the plan

def _strip_to_source(full_path, src_path):
    """Copy only source columns/tables into a fresh file (simulates Task 4 output)."""
    import shutil; shutil.copy(full_path, src_path)
    conn = sqlite3.connect(src_path)
    conn.executescript("""
        DROP TABLE IF EXISTS records_fts;
        DROP TABLE IF EXISTS record_variants;
        UPDATE records SET norm_light=NULL, norm_standard=NULL,
                           norm_aggressive=NULL, text_ar_sha256=NULL,
                           reference_display=NULL;
    """)
    conn.commit(); conn.close()

def test_materialize_reproduces_derived_content(tmp_path):
    src = str(tmp_path / "src.db"); out = str(tmp_path / "out.db")
    _strip_to_source(COMMITTED, src)
    materialize(src, out)
    a = sqlite3.connect(COMMITTED); b = sqlite3.connect(out)
    # Every scorable record's norms match the committed original.
    rows_a = dict(a.execute("SELECT id, norm_standard FROM records").fetchall())
    rows_b = dict(b.execute("SELECT id, norm_standard FROM records").fetchall())
    assert rows_a == rows_b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/ingest/test_materialize.py::test_materialize_reproduces_derived_content -v`
Expected: FAIL with `ModuleNotFoundError: sanad_ingest.materialize`.

- [ ] **Step 3: Implement `materialize()`**

```python
# ingest/sanad_ingest/materialize.py
"""Derive all recomputable corpus data from a source-only DB. No network.

Given a DB whose `records` rows carry only source columns, produce a full DB:
norm_* columns, text_ar_sha256, reference_display, record_variants (the `full`
variant), records_fts, and indexes. Reuses the exact production derivation
code so the materialised DB is identical to what `build` used to emit inline.
"""
from __future__ import annotations
import hashlib, shutil, sqlite3
from sanad.arabic.normalize import normalize
from sanad.corpus import db
from .openiti import full_text
from .build import _reference_display  # moved into this module in Task 8

class MaterializeError(Exception):
    pass

def materialize(src_path: str, out_path: str) -> dict:
    shutil.copy(src_path, out_path)
    conn = sqlite3.connect(out_path)
    try:
        conn.executescript(db.DERIVED_SCHEMA_SQL)  # CREATE record_variants + indexes; added in Task 4
        _derive_records(conn)
        _derive_variants(conn)
        db.rebuild_fts(conn)
        _assert_complete(conn)
        conn.commit()
        return db.corpus_stats(conn)
    finally:
        conn.close()

def _derive_records(conn: sqlite3.Connection) -> None:
    for rid, text_ar, coll, hadith_no, surah, ayah in conn.execute(
        "SELECT id, text_ar, collection, hadith_no, surah, ayah FROM records"
    ).fetchall():
        conn.execute(
            "UPDATE records SET norm_light=?, norm_standard=?, norm_aggressive=?, "
            "text_ar_sha256=?, reference_display=? WHERE id=?",
            (normalize(text_ar, "light"), normalize(text_ar, "standard"),
             normalize(text_ar, "aggressive"),
             hashlib.sha256(text_ar.encode("utf-8")).hexdigest(),
             _reference_display(coll, hadith_no, surah, ayah), rid),
        )

def _derive_variants(conn: sqlite3.Connection) -> None:
    for rid, text_ar, addenda in conn.execute(
        "SELECT id, text_ar, addenda_ar FROM records WHERE addenda_ar IS NOT NULL"
    ).fetchall():
        full = full_text(text_ar, addenda)
        conn.execute(
            "INSERT INTO record_variants(record_id, variant, text_ar, "
            "norm_light, norm_standard, norm_aggressive) VALUES (?,?,?,?,?,?)",
            (rid, "full", full, normalize(full, "light"),
             normalize(full, "standard"), normalize(full, "aggressive")),
        )

def _assert_complete(conn: sqlite3.Connection) -> None:
    n = conn.execute(
        "SELECT COUNT(*) FROM records WHERE unscorable_reason IS NULL "
        "AND (norm_standard IS NULL OR reference_display IS NULL)"
    ).fetchone()[0]
    if n:
        raise MaterializeError(f"{n} scorable records left un-derived")
```

  (`_reference_display`'s exact current signature is `(collection, hadith_no, surah, ayah)` after Task 8; if Task 8 has not run yet, adapt the call to the current `build._reference_display` signature and fix the import in Task 8.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/ingest/test_materialize.py -v`
Expected: PASS.

- [ ] **Step 5: Add a determinism + completeness test**

```python
def test_materialize_is_deterministic(tmp_path):
    src = str(tmp_path / "src.db")
    _strip_to_source(COMMITTED, src)
    o1 = str(tmp_path / "o1.db"); o2 = str(tmp_path / "o2.db")
    materialize(src, o1); materialize(src, o2)
    import sqlite3
    f1 = db.corpus_fingerprint(sqlite3.connect(o1))
    f2 = db.corpus_fingerprint(sqlite3.connect(o2))
    assert f1 == f2

def test_materialize_rejects_incomplete(tmp_path):
    import sqlite3, pytest
    src = str(tmp_path / "src.db")
    _strip_to_source(COMMITTED, src)
    c = sqlite3.connect(src)
    c.execute("UPDATE records SET text_ar='' WHERE unscorable_reason IS NULL LIMIT 1")
    c.commit(); c.close()
    # An empty matn normalises to '' — still non-NULL, so this instead asserts
    # the happy path stays green; the NULL-guard is exercised by forcing a NULL:
```

  Adjust the third test to force a genuinely un-derivable row (set `text_ar=NULL` on one scorable row, expect `MaterializeError`). Run and confirm PASS.

- [ ] **Step 6: Commit**

```bash
git add ingest/sanad_ingest/materialize.py tests/ingest/test_materialize.py
git commit -m "feat(ingest): materialize() derives norms/variants/FTS/indexes, no network"
```

---

## Task 3: `sanad-ingest materialize` CLI subcommand

**Files:**
- Modify: `ingest/sanad_ingest/cli.py`
- Test: `tests/ingest/test_cli_materialize.py`

**Interfaces:**
- Consumes: `materialize.materialize(src, out)`.
- Produces: `sanad-ingest materialize --in <src.db> --out <full.db>` (exit 0 on success, prints stats).

- [ ] **Step 1: Write the failing test**

```python
# tests/ingest/test_cli_materialize.py
import subprocess, sqlite3, shutil
def test_cli_materialize(tmp_path):
    src = tmp_path / "src.db"; out = tmp_path / "out.db"
    # Build a source-only src via the strip helper reused from test_materialize
    from tests.ingest.test_materialize import _strip_to_source
    _strip_to_source("data/sanad-quran.db", str(src))
    r = subprocess.run(["sanad-ingest", "materialize", "--in", str(src),
                        "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert sqlite3.connect(str(out)).execute(
        "SELECT COUNT(*) FROM records WHERE norm_standard IS NOT NULL"
    ).fetchone()[0] > 0
```

- [ ] **Step 2: Run to confirm it fails** (`sanad-ingest: invalid choice: 'materialize'`).

- [ ] **Step 3: Add the subparser** mirroring the existing `build`/`embed` subcommands in `cli.py`:

```python
mat = sub.add_parser("materialize", help="derive norms/FTS/indexes from a source-only DB")
mat.add_argument("--in", dest="src", required=True)
mat.add_argument("--out", dest="out", required=True)
# in the dispatch:
elif args.cmd == "materialize":
    stats = materialize(args.src, args.out)
    print(f"materialized: {stats}")
```

- [ ] **Step 4: Run to confirm PASS.**
- [ ] **Step 5: Commit** (`feat(ingest): sanad-ingest materialize subcommand`).

---

## Task 4: `build` emits source-only; split the schema

**Files:**
- Modify: `ingest/sanad_ingest/build.py` (stop deriving inline; move integrity checks to materialize)
- Modify: `api/sanad/corpus/schema.py` (split `SCHEMA_SQL` into `SOURCE_SCHEMA_SQL` + `DERIVED_SCHEMA_SQL`)
- Modify: `api/sanad/corpus/db.py` (add `corpus_source_fingerprint`)
- Test: `tests/ingest/test_build.py` (update), `tests/ingest/test_real_corpus.py` (update)

**Interfaces:**
- Produces: `build_corpus(...)` writes a source-only DB (no `norm_*`, no `text_ar_sha256`, no `reference_display`, no `record_variants`, no FTS, no indexes). `db.DERIVED_SCHEMA_SQL` (record_variants + all `idx_*` + records_fts). `db.corpus_source_fingerprint(conn)` (hash over source tables/columns only).

- [ ] **Step 1: Write the failing test — build output is source-only**

```python
def test_build_output_is_source_only(tmp_path):
    from sanad_ingest.build import build_corpus
    out = str(tmp_path / "src.db")
    build_corpus(lockfile="ingest/corpus.lock.toml", out=out,
                 cache=".corpus-cache", noise_report=str(tmp_path/"n.md"))
    import sqlite3; c = sqlite3.connect(out)
    # Derived tables absent, norm columns NULL.
    assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='records_fts'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM records WHERE norm_standard IS NOT NULL").fetchone()[0] == 0
```

- [ ] **Step 2: Run to confirm it fails** (build still derives).

- [ ] **Step 3: Split the schema** in `schema.py`: keep `SCHEMA_SQL` as `SOURCE_SCHEMA_SQL || DERIVED_SCHEMA_SQL` for any consumer that wants the full schema, but have `build` create only `SOURCE_SCHEMA_SQL` (records with derived columns present but left NULL, no `record_variants`, no `records_fts`, no `idx_*`). Move `CREATE TABLE record_variants`, all `CREATE INDEX idx_*`, and the FTS `CREATE VIRTUAL TABLE` into `DERIVED_SCHEMA_SQL`.

- [ ] **Step 4: Remove inline derivation from `build`**: delete the `normalize(...)` calls in `_hadith_records`/quran passes, the `record_variants` insert, the `text_ar_sha256`/`reference_display` writes, and the final `db.rebuild_fts(conn)`. Move `_reject_wholly_quranic_representations` and the duplicate-`reference_display` rejection into `materialize` (they need norms/reference_display). Leave the noise report in `build`.

- [ ] **Step 5: Add `corpus_source_fingerprint`** in `db.py` — the existing `corpus_fingerprint` restricted to `sources`, `records` (source columns only), and `translations`.

- [ ] **Step 6: Update `test_real_corpus.py`** to read a materialised DB via the fixture (introduced in Task 5) rather than the committed source-only file directly. Update `test_build.py` expectations to source-only.

- [ ] **Step 7: Run `.venv/bin/python -m pytest tests/ingest -v`; confirm PASS.**
- [ ] **Step 8: Commit** (`refactor(ingest): build emits source-only DB; derivation moves to materialize`).

---

## Task 5: Pytest materialized-DB fixture; migrate the 9 DB-reading test files

**Files:**
- Create: `tests/conftest.py` addition (session fixture) + `tests/_corpus.py` (shared path constant)
- Modify: `tests/api/test_routes.py`, `tests/eval/test_cases.py`, `tests/eval/test_runner.py`, `tests/ingest/test_real_corpus.py`, `tests/verify/test_engine.py`, `tests/verify/test_extract.py`, `tests/api/test_ask_route.py`, `tests/corpus/test_db.py`

**Interfaces:**
- Produces: `tests._corpus.MATERIALIZED_DB` (a path string), materialised once per session from the committed source-only DB.

- [ ] **Step 1: Write the failing test**

```python
# tests/corpus/test_materialized_fixture.py
import sqlite3
from tests._corpus import MATERIALIZED_DB
def test_materialized_fixture_has_norms():
    n = sqlite3.connect(MATERIALIZED_DB).execute(
        "SELECT COUNT(*) FROM records WHERE norm_standard IS NOT NULL").fetchone()[0]
    assert n > 0
```

- [ ] **Step 2: Run to confirm it fails** (`ModuleNotFoundError: tests._corpus`).

- [ ] **Step 3: Implement the fixture.** In `tests/conftest.py`, a session-scoped autouse-free fixture (or module-import side effect) that runs `materialize("data/sanad-quran.db", <cached tmp>)` once and exposes the path; `tests/_corpus.py` builds it lazily and caches under `.corpus-cache/sanad-materialized.db`, rebuilding only if the source DB's mtime is newer.

- [ ] **Step 4: Migrate the 9 files** to import `MATERIALIZED_DB` instead of the literal `"data/sanad-quran.db"`. Set `SANAD_DB` env to it where the app is constructed in tests.

- [ ] **Step 5: Run the full suite `.venv/bin/python -m pytest -q`; confirm PASS.**
- [ ] **Step 6: Commit** (`test: materialized-DB session fixture; route DB tests through it`).

---

## Task 6: Dockerfile + Vercel build materialize step

**Files:**
- Modify: `Dockerfile`, `vercel.json` (and/or `app.py` bundle config)
- Test: `tests/deploy/test_materialize_wiring.py` (a static assertion the build config invokes materialize)

**Interfaces:**
- Produces: at image/bundle build time, a full DB at `$SANAD_DB`; the committed source-only DB is the input, never opened at runtime.

- [ ] **Step 1: Write the failing test** — assert the Dockerfile runs `sanad-ingest materialize` and sets `SANAD_DB` to the derived path, and that `vercel.json`'s build step does the same:

```python
def test_dockerfile_materializes():
    txt = open("Dockerfile").read()
    assert "sanad-ingest materialize" in txt
    assert "sanad-quran.db" in txt  # source input referenced
```

- [ ] **Step 2: Run to confirm it fails.**

- [ ] **Step 3: Edit the Dockerfile** — after `COPY data/sanad-quran.db`, add:

```dockerfile
RUN sanad-ingest materialize --in /app/data/sanad-quran.db --out /app/data/sanad-full.db
ENV SANAD_DB=/app/data/sanad-full.db
```

- [ ] **Step 4: Wire the Vercel build.** In `vercel.json`, extend the build to run materialize into the function bundle before seal (a Python build step that produces `data/sanad-full.db`, kept by `excludeFiles`), and ensure `SANAD_DB` resolves to it. Because Vercel's runtime is read-only, this MUST be a build step, not first-run.

- [ ] **Step 5: Run the wiring test + full suite; confirm PASS.** Note in the commit body that the live Vercel deploy cannot be verified from this machine and must be smoke-tested by the user.
- [ ] **Step 6: Commit** (`build: derive corpus at image/bundle build; runtime opens the full DB`).

---

## Task 7: De-bukhari-fy `openiti.py`

**Files:**
- Modify: `ingest/sanad_ingest/openiti.py`
- Create: `ingest/sanad_ingest/audit_lists.py` (per-collection `_NEVER_CUT` / `_UNSCORABLE`, keyed by collection)
- Test: `tests/ingest/test_openiti.py` (update)

**Interfaces:**
- Produces: `parse_openiti(raw, *, collection: str, max_addendum: int, attribution_window: int, never_cut, unscorable)` — record IDs become `hadith:{collection}:{n}{suffix}`; the tuning scalars and audit lists arrive as parameters.

- [ ] **Step 1: Write the failing test** — parsing with `collection="muslim"` yields IDs prefixed `hadith:muslim:` and honours a passed audit list.
- [ ] **Step 2: Run to confirm it fails.**
- [ ] **Step 3: Parameterise** the hardcoded `"bukhari"` at the `flush()` ID site and lift `_MAX_ADDENDUM`/`_ATTRIBUTION_WINDOW` and the two audit lists to parameters, defaulting to the Bukhari values in `audit_lists.py` so the existing Bukhari build is unchanged.
- [ ] **Step 4: Run the Bukhari parse test + new test; confirm PASS** (Bukhari output byte-identical).
- [ ] **Step 5: Commit** (`refactor(ingest): openiti parser takes per-source collection + tuning`).

---

## Task 8: De-bukhari-fy `build.py`

**Files:**
- Modify: `ingest/sanad_ingest/build.py`
- Test: `tests/ingest/test_build.py` (update)

**Interfaces:**
- Produces: `_hadith_records` reads `collection`/`numbering_scheme` from the `LockedSource`; `_reference_display(collection, hadith_no, surah, ayah)` maps each collection to its display title.

- [ ] **Step 1: Write the failing test** — `_reference_display("muslim", "1", None, None) == "Ṣaḥīḥ Muslim 1"` and the four Sunan titles.
- [ ] **Step 2: Run to confirm it fails.**
- [ ] **Step 3: Implement** the title map (`bukhari→Ṣaḥīḥ al-Bukhārī`, `muslim→Ṣaḥīḥ Muslim`, `abudawud→Sunan Abī Dāwūd`, `tirmidhi→Jāmiʿ at-Tirmidhī`, `nasai→Sunan an-Nasāʾī`, `ibnmajah→Sunan Ibn Mājah`), transliteration matching how surah names render (confirm against `surah_name_en` values). Read `collection`/`numbering_scheme` from config.
- [ ] **Step 4: Run; confirm PASS** (Bukhari display unchanged).
- [ ] **Step 5: Commit** (`refactor(ingest): collection/numbering/display from source config`).

---

## Task 9: Six-collection citation grammar

**Files:**
- Modify: `api/sanad/verify/references.py`
- Test: `tests/verify/test_references.py` (update)

**Interfaces:**
- Produces: `_COLLECTIONS`/`_COLLECTIONS_AR`/`_HADITH_CITE` recognise all six names + aliases (Latin + Arabic); `_resolve_collection` returns the canonical id.

- [ ] **Step 1: Write the failing tests** — `nearest_reference("Muslim 1")` → `HadithReference("muslim", "1", ...)`; `"Sunan Abi Dawud 100"` → `abudawud`; Arabic `صحيح مسلم ١` resolves; an āyah cited `Tirmidhi 1` → cross-kind `WRONG_REFERENCE`; bare `Nasai` does not resolve; `Muslim 2:255` reads as collection-governed (kitāb 2, hadith 255), not surah:ayah.
- [ ] **Step 2: Run to confirm they fail.**
- [ ] **Step 3: Extend** the collection tables and `_HADITH_CITE` alternation with the five new names + aliases in both scripts. Keep the cross-kind check and "bare collection name doesn't resolve" rule intact.
- [ ] **Step 4: Run `tests/verify` + confirm PASS.**
- [ ] **Step 5: Commit** (`feat(verify): six-collection citation grammar`).

---

## Task 10: Corpus scope derived from shipped sources

**Files:**
- Modify: `api/sanad/corpus/scope.py`, and its consumers `verify/claims.py`, `agents/expand.py`, `agents/select.py`
- Test: `tests/corpus/test_scope.py`, plus the four consumer tests that pin the literal
- Frontend copy: `web/src/screens/Ask.tsx`, `web/src/screens/Verify.tsx` (header/caveat strings) + their tests

**Interfaces:**
- Produces: `corpus_scope(conn) -> str` building the caveat from the distinct hadith `collection` titles present in `sources`/`records`; all four backend consumers call it.

- [ ] **Step 1: Write the failing test** — with only Bukhari present, `corpus_scope(conn)` contains "the Qur'an and Ṣaḥīḥ al-Bukhārī" and the "absence … does not establish fabrication" clause; with Muslim added it lists both and drops "Muslim" from the "does not contain" tail.
- [ ] **Step 2: Run to confirm it fails.**
- [ ] **Step 3: Implement** `corpus_scope(conn)` and replace the four hardcoded literals with a call to it (computed once at startup, stored on `app.state`). Keep the reverent transform on any prose. Update the four consumer tests and the two web copy tests. Reverent-naming applies to the new prose.
- [ ] **Step 4: Run full backend + `web` suites; confirm PASS.**
- [ ] **Step 5: Commit** (`feat: corpus-scope caveat derived from shipped sources`).

---

## Tasks 11–15: Per-source ingest (one per `SHIP` collection from Task 1)

Repeat this task once per collection Task 1 marked `SHIP` (Muslim, Abū Dāwūd, Ibn Mājah, and Tirmidhī / Nasāʾī if they vetted). Each is its own reviewer gate.

**Files (per collection `<coll>`):**
- Modify: `ingest/corpus.lock.toml` (one `[[source]]`)
- Modify: `ingest/sanad_ingest/audit_lists.py` (this collection's `_NEVER_CUT`/`_UNSCORABLE`)
- Modify: `docs/SOURCES.md` (this collection's PD basis)
- Test: `tests/ingest/test_real_corpus.py` (this collection's pinned counts)
- Eval: `eval/cases/hadith.yaml` (this collection's adversarial cases)

**Interfaces:**
- Consumes: Task 1's `{raw_url, commit_sha}` for `<coll>`; the generalised parser (Task 7) and builder (Task 8).
- Produces: `expected_records`, `content_sha256`, `commit` measured and pinned; a per-collection eval block.

- [ ] **Step 1: Add the lockfile entry** with `format="openiti-markdown"`, `license_id="public-domain"`, `collection`, `numbering_scheme`, `raw_url`+`commit` from Task 1, and `content_sha256`/`expected_records` left as build-measured placeholders (`content_sha256 = ""`, `expected_records = 0`).

- [ ] **Step 2: First measured build.** Run `sanad-ingest build --lockfile ingest/corpus.lock.toml --out /tmp/a3.db --cache .corpus-cache --noise-report /tmp/noise-<coll>.md`. It fetches, computes the file's `content_sha256`, and reports the parsed record count. **Record both.** Pin them into the lockfile (`content_sha256`, `expected_records`). Re-run build to confirm the hash/count now match and the build is green.

- [ ] **Step 3: Build the audit lists from the noise report.** Review `/tmp/noise-<coll>.md` and scan for the three hazards, each sha256-pinned:
  - editorial pointers / incipits (e.g. «بهذا», «مثله», «نحوه») that would score a false EXACT → add to `_UNSCORABLE` ([[sanad-editorial-pointer-false-exact]]);
  - secondary narrations appended in the matn → verify `_split_secondary` cut correctly; add `_NEVER_CUT` exceptions where it over-cuts ([[sanad-hadith-secondary-narrations]]);
  - wholly-Qur'anic matns from tafsīr chapters → confirm `_reject_wholly_quranic_representations` catches them ([[sanad-hadith-quranic-matn-hazard]]).
  Each list entry pins the matn sha256 so the build fails if the text drifts.

- [ ] **Step 4: Pin the counts test.** In `test_real_corpus.py`, assert this collection's exact record count and three spot-checked matns read byte-exact from the materialised DB (verify-don't-assert: the test must query the corpus, not a fixture literal).

- [ ] **Step 5: Add the per-collection eval cases** to `hadith.yaml` (the five per-collection cases from spec §8): most-quoted bare matn (must verify), wrong-number (`WRONG_REFERENCE`), fabricated (`NOT_FOUND`), editorial-pointer (no false EXACT), wholly-Qur'anic (not scored as āyah).

- [ ] **Step 6: Run** `.venv/bin/python -m pytest tests/ingest tests/eval -q` and the eval gate; confirm zero false verifications.

- [ ] **Step 7: Write the PD basis** for this collection in `docs/SOURCES.md` (author death date; work's own PD status; not an OpenITI licence grant; markup discarded).

- [ ] **Step 8: Commit** (`feat(corpus): ingest <collection> (N records, measured & pinned)`).

---

## Task 16: Corpus-wide eval + regeneration + final gate

**Files:**
- Modify: `eval/cases/hadith.yaml` (the two corpus-wide cases), `README.md` (committed DB SHA-256), `.github/workflows/ci.yml` (fingerprint check)
- Rebuild: `data/sanad-quran.db` (source-only, committed)

**Interfaces:**
- Consumes: all shipped collections.

- [ ] **Step 1: Add the two corpus-wide eval cases** (spec §8): a hadith authentic in one shipped collection but absent from the others → `NOT_FOUND` with the reworded caveat (tested not to read as accusation); an āyah cited as a hadith → `WRONG_REFERENCE`.

- [ ] **Step 2: Rebuild and commit the source-only DB.** Run the full `sanad-ingest build` to regenerate `data/sanad-quran.db` (now source-only, all collections). Update the README's committed SHA-256 to the new file's.

- [ ] **Step 3: Update CI** (`.github/workflows/ci.yml`): the reproducibility check compares `corpus_source_fingerprint` of committed vs a fresh source-only rebuild, and asserts `materialize` determinism (fingerprint of two materialize runs equal).

- [ ] **Step 4: Run every gate** — `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check api ingest eval`, `cd web && npx vitest run && npx tsc --noEmit && npm run build`, and both eval gates. All green, zero false verifications.

- [ ] **Step 5: Commit** (`feat(corpus): Stage A3 — <N> collections live; source-only DB + build-time materialize`).

---

## Self-Review

**Spec coverage:** §4 build split → Tasks 2–6; §5 de-bukhari-fy → Tasks 7–8; §6 sources/licensing/ingest → Tasks 1, 11–15; §7 citation/scope/frontend → Tasks 9–10; §8 eval → Tasks 11–16; §10 global constraints → header. No gaps.

**Placeholder scan:** the only unfilled values are `content_sha256`/`expected_records`, which the spec (§12) and Global Constraints require to be *measured at build, then pinned* — Task 11 Step 2 measures and pins them. This is the project's contract, not a plan placeholder.

**Type consistency:** `materialize(src, out)`, `corpus_scope(conn)`, `corpus_source_fingerprint(conn)`, `_reference_display(collection, hadith_no, surah, ayah)`, `parse_openiti(..., collection=...)` are used consistently across tasks.

**Review Focus:** the five failure modes are each pinned to an owning task (see the Review Focus section).
