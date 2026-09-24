# Stage B — the Ask pipeline

**Status:** approved design, 2026-09-24. Supersedes §8 of
`2026-09-19-sanad-design.md`, which anticipated this stage before the corpus
existed. Where the two differ, this document is authoritative; §8's departures
are called out in §13 so the change is visible rather than silent.

**Goal.** Let someone ask a question in their own language and receive the
passages in Sanad's corpus that bear on it — each one verbatim, attributed, and
licensed — without Sanad ever composing scripture, grading a hadith, or
answering a question that belongs to a scholar.

**Depends on:** Stage A's verification engine, corpus and risk router, all
shipped. Nothing here changes the verify path, which remains deterministic and
offline.

---

## 1. The governing decision: a brief, not an answer

Sanad returns an **evidence brief** — the relevant āyāt and hadith, each under a
one-line framing, beneath a short neutral summary of what the sources cover. It
does not compose an answer.

This is a product decision before it is a technical one. Sanad's value is that
it declines to overstep, and "here is what these sources say" is a claim it can
stand behind in a way that "here is what Islam says" is not.

It also makes the central safety property **structural rather than policed**:

> Claude selects record IDs and writes prose. It never writes Arabic. The
> server renders every quotation from the database by ID.

There is therefore no path by which a fabricated or altered quotation reaches
the screen. The earlier design had Claude compose Arabic and a deterministic
verifier catch what was wrong with it; this removes the failure mode instead of
checking for it. Given that this project has shipped eleven defects from Arabic
altered in transit (`docs/hadith-build-log.md`), removing the path is worth more
than any guard over it.

---

## 2. Pipeline

Seven stages. Four deterministic, three call a model.

| # | Stage | Kind | Behaviour |
|---|---|---|---|
| 0 | Router | deterministic | Existing `route_risk`. `PERSONAL_RULING` / `HIGH_RISK` → handoff packet; **no later stage runs**. `DISPUTED` and `GENERAL` proceed, `DISPUTED` carrying its label through to the response. |
| 1 | Query expansion | Claude | Detect the question's language. Emit Arabic search terms. This is what lets a non-Arabic question reach Arabic-only hadith when no vector index is available, and it improves lexical recall when one is. |
| 2 | Retrieve | deterministic | FTS5 over Arabic and available translations, plus vector search, fused by reciprocal rank. Emits candidate record IDs and which corpora were reachable. |
| 3 | Select & frame | Claude | Given candidates with their text: choose the relevant ones, write one framing line each, write a short summary. Output carries record IDs and prose only. |
| 4 | Check | deterministic | The guards of §5. Blocks are hard. |
| 5 | Audit | Claude, fresh context | Receives the brief and the evidence, **not** stage 3's reasoning. Judges whether each framing is supported by the record it sits under; flags overreach, unanimity claims, flattened madhhab disagreement, and implied grading. |
| 6 | Adjudicate | deterministic | Publish, relabel as interpretation, retry once, or abstain. |

**Exactly one retry.** A stage-4 block or a stage-5 overreach verdict re-runs
stage 3 once, with the specific failures fed back, and then abstains. No loops,
bounded cost, bounded latency.

**The auditor is context-isolated** so it cannot be anchored by reasoning it
never saw. Two model instances checking each other share failure modes; that is
why stage 4 sits between them and is code.

---

## 3. Retrieval

### 3.1 Unit

**One vector per record, over the full printed text.** Not one per scorable
representation. The primary/addendum split exists to make *verification*
precise; topic retrieval wants the whole unit. The dual-representation
machinery stays a verify-time concern.

### 3.2 Model and quantization

`voyage-4` via the Voyage AI API. Anthropic publishes no first-party embedding
model and recommends Voyage (verified 2026-09-24).

Stored **binary-quantized at 1024 dimensions**: 128 bytes per record, about
**1.7 MB** for 13,365 records.

