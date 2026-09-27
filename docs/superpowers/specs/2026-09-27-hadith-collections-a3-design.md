# Sanad Stage A3 — Five more hadith collections

**Date:** 2026-09-27
**Status:** approved (design), pending implementation plan
**Builds on:** `docs/superpowers/specs/2026-09-22-hadith-corpus-design.md` (Stage A2,
Bukhari) — this spec extends that machinery to five further collections
**Depends on:** Stage A, A2, C, B (all shipped)

## 1. What we are building

Ṣaḥīḥ Muslim and the four Sunan — Abū Dāwūd, al-Tirmidhī, an-Nasāʾī, Ibn
Mājah — ingested into the existing corpus on exactly the terms Bukhari was: matn
matched, isnād shown, collection named, absence stated honestly. Every
collection that meets the per-file vetting bar ships; any that cannot be sourced
to that bar is deferred and named in the corpus caveat.

The verification engine does not change. The A2 spec already made the corpus
multi-collection in principle — `records` carries `collection`, matching is
matn-only and corpus-agnostic, citation parsing is a dispatched grammar. What
changes is: (a) the build is split so the committed database stays under
GitHub's 100 MB per-file limit; (b) the handful of `bukhari`-hardcoded points
are parameterised; (c) five sources are vetted, ingested, and evaluated; (d) the
corpus-scope copy stops being a hand-maintained literal.

## 2. Non-goals

- **No gradings.** Unchanged from A2 §2/§9.3: Sanad confirms wording, grades
  nothing. The `gradings` table stays empty for all six collections. al-Tirmidhī's
  own classical gradings are public domain but are **out of scope for this
  stage** — a decision taken deliberately (2026-09-27) to keep one consistent
  "confirms wording, does not grade" story across the whole corpus. They may be
  a later stage.
- **No hadith translations bundled.** Unchanged from A2 §2. English renderings
  of these collections are modern (copyright) or of uncertain provenance. A
  model-generated, clearly-labelled English rendering in Ask is a **separate
  follow-up spec**, not part of A3.
- **No isnād analysis, no re-OCR, no text correction.** Unchanged from A2.
- **No conversational Ask.** Threaded follow-up in Ask is a separate follow-up
  spec (it makes the pipeline stateful and needs new cross-turn grounding
  guards).

## 3. Decisions taken

| Question | Decision |
|---|---|
| Which collections | Muslim + the four Sunan; ship every one that vets to the Bukhari bar |
| Two unsourced texts | Tirmidhī & Nasāʾī get a sourcing spike first (Task 1); ship if they pass, defer with an honest caveat if not |
| Gradings | None, for any collection (§2) |
| 100 MB limit | Commit a **source-only** DB; derive norms/FTS/indexes at build time and in tests, network-free (§4) |
| Legal basis | Each work's own public-domain status, per author death date; **not** an OpenITI licence grant ([[sanad-licensing-basis-pattern]]) |
| Numbering | Each collection displays in its edition's own numbering; out-of-range citations say so, never silently re-resolve |
| Scope copy | Derived from the shipped `sources`, not hand-maintained literals (§7) |

## 4. Build architecture: source-only DB + materialize

**The problem.** The committed `data/sanad-quran.db` is 58 MB, and more than half
is derived: the three `norm_*` columns, `text_ar_sha256`, `reference_display`,
`record_variants`, `records_fts` + its five shadow tables (~15 MB), and the
B-tree indexes (~14 MB) are all recomputable from the source columns with **no
network**. Six collections would push a full DB past ~200 MB — over GitHub's
per-file ceiling.

**The split.** The build gains a derivation boundary:

- **`sanad-ingest build`** (network, from the lockfile) writes the **source-only**
  committed DB. It populates only source columns — `text_ar`, `isnad_ar`,
  `addenda_ar`, `kind`, `collection`, `book_no`, `chapter_ar`, `hadith_no`,
  `numbering_scheme`, `unscorable_reason`, `surah`/`ayah`/`surah_name_*`,
  `bismillah` — plus the `sources` and `translations` tables. It does **not**
  compute `norm_*`, `text_ar_sha256`, `reference_display`, `record_variants`,
  `records_fts`, or indexes.
