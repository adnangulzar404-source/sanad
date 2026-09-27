# Sanad — Ask hadith English translation

**Date:** 2026-09-27
**Status:** approved (design), pending implementation plan
**Depends on:** Stage B (Ask, shipped). Independent of Stage A3.

## 1. What we are building

An English rendering of each hadith matn shown in the Ask evidence brief. Because
no copyright-clean English translation of these collections can be bundled (A2
§2), the rendering is **model-generated** and **clearly labelled as
non-authoritative**. The verbatim Arabic remains the canonical thing on screen;
the rendering is an aid, not a source.

## 2. Why model-generated, and why labelled

The Qur'an ships Pickthall (public domain), so āyāt already have a canonical
`translation_en`. Hadith do not, and the widely-used English translations are
modern (copyright) or of uncertain provenance. A model rendering is the only
licensing-clean way to give English on hadith. It carries one honest risk — a
model translation of scripture can be subtly wrong — which the label mitigates
rather than eliminates. This is the same class of output as the existing Ask
`framing` line (model-authored English about the evidence), extended to a
line-level translation of the matn.

## 3. Non-goals

- **Not a canonical translation.** Never presented with the authority of the
  Arabic. Never stored in the corpus. Never applied to Qur'an āyāt (those keep
  Pickthall).
- **No translation of the isnād.** The chain is shown in Arabic in the `.data`
  register; it is apparatus, not the quoted text.
- **No offline/batch translation store.** Generated per request, in-pipeline.

## 4. Where it happens: fold into select&frame

The Ask stage-3 select&frame model call already receives the candidate records
(including the Arabic matn) and writes English `framing` per selected item. Add a
`matn_translation` field to that stage's structured-output schema, one per
selected hadith item. No new model call, no new stage — the model already has the
matn in context.

- The field is **English prose**, so it passes through the existing `reverent`
  transform (I2: reverent runs on prose, never on canonical text) — a rendering
  should say "Allah", matching Pickthall.
- The field is **not Arabic**, so it does not violate I1 (Arabic shown only from
  `record` objects). The existing guard that rejects Arabic in model prose
  (`pipeline/guards.py`) is **extended to cover `matn_translation`**: a rendering
  that contains Arabic-script characters is rejected, exactly as `framing` is.
- Qur'an items are **not** given a `matn_translation`; the pipeline uses their
  canonical `translation_en` (Pickthall) as today.

## 5. Data flow and display

- `AskItem` (`web/src/api/client.ts`) and the stage-3 payload gain
  `matn_translation: string | null`.
- `AskEvidenceCard` renders, under the matn:
  - the canonical `translation_en` when present (Qur'an), labelled as Pickthall,
    as today; else
  - the `matn_translation` when present (hadith), under the fixed label
    **"Sanad's plain-English rendering — not an authoritative translation."**
- The label is `.data` register (apparatus voice), visually subordinate to the
  Arabic matn, the same way the isnād and disclaimers are.

## 6. Guards and evaluation

- **Guard (extended):** `matn_translation` is subject to the no-Arabic-in-prose
  guard; a violating item is dropped/abstained, never rendered.
- **Eval cases** (Ask suite): (1) a hadith item's `matn_translation` is present,
  non-empty, and contains no Arabic; (2) a Qur'an item shows Pickthall, not a
  model rendering; (3) the label text is present whenever a model rendering shows;
  (4) reverent naming holds in the rendering ("Allah", not "God").

## 7. Files

```
api/sanad/agents/select.py           + matn_translation in the schema + prompt rule
api/sanad/pipeline/guards.py         no-Arabic guard covers matn_translation
api/sanad/api/routes.py              matn_translation through reverent(); into payload
api/sanad/api/schemas.py             + matn_translation
web/src/api/client.ts                + matn_translation on AskItem
web/src/components/AskEvidenceCard.tsx   render rendering + fixed label
eval/cases/ask.yaml                  the four cases above
```

## 8. Global constraints

No gradings; anti-fabrication I1/I2; reverent naming on prose only; Ask model
`claude-sonnet-4-6`; every test capable of failing. Arabic never authored by the
model — the rendering is English, and the guard enforces it.
