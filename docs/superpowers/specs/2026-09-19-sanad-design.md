# Sanad — design spec

**Date:** 2026-09-19
**Status:** approved, pending implementation plan
**Supersedes:** the Phase 1 sketch in `docs/ROADMAP.md`

## 1. What we are building

Sanad turns the current static prototype into a running service that verifies
Islamic textual claims against a licensed, checksummed corpus.

Two modes, deliberately separate:

- **Verify** — paste any text (from a chatbot, a book, a sermon) and Sanad
  reports which quotations are in the corpus verbatim, which are near-misses,
  which carry the wrong reference, and which are not there at all. Fully
  deterministic. No model runs. No API key needed.
- **Ask** — a question goes through a multi-stage pipeline in which Claude
  generates, deterministic code verifies, and a second Claude instance audits.
  Output is published only if it survives all stages.

The product claim is narrow and defensible: *Sanad does not know whether a
statement about Islam is true. It knows whether a quotation is real, where it
came from, and whether a conclusion outruns its evidence.*

## 2. Non-goals

Carried forward from `docs/ROADMAP.md`, unchanged:

- Autonomous fatwa generation.
- Silent correction of a Qur'an or Hadith quotation. Sanad reports a
  discrepancy; it never rewrites the user's text.
- Unlicensed scraping.
- Training on real user conversations.

Added here:

- No isnad/rijal authenticity reasoning in v1. Narrator-chain evaluation is a
  scholarly discipline, not a string-matching problem, and faking it would be
  worse than omitting it.
- No claim that an absent quotation is fabricated. Absence from *this* corpus
  is absence from this corpus. The UI must say that.

## 3. Decisions already taken

| Question | Decision |
|---|---|
| Scope | Real backend, real corpus, deployed service |
| Qur'an text | Tanzil, verbatim, CC BY 3.0, attribution preserved |
| Qur'an translation | Public-domain edition only |
| Hadith | Public-domain Arabic matn bundled; translations linked, not bundled |
| Modern gradings | Not bundled — out of copyright scope |
| Architecture | Single service, corpus as one checksummed SQLite file |
| Backend | Python 3.10+, FastAPI |
| Frontend | React + Vite, motion-driven |
| LLM | Claude, in Ask mode only; Verify mode has zero model dependency |
| Verifier | Deterministic code, never a model |

## 4. Architecture

```
                    ┌─────────────────────────────┐
  sanad-ingest ───► │  sanad.db  (SQLite + FTS5)  │ ◄─── hash-verified at boot
   (offline CLI)    │  records · sources · fts    │
                    │  translations · embeddings  │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │        FastAPI service       │
                    │                              │
   POST /api/verify │  ┌────────────────────────┐  │
   ───────────────► │  │ verify engine (pure)   │  │  no model, no key
                    │  └────────────────────────┘  │
                    │                              │
   POST /api/ask    │  ┌────────────────────────┐  │
   ───────────────► │  │ pipeline: 6 stages     │  │  SSE stream
   (SSE)            │  │ 2 of them call Claude  │  │
                    │  └────────────────────────┘  │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │   React + Vite frontend      │
                    └─────────────────────────────┘
```

One process. One database file. The frontend is a static build that can be
served by the API or by any CDN.

## 5. Corpus and provenance

### 5.1 The lockfile is the contract

`ingest/corpus.lock.toml` is committed and is the authoritative record of what
the corpus contains:

```toml
[[source]]
id            = "tanzil-uthmani-1.1"
kind          = "quran-arabic"
title         = "Tanzil Qur'an Text (Uthmani)"
url           = "https://tanzil.net/download/"
edition       = "1.1"
license       = "CC-BY-3.0"
license_url   = "https://tanzil.net/docs/text_license"
attribution   = """Qur'an text from the Tanzil project — https://tanzil.net
Copyright (C) 2007-2024 Tanzil Project. Licensed under CC BY 3.0.
Verbatim copy; no modifications."""
upstream_sha256 = "<pinned>"
modifications = "none"
```