| dtype | per record | corpus total |
|---|---|---|
| float32 | 4096 B | 55 MB |
| int8 | 1024 B | 13.7 MB |
| **binary** | **128 B** | **1.7 MB** |

Binary is chosen because the corpus already faces a size ceiling (§11) and
because at this scale recall matters more than fine ranking: 13,365 documents,
fused with exact-term FTS5, feeding a model that then *selects* from the
candidates. If measured recall disappoints, int8 is a one-line change and a
rebuild.

The `embeddings` table exists and is empty. It gains one column:

```sql
CREATE TABLE IF NOT EXISTS embeddings (
  record_id TEXT PRIMARY KEY REFERENCES records(id),
  model     TEXT NOT NULL,
  dim       INTEGER NOT NULL,
  dtype     TEXT NOT NULL,   -- NEW: 'binary' | 'int8' | 'float32'
  vec       BLOB NOT NULL
);
```

No `ALTER TABLE` is issued. The corpus is rebuilt and recommitted.

`CREATE TABLE IF NOT EXISTS` does not retrofit columns. Adding `dtype` means
rebuilding and recommitting `data/sanad-quran.db`, and tests pinned to the
corpus hash move with it. Rebuild, never migrate.

### 3.3 The vectors are a committed artifact — a deliberate exception

Every other byte of the corpus rebuilds byte-identically from sources pinned by
hash in `ingest/corpus.lock.toml`. **The vectors cannot.** They come from a
hosted model we do not control and cannot pin beyond its name.

They are therefore committed as an artifact, recorded with the model name, the
dimension, the dtype and the date generated, and pinned by content hash. A
normal `sanad-ingest build` does not need a Voyage key; regenerating the
vectors is a separate, explicit command that does.

This exception is written down because the project's rule is to record *why* a
thing is permissible, not merely that it is (`docs/hadith-build-log.md`,
`docs/SOURCES.md`). An undocumented inconsistency here would read later as an
oversight.

### 3.4 Fusion

Reciprocal rank fusion over the lexical and vector result lists. RRF needs no
score calibration between two retrievers on different scales, which is the
reason to prefer it over a weighted sum here.

### 3.5 Degradation

| Available | Ask behaviour |
|---|---|
| Anthropic + Voyage keys | Full pipeline. |
| Anthropic only | No vectors. Stage 1's Arabic terms drive FTS5. Reduced recall, stated in the response. |
| Voyage only, or neither | Ask unavailable, and says so. **Verify is untouched and fully functional.** |

Verify never required a key and still does not. A cloned repository runs the
whole Track 4 claim with no credentials.

### 3.6 Language reachability

| Question in | Qur'an | Hadith |
|---|---|---|
| Arabic | lexical + vector | lexical + vector |
| English | lexical (Pickthall) + vector | vector, or expanded Arabic terms |
| Urdu | lexical (once ingested) + vector | vector, or expanded Arabic terms |
| Other | vector only | vector only |

The last row is load-bearing: a German or Spanish question works **only** while
the Voyage key does. Without it, retrieval reaches nothing, and the response
must say that rather than returning a thin brief that resembles an answer.
`reached` and `unreached_reason` in the response payload (§7) exist for this.

---

## 4. Language of the response

Prose matches the question's language. **Quotations are always the original
Arabic**, with a licensed translation displayed alongside where one exists.

Hadith have no licensed translation in any language, and none is expected
(`docs/GAPS.md` §1). For a hadith in a non-Arabic brief, stage 3's framing line
serves as a **labelled explanation** — visibly the model's description of what
the passage says, never presented as a translation of Sahih al-Bukhari. The
distinction is enforced in the UI by presentation, and in the spec by this
sentence: Sanad publishes no hadith translation.

---

## 5. Guards (stage 4)

Ordered by how well they actually work, which is how they should be read.