- **`sanad-ingest materialize --in <source.db> --out <full.db>`** (no network)
  derives everything from the source columns: the three `norm_*` columns,
  `text_ar_sha256`, `reference_display`, the rebuilt `record_variants` (the
  `full` variant = primary + addenda rejoined via `openiti.full_text`),
  `records_fts` + shadow tables, and all indexes. It reuses the existing
  `sanad.arabic.normalize.normalize`, `db.rebuild_fts`, and the `CREATE INDEX`
  statements in `SCHEMA_SQL`.

**Integrity checks move to `materialize`.** The two checks that need norms — the
duplicate-`reference_display` rejection and the wholly-Qur'anic-matn guard
(`_reject_wholly_quranic_representations`, which compares normalised hadith to
normalised āyāt) — run in `materialize`. It also asserts **no `norm_*` is left
NULL** on any scorable record: a materialised DB with a NULL norm is a build
failure, not a silent runtime miss.

**Where `materialize` runs:**

- **Dockerfile:** after `COPY data/sanad-quran.db`, a build step runs
  `materialize` to a runtime path, and `SANAD_DB` points at the full DB. No
  network, hermetic.
- **Vercel build:** the same derivation before the function bundle is sealed, so
  the serverless function ships the full DB.
- **Tests:** a **session-scoped pytest fixture** runs `materialize` once from the
  committed source DB into a cached temp path. The nine test files that hardcode
  `data/sanad-quran.db` import **one shared "materialized DB path"** the fixture
  provides, instead of the literal.

**CI reproducibility.** The existing check rebuilds from the lockfile over the
network and compares fingerprints. It is adjusted so: (a) the committed
source-only DB's *source* fingerprint equals a fresh source-only rebuild's; and
(b) `materialize` is deterministic — `materialize(source)` byte-content is
reproducible across two runs (fingerprint over the derived tables). The README's
committed SHA-256 is updated to the source-only DB's.

**Expected sizes.** Source-only today ≈ 13 MB; with six collections ≈ 40–50 MB —
comfortably under 100 MB, and it keeps headroom as coverage grows. This also
matches the project's existing principle that derived data is not committed (the
Voyage vectors DB is already a non-committed sidecar).

## 5. Pipeline generalisation (de-bukhari-fy)

Every `bukhari`-specific point identified in the pipeline becomes per-source
configuration. Nothing about the parsing *algorithm* changes.

**`ingest/sanad_ingest/openiti.py`:**

- Record-ID prefix `hadith:bukhari:<n>` → `hadith:<collection>:<n>` (the
  `bukhari` literal at the `flush()` site is parameterised).
- The per-edition tuning constants `_MAX_ADDENDUM` and `_ATTRIBUTION_WINDOW`,
  and the sha256-pinned audit lists `_NEVER_CUT` and `_UNSCORABLE`, become
  **per-source**. The file's own comments already warn these MUST be re-measured
  per edition. Scalar constants, the display title, and the numbering scheme are
  carried in the lockfile `[[source]]`; the sha256-pinned audit lists stay in
  code, keyed by collection, because they are hand-audits of specific matns.

**`ingest/sanad_ingest/build.py`:**

- `_hadith_records` reads `collection` and `numbering_scheme` from the source
  config instead of hardcoding `"bukhari"` / `"bugha-1987"`.
- `_reference_display` maps each collection to its title: `Ṣaḥīḥ Muslim`, `Sunan
  Abī Dāwūd`, `Jāmiʿ at-Tirmidhī`, `Sunan an-Nasāʾī`, `Sunan Ibn Mājah`
  (transliteration matching how the surah names already render — decided at
  implementation). The duplicate-`reference_display` rejection is unchanged;
  display strings already include the collection name, so they stay globally
  unique.

## 6. Sources, licensing, per-edition ingest

**Task 1 is a sourcing spike.** Locate and vet OpenITI "JK" files for **Tirmidhī
and Nasāʾī** against the same seven-criterion bar Bukhari passed: complete and
internally consistent `#META#` provenance, a named printed edition, the
`ara1.completed` stage, and no placeholder / raw-Shamela-scrape metadata. Muslim,
Abū Dāwūd, and Ibn Mājah have candidate JK files from the 2026-09-20 assessment
but still receive a final per-file vet. The spike's output is the definitive list
of which collections ship in A3.