`sanad-ingest` refuses to build if a downloaded file's SHA-256 does not match
the lockfile. A corpus that cannot be reproduced is not shipped.

### 5.2 Licence handling per layer

- **Qur'an Arabic.** Tanzil requires verbatim copying, attribution, a link to
  tanzil.net, and preservation of the notice. The canonical `text_ar` column is
  never modified — every normalization is written to a *separate* column. The
  attribution string is stored in the database and rendered on every evidence
  card that draws on it.
- **Qur'an translation.** Public domain only. Pickthall (d. 1936) is clean
  worldwide under life+70. Yusuf Ali (d. 1953) is clean in life+70
  jurisdictions as of 2024 but not uniformly; prefer Pickthall. **Saheeh
  International is not permissively licensed and must not be bundled.**

  **Tanzil's `en.pickthall` is the chosen source.** An earlier revision of this
  spec ruled Tanzil out for translations. That was wrong, and the correction
  matters enough to record why.

  The earlier reading stopped at one sentence on tanzil.net/trans — "The
  translations provided at this page are for non-commercial purposes only." The
  full terms and the downloaded file say something different:

  - The per-file footer on `en.pickthall` is **metadata only**: name,
    translator, language, id, last-update, source. It asserts no copyright, no
    licence, and no reserved rights. Tanzil's Arabic text, by contrast, ships a
    28-line block asserting CC BY 3.0 and demanding it not be removed. Tanzil
    asserts rights where it holds them; it asserts none here.
  - The terms direct a commercial user to "obtain necessary permission from
    **the translator or the publisher**" — pointing away from Tanzil, which is
    a disclaimer of ownership rather than an assertion of it.
  - "Redistributing the following **list** is not allowed" governs the curated
    table of translations (a collection right). Shipping one translation's text
    does not engage it.
  - The link-back requirement applies above three translations. We bundle one.

  Pickthall died in 1936. The work has been public domain since 2007 in
  life+70 jurisdictions, and since 1 January 2026 in the US (published 1930,
  95 years from publication). A faithful transcription of a public-domain text
  attracts no new copyright, so Tanzil's digitisation adds no protectable
  layer. There is no rights holder left to ask.

  **Our legal basis is Pickthall's public-domain status, not a grant from
  Tanzil.** This distinction is load-bearing: Sanad's code is MIT, so a
  downstream user could act commercially, which would cross Tanzil's
  non-commercial line if that line were what we relied on. It is not. Record
  the basis in `corpus.lock.toml`, not merely the URL.

  Compliance actions, all required:
  1. Link to https://tanzil.net/trans/ in the README and in the UI wherever a
     translation is displayed.
  2. Store the file's metadata footer verbatim in `sources.attribution`, as we
     do for the Arabic.
  3. Never redistribute Tanzil's translations list.
  4. Surface Tanzil's accuracy disclaimer — "No translation of Quran can be a
     hundred percent accurate, nor can it be used as a replacement of the
     Quran text" — next to every rendered translation. This is not boilerplate;
     it is the same claim Sanad makes about itself, and hiding it in a licence
     file would contradict the product.

  Not bundled, still in copyright: Saheeh International, Hilali & Khan,
  Maududi, Arberry (d. 1969), Mubarakpuri, Qarai, Daryabadi. `en.itani`
  (Talal Itani, modern English) is a plausible second candidate but its
  public-domain dedication is unverified; do not add it on memory alone.

  Per §7 the translation is display-only — verification is Arabic-against-Arabic
  and never reads it. Format is identical to the Arabic export
  (`surah|ayah|text`), so `parse_tanzil` handles it unchanged.
- **Hadith Arabic matn.** The classical text is public domain. The copyright
  risk sits in modern critical editions, vowelling, apparatus, and publisher
  numbering. Ingest must record which digital edition was used and what its
  provenance is. *This source is not yet chosen — see §13.*