| Guard | Strength | Rule |
|---|---|---|
| Cited ID in candidate set | **airtight** | Every `record_id` in stage 3's output must appear in stage 2's candidates. A model cannot cite what retrieval never surfaced. |
| No Arabic in generated prose | **airtight** | Any Arabic codepoint in a framing or summary is a block. This is what makes fabrication structurally impossible. |
| Length bounds | **airtight** | `summary` ≤ 80 words, each `framing` ≤ 25 words (§7). A brief that grows without bound is a composed answer arriving through the back door. |
| No unanimity claim | good | The vocabulary is narrow: ijmāʿ, "all scholars agree", "unanimously", "there is no disagreement". |
| No grading vocabulary | **partial** | See below. |

### The grading guard is partial, and this is deliberate

The obvious implementation — a wordlist — is **wrong**, and the plan must not
use one. Two collisions make it wrong:

- **`sahih` is half the collection's title.** Every legitimate citation of
  *Sahih al-Bukhari* contains it. A bare block rejects nearly every brief.
- **`hasan` is a narrator's name.** al-Ḥasan al-Baṣrī, al-Ḥasan ibn ʿAlī. A
  framing line naming a narrator would be blocked, retried, and abstained —
  the guard would suppress correct output.

So the guard blocks a grading term only where it is **not** part of a known
collection title and **not** immediately adjacent to a name particle
(`ibn`, `bin`, `al-`, `abu`). Terms: صحيح / `sahih` / `saheeh` / `ṣaḥīḥ`,
ضعيف / `daif` / `da'if` / `daeef` / `ḍaʿīf`, موضوع / `mawdu` / `mawdoo` /
`mawḍūʿ`, `matruk`.

`hasan` and `munkar` are **deliberately excluded from the hard block** — too
collision-prone to be worth it — and left to the audit stage.

The list and its exclusions live in one named constant with this reasoning
beside it. Each collision above becomes a test case: "Sahih al-Bukhari 2866"
must pass, "this hadith is sahih" must block.

Not blocked: English "authentic", "sound", "weak", "reliable". They are ordinary
words — "a weak argument", "sound reasoning" — and blocking them outright
produces false positives on legitimate prose.

So the regex is the cheap majority of cases and the audit stage is the rest, and
**neither is a guarantee**. Recorded here so it is a known limit rather than an
assumed guarantee.

### What stage 4 cannot see

**Whether a framing line fairly characterises the record it sits under.** A
framing that subtly misrepresents an āyah passes every deterministic check: it
cites a real ID from the candidate set, contains no Arabic, claims no grading
and no unanimity.

That is stage 5's job. Stage 5 is a model. **This failure mode therefore has no
hard guard**, and the honest statement of Sanad's Ask guarantee is:

> The quotations are real, complete, correctly attributed and correctly
> licensed — guaranteed by construction. The framing around them is reviewed by
> a second model and is not guaranteed.

This limit is stated in the UI, not only here.

---

## 6. Abstention

Abstention is a **success state**, reported and counted as one.

Triggers:

1. Retrieval returns no candidate above the relevance floor.
2. Stage 3 selects no candidate as relevant.
3. Stage 4 blocks twice (once, retry, block again).
4. Stage 5 judges overreach twice.

**The relevance floor is a fused-RRF-rank cutoff, not a similarity threshold** —
RRF scores are not comparable across queries, so an absolute score floor would
be meaningless. Retrieval passes the top *k* candidates to stage 3 and lets the
model judge relevance; trigger 1 fires only when *both* retrievers return
nothing at all. The value of *k* is fixed in the plan from measurement against
real questions, with the measured basis recorded — not chosen by intuition.

### Wording

**"Not in this corpus" is not "not in Islam."** Sanad holds the Qur'an and one
hadith collection. A question may be well addressed in Sahih Muslim or the four
Sunan, which are not here. An abstention names what was searched and what is
absent, reusing the scope text already in `api/sanad/corpus/scope.py`.

This mirrors `NOT_FOUND` in Verify, which has always meant "not in this corpus,
never fabricated". Ask inherits the semantics rather than inventing new ones.

---

## 7. API

### `POST /api/ask` — SSE

