# Sanad Stage C — frontend design spec

**Date:** 2026-09-20
**Status:** approved, pending implementation plan
**Builds on:** `docs/superpowers/specs/2026-09-19-sanad-design.md` (§10 fixes the
visual direction; this spec makes it concrete)
**Depends on:** Stage A, shipped — `POST /api/verify`, `GET /api/search`,
`GET /api/records/{id}`, `GET /api/corpus`, `GET /api/health`

## 1. What we are building

A single screen that takes arbitrary pasted text and shows it being taken
apart: which quotations are genuinely in the corpus, which are misquoted,
which carry the wrong citation, which are absent, and which questions should
never have been answered by software at all.

Stage A proved the engine. Stage C makes it legible. Nothing here adds
verification logic — every verdict on screen comes from the Python engine, and
the frontend's only job is to render what it says without overstating it.

## 2. Non-goals

- **No verification logic in the frontend.** Not a reimplementation, not a
  shortcut, not a "quick client-side pre-check". One engine. A second verifier
  that can disagree with the first is the defect this whole project spent its
  time hunting.
- No Ask mode. That is Stage B. No stub, no placeholder tab, no static diagram
  of a pipeline that does not run.
- No corpus browser, and **no search UI at all**. `GET /api/search` stays
  available to the API's consumers, but nothing in Stage C calls it. Nobody
  asked for search; the demo is paste-and-dissect, and a search box would take
  attention from it. Revisit only if using the Verify screen shows a real need.
- No authentication, no accounts, no history. Nothing to store means nothing
  to leak, which matches the README's promise not to retain user text.

## 3. Decisions taken

| Question | Decision |
|---|---|
| Hosting | One Vercel project serving both the static frontend and the API |
| Origin | Same-origin, so no CORS configuration |
| Framework | React + Vite + TypeScript (fixed by the Stage A spec §3) |
| Scope | One Verify screen plus a provenance panel |
| API types | Generated from the API's own OpenAPI schema |
| GitHub Pages | Keeps serving the Phase 0 prototype, banner links to the live demo |

Two options were considered and rejected:

**Client-side verification with WASM SQLite.** Would let GitHub Pages host
everything with no server. Rejected because it requires reimplementing the
verification engine in TypeScript, producing two verifiers that can disagree.

**GitHub Pages frontend with the API on a separate host.** Chosen initially,
then reconsidered. Two deploys that move independently need CORS and a
mechanical drift check; one origin needs neither.

## 4. Architecture

```
                    sanad.vercel.app
   /               →  React static build
   /api/verify     →  FastAPI on Vercel's Python runtime
   /api/search     →  same
   /api/records/*  →  same
   /api/corpus     →  same
   /api/health     →  same
```

### 4.1 What the repository needs

Three additions, none of which exist today:

1. **A root entrypoint.** Vercel's Python runtime loads a top-level `app`
   from `app.py` / `main.py` / `index.py`. Ours lives behind a factory at
   `api/sanad/api/app.py`, so a three-line root shim imports and calls it.
2. **`vercel.json` with `excludeFiles`.** Vercel bundles everything reachable
   at build time with no tree-shaking. Without an exclusion list the serverless
   function would carry `tests/`, `eval/`, `docs/`, `.venv/` and the SDD
   workspace. The corpus (~5 MB) stays; the limit is 500 MB.
3. **`SANAD_AUDIT_DB=/tmp/sanad-audit.db`.** Serverless filesystems are
   read-only outside `/tmp`. The corpus is already opened read-only so it is
   unaffected; only the audit log needs redirecting, and it becomes ephemeral.
   That is acceptable — the Stage A spec already notes audit persistence
   requires a volume.

**Naming collision to avoid:** the Python package lives in a directory called
`api/`, and Vercel treats `/api` as its file-based functions convention. Use
the framework-preset entrypoint and explicit routing, not that convention.

### 4.2 The API client is generated, not written

`web/src/api/client.ts` is generated from `/openapi.json` and checked in. CI
regenerates it and fails if the committed copy differs.