- **Hadith translations and modern gradings.** Not bundled. Rendered as
  outbound links. Classical gradings stated by the compiler themselves (e.g.
  al-Tirmidhī's own labels) are part of the matn and may be included, flagged
  `is_classical = 1`.

### 5.3 Where the database lives

| Artifact | Size | Location |
|---|---|---|
| `data/sanad-quran.db` | ~5 MB | committed to the repo — zero-setup demo |
| `sanad-corpus-vX.Y.Z.db.zst` | ~150 MB | GitHub Release asset (2 GB limit, unmetered) |
| Container image with DB baked in | — | GHCR, public |

GitHub hard-rejects files over 100 MB, so the full corpus cannot be committed
and Git LFS's 1 GB/month free bandwidth would not survive real traffic. The
release-asset route is not a workaround — it is the provenance mechanism. At
boot the API resolves the DB in this order:

1. `SANAD_DB` env var path, if set.
2. `data/sanad.db`, if present.
3. Download the release asset pinned in `corpus.lock.toml`.
4. Fall back to `data/sanad-quran.db` (Qur'an only) and log a clear warning.

In cases 2 and 3 the SHA-256 is verified against the lockfile and **the service
refuses to start on mismatch**.

### 5.4 Schema

```sql
CREATE TABLE sources (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL,     -- quran-arabic | quran-translation | hadith-arabic
  title           TEXT NOT NULL,
  publisher       TEXT,
  edition         TEXT,
  url             TEXT NOT NULL,
  license_id      TEXT NOT NULL,
  license_url     TEXT,
  attribution     TEXT NOT NULL,     -- exact notice, rendered in the UI
  retrieved_at    TEXT NOT NULL,
  upstream_sha256 TEXT NOT NULL,
  modifications   TEXT NOT NULL      -- 'none' for verbatim sources
);

CREATE TABLE records (
  id                TEXT PRIMARY KEY,   -- quran:2:255 | hadith:bukhari:1:1
  source_id         TEXT NOT NULL REFERENCES sources(id),
  kind              TEXT NOT NULL,      -- ayah | hadith
  surah             INTEGER,
  ayah              INTEGER,
  surah_name_ar     TEXT,
  surah_name_en     TEXT,
  collection        TEXT,
  book_no           INTEGER,
  chapter_ar        TEXT,
  hadith_no         TEXT,
  numbering_scheme  TEXT,              -- which edition's numbering this is
  text_ar           TEXT NOT NULL,     -- canonical, verbatim, never altered
  text_ar_sha256    TEXT NOT NULL,
  norm_light        TEXT NOT NULL,     -- tier 1
  norm_standard     TEXT NOT NULL,     -- tier 2
  norm_aggressive   TEXT NOT NULL,     -- tier 3
  reference_display TEXT NOT NULL
);

CREATE TABLE translations (
  record_id TEXT NOT NULL REFERENCES records(id),
  source_id TEXT NOT NULL REFERENCES sources(id),
  lang      TEXT NOT NULL,
  text      TEXT NOT NULL,
  PRIMARY KEY (record_id, source_id)
);

CREATE TABLE gradings (
  record_id    TEXT NOT NULL REFERENCES records(id),
  authority    TEXT NOT NULL,
  grade        TEXT NOT NULL,
  is_classical INTEGER NOT NULL,       -- 1 = stated by the compiler
  source_id    TEXT NOT NULL REFERENCES sources(id)
);

CREATE VIRTUAL TABLE records_fts USING fts5(
  record_id UNINDEXED,
  norm_standard,
  norm_aggressive,
  translation,
  tokenize = "unicode61 remove_diacritics 2"
);

CREATE TABLE embeddings (
  record_id TEXT PRIMARY KEY REFERENCES records(id),
  model     TEXT NOT NULL,
  dim       INTEGER NOT NULL,
  vec       BLOB NOT NULL              -- int8-quantized
);

CREATE TABLE audit_log (
  id          INTEGER PRIMARY KEY,
  ts          TEXT NOT NULL,
  request_id  TEXT NOT NULL,
  stage       TEXT NOT NULL,
  verdict     TEXT NOT NULL,
  detail_json TEXT NOT NULL
);
```

`audit_log` stores stage verdicts and record IDs — **never user question text**,
per the "no real user conversation data" constraint in the README.

## 6. Arabic normalization

The prototype's single normalization pass is replaced by **three tiers**, and
the tier that produced a match is reported to the user.

| Tier | Transform | Purpose |
|---|---|---|
| `light` | NFC; strip tatweel `U+0640` | Whitespace/kashida-insensitive exact match |
| `standard` | light + strip harakat `U+064B–U+065F`, superscript alef `U+0670`, Qur'anic annotation marks `U+06D6–U+06ED` | Undiacritized text matching |
| `aggressive` | standard + fold `آ أ إ ٱ → ا`, `ى → ي`, `ة → ه`, strip non-Arabic | Catch sloppy transcription |

This tiering matters more than it looks. **For a verifier, over-normalization
is a correctness bug, not a convenience.** Folding aggressively means a genuine
misquote matches a real verse and gets reported as verified — the exact failure
Sanad exists to prevent. So:

- A match at `light` is reported as **exact**.
- A match at `standard` is reported as **exact, orthography differs**.
- A match at `aggressive` is reported as **near match** and always shows a
  character-level diff, never a bare green tick.

Similarity uses normalized Levenshtein, as in the prototype, but thresholds are
applied per tier rather than globally. The existing `0.995 / 0.86 / 0.72`
constants carry over as the starting point for the `aggressive` tier and are
re-tuned against the evaluation set.

## 7. Retrieval: two different problems

Verify and Ask need different machinery, and conflating them is a trap.

- **Verify is a string problem.** Given an Arabic span, is it in the corpus
  verbatim? Normalized exact match, then bounded edit distance over FTS5
  candidates. **Embeddings are never consulted** — semantic similarity would
  happily rate a misquote as a match.
- **Ask is a topic problem.** "What does the Qur'an say about patience?" needs
  semantic search over embeddings, fused with BM25 via reciprocal rank fusion.

Consequence: the vector layer is **optional**. The verifier has no ML
dependency, so the repo stays clone-and-run for anyone without a model or an
API key.

## 8. Ask mode pipeline

Six stages. Four are deterministic. Two call Claude.

| # | Stage | Kind | Behaviour |
|---|---|---|---|
| 0 | Router | deterministic | Classifies `PERSONAL_RULING` / `HIGH_RISK` / `DISPUTED` / `GENERAL`. Personal rulings produce a specialist handoff packet and **the generator never runs**. |
| 1 | Retriever | deterministic | Hybrid FTS5 + vector, RRF-fused, top-k evidence with record IDs. |
| 2 | Generator | `claude-opus-5` | Answers from the evidence set only. Structured output: every sentence carries either a record ID or an `interpretation` label. Arabic quotes must be copied from the evidence, not composed. |
| 3 | **Verifier** | **deterministic** | Re-runs the §6/§7 Verify engine over the generator's own output. Any Arabic span that is not an exact corpus match is **hard-blocked**. Any cited record ID not in the evidence set is **hard-blocked**. |
| 4 | Auditor | `claude-opus-5`, fresh context | Receives the answer and the evidence — **not** the generator's reasoning. Judges claim-level entailment; flags overreach, unanimity/ijmāʿ claims, and flattened madhhab disagreement. Structured verdict, not prose. |
| 5 | Adjudicator | deterministic | Combines verdicts: publish, relabel as interpretation, retry once, or abstain. |

Design properties that make this more than theatre:

- **The verifier is code.** Two Claude instances checking each other share
  failure modes; a deterministic string check does not.
- **The auditor is context-isolated.** It cannot be anchored by reasoning it
  never sees.
- **Exactly one retry.** Verifier blocks → regenerate once with the specific
  failures fed back → abstain. No loops, bounded cost.
- **Abstention is a success state,** not an error. It is reported as such and
  counted in the metrics.

An optional **madhhab panel** stage runs when the router returns `DISPUTED`:
it presents multiple positions with their evidence rather than flattening them,
as required by `docs/GAPS.md` §5.

### Claude API usage

- Model `claude-opus-5` for both generator and auditor.
- `thinking: {type: "adaptive"}`.
- Structured output via `output_config: {format: {...}}` — not the deprecated
  `output_format`.
- Streaming, so pipeline stages surface in the UI as they complete.
- Official `anthropic` Python SDK. No raw HTTP, no OpenAI-compatible shims.
- The corpus evidence block is placed before the volatile question and marked
  with `cache_control` so the prefix caches across requests.

## 9. API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/verify` | Deterministic verification. No model. Returns quotations, claims, risk, overall verdict. |
| `POST /api/ask` | SSE stream of pipeline stage events. |
| `GET /api/records/{id}` | Full evidence card: canonical text, checksum, source, licence, attribution. |
| `GET /api/search` | Corpus browse. |
| `GET /api/corpus` | Manifest: sources, licences, record counts, DB hash. |
| `GET /api/health` | Liveness plus corpus hash verification status. |

`GET /api/corpus` is a first-class feature, not plumbing: it is how a reviewer
confirms the shipped corpus matches the lockfile.

## 10. Frontend direction

Detailed token system is produced at implementation time under the
`frontend-design` skill. The direction is fixed here.

**Grounding.** *Sanad* (سند) is the chain of transmission — the support that
carries a report back to its origin. The visual argument is the trace: a claim,
the link, the source, the licence. Islamic manuscript convention supplies the
structural vocabulary — the ruled text block, the distinction between *matn*
(the text) and *ḥāshiya* (the gloss in the margin), the rosette marking an āyah
boundary.

**Explicitly not** the default AI clusters the `frontend-design` skill names:
no warm cream + serif + terracotta, no near-black + acid green, no broadsheet
hairlines. In particular, no beige-parchment pastiche — this is an
instrument, not a facsimile.

**Signature element: the isnad trace.** A vertical chain that resolves as
verification runs — quote → normalized form → matched record → source →
licence. It is the product's thesis rendered as an object on screen.

**Motion has jobs, not decoration:**

- Evidence cards arrive as retrieval completes, ordered by score.
- Character-level diff animates on near-matches, so the user sees precisely
  which letters differ.
- Pipeline stages illuminate from SSE events; the adjudicator gate visibly
  opens or refuses.
- A blocked span stays visible and marked. Nothing that failed is hidden.

Arabic typography is a first-class requirement: proper naskh face, correct RTL
handling, diacritics rendered at readable size, and canonical text never
reflowed in a way that alters it.

## 11. Evaluation

Formalizes `docs/GAPS.md` §9.

- `eval/cases/*.yaml` — the prototype's 20 adversarial cases, restructured and
  extended. Each case: input text, expected per-span verdict, rationale.
- Case families: exact quote; diacritic variance; single-letter mutation;
  correct text with wrong surah; correct text with wrong āyah; fabricated
  hadith; real hadith with invented number; valid quote followed by an
  unsupported legal conclusion; unanimity claim; personal-ruling question.
- Metrics: exact-quote accuracy, wrong-reference detection rate,
  fabrication detection rate, abstention rate, false-verification rate.
- **False verification — calling a misquote verified — is the critical metric.**
  CI fails on any regression in it. The others are tracked; this one gates.
- The Ask pipeline is evaluated end-to-end with a recorded-response fixture set,
  so CI does not require an API key.

## 12. Repository layout

```
api/
  sanad/
    arabic/        normalization tiers, similarity
    corpus/        schema, DB access, hash verification
    verify/        deterministic verification engine
    retrieve/      FTS5 + vector + RRF
    agents/        generator, auditor (Claude)
    pipeline/      router, adjudicator, orchestration, SSE
    api/           FastAPI routes
  tests/
ingest/
  corpus.lock.toml
  sanad_ingest/    downloader, hash check, builder
web/               Vite + React + Motion
eval/              cases, runner, metrics
data/
  sanad-quran.db   committed, ~5 MB
docs/
index.html         the Phase 0 prototype; stays at repo root so GitHub Pages
                   keeps serving a working demo until Stage C replaces it
.github/workflows/ ci.yml, corpus-release.yml, pages.yml
```

## 13. Implementation sequencing

This spec is too large for one implementation plan. It decomposes into three
stages, each of which ships something usable on its own and gets its own plan.

**Stage A — deterministic core.** Lockfile, `sanad-ingest`, Qur'an corpus,
three-tier normalization, the Verify engine, `POST /api/verify`, evaluation
harness, CI. No model, no key, no frontend work beyond a plain page.
*Ships as:* a working verifier. This is the whole Track 4 claim, standing alone.

**Stage B — Ask pipeline.** Retrieval (FTS5 + vector + RRF), the six-stage
pipeline, both Claude stages, SSE, audit log, fixture-based pipeline eval.
*Depends on:* A's verify engine, which is stage 3 of the pipeline.

**Stage C — frontend.** React + Vite, the isnad trace, motion, Arabic
typography, both modes wired to the API.
*Depends on:* A and B's endpoints, though it can begin against A alone.

Hadith ingest slots into Stage A once §14.1 is resolved; if it is not resolved
in time, A ships Qur'an-only and Hadith lands later without rework, because the
schema already accommodates it.

## 14. Open items

1. **Hadith Arabic source is not yet chosen.** Requirements: public-domain
   classical matn, documented provenance, stable numbering, machine-readable.
   `fawazahmed0/hadith-api` declares Unlicense but does not document the
   provenance of its underlying translations — a repo cannot relicense text it
   does not own, so it fails the `docs/SOURCES.md` test. OpenITI has scholarly
   metadata but no licence stated on its landing page. sunnah.com returned 403
   to automated access, so its API terms could not be verified from this
   machine. **This must be settled before the Hadith ingest is written.** The
   Qur'an layer does not depend on it and proceeds in parallel.
2. **Qur'an translation source.** Tanzil is ruled out (see §5.2 — their
   translations carry a non-commercial restriction). Need a Pickthall
   transcription from a distributor imposing no terms beyond the work's own
   public-domain status. A faithful transcription of a public-domain text
   attracts no new copyright, so the question is purely about the
   distributor's asserted terms, not the text. Display-only layer; does not
   gate Stage A.
3. **Deployment target** — Fly.io, Render, or self-hosted. Affects only the
   deploy workflow; the container is the same.
4. **Embedding model** — must be Arabic-capable. Local sentence-transformers
   keeps the build reproducible and key-free; an API adds a dependency. Decide
   at implementation, defaulting to local.
5. **Repo hygiene** — `data/`, `docs/`, `.github/`, and `.gitignore` exist in
   `sanad-github-ready-v2.zip` but were never pushed. `README.md` documents
   files that are not in the repository, and the missing `pages.yml` is why
   Pages does not deploy. Restore these as the first commit, then delete the
   committed zip.

## 15. Risks

| Risk | Mitigation |
|---|---|
| Hadith licensing stays unresolved | Qur'an layer ships standalone; Hadith schema and loader are built and left empty. The UI states the corpus boundary rather than implying completeness. |
| Over-normalization produces false verifications | Three-tier normalization; tier reported; `aggressive` matches never present as verified. Gated in CI. |
| Generator fabricates a plausible quote | Deterministic verifier hard-blocks any span absent from the corpus. Not a prompt instruction — a code path. |
| Auditor rubber-stamps the generator | Fresh context; sees output and evidence only, never reasoning. |
| Users read Sanad as issuing rulings | Router diverts personal questions to handoff before generation. Non-negotiable, enforced in code. |
| Corpus tampering | SHA-256 verified at boot against the committed lockfile; service refuses to start on mismatch. |
