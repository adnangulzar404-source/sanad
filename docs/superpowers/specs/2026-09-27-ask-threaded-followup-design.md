# Sanad — Ask threaded follow-up

**Date:** 2026-09-27
**Status:** approved (design), pending implementation plan
**Depends on:** Stage B (Ask, shipped). Independent of Stage A3.

## 1. What we are building

The ability to ask a follow-up question in Ask that carries the context of the
previous turn — so "what about in Muslim?" or "is that one authentic?" is
understood against the answer just given, rather than as a cold question.

## 2. The load-bearing constraint: context must not leak fabrication

Ask's anti-fabrication guarantee is **structural, not policed**: the model writes
English and cites record IDs; the server renders every Arabic quotation from the
DB by ID. Threading must not weaken this. The single hazard is that conversation
history becomes a channel through which un-grounded Arabic (or a fabricated
citation) is carried forward and re-displayed as if canonical.

**The rule that keeps threading safe:** history handed to the model contains
**only English framing/summary text and record IDs — never raw Arabic**. Every
Arabic quotation in every turn's answer is re-rendered from the DB by ID, in that
turn. The model is never given Arabic prose it could parrot into a later turn.
The display contract (I1) holds per turn, unchanged.

## 3. Non-goals

- **No server-side session store.** The function stays stateless (Vercel-friendly).
- **No unbounded history.** A capped window (see §5), not the whole conversation.
- **No cross-turn corpus expansion.** Each turn retrieves and grounds afresh;
  history steers the *question*, never substitutes for retrieval.

## 4. Architecture: client-held history, stateless server

The client accumulates the conversation and sends prior turns with each request;
the server holds no session. `AskRequest` gains:

```
history: list[AskTurn]   # oldest → newest, capped
AskTurn = { question: str, summary: str | null, item_ids: list[str] }
```

`item_ids` are corpus record IDs the prior turn cited. No Arabic, no framing prose
beyond the short `summary`. The server:

1. **Router** runs on the *new* question with history as context (a follow-up can
   escalate risk — e.g. a neutral thread turning into a personal ruling — so the
   router and the handoff logic run every turn, never cached from turn 1).
2. **Query expansion** receives the history (English + IDs) so pronouns and
   ellipsis resolve ("that hadith", "in Muslim").
3. **Retrieve / select / guards / audit / adjudicate** run exactly as today, on
   this turn's candidates. The model MAY cite a carried-forward `item_id` from
   history; the server re-renders it from the DB by ID. The guard set is extended
   so the valid-citation set = this turn's candidates ∪ history `item_ids`
   (re-fetched from the DB), and nothing else. Any Arabic in prose is still
   rejected.

## 5. Bounds and failure behaviour

- **History window:** the last N turns (N = 6 proposed), each `summary` length-
  capped; older turns dropped. A follow-up whose referenced `item_id` is no longer
  in the window simply isn't privileged — the turn still retrieves normally.
- **Abstention / handoff are per turn.** A follow-up that routes to handoff shows
  the handoff and suppresses evidence, regardless of earlier turns.
- **A malformed / oversized history is rejected** with the same 422 shape as an
  oversized question; the server never trusts history blindly (item IDs are
  validated against the corpus; unknown IDs are ignored, not rendered).

## 6. Display

- `web/src/screens/Ask.tsx`: after a result, a "next question" box. The
  `useAsk` hook accumulates `AskTurn`s (question + returned summary + returned
  item IDs) and sends them as `history` on the next `run`. Each answer renders as
  its own brief in a running list; the anti-fabrication rendering (Arabic only
  from `record`) is unchanged per answer.
- A "start over" control clears the client history.

## 7. Guards and evaluation

- **Guard (extended):** valid-citation set includes history `item_ids` re-fetched
  from the DB; unknown/again-Arabic content is rejected. No-Arabic-in-prose holds
  per turn.
- **Eval cases:** (1) a follow-up "what about in Muslim?" retrieves and grounds
  Muslim evidence afresh (does not echo turn-1 Arabic); (2) history text
  containing a fabricated Arabic string never appears in the answer (adversarial —
  the server ignores Arabic in history); (3) a follow-up that escalates to
  personal-ruling routes to handoff; (4) an unknown `item_id` in history is
  ignored, not rendered; (5) history is capped — turn N+7 does not carry turn 1.

## 8. Files

```
api/sanad/api/schemas.py         + AskTurn, history on AskRequest (validated, capped)
api/sanad/agents/router.py       history as context; risk re-evaluated each turn
api/sanad/agents/expand.py       history (English + IDs) for reference resolution
api/sanad/pipeline/guards.py     valid-citation set ∪ history item_ids (re-fetched)
api/sanad/api/routes.py          thread the history through; per-turn abstain/handoff
web/src/api/client.ts            AskTurn type; history on the request
web/src/api/useAsk.ts            accumulate turns; send history; start-over
web/src/screens/Ask.tsx          next-question box; running answer list
eval/cases/ask.yaml              the five cases above
```

## 9. Global constraints

Anti-fabrication I1/I2 held **per turn**; Arabic never authored by the model and
never carried through history; reverent naming on prose only; Ask model
`claude-sonnet-4-6`; risk router and handoff run every turn; every test capable of
failing. The server remains stateless.

## 10. Open items

1. **History window N** (proposed 6) and per-`summary` cap — tuned at
   implementation against token cost.
2. **Multi-answer layout** — running list vs. replace-in-place — decided against
   the existing Ask visual language at implementation.