This is not ceremony. Stage A shipped ten defects of one shape: two things that
were supposed to agree, quietly diverging, with every test still passing — the
wrong Tanzil export, a `format` field honoured in one code path and not
another, a spec saying `aggressive` where the code said `standard`. A
hand-written API type is the same bug waiting in a new place. A generated
client turns a renamed field into a build failure instead of a blank space in
the UI.

## 5. The screen

```
┌────────────────────────────────────────────────────────┐
│  paste anything — a chatbot answer, a sermon, a post   │
│                                    [Verify]  [Example] │
└────────────────────────────────────────────────────────┘

YOUR TEXT — marked in place, never rewritten
┌────────────────────────────────────────────────────────┐
│ Islam teaches tawhid. The Qur'an says                  │
│ «قُلْ هُوَ ٱللَّهُ أَحَدٌ» (Al-Baqarah 2:255). All scholars agree… │
│  └──── wrong reference ────┘        └─ unanimity claim ─┘│
└────────────────────────────────────────────────────────┘

EVIDENCE — one isnad trace per span
┌────────────────────────────────────────────────────────┐
│ ◆ WRONG REFERENCE                                       │
│ ├─ you quoted     قُلْ هُوَ ٱللَّهُ أَحَدٌ                      │
│ ├─ normalized     قل هو الله احد            tier: light  │
│ ├─ matched        Al-Ikhlas 112:1                        │
│ ├─ you cited      Al-Baqarah 2:255              ✕ broken │
│ ├─ source         Tanzil Uthmani 1.1                     │
│ └─ licence        CC BY 3.0 · ⌗8774f388…                 │
└────────────────────────────────────────────────────────┘
```

The user's text is **marked, never rewritten**. Stage A's non-goals forbid
silent correction of a quotation; the frontend honours that by never
substituting the corpus reading for what the user typed.

### 5.1 The isnad trace is the evidence card

Spec §10 asked for "a vertical chain that resolves as verification runs —
quote → normalized form → matched record → source → licence". That chain is not
decoration over a result; it **is** the result. One rule governs the whole
visual grammar:

> The chain either completes or it visibly breaks, and you can see which link
> failed.

| Verdict | Chain behaviour |
|---|---|
| `EXACT` | completes, unbroken |
| `EXACT_ORTHOGRAPHY` | completes; the normalized link is annotated with what differed |
| `NEAR_MATCH` | breaks at the text link; character diff rendered inline |
| `WRONG_REFERENCE` | solid through "matched", struck at "you cited" |
| `NOT_FOUND` | terminates early, corpus-scope caveat attached |

`also_at` renders on the matched link when non-empty: a verse appearing 31
times is reported as appearing 31 times, not silently attributed to one ayah.

### 5.2 Three rules that separate an honest tool from a slick one

**Never colour alone.** Every verdict carries a distinct glyph, a text label
and a distinct chain state. The difference between "verified" and "near match"
is too consequential to encode as a hue a reader may not distinguish.

**`NOT_FOUND` carries its caveat inline.** "Not in this corpus; no Hadith
edition is bundled" sits with the verdict, not in a page footer. It is the one
verdict a reader could mistake for an accusation of fabrication.

**A personal-ruling question shows no verdict at all.** When `risk` is
`PERSONAL_RULING`, the evidence stack is replaced by the handoff card — the
warning *instead of* a verdict, not alongside one. Answering was the wrong
move; showing an answer with a caution attached would still be answering.

### 5.3 Arabic typography

A naskh face under the SIL Open Font License — Amiri or Noto Naskh Arabic,
both freely redistributable, so the licensing question does not reopen.
Canonical text set large enough that diacritics are legible, which is larger
than ordinary UI type. Correct RTL. Canonical text is never re-wrapped or
re-spaced in a way that alters it.

## 6. Provenance panel

Reachable from the licence link at the foot of every trace, and directly.
Renders `GET /api/corpus`:

- each source with its licence and edition
- the Tanzil notice **verbatim** — the file says "PLEASE DO NOT REMOVE OR
  CHANGE THIS COPYRIGHT BLOCK", so it is reproduced exactly, never summarised
- Tanzil's accuracy disclaimer wherever English is shown
- record counts and the corpus SHA-256