**Per vetted source:**

- A `[[source]]` lockfile entry: pinned `commit`, `content_sha256` and
  `expected_records` **measured at first build then pinned** (never guessed),
  `format = "openiti-markdown"`, `license_id = "public-domain"`, plus the new
  config fields (`collection`, `numbering_scheme`, display title, per-edition
  parser scalars).
- The legal basis written into `docs/SOURCES.md`: each author died pre-1000 CE
  (Muslim d. 875, Abū Dāwūd d. 889, al-Tirmidhī d. 892, an-Nasāʾī d. 915, Ibn
  Mājah d. 887), so matn and isnād are public domain without qualification. The
  basis is the **work's own PD status, not an OpenITI licence grant** — OpenITI's
  data repos carry no LICENSE file; markup is parsed and discarded so only
  PD text is stored; attribution is credit, not compliance
  ([[sanad-licensing-basis-pattern]]).
- **Re-measured parser constants** and a **hand-built audit list** for that
  edition, derived from its own noise report and a pointer/incipit scan. The
  three recorded hazards recur per collection and each is checked per source:
  editorial pointers producing false EXACT matches
  ([[sanad-editorial-pointer-false-exact]]); secondary narrations hidden inside
  the matn ([[sanad-hadith-secondary-narrations]]); a matn that is wholly Qur'an,
  common in tafsīr chapters ([[sanad-hadith-quranic-matn-hazard]]).

**Numbering.** Each collection displays in its edition's own numbering. A
citation whose number exceeds that collection's corpus maximum is out of range
and the verdict says so — it never silently falls back to another reading (A2
§8). The known gap — OpenITI edition numbering may differ from the sunnah.com /
USC-MSA numbering many users type — is documented as a limitation, not papered
over.

**Character integrity.** Arabic is stored byte-for-byte as fetched;
`content_sha256` pins the raw file and the build refuses on drift
([[sanad-character-transit-defect]]).

## 7. Citation, scope, product surface

**`api/sanad/verify/references.py`:** extend `_COLLECTIONS`, `_COLLECTIONS_AR`,
and `_HADITH_CITE` to recognise all six collections and their aliases, in Latin
and Arabic script (e.g. `Muslim`, `Abu Dawud`/`Abī Dāwūd`,
`Tirmidhi`/`Tirmidhī`/`Jami`, `Nasa'i`/`Nasāʾī`, `Ibn Majah`/`Mājah`). The
cross-kind check (an āyah cited as `Muslim 1` → `WRONG_REFERENCE`) and the "bare
collection name does not resolve" rule are unchanged.

**Scope drift fix.** The A2 spec left four hand-maintained "Qur'an and Sahih
al-Bukhari" literals (`corpus/scope.py`, `verify/claims.py`, `agents/expand.py`,
`agents/select.py`). A3 replaces them with **one scope value derived from the
shipped `sources`** at startup, so adding or deferring a collection updates a
single place and the four surfaces cannot drift apart. The caveat keeps its
meaning: absence from this corpus does not establish fabrication.

**Reverent naming.** Any new or changed English prose obeys the standing rule —
"Allah" not "God", honorifics after prophets — via the existing `reverent`
transform, applied to prose only, never to canonical corpus text
([[sanad-reverent-naming-policy]]).