One event per stage. Streaming the derivation is not decoration: **Sanad's
argument is to show the chain, and the chain by which it reached an answer is
the same argument applied to itself.**

| Event | Payload |
|---|---|
| `router` | `risk`, `requires_handoff`; on handoff, the packet and no further events |
| `expand` | `question_language`, `search_terms` |
| `retrieve` | `candidate_count`, `reached`, `unreached_reason` |
| `select` | provisional items and summary |
| `check` | per guard: name, `pass` \| `block`, detail |
| `audit` | verdict, flags |
| `final` | the payload below |
| `error` | code and message; never a stack trace |

### Final payload

```
status            "published" | "abstained"
question_language ISO 639-1 code, detected at stage 1
summary           <= 80 words, or null when abstained
items             [{ record_id, framing, record }]   framing <= 25 words
reached           { quran: bool, hadith: bool }
unreached_reason  string or null
risk              existing RiskCode
requires_handoff  bool
abstain_reason    string or null
```

The length bounds are part of the contract, not style guidance: a brief is a
brief, and an unbounded `summary` is a composed answer arriving through the
back door. Stage 4 enforces them.

`record` is inlined **by the server reading the database**, never echoed from
model output. One round trip, and the §1 safety property holds because the
server is the renderer.

### Unchanged endpoints

`/api/verify`, `/api/records/{id}`, `/api/search`, `/api/corpus`, `/api/health`
are untouched.

---

## 8. Frontend

A new `Ask` screen beside `Verify`, with tab navigation.

**Reused as-is:** `EvidenceCard`, `IsnadTrace`, `ProvenancePanel`,
`HandoffCard`.

**New:** a composer; `PipelineTrace` rendering the stage stream; `EvidenceBrief`
wrapping the summary and the framed items.

**Displayed, not buried:** the reachability line from §3.6, and the §5
guarantee statement — what is guaranteed by construction and what is not.

### Debt paid here, because Stage B touches the API anyway