This panel is where the product's central claim gets cashed. No other
verification tool shows the checksum behind a verse.

## 7. Motion

Motion draws attention to a verdict. It never encodes one.

- Chain links resolve top-to-bottom, roughly 40 ms staggered — the trace is
  seen being built rather than replaced by a spinner
- Differing characters mark themselves in on a near-match, so the eye lands on
  what changed
- A broken link snaps and stays marked; nothing that failed fades out
- **`prefers-reduced-motion` is fully supported.** If disabling motion loses
  meaning, the design is wrong and the meaning moves into the static state.

## 8. Error and empty states

| Condition | Behaviour |
|---|---|
| API unreachable | "Cannot reach the verifier." Never an empty result. |
| API returns 5xx | The error, plus what the user can do. Never a silent blank. |
| Text with no Arabic | "No quotations found to check" — distinct from `NOT_FOUND` |
| Empty input | Verify disabled; no request |
| Slow response | The trace scaffold renders immediately, links resolve as data arrives |

The distinction between "we found nothing to check" and "we checked and it is
not in the corpus" must never collapse. Silence must never be mistakable for a
verdict.

## 9. Component structure

```
web/
  src/
    api/client.ts          generated from /openapi.json — do not hand-edit
    api/types.ts           generated
    components/
      IsnadTrace.tsx       the chain; one per span
      EvidenceCard.tsx     verdict header + trace + diff
      MarkedText.tsx       the user's text with spans marked in place
      CharDiff.tsx         character-level diff rendering
      VerdictBadge.tsx     glyph + label + state, colour-independent
      HandoffCard.tsx      replaces the stack on PERSONAL_RULING
      ProvenancePanel.tsx  /api/corpus rendered
      ErrorState.tsx       unreachable / 5xx / empty, each distinct
    screens/Verify.tsx
    theme/tokens.css       the design system; produced under frontend-design
    App.tsx
  index.html
  vite.config.ts
```

Each component has one job and can be understood without reading its
neighbours. `IsnadTrace` takes a `Match` and renders a chain; it does not know
what a verdict means beyond how to draw it.

## 10. Testing

Vitest and Testing Library. The tests that matter are the honesty ones:

- a `NOT_FOUND` result renders its corpus-scope caveat
- a `PERSONAL_RULING` renders the handoff card and **no** verdict
- verdicts remain distinguishable with colour removed
- an unreachable API renders "cannot reach the verifier", not an empty stack
- "no Arabic found" and `NOT_FOUND` render differently
- `also_at` renders when populated and is absent when empty
- canonical Arabic is rendered byte-identical to the API response
- the generated client matches `/openapi.json` (CI check, not a unit test)

## 11. Deployment

One Vercel project, built from `main`.

- Python: root entrypoint, `vercel.json` excludes, `SANAD_AUDIT_DB=/tmp/...`
- Frontend: `web/` builds to static output served at `/`
- GitHub Pages continues serving the Phase 0 prototype; its banner links to the
  live demo so both URLs are honest about what they are

## 12. Open items

1. **The design token system** — palette, type scale, spacing — is produced at
   implementation time under the `frontend-design` skill, constrained by spec
   §10: no warm cream + serif + terracotta, no near-black + acid green, no
   broadsheet hairlines, no beige-parchment pastiche.
2. **Vercel account** is the user's to create. Nothing else blocks; the
   frontend can be built and run against `localhost:8000` throughout.
3. **Nothing else.** Search was considered and cut (see §2). The design token
   system and the Vercel account are the only two things outstanding, and
   neither blocks implementation starting.

## 13. Risks

| Risk | Mitigation |
|---|---|
| Frontend overstates a verdict | Verdict rendering is driven entirely by the API's `verdict` field; the UI has no logic that could upgrade one |
| A second verifier appears by accident | No verification logic in `web/`, enforced by review; the generated client makes the API the only source of results |
| The honest caveats get designed away for looks | They are specified as required elements with tests, not as copy someone can trim |
| Serverless cold start reads as a hang | Trace scaffold renders immediately; the loading state is visible and labelled |
| Motion excludes users | `prefers-reduced-motion` fully supported; motion never carries meaning alone |