**Frontend.** `EvidenceCard` and the Ask screen already render `collection`,
`isnad_ar`, and `reference_display` generically, and the "does not grade" line
already fires on any hadith record — so only the caveat and header copy change
(the Ask header's "the Qur'an and Sahih al-Bukhari" and the Verify caveat). The
provenance panel picks up the new sources automatically.

## 8. Evaluation

`eval/cases/hadith.yaml` gains adversarial cases **per shipped collection**,
mirroring the Bukhari eight, under the same CI gate — **zero false
verifications, no exceptions**. For each collection:

1. A most-quoted matn, **quoted bare** — must verify (the storage regression
   canary: fails if full text ever lands in `text_ar`).
2. A real hadith with a **wrong number** — `WRONG_REFERENCE`, not `EXACT`.
3. A **fabricated** hadith in circulation — `NOT_FOUND`, no near-match reach.
4. An **editorial-pointer / incipit** matn — must not return a false `EXACT`
   ([[sanad-editorial-pointer-false-exact]]).
5. A **wholly-Qur'anic** matn from a tafsīr chapter — must not score as an āyah
   ([[sanad-hadith-quranic-matn-hazard]]).

Plus corpus-wide:

6. A hadith authentic in one shipped collection but **absent from the others** —
   `NOT_FOUND` with the reworded caveat, tested so it does not read as an
   accusation.
7. An **āyah cited as a hadith** (`al-Tirmidhī 1`) — `WRONG_REFERENCE` via the
   cross-kind check.

`tests/ingest/test_real_corpus.py` count assertions are updated to the
per-collection measured values, pinned after the first build. Every test must be
capable of failing ([[sanad-verify-dont-assert]]) — a test that passes against a
corpus it never queries is not a test.

## 9. Files

```
ingest/
  corpus.lock.toml                    + up to 5 [[source]] entries; new per-source config fields
  sanad_ingest/openiti.py             collection-parameterised ID prefix; per-source constants + audit lists
  sanad_ingest/build.py               source-only output; collection/numbering/display from config
  sanad_ingest/materialize.py         NEW — derive norms/variants/FTS/indexes + integrity checks, no network
  sanad_ingest/cli.py                 + `materialize` subcommand
api/sanad/
  verify/references.py                six-collection citation grammar
  corpus/scope.py                     scope derived from shipped sources
  verify/claims.py, agents/expand.py, agents/select.py   consume the derived scope
web/src/
  screens/Ask.tsx, screens/Verify.tsx (or components) copy updates only
Dockerfile                            + materialize step; SANAD_DB → full DB
vercel.json / build                   + materialize step before bundle seal
.github/workflows/ci.yml              source fingerprint + materialize-determinism checks
tests/                                shared materialized-DB fixture; 9 files import it; real-corpus counts
eval/cases/hadith.yaml                per-collection adversarial cases
docs/SOURCES.md                       per-source PD basis
data/sanad-quran.db                   rebuilt source-only (committed); README SHA-256 updated
```

## 10. Global constraints

Carried into every task's requirements:

- **No gradings**, any collection (§2).
- **Byte-exact Arabic**, sha256-pinned; no silent correction
  ([[sanad-character-transit-defect]]).
- **Anti-fabrication display contract:** Arabic shown only from server `record`
  objects; English is model/app prose. The `reverent` transform runs on prose
  only ([[sanad-reverent-naming-policy]]).
- **Licensing basis recorded per source** — the *why*, not just the source
  ([[sanad-licensing-basis-pattern]]).
- **Every test must be able to fail** ([[sanad-verify-dont-assert]]).
- **Ask model:** `claude-sonnet-4-6` (the deterministic pipeline carries the
  grounding and guards, so Opus is not required for the model stages).

## 11. Risks

| Risk | Mitigation |
|---|---|
| Full text stored in `text_ar`, breaking short-quote matching | Eval case 1 per collection is the most-quoted bare matn |
| A collection cannot be sourced to the vetting bar | Task 1 spike decides; ship what passes, defer the rest, name it in the caveat |
| Committed DB crosses 100 MB | Source-only commit + build-time derivation (§4); measured sizes leave headroom |
| Materialised DB has a NULL norm (silent miss) | `materialize` asserts no NULL norm on scorable records; build fails otherwise |
| Edition numbering ≠ the numbering users type | Documented limitation; out-of-range citations say so, never re-resolve |
| Scope literals drift across four files | Scope derived from shipped sources; one source of truth (§7) |
| Per-edition parser constants copied from Bukhari | Each edition re-measures constants and rebuilds its audit list (§6) |
| Cheaper model degrades a model stage | Guards and grounding are deterministic and unchanged; eval gate (zero false verifications) applies to the full pipeline |

## 12. Open items

1. **`content_sha256`, `commit`, `expected_records`** per source — measured at
   first build, then pinned. Not guessed here.
2. **Tirmidhī / Nasāʾī availability** — resolved by the Task 1 spike; A3 ships
   the collections that pass.
3. **`reference_display` transliteration** — full diacritics vs plain, decided at
   implementation against how surah names already render (cosmetic).