- **R46** — `also_at` currently carries two distinct relations ("identical text
  at the matched tier" and "the containing āyah"). Split `contained_in` out.
  Deferred from the hadith branch specifically until this stage.
- **`<mark title>` accessibility** — the brief introduces newly annotated text
  and must not repeat the project's known screen-reader gap.

---

## 9. Audit log and privacy

The existing separate audit database gains Ask rows: stage verdicts, record
IDs, risk code, abstention reason, guard blocks.

**The question text is never written**, nor are the search terms derived from
it. Same rule and same reasoning as `/api/verify`
(`api/sanad/api/routes.py`): no accounts, no analytics, nothing to anonymize.

---

## 10. Evaluation

**The suite gates the guards, not the model.** We cannot make Claude behave. We
can prove that when it misbehaves, nothing reaches the user. Stating the goal
this way is what makes it achievable.

### Layer 1 — adversarial stage-3 fixtures (**the CI gate**)

Hand-written model outputs, each attempting one attack: a fabricated record ID;
a real ID outside the candidate set; Arabic in a framing; Arabic in the summary;
a grading claim; a unanimity claim; an over-length summary.

Paired with them, the **collision cases that must pass**: a framing citing
"Sahih al-Bukhari 2866", and one naming al-Ḥasan al-Baṣrī. These exist because
the naive grading guard rejects both (§5), and a guard that suppresses correct
output fails as surely as one that admits wrong output.

No model call — these are synthetic. **Stage 4 must block 100% of them, and CI
fails otherwise.** Same shape as the existing false-verification gate.

**The gate must also fail if a fixture that ought to pass is blocked.** Without
that, the guards could be satisfied by blocking everything, and the gate would
read green while Ask returned nothing. This branch has already shipped two
Criticals through a gate blind to a defect class; the counter-test is cheap.

### Layer 2 — recorded-response fixtures

Real Claude and Voyage responses captured once and replayed, so CI needs no
key. Exercises stages 0, 2, 4 and 6 against realistic output.

### Layer 3 — live smoke tests, outside CI

A small set run with real keys before a release. Recorded fixtures cannot catch
the model changing behaviour underneath us.

### Tracked, not gated

Abstention rate. Too low means overreach, too high means useless, and no
threshold between them is defensible as a build failure. Reported each run.

---

## 11. Interaction with the corpus size ceiling

`data/sanad-quran.db` is 57 MB, of which roughly 70% is derived data. Six
collections would approach 220 MB, past GitHub's 100 MB hard per-file limit.

Stage B makes this **marginally** worse: binary vectors add about 1.7 MB. That
is deliberate — it is why binary was chosen over int8's 13.7 MB.

The fix (external-content FTS; deriving norms, indexes and FTS at image build
rather than committing them) is scheduled with Stage A3, not here. One
constraint it must respect, recorded now because it is easy to get wrong:
**the derive step must run at image build, not first request** — Vercel's
filesystem is read-only at runtime, so a first-run derive would pass locally and
fail only on deploy. Note also that vectors are **not** derivable offline (§3.3)
and stay committed regardless.

---

## 12. Out of scope for Stage B

Named so the boundary is explicit rather than ambiguous.

- **Urdu translation ingestion.** Corpus work; grouped with Stage A3. Ask is
  written language-agnostically and picks Urdu up when it lands.
- **The madhhab panel.** `DISPUTED` questions get their label and a brief.
  Presenting multiple positions with their evidence is a separate feature.
- **Sahih Muslim and the four Sunan.** Stage A3.
- **German and Spanish translations.** No licensable source identified
  (`docs/GAPS.md` §1).

## 13. Departures from `2026-09-19-sanad-design.md` §8

| §8 said | This spec says | Why |
|---|---|---|
| Generator composes an answer; Arabic quotes copied from evidence | Model never emits Arabic; server renders from DB | Structural beats policed (§1) |
| Six stages | Seven — query expansion added | Non-Arabic questions cannot otherwise reach Arabic-only hadith |
| Verifier re-runs the Verify engine over generated Arabic | No generated Arabic exists to verify; stage 4 checks IDs, script, grading, unanimity | Follows from §1 |
| Madhhab panel for `DISPUTED` | Out of scope | Separate feature (§12) |
| Vector layer unspecified | Voyage `voyage-4`, binary, committed artifact | Anthropic offers no embedding model; reproducibility exception documented (§3.3) |

## 14. Known limits

1. **Framing fairness has no hard guard** (§5). The strongest statement Sanad
   can make is that the quotations are guaranteed and the framing is reviewed.
2. **Hadith reach non-Arabic speakers only through model-written explanation.**
   No licensed translation exists. The explanation is labelled, but a reader may
   still treat it as authoritative.
3. **Two external dependencies.** Ask needs Anthropic and, for full retrieval,
   Voyage. Either can rate-limit mid-demonstration. Verify needs neither.
4. **Vectors are not reproducible** from pinned sources (§3.3) — the only part
   of the corpus that is not.
5. **`DISPUTED` is labelled, not explained** until the madhhab panel exists.

## 15. Open decision

**Public demo key exposure.** Ask needs an Anthropic key, and the hosted demo
needs one to be usable by a reviewer who will not paste their own. The spend
cap, request limit and abuse posture are unresolved and must be settled **before
the demo is public**, not at build time. Recorded here so it is not discovered
at launch.

## 16. Repository layout

```
api/sanad/
  retrieve/   FTS5, vector search, RRF fusion
  agents/     query expansion, select-and-frame, audit
  pipeline/   orchestration, guards, adjudication, SSE
ingest/sanad_ingest/
  embed.py    explicit vector generation; the only thing needing a Voyage key
eval/
  cases/ask/  adversarial stage-3 fixtures, recorded responses
web/src/
  screens/Ask.tsx
  components/PipelineTrace.tsx, EvidenceBrief.tsx, AskComposer.tsx
```
