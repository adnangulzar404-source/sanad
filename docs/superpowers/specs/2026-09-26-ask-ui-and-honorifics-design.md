# Ask UI + reverent-naming transform — design

**Date:** 2026-09-26
**Status:** approved (design), pre-implementation
**Builds on:** `docs/superpowers/specs/2026-09-24-ask-pipeline-design.md` (the Ask
pipeline backend, already shipped and live: `POST /api/ask` streaming SSE).

## Goal

Two changes, one branch:

1. **Ask UI.** A browser screen that lets a user type a question and watch the
   `/api/ask` evidence-brief pipeline run stage-by-stage, then read the result,
   with a Verify | Ask tab switch. The backend is already live and stable; this
   is the frontend it never got, plus the SSE plumbing to consume it.
2. **Reverent-naming transform.** App-wide: always write **"Allah"** (never
   "God"), and append Arabic honorifics after prophets' names — **ﷺ** after
   Muhammad, **عليه السلام** after every other prophet.

## The two load-bearing invariants

These are the reason the design is shaped the way it is. Everything else serves
them.

### I1 — The display contract (inherited from the Ask pipeline spec)

Arabic text shown to the user is rendered **only** from a `record` object
returned by the server (sourced from the SQLite corpus by id). It is **never**
interpolated from a model-authored field (`summary`, `framing`). Fabrication of
scripture is structurally impossible because the model never supplies the
Arabic; the UI must not reintroduce that possibility by, e.g., dangerously
rendering model prose as HTML or concatenating model text into an
Arabic-displaying element. The one Arabic string the UI/server *may* add to
prose is a **fixed honorific constant** (I2) — never scripture, never a record
field, never model output.

### I2 — The transform boundary

The reverent-naming transform (Allah-substitution + honorific insertion) runs
**only** on English prose that is either app-authored (static UI copy) or
model-authored (`summary`, `framing`). It **NEVER** touches canonical corpus
text: `record.text_ar`, `record.translation_en` (Pickthall), `record.isnad_ar`,
or any other record field. Altering the Pickthall translation or the Arabic
scripture would break the verbatim-source guarantee this whole project rests on
(see the character-in-transit and licensing-basis lessons). Pickthall already
renders the divine name as "Allah," so nothing is lost by leaving it verbatim.

The honorific glyphs are added **after** the deterministic guards
(`pipeline/guards.py`) have already passed on pure-English model prose. They
therefore do not trip `no_arabic_in_prose`, and they do not count as
model-produced Arabic. This is the single, deliberate, documented exception to
"no Arabic in prose": editorial honorific convention, applied by the app to
prose it is displaying, never scripture the model tried to emit.

## Part A — The reverent-naming transform

### A.1 Module

New module `api/sanad/text/reverent.py` (server-side, so it is pytest-testable
and consistent for every client). Pure functions, no I/O:

```
def reverent(text: str) -> str
```

`reverent` composes two idempotent passes:

1. **Divine name.** Replace the whole word `God` / `god` (word-boundaried,
   case-sensitively producing `Allah`) → `Allah`. Possessive `God's` → `Allah's`.
   Does not touch substrings (`Godfrey`, `good`).
2. **Honorifics.** After a recognized prophet name that is not already followed
   by its honorific, append the fixed constant:
   - Muhammad (and the spellings `Muhammed`, `Mohammed`, `Mohammad`) → name + `" ﷺ"`
     (U+FDFA, written via `chr(0xFDFA)` in source per the character-in-transit
     rule — never a typed glyph).
   - Every other prophet in `PROPHETS` → name + `" عليه السلام"` (also built via
     `chr()` escapes).
   Idempotent: if the honorific (or its Latin equivalent) already follows the
   name, do not add a second one.

`PROPHETS`: the prophets named in the Qur'an, each with its common English and
transliterated spellings — e.g. Adam; Noah/Nuh; Abraham/Ibrahim; Ishmael/Ismail;
Isaac/Ishaq; Jacob/Yaqub; Joseph/Yusuf; Moses/Musa; Aaron/Harun; David/Dawud;
Solomon/Sulayman; Job/Ayyub; Jonah/Yunus; Jesus/Isa; Zachariah/Zakariya;
John/Yahya; Lot/Lut; Hud; Salih; Shuayb; Idris; Dhul-Kifl; Elijah/Ilyas;
Elisha/Alyasa. (Muhammad handled separately, above.) The exact table is fixed in
the module with a source comment; adding a spelling later is a one-line change.

Honorific constants are defined once via `chr()` and printed during review, per
`sanad-character-transit-defect` — an Arabic honorific with a silently-wrong
codepoint is exactly the class of bug that memory exists to prevent.

### A.2 Where it is applied

- **Ask model prose:** in `api/sanad/api/routes.py`, in the `/api/ask` `final`
  event assembly (after guards, where `record` enrichment and `corpus_scope`
  already happen): apply `reverent()` to `payload_out["summary"]` and to each
  item's `framing` **before** they are sent to the client. Record fields are
  enriched separately and are **not** passed through `reverent()`.
- **Static UI copy:** authored by hand with "Allah" and the correct honorifics
  directly in the JSX. No runtime transform needed for static strings.

### A.3 What it is NOT applied to

Every `record` field (see I2). The route enriches items with `db.get_record(...)`
→ `_record_out(...)`; that path is untouched. A test asserts a record whose
translation contains "God" (hypothetically) or a prophet name is returned
verbatim.

### A.4 Model instruction

The Ask stage-3 (select & frame) and stage-1 (expand) system prompts already
tell Claude to write English prose; add a line instructing it to use "Allah"
rather than "God." The deterministic `reverent()` pass is the safety net for
slips; the instruction reduces how often the net is needed.

## Part B — The Ask UI

### B.1 Navigation (`web/src/App.tsx`)

Replace the direct `<Verify/>` render with a two-tab header: **Verify** | **Ask**.
Default landing is **Verify** (the established primary; needs no API key). The
shared provenance panel and corpus footer stay below both tabs. Tab state is
local React state (no router dependency). The existing `#provenance` hash
behavior is preserved.

### B.2 SSE client (`web/src/api/useAsk.ts`)

A hook mirroring `useVerify`, but streaming. `EventSource` is GET-only and the
endpoint is POST, so use `fetch` + `response.body.getReader()` and parse
`data: {json}\n\n` frames by hand (no new dependency; the frame format is
trivial). No auto-reconnect — a re-fired pipeline is a second Claude spend.

State shape:
```
type AskState = "idle" | "streaming" | "done" | "unreachable" | "error";
stages: partial record of stage-name -> "pending" | "active" | "done"
final: AskFinalOut | null
```
`run(question)` opens the stream, updates `stages` as `router/expand/retrieve/
select/check/audit` frames arrive, stores the `final` frame, and handles the
`error` frame + a mid-stream drop (→ `error`) and an unreachable endpoint
(→ `unreachable`, reusing the `NOT_UP_YET` treatment from `useVerify`).

### B.3 Ask screen (`web/src/screens/Ask.tsx`)

- Question `textarea` + **Ask** button + **Load example** (example question:
  "Is there a hadith that actions are judged by intentions?").
- **Live pipeline reveal** (the chosen streaming UX): a vertical stage list that
  lights up as frames arrive — *Understanding your question → Searching the
  corpus → Selecting evidence → Checking safety guards → Auditing* — each
  flipping pending → active → done.
- **Results (`final.status === "published"`):** lead with `final.summary`
  (labelled as Sanad's English framing), then one card per `final.items[i]`:
  the English `framing`, then the record rendered from `item.record` (reference,
  Arabic `text_ar`, translation if present, isnād trace for hadith) via a small
  `AskEvidenceCard` that wraps the existing record display. A `reached`
  indicator (Qur'an / Ḥadīth), the same "does not grade authenticity" and
  translation disclaimers Verify shows, and the `corpus_scope` note.
- **Abstained (`status === "abstained"`):** show `final.abstain_reason` honestly
  + `corpus_scope`. No fabricated filler. (The old missing-key case is now just
  a normal abstain.)
- **Handoff (`requires_handoff`):** render the existing `HandoffCard` with
  `final.risk`.
- **Errors:** reuse `ErrorState` (unreachable / server) for the `error` frame
  and stream drops.

### B.4 Reuse

`HandoffCard`, `ErrorState`, and the record-rendering internals of
`EvidenceCard`/`IsnadTrace` are reused. Ask's `items` shape differs from
Verify's `quotations`, so `AskEvidenceCard` is a thin new wrapper, not a fork of
`EvidenceCard`.

## Error handling summary

| Condition | UI |
|---|---|
| endpoint unreachable / 502/503/504 | `ErrorState kind="unreachable"` (not-up-yet copy) |
| SSE `error` frame | `ErrorState kind="server"` |
| mid-stream connection drop | `ErrorState kind="server"` |
| `final` abstained | `abstain_reason` + corpus scope |
| `final` handoff | `HandoffCard` |

## Testing

**pytest (`api/tests/text/test_reverent.py`):**
- `God`→`Allah`, `god`→`Allah`, `God's`→`Allah's`; `Godfrey`/`good` untouched.
- Muhammad (all four spellings) gets ﷺ; a sample of other prophets get عليه السلام.
- Idempotency: applying twice adds nothing.
- Honorific constants are the exact intended codepoints (printed in the test).
- **Boundary:** a route-level test that a returned `record`'s `text_ar` /
  `translation_en` are byte-identical to the DB (transform never ran on them),
  while `summary`/`framing` in the same response are transformed.

**vitest (`web/src/screens/Ask.test.tsx`, `web/src/api/useAsk.test.ts`):**
- `useAsk` against a mocked `ReadableStream` of SSE frames → published,
  abstained, handoff, and error paths; stage progression asserted.
- Screen renders each state; the published state renders record-sourced Arabic.
- **Invariant test:** no Arabic appears in the rendered output except inside
  record-sourced elements and the fixed honorific constants.

## Out of scope

- Companion honorifics (رضي الله عنه) — only prophets, per the request.
- Vector retrieval on the deployed instance (still lexical-only; unrelated).
- Any change to the Verify verdict logic or the corpus.

## Files

- Create: `api/sanad/text/reverent.py`, `api/tests/text/test_reverent.py`,
  `web/src/api/useAsk.ts`, `web/src/screens/Ask.tsx`,
  `web/src/components/AskEvidenceCard.tsx`, `web/src/api/useAsk.test.ts`,
  `web/src/screens/Ask.test.tsx`.
- Modify: `api/sanad/api/routes.py` (apply `reverent()` in the `final`
  assembly), `api/sanad/agents/*` stage prompts (Allah instruction),
  `web/src/App.tsx` (tab nav), `web/src/api/client.ts` / `types.ts` (Ask types
  if not already generated), Verify static copy for "Allah"/honorifics.
