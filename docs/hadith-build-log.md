# Hadith corpus build log

The decision and defect record for Stage A2, the ingestion of Sahih al-Bukhari
into Sanad's corpus. Written as the work happened, over ten tasks, a
whole-branch review and two fix rounds.

It is kept because the interesting part of this build was not the code. Every
serious defect here was found by measuring rather than reading, several were
found *after* a green test suite, and a handful of the tests written to catch
them turned out to be incapable of failing. Five more collections are still to
be ingested and they will meet the same hazards, so the reasoning is worth more
than the diff.

Entries marked `R<n>` are rulings: a decision, its reason, and what it costs if
it is wrong. They are numbered in the order they were made and are not
retracted when they turn out wrong — R13 and R20 were both overturned, and the
argument that overturned them is recorded in place rather than replacing them.

This file was produced from the build ledger verbatim. It is a working record,
not a polished narrative, and it says where it is uncertain.

Spec: docs/superpowers/specs/2026-09-22-hadith-corpus-design.md (read; binding authority)
Worktree: /home/gulzara1/p-app/sanad/.claude/worktrees/stage-a-deterministic-core
Branch: worktree-stage-a-deterministic-core
Base: f4a4ed3
Baseline at start: 257 Python tests pass, 85 web tests pass.
Source file: /tmp/bukhari.txt (backup /tmp/bukhari-keep.txt)
  sha256 69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7

## Pre-flight scan

### Cross-task pairs (shared file or interface)

| Pair | Produces → Consumes | Finding |
|---|---|---|
| 1 → 4 | `LockedSource.{commit,expected_records}` → build enforces count | OK |
| 2 → 4 | `HadithUnit.{record_id,hadith_no,kitab_no,bab_ar,isnad_ar,matn_ar}` → `_hadith_records` | OK; `kitab_ar`/`is_repeat` unconsumed — **R1** |
| 2 → 9 | noise report → eval-case selection | OK |
| 3 → 4 | `Record.isnad_ar` → build | OK |
| 3 → 7 | `Record.isnad_ar` → `RecordOut` | OK |
| 4 → 5,6,9 | built corpus → engine/reference/eval tests | OK |
| 5 → 6 | `HadithReference.hadith_no` (str) vs `Record.hadith_no` (TEXT) | OK — types agree |
| 6 → 9 | verdicts → eval expectations | OK |
| 7 → 8 | `RecordOut.{isnad_ar,collection,hadith_no}` → regenerated `types.ts` | OK |

### Per-task internal consistency

| Task | Finding |
|---|---|
| 1 | **CONFLICT — R2**: `_REQUIRED` in lockfile.py includes `expected_lines`; the Bukhari entry supplies `expected_records` instead, so `load_lockfile` would reject it. |
| 2 | Self-consistent. Test derives expected text by an independent path (string replace on the raw slice) from the parser's line walk, so it is a genuine cross-check, not a tautology. Residual: **R3** (`~~` join rule). |
| 3 | Self-consistent. |
| 4 | **CONFLICT — R4**: plan's test calls `build_corpus(db, only_sources=[...])`; the real signature is `build_corpus(lockfile, out_db, cache_dir)`. |
| 5 | **DEFECT — R5**: `_COLLECTIONS` dict is defined but the regex hardcodes bukhari — dead code in the plan's own implementation block. |
| 6 | Self-consistent. |
| 7 | **DEFECT — R6**: `test_no_grading_is_ever_returned` forbids the substring `"authentic"`, but the new `CORPUS_SCOPE` contains "authentic and simply outside…". It also forbids `sahih"`, while every hadith's `reference_display` is "Sahih al-Bukhari N". The test as written cannot pass. |
| 8 | Consistent. 85 + 4 new = 89. |
| 9 | **CONFLICT — R7**: YAML uses `expect_scope_caveat`, `expect_handoff`, `expect_no_verdict`, `expect_not_verdict`; `eval/runner.py`'s `Case` supports only `expect_verdict`, `expect_record`, `expect_claim`, `expect_risk` (+ `rationale`). `expect_not_verdict: NEAR_MATCH_TO_OTHER_RECORD` is not a verdict at all. |

## Rulings

Ruling: R1 — `reference_display` must disambiguate records that share a
printed number. Two records both rendering "Sahih al-Bukhari 619" while
carrying *different text* (27 degrees vs 25) is the duplicate-verse problem
Stage A solved with `also_at`, reappearing. The mukarrar variant renders
"Sahih al-Bukhari 619 م"; a bare collision (3905) renders "Sahih al-Bukhari
3905 (2)". This also makes `is_repeat` load-bearing rather than parsed-then-
discarded. Cost if wrong: a slightly unusual citation string on 6 of 7,129
records.

Ruling: R2 — `expected_lines` becomes conditional, not unconditionally
required. Formats `xml` and `txt-2` require `expected_lines`; format
`openiti-markdown` requires `expected_records`. Enforced per-format rather
than by making both optional, because an unchecked count is how a truncated
download would pass silently. Cost if wrong: one more branch in the loader.

Ruling: R3 — the `~~` continuation joins with a SPACE, not empty string.
Measured: joining empty produces "عنعائشة" and "صلاةالجماعة" (two words run
together) in real records, so empty-join is demonstrably wrong. The
implementer must additionally verify hadith 1's assembled matn reads as the
known text of *innamā al-aʿmālu bi'l-niyyāt* before accepting the rule.
Cost if wrong: if OpenITI ever splits a word across a `~~` boundary, that word
gains a spurious space; the noise report would not catch it, so the
verification against a known text is the real guard.

  R3 RESOLVED by the controller before Task 2 was dispatched, so the
  implementer does not have to guess. Measured against the real file:
  in the raw bytes a continuation is `line1\n~~line2`, so the newline is
  already the separator and `~~` is merely a marker. A line-based parser that
  joins `line[2:]` fragments with `""` destroys that separator (producing
  "عنعائشة", "صلاةالجماعة"); joining with `" "` restores it. Verified
  end-to-end: hadith 1's space-joined matn contains the canonical opening
  "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى" exactly, and space-join and
  newline-preserving reads agree at 72 tokens. Space-join is correct.

Ruling: R4 — Task 4's tests call the real signature
`build_corpus(lockfile, out_db, cache_dir)` and assert against the full built
corpus rather than a source-filtered subset. Adding an `only_sources`
parameter purely to make a test convenient is production code shaped by test
convenience. Cost if wrong: Task 4's tests build the whole corpus and so run
slower.

Ruling: R5 — delete the `_COLLECTIONS` dict from Task 5. One collection
ships; the regex names it directly. Reintroduce a table when a second
collection lands. Cost if wrong: a tiny refactor when Muslim is added.

Ruling: R6 — Task 7's no-grading test asserts on STRUCTURE, not substrings.
It asserts the response exposes no `gradings`/`grade` key on any record, and
that the `gradings` table is empty. Substring bans are unworkable here:
"Sahih" is in the collection's own title and "authentic" is in the corpus-
scope caveat, so the test as written forbids the correct output. The
user-facing "does not grade authenticity" copy is covered by Task 8's
`no-grading` test. Cost if wrong: a response could theoretically carry grading
vocabulary in free text; nothing in the code path generates free text.

Ruling: R7 — Task 9's cases use only the existing Case schema
(`expect_verdict`, `expect_record`, `expect_risk`, `rationale`). Dropped:
`expect_scope_caveat` (the caveat is response-level and is already asserted in
Task 7), `expect_handoff`/`expect_no_verdict` (both implied by
`expect_risk: PERSONAL_RULING` plus the runner's existing false-verification
gate), and `expect_not_verdict` (not a verdict; the real requirement is
"must not match a different record", which `expect_record` expresses when a
verdict is produced). Extending runner.py's schema to host four new
assertion types is scope creep into Stage A's eval harness. Case 8's measured
verdict is pinned once observed, with its rationale recorded. Cost if wrong:
one fewer machine-checked assertion on the handoff case, which Task 8's
frontend test and Stage A's 35 existing cases already cover.

---

## Task log

Task 1: implemented (commit b4bbc04, 259 passed + 1 xfailed, ruff clean).
  R2 applied as per-format enforcement. `gh` auth failed with 401 (stale
  token, not the rate limit I predicted), so the commit pin was omitted per
  the authorised route: `master` URL, TODO in the lockfile, and an
  `xfail(strict=True)` test so the gap fails loudly the moment someone fills
  the pin in without converting the test back.

Task 1: review found one Critical — the R2 enforcement had NO test. The
  reviewer deleted the entire enforcement block and `tests/ingest/` passed
  68/68 unchanged. The twelfth instance of this project's signature defect,
  and the first inside a guard added by a controller ruling in the same
  session that ruled it. Worth noting: the ruling specified behaviour but not
  its negative test, and that gap is where the hole appeared.

Task 1: fix round 1/5 (2 addressed, 0 open — negative tests for both arms of
  the per-format rule, plus the misleading test name; commits
  b4bbc04..db8eeb9). Mutation verified twice independently: implementer saw
  "2 failed ... DID NOT RAISE LockfileError" with enforcement removed; the
  re-reviewer repeated the mutation itself and observed the same, then
  confirmed the tree byte-identical afterwards.

Task 1: minor (deferred): commit pin is still a branch URL, not a SHA. Real
  reproducibility debt, visible via the xfail. Needs a working `gh auth
  login` or a manual SHA from the file's History page.

Task 1: DEBT RESOLVED — Adnan ran `gh auth login`, so the pin is now known
  and VERIFIED, not merely looked up:
    commit 47dfd28db9e158c7101c7df1162d4dc99bb70303 (2025-11-27, "ns update")
  Fetched the file at that exact ref via `gh api ... -H "Accept:
  application/vnd.github.raw"` and hashed it: it is byte-identical to the
  measured download (both
  69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7, both
  5,524,762 bytes). So the pin points at the bytes the corpus was built from,
  which is the property that actually matters — a SHA that resolved to
  different content would be worse than no SHA.
  NOT APPLIED YET: Task 2's implementer is live on this branch and the skill
  forbids concurrent implementers. Apply as a small dispatch once Task 2
  completes — set `commit`, swap the `master` URL for the pinned one, drop
  the lockfile TODO, and convert the `xfail(strict=True)` test into a real
  passing assertion (strict means it will fail loudly if only the pin is
  filled in and the test is left alone, which is the behaviour we wanted).

Task 1: DEPENDENCY FOR TASK 4 — `fetch.py`'s `fetch_source` compares
  `verse_count != src.expected_lines` unconditionally, which is `None` for
  Bukhari and so always mismatches, and `parser_for("openiti-markdown")`
  raises `ValueError` before that. Correctly out of scope for Task 1 (no test
  drove it); Task 4 MUST fix both or it cannot build.

Task 1: complete (commits f4a4ed3..db8eeb9, review clean)

Task 2: implemented (commit 9ab7b2d, 272 passed + 1 xfailed, ruff clean).
  Parser hit 7,129 on the nose and matched every measured fact. Reviewer
  re-ran it independently and confirmed: 7,129 records, the 4 unmarked hadith
  exactly (2795/6964/6965/6966), `is_repeat` correct on all 5 duplicate
  numbers, zero leaked markers across all records, and no altered letters.
  It further verified the central invariant by extracting all 1,261
  `@QB@…@QE@` spans inside hadith across 716 records and confirming every one
  survives verbatim in stored text with markers gone.

  The implementer modified one brief-given test and flagged it rather than
  quietly shipping it. My hypothesis (that the offending `@QB@` sat on
  numbered bab units, so the fix would not address the stated cause) was
  WRONG for the fixture: the reviewer checked and the fixture's first `@QB@`
  genuinely is on a `### ||` line. The change was honest and the test still
  fails when the ayah text is deleted.

Task 2: review found 2 Important, 5 Minor, 0 Critical. Important 1 is the
  notable one: the report claimed "zero noisy records" as the justification
  for writing no test for the noise scan — there are actually 9. The parser
  was right; the verification claim was false, and it left a spec requirement
  (§10 flag-never-correct) with no coverage. The recurring shape here is not
  bad code, it is confident unverified claims about code.

Task 2: fix round 1/5 (2 Important + 3 Minor addressed, 0 open; commits
  9ab7b2d..2accd8d, 278 passed + 1 xfailed). Re-reviewer verified
  independently: ran both the old and new parser side by side over the full
  file — same 7,129 ids, **0 diffs in matn_ar, 0 diffs in isnad_ar**, changes
  confined to kitab_ar/bab_ar as intended. Mutation-tested the heading
  assembly (4 tests failed, 563 unbalanced vs expected 12), restored, tree
  clean.

  Implementer declined to write the literal "no bab_ar is unbalanced" test
  because 12 headings genuinely never close their paren in the source, and
  wrote a bounded-count test instead. Correct call — asserting something
  false about the source would have forced a fix that corrupts the text. The
  re-reviewer independently recounted from raw source and confirmed 12.

Ruling: R8 — `kitab_ar` has the same truncation defect as `bab_ar` (17 of 100
  headings), found during the fix and left unfixed. Deferring it: Task 4's
  record mapping stores `book_no` and `chapter_ar` but NOT the kitab name, so
  nothing downstream consumes `kitab_ar` and the defect is invisible to the
  product. Revisit only if a later task starts displaying book names. Cost if
  wrong: if someone surfaces `kitab_ar` without checking, 17% of book names
  render truncated — hence this ledger entry.

Task 2: complete (commits db8eeb9..2accd8d, review clean)

Task 3: implemented (commits c838f6c + 5244fb2, 281 passed, 0 xfailed, ruff
  clean). Two pieces: the verified commit pin (closing Task 1's debt, xfail
  converted to a real passing assertion rather than deleted) and the
  `isnad_ar` column.

  Unplanned but correct: adding the column broke 53 tests, because
  `data/sanad-quran.db` is a git-tracked prebuilt corpus and
  `CREATE TABLE IF NOT EXISTS` does not retrofit columns. The implementer
  rebuilt the DB from cached sources and bundled it into the schema commit.

Task 3: review clean — no Critical, no Important, no Minor. Independently
  confirmed: `isnad_ar` is NULL for all 6,236 ayah rows; it appears nowhere in
  `rebuild_fts`, the FTS virtual table, `engine.py` or `routes.py`, so it is
  stored and never scored exactly as designed; old vs new DB both hold 6,236
  ayah records with byte-identical sampled verse text and zero hadith.
  Mutation-tested by dropping `isnad_ar` from `_RECORD_COLS` (test failed),
  restored, tree clean.

  Stale-hash question resolved, and it matters for the product's core claim:
  `tests/api/test_routes.py` computes the corpus hash DYNAMICALLY from the
  live file rather than asserting a literal, so the rebuild broke nothing. The
  only literal hashes in the repo are mocked fixture data in web component
  tests against a stubbed fetch. Reproducibility claim intact.

  Reviewer's judgement on bundling the rebuilt binary into the schema commit:
  acceptable, because splitting it would leave an intermediate commit whose
  checked-in DB does not match its own schema. Agreed.

Task 3: complete (commits 2accd8d..5244fb2, review clean)

Task 4: review agent ran 57+ min without reporting and was stopped. Its
  headline question gates the rest of the plan, so the controller measured it
  directly instead of waiting:

    hadith records                                   7129
    matns containing a narration verb                 540   (impl. reported 305)
    sample N=25, quoting ONLY the primary matn:
       >=0.86 (verifies)                                1
       0.60-0.86 (near/miss)                           15
       <0.60 (NOT_FOUND)                                9
    trailing-chain fraction of stored text  median 0.38, max 0.91
    empty/whitespace matns                              6

  The 540 vs 305 gap is regex breadth: the implementer matched حدثنا/أخبرنا,
  the controller also حدثني/أخبرني/حدّثنا. 540 is the correct figure.

  This is CRITICAL, not the "modest degradation" the report implied. 7.6% of
  Bukhari is unmatchable the way people actually quote it -- one of 25 sampled
  records verifies, nine return NOT_FOUND.

Ruling: R9 -- the `*` boundary is necessary but NOT sufficient. The al-Bugha
  edition appends secondary narrations after the primary matn, and marks each
  with an attribution the parser can see: `قال <name>` / `وقال <name>`
  immediately preceding a narration verb (حدثنا/حدثني/أخبرنا/أخبرني).
  Measured examples: h:10 `...ما نهى الله عنه | قال أبو عبد الله وقال أبو
  معاوية حدثنا داود...`, h:22 `...في جانب السيل | قال وهيب حدثنا عمرو...`,
  h:40 `...أنكروا ذلك | قال زهير حدثنا أبو إسحاق...`.

  So `text_ar` must hold exactly ONE narration's matn -- the primary. Trailing
  secondary material is preserved verbatim in a NEW display-only, unscored
  column `addenda_ar`. It is never discarded, and never merged into
  `isnad_ar`: that column means *chain*, the trailing material is chain plus
  variant matn, and quietly mislabelling it is the exact class of defect this
  project keeps catching. This does NOT violate the spec's "never guess a
  boundary the source does not mark" -- the source marks it, just not with
  `*`. Where no attribution is visible, no cut is made.
  Cost if wrong: an over-eager cut truncates genuine matn, which is worse than
  the bug being fixed -- hence the mandatory measurement and the requirement
  that a cut never leaves a primary shorter than the addendum it removed
  without being counted and sampled.

Ruling: R10 -- 6 records carry an empty/whitespace `text_ar` (218, 1620, 3584,
  4063, 5833, 6050). Their `isnad_ar` runs right up to `قال` with the
  prophetic words missing, so the matn is being dropped, not absent. An empty
  scored text is a live verification hazard, not cosmetics. Root cause must be
  found in the raw file; zero empty matns is the acceptance bar, and if the
  source genuinely has none for some unit, that unit is flagged and excluded
  rather than stored empty.

Task 4: fix round 1/5 (commits 066f4b0, 7d97313; 319 pytest + 85 vitest pass,
  ruff clean apart from a PIE810 pre-existing at 6dd7350). 155 records cut:
  on those 155, scoring goes 9/65/81 EXACT/NEAR/NOT_FOUND -> 155/0/0. Empty
  scored texts 6 -> 0. Record ids, reference_display, bab_ar, kitab_ar
  byte-identical across all 7,129 units; removed text byte-identical in
  addenda_ar; addenda_ar absent from rebuild_fts, the FTS table, engine.py and
  routes.py. Build deterministic over two runs.

  Implementer declined the bare-verb fallback (pre-authorised) after measuring
  2943 and 3723 as prophetic speech containing a narration verb, and deviated
  on R10: nothing is excluded, the build now raises BuildError on any empty
  scored text and the three units join the unmarked set (4 -> 7).

Ruling: R11 -- the R10 exclusion instruction was wrong and the implementer was
  right to refuse it. The only deterministic signal fires equally on 218/1620
  (bare chains) and 5833 (a real matn in front of a misplaced `*`), so
  excluding on it would delete a genuine hadith. Failing the build loudly is
  strictly better than silently dropping text. R10's exclusion clause is
  withdrawn; its zero-empty-matns bar stands and is met.
  Cost if wrong: a future source with a genuinely matn-less unit fails the
  build instead of ingesting -- a loud, cheap failure.

Task 4: controller review of fix round 1 -- NOT accepted, round 2 dispatched.
  Measured the residual myself rather than trusting the round-1 framing:

    uncut records still containing a narration verb              393
    sample N=25 of those, quoting only the primary matn:
       >=0.86 verifies      7
       0.60-0.86 near      12
       <0.60 NOT_FOUND      6

  18 of 25 still fail. The defect is reduced, not resolved.

Ruling: R12 -- the detection is anchored on the wrong signal. Requiring a
  backward `قال <name>` attribution suppresses the fix:

    uncut with narration verb                                    393
      verb FOLLOWED by chain material within 40 chars            303
      AND also preceded by قال/وقال/فقال <name> [و|ف]             21

  ~282 marked secondary narrations are invisible to the round-1 rule, missed
  on nothing more than a trailing particle or a prefix -- 621 (`قال شعيب و`),
  3896 (`قال هشام ف`), 1663 (`فقال`), plus fresh full chains at 3400 and 5989
  with no attribution at all.

  What discriminates a secondary chain from genuine matn is what FOLLOWS the
  verb -- a narrator name, عن, بن/ابن, another narration verb -- not what
  precedes it. The implementer's own strongest counterexample proves it: 1098
  is `حدثني بأرجى عمل عملته`, the Prophet telling Bilal *tell me the deed you
  most hope for*, where حدثني is followed by a prepositional phrase and a
  forward test excludes it automatically. So: cut on the forward signal, and
  where an attribution immediately precedes, cut before it so it travels with
  the addendum it introduces.
  Cost if wrong: genuine matn truncated, which is worse than the bug -- hence
  the unchanged requirement to measure, to sample 25 cuts uncurated, and to
  implement only the subset that can be defended.

  Accepted without revisiting: BuildError over exclusion (R11), the 9 -> 72
  noise count pinned by a characters-still-present test, `%`/`(`/`)` surviving
  into scored text under the no-normalisation rule, and the stop-list sha256
  tripwire. Carried into round 2: mutation-test the two assertions the
  implementer flagged as untested (Concern 7).

Task 4: fix round 2/5 (commit feda861; 330 pytest + 85 vitest pass, ruff clean
  apart from the pre-existing PIE810). R12 confirmed correct by the
  implementer's own measurement: re-checked against a forward test, 2943, 3723,
  1098 and 50 are all excluded automatically with no special case. Cuts
  155 -> 395, every round-1 cut preserved (2487 moves to an earlier,
  better-marked boundary). On the 240 new cuts the primary scored
  17 EXACT / 93 near / 130 NOT_FOUND before and 395/395 EXACT after;
  verify_spans returns EXACT on all 395. matn+addenda byte-identical to round 1
  for 7,128 of 7,129 units. The proclitic fix (wa-/fa- before the verb) is what
  unlocked 621 and 3896. Three of sixteen mutations survived first pass and
  each was answered with a new test.

Controller verification of round 2, measured independently rather than taken
  from the report:

    cut records                                                  395
    empty scored texts                                             0
    uncut records whose matn holds a narration verb              153
      ... of those, verb FOLLOWED by chain material               42

  42 of 7,129 (0.6%), down from 540. Accepted as a documented limitation.
  Note the report said 121 uncut-with-verb where the controller measures 153 --
  regex breadth again (حدّثنا/حدثني/أخبرني). The figure that matters, 42, is
  the chain-followed subset and is not in dispute.

Ruling: R13 -- a CRITICAL predating both fix rounds, found while verifying
  round 2. Eleven records carry a matn that is an editorial back-reference
  rather than a text (بهذا، بذلك، مثله، نحوه، بنحوه), plus abridgements where
  the edition prints one word and cross-references elsewhere (1915 التمسوا،
  3777 بايعوني، 3957 ذكر القصة). They are scored like any other record, so:

    'The scholar said «بهذا» in his lecture.'  -> EXACT 1.0  Sahih al-Bukhari 1379
    'He narrated «مثله» to us.'                -> EXACT 1.0  Sahih al-Bukhari 3457
    'The Prophet said «نحوه» here.'            -> EXACT 1.0  Sahih al-Bukhari 2483

  بهذا is an Arabic commonplace meaning "with this". Sanad manufactures a
  Bukhari citation for it with full confidence. Fabricating a citation out of a
  common phrase is the precise failure this product exists to prevent.

  Ruled: a matn that is an editorial pointer or abridgement is not an
  independently quotable text and must not be scorable -- excluded from
  rebuild_fts, the FTS table and the fuzzy candidate set, exactly as isnad_ar
  and addenda_ar are. It keeps its id, reference_display and display, and stays
  reachable by reference lookup. Nothing is deleted.

  Detection is an AUDITED CLOSED LIST, not a heuristic, and explicitly not a
  length floor: الحرب خدعة (10 chars) and انشق القمر are genuine and must keep
  verifying, and Qur'anic records go down to 2 chars (طه). Each short candidate
  is read in the raw source and classified, genuine ones recorded too.
  Cost if wrong: an over-broad list silently makes real hadith unverifiable --
  the mirror of the bug -- hence the mandatory الحرب خدعة and طه regression
  tests.

  Controller checked the raw source directly and confirmed there is NO
  truncation bug behind the one-word matns: the file really reads
  `* بايعوني \ 1 \`. Told the implementer so, to stop it re-deriving.

Task 4: fix round 3/5 (commits 131420c, 9adf835; 341 pytest + 85 vitest pass,
  ruff clean apart from the pre-existing PIE810; 13 mutations applied, 13
  killed). `records` gains `unscorable_reason TEXT`. A reason excludes the
  record from rebuild_fts -- hence the FTS table and the fuzzy candidate set --
  and from engine._exact_at_tier, which reads `records` directly and was the
  tier actually emitting the false EXACT 1.0. The audited list lives in
  openiti._UNSCORABLE as record_id -> (sha256-of-matn, reason), so a changed
  matn under a listed id stops the build rather than carrying the old
  judgement forward.

  The audit: four scans over all 7,129 units, then every matn <=24 chars (92)
  read in the raw source. 17 excluded -- 11 pointers, 2 bare incipits
  (1915, 3777), 3 deferrals (335, 3801, 3957), 1 tahwil fragment (237).
  Criterion: no complete proposition of the narration remains. Every excluded
  record's content survives elsewhere as a scorable matn (237's story is at
  3641). DB rebuilt, sha256 0c95f832..., reproduced byte-identically.

Controller verification of round 3, measured independently:

    unscorable records                                            17
    total records                                              13365
    hazard probes بهذا/مثله/نحوه/بذلك/بايعوني/التمسوا/ذكر القصة
                                        all NOT_FOUND (0.03-0.25)
    الحرب خدعة / انشق القمر / مطل الغني ظلم / كل معروف صدقة / طه
                                        all still EXACT 1.0
    excluded records resolving via get_record                  17/17
    verbatim-quote regression, hadith                          60/60 EXACT
    verbatim-quote regression, ayah                            40/40 EXACT

  Both directions clean. Round 3 accepted.

Ruling: R14 -- the 17 unscorable records also drop out of GET /search, which
  shares the FTS index. The implementer flagged this as beyond spec and
  unspecified either way. Ruled correct and intentional: a text that cannot be
  verified against should not be offered as a search result either, or the
  product invites the user to quote something it will then refuse to confirm.
  Cost if wrong: 17 of 13,365 records are reachable only by reference lookup,
  not by search -- recorded here so it is a known trade, not a surprise.

Ruling: R15 -- concerns 2, 3, 4 accepted without further rounds. The audit's
  completeness is unprovable (a pointer-shaped matn longer than 24 chars using
  unscanned vocabulary would not have surfaced); the 335-vs-4674/587/6655 line
  is a syntactic judgement, though all three kept records are measured
  non-hazards at 0.52/0.63/0.83 NOT_FOUND; and pinning the digest of the
  *parsed* matn couples the audit to the parser, which is the safe direction.
  Cost if wrong: a missed pointer keeps one false-EXACT path open -- bounded,
  since every known hazard phrase is now measured NOT_FOUND.

  Note for the record: a third consecutive round turned up a test that could
  not fail -- the first Qur'an guard queried kind='quran' where Qur'anic rows
  are stored as 'ayah'. Mutation design caught it. That is three rounds, three
  incapable-of-failing tests found only by mutation.

Task 4: fix round 4/5 -- concern 5 closed (commit a5d91e9). _hadith_records now
  raises BuildError naming every _UNSCORABLE id absent from the parsed records,
  so a future edition dropping a listed id fails the build instead of leaving a
  silently unused entry. 342 pytest + 85 vitest, 2 mutations applied and killed.

Task 4: fix loop COMPLETE. Independent review of the full range
  6dd7350..a5d91e9 was dispatched (review package
  review-6dd7350..a5d91e9.diff already generated) and then STOPPED when the
  session paused. NOT YET REVIEWED -- re-dispatch it before Task 5.

  Its mandate, to reuse verbatim: skip the twelve things the controller already
  verified (listed above under "Controller verification of round 3") and spend
  the budget on (1) OVER-CUTTING -- an independent sample of >=25 of the 395
  cuts, chosen by the reviewer's own method, judging whether a complete
  narration remains; (2) whether addenda_ar or unscorable_reason can reach any
  scoring path, especially engine._exact_at_tier which reads `records` directly
  and was the real source of the false EXACT; (3) byte-level integrity of
  matn+addenda against the pre-cut text; (4) tests that cannot fail. Hard
  25-minute bound with partial reporting required -- the first reviewer on this
  task ran 57+ minutes and returned nothing.

SESSION PAUSED at Adnan's request, 2026-09-22. Resume at: re-dispatch the Task 4
  review, then Tasks 5-10 (citation parsing, cross-kind reference checking, API
  surface, frontend isnad + gradings, eval cases, docs). Nothing is pushed.

CORRECTION to the entry above: the review DID report before it was stopped.
  Report at .superpowers/sdd/2026-09-22-hadith-corpus/task-4-review-report.md.
  1 Critical, 2 Important, 3 Minor. Task 4 is NOT complete. Resume here.

  C1 (Critical) -- OVER-CUTTING, the exact risk the rounds were warned about.
  Hadith 342 and 3164 (the Isra'/Mi'raj narration) are cut MID-NARRATION, not
  between narrations. The rule fires on a sub-narrator's chain aside
  (`قال بن شهاب فأخبرني بن حزم…`) after which the SAME story resumes in the
  Prophet's first person (`قال النبي … ثم عرج بي`). ~712 and ~701 bytes move
  into addenda_ar: the fifty prayers, the returns to Musa,
  `هي خمس وهي خمسون لا يبدل القول لدي`, Sidrat al-Muntaha. Both sit UNDER the
  _MAX_ADDENDUM = 1000 cap that was supposed to catch precisely this, so the
  "clean distribution gap" that constant is justified by does not exist. R13's
  stated cost-if-wrong has materialised.

  I1 (Important) -- the cut MANUFACTURES NEW false EXACTs. Verified by running
  verify_spans: `مر النبي صلى الله عليه وسلم برجل` -> EXACT 1.0 Bukhari 632,
  and `كان للنبي … ناقة` -> EXACT 1.0 Bukhari 6136. Root cause: round 3's audit
  read window was 24 characters, sized against the PRE-cut corpus and never
  re-widened after 395 cuts created new short primaries. So R13's audit must be
  re-run over the post-cut distribution, not merely extended.

  I2 (Important) -- addenda_ar and unscorable_reason never reach RecordOut, so
  "stored and displayed" is false; they are stored and invisible. Affects
  Task 7/8's API and frontend surface.

  Verified clean by the reviewer: no leak into any scoring path; 13,365 records
  / 13,348 FTS rows / 17 excluded, arithmetic closes; all 7,129 units
  byte-identical between parser output and the shipped DB.

  Reviewer's honest limits: 29 of 395 cuts read in Arabic (7%), own
  stratification, 5 checked against raw source; short-primary probe exhaustive
  (24/24); mutation evidence for only 1 of 12 tests because that work was still
  running when the session paused; it flagged its own reconstruction check as
  buggy and discounted it.

  NOTE: stopping the reviewer left a mutation applied to the working tree
  (_MAX_ADDENDUM 1000 -> 2000). Reverted; tree clean at a5d91e9. Check for this
  whenever a mutating reviewer is killed mid-run.

  Resume plan: fix round 5/5 on C1 + I1 + I2, then a fresh scoped re-review
  covering the over-cutting sample and the mutation work that did not finish.

SESSION RESUMED 2026-09-23.

Ruling: R16 -- stop trying to perfect the boundary detector; make the product
  stop depending on it. Three rounds have now tuned that heuristic and the
  review still found it firing mid-narration. Confirmed C1 in product terms
  before ruling:

    hadith 342, quote the primary matn        -> EXACT 1.0  Sahih al-Bukhari 342
    hadith 342, quote the FULL printed hadith -> NOT_FOUND 0.64

  Quoting the whole hadith as the edition prints it is the most natural thing a
  person can do with the Isra'/Mi'raj narration, and the cut broke it.

  Ruled: score TWO representations per record -- the primary matn AND the full
  printed text (matn + addenda) -- both resolving to the same record and the
  same reference_display. Record count is unchanged; only the index gains rows.
  This makes the detector's precision non-load-bearing: over-cut and under-cut
  both stop costing a verification. Also: refuse cuts that leave a stub primary
  (a measured floor, not a round number -- this is what should have caught I1's
  632 and 6136), re-run R13's pointer audit over the post-cut length
  distribution, and surface addenda_ar/unscorable_reason in RecordOut so
  "stored and displayed" stops being half true.
  Cost if wrong: two indexed representations per hadith enlarge the FTS table
  and could let one record surface twice in also_at or the quotation list --
  called out in the brief as a thing to prevent explicitly.

  Hypothesis tested and REJECTED by the controller before dispatch, recorded so
  nobody rebuilds it: "the name at the cut point already appears in this
  record's own isnad" does NOT discriminate an internal aside from a genuine
  secondary narration. It flags 57 of the 395 cuts, including hadith 40, which
  earlier rounds verified as a genuine secondary narration.

Task 4: fix round 5/5 dispatched to a FRESH implementer (skill: rounds >=4 use
  a new agent on a more capable model). Brief at task-4-fix-5-brief.md.

Task 4: fix round 5/5 (commit 610aa22; 375 pytest + 85 vitest, tsc clean, ruff
  unchanged at 12 pre-existing; 23 mutations applied, 23 killed -- the four that
  survived the first pass were answered with three new tests and a replaced
  assertion). R16 implemented: two scored representations per record.

  Implementer's own corpus-wide verification: 342 and 3164 EXACT in both
  directions; 383 cut records x 2 = 766/766 EXACT; 7,112/7,112 scorable hadith
  primaries; 6,236/6,236 Qur'an; all four I1 stubs NOT_FOUND with the whole
  hadith still EXACT; index arithmetic 13,348 + 383 = 13,731; DB sha256
  17f4ea48...

Controller verification of round 5, measured independently:

    342 / 3164, primary matn                     EXACT 1.0  (both)
    342 / 3164, full printed hadith              EXACT 1.0  (both)
    342 full text -> quotations returned                 1  (no double-report)
    I1 stubs 632 / 6136                          NOT_FOUND (0.46 / 0.59)
    primary verbatim, corpus-wide              7112/7112 EXACT, 0 failures
    full-text verbatim, corpus-wide              383/383 EXACT, 0 failures

  Counts reproduce the report exactly. C1 and I1 closed; I2 done.

Ruling: R17 -- the stub-primary floor from R16 section 2 is withdrawn. The
  implementer measured _MIN_PRIMARY = 32 and then found, correctly, that no
  length measure separates a stub from a short matn in either direction. The
  evidence says it is actively miscategorising:

    "hazards" it suppressed, both genuine correct cuts:
      2390  من أعتق شقيصا من عبد   + fresh full chain حدثنا مسدد ...
      6949  لا يزال يلقى في النار  + same shape
    genuine short matns it cost standalone verification:
      1366  لا توكي فيوكى عليك
      2301  لا تلتقط لقطتها إلا لمعرف
      2405  لا أزال أحب بني تميم
      3179  لم يكذب إبراهيم إلا ثلاثا
      5526  أنه نهى عن خاتم الذهب

  So the floor costs seven real verifications and buys nothing: the cuts that
  are genuinely wrong (632, 6136) are already caught by the audited,
  sha256-keyed _NEVER_CUT list. That list judges MEANING, which is the only
  thing that works here -- R13 reached the same conclusion for the pointer
  records against the same temptation to use a length rule. Round 6 dispatched
  to drop the floor and let those nine cut, with any genuinely bad primary
  going on _NEVER_CUT individually, justified from the raw source.
  Cost if wrong: nine records gain a short scored primary; bounded, auditable,
  and pinned by the existing hazard-phrase and regression tests.

  Note this exceeds the skill's 5-round cap. Adjudicated rather than parked:
  five famous hadith left unverifiable is load-bearing for a verification tool,
  the change is small and well specified, and the mechanism already exists.

Open and deliberately not fixed: review Minor M1 -- chain residue stranded at
  the end of ~98 primaries. Display-only, no verdict effect. And concern 4,
  which is correct and expected: dual representation makes a wrong cut harmless
  for verification, not right -- 342 is still split mid-narration in what a
  reader sees, and Task 8's display work should present matn+addenda as one
  continuous text.

Task 4: fix round 6 (commit 96d592c). R17 implemented, _MIN_PRIMARY gone.
  Before removing it the implementer read all nine records in the pinned raw
  source: each is a genuine matn followed by a fresh complete chain, so none
  needed _NEVER_CUT. Best piece of evidence in the whole task -- 2390's own
  addendum ends `اختصره شعبة`, "Shu'ba abridged it", the edition stating that
  the short wording is deliberate. That is source-level confirmation, better
  than the controller's inference from the chain's shape.
  375 pytest + 85 vitest, tsc clean, 26 mutations applied and 26 killed
  (including M24, which reinstates a 32-char floor and is killed by both the
  parser and the build tests). DB sha256 d1b035af..., 13,365 records / 393 cut /
  392 variants / 13,740 FTS rows.

Controller verification of round 6, measured independently:

    لا توكي فيوكى عليك        EXACT 1.0  Sahih al-Bukhari 1366
    من أعتق شقيصا من عبد      EXACT 1.0  Sahih al-Bukhari 2390
    stub 632                  NOT_FOUND 0.46
    بهذا                      NOT_FOUND 0.22
    الحرب خدعة / طه           EXACT 1.0
    primary sweep           7112/7112, 0 failures
    full-text sweep           392/392, 0 failures
    records 13,365 | unscorable 17

Task 4: COMPLETE (commits 6dd7350..96d592c, six fix rounds, review findings
  C1/I1/I2 all closed and independently re-verified). Carried forward as known
  and documented, not defects to re-litigate: review Minor M1 (chain residue at
  the end of ~98 primaries, display-only) and the fact that a wrong cut is now
  harmless for verification but still wrong for display -- Task 8 should render
  matn + addenda as one continuous text.

Task 5: implemented (commits bc26dbd, 2771643; 386 pytest passed vs 383
  baseline, 85 vitest unchanged, ruff byte-identical to the 12-finding
  baseline). Parses Bukhari citations as their own reference family.

  Three concerns, all sound:
  1. Deviated from the brief's literal _HADITH_CITE regex, which contains a
     literal fullwidth colon U+FF1A -- confirmed by hexdump of the brief.
     Used the ： escape form per the module's own character-safety
     convention. That glyph is a character-in-transit defect in the PLAN, not
     the implementation. See [[sanad-character-transit-defect]].
  2. Mutation testing found TWO OF THE BRIEF'S OWN GIVEN TESTS were incapable
     of catching real bugs (wrong number in a kitab:hadith pair; an
     out-of-range citation surviving as a HadithReference) -- both only
     asserted the absence of a plain verse Reference. Supplementary tests
     added. Fourth time on this branch that mutation has caught this; the plan
     text is NOT a safe source of test quality.
  3. Broadening parse_references' return type broke its only consumer:
     verify_spans crashed with AttributeError 'HadithReference' object has no
     attribute 'surah' on realistic input. Fixed with a filter plus a
     regression test, going outside the brief's file list into engine.py.

Ruling: R18 -- concern 3's scope deviation is endorsed. Leaving a live crash in
  place to stay inside a stated file list is the wrong kind of obedience. The
  brief's file list is guidance for where work is expected, not a boundary that
  outranks shipping working code.

Controller verification of Task 5, measured independently:

    «الحرب خدعة» cited as (Bukhari 3030)  -> WRONG_REFERENCE, real ref 2866
    'Sahih al-Bukhari 342'                -> HadithReference 342
    'Bukhari 1:2'                         -> HadithReference 2  (hadith no.)
    'Bukhari 99999'                       -> not parsed
    'Muslim 12'                           -> not parsed (not in corpus)

Ruling: R19 -- gap found by the controller, fix round dispatched. Arabic-script
  hadith citations do not parse:

    'صحيح البخاري ٣٤٢'  -> []          should be HadithReference 342
    'الإخلاص ١١٢:١'      -> Reference   the Qur'an side already handles this

  This is an INCONSISTENCY, not a uniform limitation: a text written in Arabic
  gets its Qur'an citations checked and its hadith citations silently ignored,
  so no WRONG_REFERENCE is ever raised where one is due. The plan's Task 5 says
  nothing about Arabic-script citations -- a gap in the plan, not the
  implementation. Machinery already exists on the Qur'an path including
  Arabic-Indic digit handling and must be reused, not duplicated.
  Cost if wrong: a broader Arabic citation regex could produce spurious
  HadithReferences from ordinary Arabic prose mentioning البخاري -- hence the
  instruction to match the Qur'an path's existing conventions rather than
  invent looser ones.

Also on the branch: commit 3fd49e4, frontend only -- the two "broken" verdicts
  now use Arabic scribal marks (NEAR_MATCH † -> ٭ U+066D, WRONG_REFERENCE
  ‡ -> ؞ U+061E) so the verdict set is one typographic family. Sacred marks
  such as U+06E9 PLACE OF SAJDAH deliberately avoided for error states.
  Codepoints verified on disk after writing. Adnan chose this from options.

Task 5: Arabic-script citations added (commit 6c7ae4a; 399 pytest, +13 tests,
  85 vitest unchanged, ruff at the 12-finding baseline). All new branches
  mutation-tested, none found incapable of failing. Includes a confirmed-zero
  non-ASCII byte scan of references.py.

Controller verification of Task 5, measured independently:

    'صحيح البخاري ٣٤٢'      -> HadithReference 342
    'البخاري ٣٤٢'           -> HadithReference 342
    'رواه البخاري 342'      -> HadithReference 342
    'صحيح البخاري ۳٤۲'      -> HadithReference 342   (mixed digit scripts)
    'البخاري'               -> not parsed            (no false positive)
    'قال البخاري رحمه الله' -> not parsed            (no false positive)
    'المسلم ١٢'             -> not parsed

Task 5: COMPLETE (commits bc26dbd, 2771643, 6c7ae4a). Parsing scope is correct.

Task 6: dispatched with a controller findings file (task-6-findings.md) that
  outranks the brief. Three defects measured in the LIVE engine after Task 5
  landed -- none of them Task 5's fault, all of them exactly what Task 6 exists
  to fix:

  D1 (Critical) -- a Qur'anic citation attaches to a HADITH quotation:

    'The Prophet said «الحرب خدعة» (Bukhari 2866), and the Qur'an says
     «قُلْ هُوَ ٱللَّهُ أَحَدٌ» (112:1).'

      span='الحرب خدعة'   WRONG_REFERENCE  given_ref=112:1
      span='قل هو الله أحد' EXACT          given_ref=112:1

    The hadith is cited CORRECTLY -- الحرب خدعة really is Bukhari 2866 -- and
    Sanad tells the user their reference is wrong, because nearest_reference
    returns the Qur'anic 112:1 from the far end of the sentence while the
    adjacent (Bukhari 2866) is parsed and then ignored. Telling someone their
    correct citation is wrong is a false accusation of misattribution and sits
    in the same severity class as a false EXACT.

    Required property: a reference may attach only to a quotation OF ITS OWN
    KIND, by construction rather than by distance. window=180 must not be
    widened to make any case pass.

  D2 (Important) -- an Arabic citation is scored as though it were a quotation.
    'قال النبي «الحرب خدعة» (صحيح البخاري ٣٠٣٠)' returns THREE quotations, the
    third being the citation itself, so the user is told
    "صحيح البخاري ٣٠٣٠ -- not in this corpus". Only affects people writing in
    Arabic, who are the audience most likely to cite in Arabic. The separate
    `قال النبي` NOT_FOUND is bare prose in an Arabic run and is explicitly out
    of scope.

  D3 (Minor) -- 'صحيح البخاري ٠' parses to hadith_no '0'. The upper bound is
    enforced (Bukhari 99999 rejected), the lower bound is not.

  Also carried into the dispatch: Task 5's engine.py filter is superseded and
  must not be left alongside the new mechanism doing an overlapping job; and
  the two scored representations per hadith must be treated as one record so
  reference checking cannot report the same record twice.

Task 6: implemented (commits 0f640cc, ce7cf93; 441 pytest vs 399 baseline,
  +42 tests; eval gate 35/35 with 0 false verifications; vitest 85/85; ruff at
  the 12-finding baseline; 25 mutations applied, 25 killed, 0 survived).
  The agent stopped once mid-task after the TDD red step and was resumed from
  that point; no work was lost.

Controller verification of Task 6, measured independently:

    hadith cited CORRECTLY + unrelated Quran cite
        'الحرب خدعة'   EXACT            ref=Bukhari 2866   (D1 fixed)
        'قل هو الله أحد' EXACT          ref=112:1
    hadith cited WRONGLY
        'الحرب خدعة'   WRONG_REFERENCE  ref=Bukhari 3030
    arabic citation span no longer scored as a quotation        (D2 fixed)
    ayah cited correctly / wrongly     EXACT / WRONG_REFERENCE  (no regression)
    'صحيح البخاري ٠' and 'Bukhari 0' rejected; 1 and 7124 parse (D3 fixed)

Ruling: R20 -- MY FINDINGS FILE WAS WRONG, and the implementer was right to
  flag it (its concern 4) rather than silently pick a side. D1's fix
  instruction said "a reference may attach only to a quotation of its own
  kind". That over-corrected and suppressed a real defect class:

    'It says «قُلْ هُوَ ٱللَّهُ أَحَدٌ» (Bukhari 12).'  -> EXACT, ref=None
    'It says «الحرب خدعة» (Quran 2:255).'              -> EXACT, ref=None

  Someone attributes a Qur'anic verse to Sahih al-Bukhari and Sanad answers
  Verified without complaint. That is a category error about scripture and a
  worse misattribution than a wrong hadith number.

  Correct rule, which is what the plan's own tests encoded all along:
    1. A citation attaches to the quotation it is NEAREST to, across all
       references regardless of kind. Proximity decides attachment.
    2. Once attached, a kind mismatch between citation and the record the text
       was found in is a WRONG_REFERENCE.
  D1 still comes out right under this rule because the adjacent (Bukhari 2866)
  beats the distant (112:1) on proximity -- which was always the actual bug.
  Explicitly instructed: if D1 only passes because of a kind filter, the
  proximity logic is still wrong and that is what needs fixing.
  Cost if wrong: over-eager cross-kind flagging would produce false
  WRONG_REFERENCE on texts where a nearby citation genuinely refers to
  something else -- bounded by the existing window=180 and the eval gate.

Ruling: R21 -- the implementer's concern 1 is to be fixed, not parked.
  'صحيح البخاري ٩٩٩٩' still survives as a span and reports NOT_FOUND, because
  the D2 filter keys off what parse_references RETURNS. The agent held back
  because the fix needs a new public name that the brief's interface section
  does not list. Same ruling as R18: a brief's interface list is guidance about
  where work is expected, not a boundary that outranks shipping correct
  behaviour. Expose the span claim.

Accepted as found, do not revisit: concern 2 (قال النبي scores NOT_FOUND, bare
  Arabic prose in a run, explicitly out of scope and pinned by assertion);
  concern 3 (the agent contaminated its own tree during mutation testing when
  an outer timeout killed a run before restore, and separately hit a stale .pyc
  from a size- and mtime-identical restore -- it caught both, cleared the
  caches and re-ran the whole round on verified-clean source with a byte-for-
  byte restore assertion); concern 5 (a test it wrote and then deleted as
  incapable of failing, naming the pre-existing test in the same position
  rather than quietly changing it).

Task 6: fix round (commits b316112, e1c5dcc; 452 pytest, 85 vitest, eval 35/35
  with 0 false verifications, ruff at baseline, 28/28 mutations killed).
  R20 and R21 both implemented.

  nearest_reference is back to its original signature and attaches purely on
  proximity; _reference_conflicts compares kind first and reports a mismatch as
  WRONG_REFERENCE. _NearbyReferences was DELETED, not disabled -- no kind
  filter remains anywhere on the attachment path. The implementer proved D1 is
  not being propped up by one by mutating the proximity logic directly
  (min -> max), which D1's own test kills. The 13,348-record cross-kind sweep
  had its expectation inverted and now asserts every cross-kind citation is
  flagged. R21 done via parse_citations -> ParsedCitations(references, spans),
  with parse_references kept as a behaviour-preserving wrapper.

Controller verification of the Task 6 fix round, measured independently:

    ayah attributed to Bukhari       WRONG_REFERENCE  ref=Bukhari 12
    hadith attributed to the Qur'an  WRONG_REFERENCE  ref=2:255
    D1 (correct hadith cite + distant Quran cite)  EXACT  ref=Bukhari 2866
    bare surah name '(Al-Ikhlas)', no verse number EXACT  -- not flagged
    out-of-range arabic citation     no longer scored as a quotation
    ayah cited correctly / wrongly   EXACT / WRONG_REFERENCE
    full suite                       452 passed, tree clean

Task 6: COMPLETE (commits 0f640cc, ce7cf93, b316112, e1c5dcc).

  Three things the implementer surfaced that are worth keeping:
  1. One of its own mutations was a NO-OP reported as "survived" -- it inserted
     dead code, changed nothing, passed everything, and was caught by reading
     the diff rather than the result. Second time in this task the measuring
     instrument was the fault. Standing hazard: a mutation that does not change
     behaviour is indistinguishable from a surviving one in the log, and so is
     a mutation that TIMES OUT (one did, pulling in the 7,112-record sweeps; it
     was re-run narrowly rather than counted either way).
  2. A mutation genuinely survived and earned a new test: the
     `given.ayah is not None` guard in _reference_conflicts could be deleted
     with the whole suite green, because every other name-citation test also
     gave a verse number or cited across kinds. Deleting it turns every bare
     surah-name citation ("Al-Ikhlas", no verse) into a WRONG_REFERENCE -- i.e.
     Sanad calling correct citations misattributions. Now pinned in both
     directions. Pre-existing logic that had no test because nothing exercised
     it alone.
  3. Its report's section A1 diagnoses the shape of the original error: the
     wrong invariant was made STRUCTURAL, and the code, docstrings and tests
     all agreed with each other while being wrong together. That is the same
     shape as the R2 and false-EXACT defects earlier on this branch.

  Open, deliberately: _select_by_reference's cross-kind tie fallback cannot
  fire on today's corpus (measured: no ayah shares text with any hadith across
  all 13,365 records), so it is covered only by a synthetic fixture. Correct
  and cheap, but it guards against a corpus we do not have -- first thing to
  re-examine when another collection lands.

Ruling: R22 -- corpus scope wording, chosen by Adnan from three options:

    "This corpus contains the Qur'an and Sahih al-Bukhari. It does not contain
     Sahih Muslim, the four Sunan, or any other collection, so absence from
     this corpus does not establish that a quotation is fabricated."

  Rationale for naming the absent collections explicitly rather than saying
  "only": a reader who does not know the field cannot otherwise tell that this
  corpus is a small slice of the hadith literature, and the line is hardest to
  misread as completeness. Cost: it is long for something carried on every
  response. This string is asserted in tests on both sides (api and
  web/tests/screens/Verify.test.tsx has a SCOPE const) -- both must be updated.

Task 7: implemented (commits 3cec72a, b8ce3f5; 457 pytest vs 452 baseline,
  85 vitest, ruff at the 12-finding baseline). No outstanding concerns. One
  self-corrected incident: a git checkout during mutation testing reverted
  uncommitted routes.py changes; caught via git diff, reapplied by hand and
  verified byte-identical. That is the THIRD time on this branch that a
  mutation-testing procedure damaged its own working tree -- the technique is
  load-bearing here and its failure modes are now a known hazard in their own
  right.

Controller verification of Task 7, measured independently against the live app:

    CORPUS_SCOPE byte-for-byte equal to R22's chosen wording      TRUE
    propagated to all 4 web fixtures                              TRUE
    stale "Qur'an only" in code                                   none
      (remaining hits are historical specs/plans -- correctly left alone)
    POST /api/verify on a cited hadith
      verdict EXACT, 1 quotation, collection=bukhari,
      hadith_no=2866, reference_display='Sahih al-Bukhari 2866',
      isnad_ar present
    authenticity/grading-shaped fields in RecordOut               NONE
    GET /api/corpus  13,365 records, 3 sources, scope line present,
      OpenITI edition metadata and public-domain basis intact

Task 7: COMPLETE (commits 3cec72a, b8ce3f5).

Task 8: implemented (commits fb9cbf6, 82a0eeb; 457 pytest, 96 vitest vs 85
  baseline, tsc clean, generate:client produced no diff on types.ts).

Controller verification of Task 8, measured independently:

    matn rendered as text_ar + " " + addenda_ar, one continuous block,
      no heading between them -- matches the backend's own join, which is
      how the full-printed-text representation is built
    isnad_ar rendered, display only
    no-grading line renders ONCE and only when a hadith is present
      (guarded on q.record?.collection, mirroring the translation
      disclaimer pattern Adnan asked for at the start of this work):
        "Sanad confirms wording against this printed edition. It does not
         grade authenticity (sahih/da'if); that requires a scholarly source."
    MarkedText now carries aria-label with the verdict label
    96 vitest pass, tsc --noEmit clean

Ruling: R23 -- the MarkedText accessibility fix uses aria-label rather than
  visually-hidden text, and that is the right trade even though aria-label on
  <mark> depends on ARIA naming rules and AT support that cannot be verified
  here. Hidden text inside the mark would enter textContent and break the
  exact-text contract -- the Stage C property that Sanad never substitutes the
  corpus reading for what the user typed -- which is load-bearing and has its
  own test. Recorded as an IMPROVEMENT ON title ALONE, NOT AS A VERIFIED FIX.
  Cost if wrong: the verdict stays inaudible to some screen readers, i.e. the
  pre-existing gap persists for those users rather than being made worse.
  Must be checked against a real screen reader (NVDA or VoiceOver) before this
  is claimed as resolved anywhere user-facing.

  Implementer's second concern accepted: the 17 unscorable records get no
  distinct "pointer, not independently quotable" label in the UI. They cannot
  currently reach /api/verify results at all, so there is nothing to explain
  yet. Revisit if reference lookup ever surfaces them directly.

Task 8: COMPLETE (commits fb9cbf6, 82a0eeb).

Ruling: R24 -- SEQUENCING, set by Adnan on 2026-09-23. After Stage A2's tasks 9
  and 10 and the whole-branch review: Stage B (the Ask route) comes NEXT, and
  Stage A3 (Sahih Muslim and the four Sunan) comes after it. This reverses the
  controller's earlier default of A3 before B.

  The original argument for Ask-last was that its eval suite must be re-run
  whenever the corpus shifts, and this branch proved the point -- the corpus
  changed shape three times during Stage A2 (395 records cut, 17 made
  unscorable, every hadith reindexed under two representations). That cost is
  real and does not go away; it is simply outweighed. Qur'an + Bukhari is
  already enough corpus for Ask mode to be useful and demonstrable, and a
  multi-agent Ask tab is the more visible deliverable for a competition entry
  than a sixth hadith collection.

  Consequence to plan for: Ask's eval suite will need re-running when Stage A3
  lands. Budget for it rather than being surprised by it.

Task 9: implemented (commits 1992051, 9e137b6, 68215b9; eval 54 cases /
  0 failed / 0 false verifications, up from 35; pytest 474 vs 457; vitest 96;
  tsc clean; ruff at baseline; 24 mutations run, 0 survivors).

Controller verification of Task 9, measured independently:

    eval 54 cases, 0 failed, 0 false verifications
    verdict distribution  EXACT 17 | EXACT_ORTHOGRAPHY 2 | NEAR_MATCH 6
                          NOT_FOUND 11 | WRONG_REFERENCE 8

  The spread across all five verdicts is itself the signal -- an adversarial
  suite that clusters on one verdict is not adversarial.

Ruling: R25 -- both out-of-brief changes CONFIRMED, not reverted.
  (a) The hadith_unverifiable claim note read "No licensed Hadith edition is
      bundled in this corpus. Treat as unverified." True until Bukhari was
      ingested, false afterwards, and it was being printed beside a hadith this
      corpus had just matched word for word -- Sanad contradicting its own
      result inside the same response. Now states the scope limit and the
      refusal to grade, both of which remain true in every case.
  (b) CORPUS_SCOPE moved to sanad/corpus/scope.py, re-exported from routes, so
      the eval runner can assert it without importing FastAPI. String verified
      byte-identical.

Ruling: R26 -- open question left unruled by the implementer, ruled here: the
  hadith caution flag KEEPS firing even on a hadith Sanad has just confirmed
  EXACT. Suppressing it would require coupling the claim scanner to
  verification results, which is real architectural cost, and the rewritten
  note is truthful in every case -- it states the scope limit and the no-grading
  position, neither of which stops being true because this particular citation
  checked out. Cost if wrong: mild redundancy against Task 8's no-grading line,
  which is shown once per result. Revisit only if users report it as noise.

Ruling: R27 -- the implementer's concern 4 is a hole in the GATE, not in a
  case, and is being closed rather than deferred. Today the gate reads
  `if case.expect_verdict not in VERIFIED and any(...)`, so for any case
  expecting a verified verdict the false-verification gate is off entirely --
  including for that case's OTHER spans. A case quoting a real ayah alongside a
  fabricated hadith, expecting EXACT for the first, would let the fabrication
  verify invisibly. No current case is exposed; the gate must not depend on
  that remaining true, because it is the one mechanism standing between this
  project and its worst failure. Fix dispatched: make the gate span-aware, with
  a per-case count of legitimately-verifying spans, prove it with a case that
  fails under the old gate and passes under the new one, and mutation-test the
  gate itself. Explicitly instructed NOT to weaken any existing case to
  accommodate the new gate -- if it trips on one, that is a finding to report.

  Accepted as stated: concern 1 (a brief-supplied case that could not fail,
  caught by mutation rather than review -- fourth on this branch, first found
  this way -- replaced with one exploiting hadith 16 and 6542 printing
  byte-identical matns, so an unparsed citation falls back to the wrong
  occurrence and the case fails); and concern 3 (the two absent-from-corpus
  cases hold the only TYPED Arabic in the suite, since text not in the corpus
  cannot be copied out of it; codepoints read back and recorded, a test asserts
  neither string is in the corpus, and the implementer states plainly it cannot
  prove they are the canonical wording of those sayings).

  Measured and worth keeping: 'hadith-quoted-with-its-isnad' is NOT_FOUND at
  aggressive-tier 0.4119, and lowering NEAR_THRESHOLD is quantifiably the wrong
  fix -- at 0.40 that text does not find hadith 1, it near-matches Sahih
  al-Bukhari 4783 at the same score. The case pins expect_no_other_record
  rather than the verdict, so a genuine future improvement will not fail it.

Task 9: gate fix (commit 3e1e391; eval 54/54, 0 false verifications; pytest 480
  vs 474; vitest 96; tsc clean; ruff baseline; 7 gate mutations + 2 engine
  re-runs, 0 survivors; Task 9 running total 33 mutations, 0 survivors).

  R27 implemented as Case.verified_span_budget(). The gate now counts verified
  spans and trips per EXCESS SPAN rather than per case. Default is the tightest
  reading of what the case already says -- 0 when expect_verdict is not a
  verified verdict, 1 when it is -- and declaring a budget ARMS the gate at n+1
  rather than switching it off, so a declaration is a stronger statement than
  the default, not a weaker one. Malformed budgets are rejected at load time,
  including `True`, which passes isinstance(x, int) and would silently mean 1.

  The finding, reported rather than tuned away as instructed: running the new
  gate before touching any case produced exactly one failure --
  hadith-correct-citation-not-flagged-by-a-distant-one, 2 verified spans
  against a default budget of 1. Legitimate: two correctly cited genuine
  quotations, a hadith and an ayah, each beside its own citation, both of which
  SHOULD verify. It now declares expect_verified_spans: 2 and remains gated on a
  third span, with expect_verdict/expect_record/forbid_verdict untouched. A
  sweep confirmed it is the only case over the default, and a test asserts that
  exactly one case declares a budget at all -- so the escape hatch cannot spread
  one case at a time unnoticed.

Controller verification of the Task 9 gate fix, measured independently:

    eval 54 cases, 0 failed, 0 false verifications
    exactly one case declares expect_verified_spans (hadith.yaml:99)
    INDEPENDENT MUTATION by the controller: disabling the gate
      (`len(verified) > budget` -> `> budget + 99`) fails 4 tests, including
      test_gate_catches_a_false_verification_in_a_second_span.
      Restored byte-identical (md5 verified), tree clean.

  The gate is real coverage, not decorative. Given three separate incidents on
  this branch where mutation testing damaged its own working tree, the restore
  was hash-verified rather than assumed.

Task 9: COMPLETE (commits 1992051, 9e137b6, 68215b9, 3e1e391).

  Open, recorded not hidden: the budget governs HOW MANY spans verify, not
  WHICH. A case licensing one verified span would still pass if the wrong span
  verified and the right one did not. Closing that needs per-span positional
  expectations, a larger schema change no current case needs --
  expect_record pins the first span and expect_no_other_record pins all of
  them, which covers every multi-span case in the suite today.

Task 10: COMPLETE (commits 2de4390, 02d62b2).

  Reported DONE_WITH_CONCERNS at 2de4390. Controller re-measured every figure
  against the live corpus rather than accepting the report:

    db sha256  d1b035afa4d324907e56a50351bb0ed8cb90d73f212784942d29f58069096338
    records    13365   (6236 ayat + 7129 hadith)
    cut        393     (addenda_ar not null), 1 of them unscorable
    unscorable 17

  Full verification passed: 480 pytest, 96 vitest, tsc clean, `npm run build`
  succeeded, ruff at the 12-finding baseline, eval 54/54 with 0 false
  verifications, and the corpus rebuild from cached sources is byte-identical
  to the committed DB.

  R28: the agent was right and I was wrong -- my "395 cut records" figure was
  stale (actual 393) and had propagated through several task briefs. A number
  I carried in prose for three tasks was never re-derived. Cost if wrong: a
  brief's stated baseline disagrees with the corpus an implementer measures,
  and they either waste a round reconciling it or, worse, trust the brief.
  Mitigation applied: figures in briefs are now re-queried at compose time.

  Concern 3 (docs/GAPS.md stale) addressed by the controller in 02d62b2,
  outside the brief's file list.

  R29: GAPS.md needed more than ticking boxes. Written before any code
  existed, it listed shipped work as open P0 gaps -- but several entries had
  also become deliberate non-goals rather than work outstanding (hadith
  grading, rijal data, written permission). Ticking or deleting both would
  have been wrong: a deleted line reads as forgotten, a ticked one claims work
  we did not do. Added a third marker, [~], for refusals-with-reasons.
  Cost if wrong: a reviewer reads a non-goal as an oversight, which is
  recoverable; the reverse -- a grading gap read as merely unfinished --
  invites someone to "finish" it.

  Three claims I was about to write turned out wrong or unverified and were
  corrected by measurement before the commit: DISPUTED does NOT force a
  handoff (only PERSONAL_RULING and HIGH_RISK do); chapter_ar is empty on 33
  of 7129 records and whether that is upstream or a parser drop is UNCHECKED,
  now recorded as such; the Vercel demo has never been loaded from a browser
  here. Consistent with the branch's standing lesson -- the errors come from
  what gets asserted without measuring, not from what gets measured wrong.

All ten tasks complete. Next: whole-branch review over ca9e03f..HEAD
(34 commits, 49 files, +8043/-192) on the most capable model.

## Whole-branch review (ca9e03f..HEAD) — CHANGES_REQUIRED

Report: `.superpowers/sdd/2026-09-22-hadith-corpus/final-review-report.md`
2 Critical, 2 Important, 6 Minor. Reviewer re-measured every figure in the
brief and found them all correct, killed all eight mutations it applied, and
restored the tree hash-verified.

Controller independently reproduced C1, C2, I1, I2 and M1 against the live
corpus before ruling. C1 and C2 are confirmed verbatim:

    «فكان قاب قوسين أو أدنى فأوحى إلى عبده ما أوحى»   -> EXACT 1.0 bukhari:4575
    same + Tanzil diacritics + "(53:9)"                -> WRONG_REFERENCE
    «الحرب خدعة» (Sahih al-Bukhari, Book 52, Hadith 268) -> WRONG_REFERENCE
    «الحرب خدعة» (Bukhari 12345)  -> parsed as 1234 -> WRONG_REFERENCE

R30 (C1): a hadith representation whose scored text is wholly a Qur'anic
quotation must not be scorable as hadith. Fixing only record 4575's cut would
leave the class open; fixing only the invariant would leave a wrong cut in the
corpus. Do both. The reviewer measured exactly 1 of 7,504 scorable
representations is wholly Qur'anic, so the invariant's blast radius is known
and it is an assertion about the corpus, not a heuristic. Cost if wrong: a
genuine hadith whose entire matn is an ayah stops being findable by its own
text -- it remains findable by reference, and no such record exists today.

R31 (C2): a book-relative citation must never produce WRONG_REFERENCE.
"Book 52, Hadith 268" is USC-MSA/sunnah.com numbering -- the form most people
copy-paste -- and reading it as an al-Bugha sequential number tells someone
their correct citation is wrong. We have no USC-MSA -> al-Bugha book mapping
and will not invent one. Not attaching is honest; attaching as unresolvable is
better if cheap. Cost if wrong: a genuinely wrong book-relative citation goes
unflagged, which is silence, not a false accusation.

R32 (I1): unscorability is currently judged on a record's primary and applied
to BOTH representations. Record 237's primary is a 40-char fragment ending at
the tahwil mark and is rightly unscorable; its 869-char full printed narration
is not, yet returns NOT_FOUND 0.37. Apply unscorability per representation.
I accept the reviewer's disagreement with R13: "237's story is at 3641" is
true of the story and false of the text, and the text is what we match.

R33 (I2): `index.html` tells the public "No Hadith edition is bundled
anywhere" and "Adapter only -- no edition shipped". This is the same defect as
R25(a), which was fixed in `claims.py` while the test written to prevent it
stopped at claim notes. The GitHub Pages entry point is the most public
surface we have. Fix the copy AND widen the test past claim notes.

R34 (M5): the eval gate counts false EXACT and cannot see a false
WRONG_REFERENCE. This branch shipped two of the latter (C1's second half and
C2), so the omission is load-bearing, not theoretical. Extend the gate.

R35: M1 fixed (same false-accusation class, trivial). M2 fixed if trivial.
M3 parked -- a comment documenting a measured fact is where that belongs.
M4 parked -- "no schema version marker" is correct while nothing assumes a
migration path; adding one now is speculative. M6 unmeasured by the reviewer,
so measure it before deciding; report the measurement either way.

## Fix round — 9 commits, b1caee9..2f9621a

Report: `.superpowers/sdd/2026-09-22-hadith-corpus/final-fix-report.md`.
All eight in-scope findings fixed; M3 and M4 stayed parked as ruled.

Controller re-measured rather than accepting the report:

    C1 bare ayah   «فكان قاب قوسين...»            EXACT bukhari:4575 -> NOT_FOUND
    C1 cited       same + diacritics + "(53:9)"   WRONG_REFERENCE   -> NOT_FOUND
    C2 book-rel    "(Book 52, Hadith 268)"        WRONG_REFERENCE   -> EXACT
    M1 5-digit     "(Bukhari 12345)"              WRONG_REFERENCE   -> EXACT
    control        "(Bukhari 1)"                  still WRONG_REFERENCE
    single ayah    «فَكَانَ قَابَ قَوْسَيْنِ أَوْ أَدْنَىٰ» (53:9)  EXACT quran:53:9
    4575 full text                                  EXACT bukhari:4575
    237 addendum                                    NOT_FOUND -> NEAR_MATCH 237

  The two C1 NOT_FOUNDs are the pre-existing multi-ayah limitation, not a
  regression: 53:9 alone returns EXACT quran:53:9 at light tier and
  EXACT_ORTHOGRAPHY undiacriticised. Record 4575 is now uncut, primary = the
  full printed hadith, addenda NULL.

  Independent containment scan: 7,504 scorable representations, **0** wholly
  Qur'anic -- matching the reviewer's figure exactly. And the invariant is
  NOT vacuous: the pre-fix 4575 primary IS caught by it (`True`), the post-fix
  primary is not (`False`). It would have stopped the build on the defect it
  exists to prevent, which is the only proof that mattered.

  eval 61/61, 0 false verifications, **0 false misattributions** (the new
  counter). ruff 1 on the CI path (`api ingest eval`) and 12 repo-wide -- both
  at baseline; the "12" in earlier notes is `ruff check .`, worth stating
  because the two numbers look like a discrepancy and are not. DB
  `ab96d484370fe8a4555a691192886504b95ed07bc1fcf10fabbf0a34ca530083`,
  tree clean.

R36 (concern 1): I1 narrows R14 by consequence -- hadith 237 is now reachable
in `/api/search` through its full-text representation. Accepted, and it is the
better behaviour: the indexed string is a real 869-character narration, and a
reader who quotes it should find it. R14's principle was that a *pointer* must
not answer as though it were a text; a pointer fragment and the narration
printed beneath it are different strings, and only the first was ever the
concern. Cost if wrong: a record whose primary is a pointer becomes findable
by the text it points at, which is what a reader quoting that text wants.

R37 (concern 4): a C1 mutant SURVIVED and the agent found and fixed it --
every C1 test called the invariant directly, so deleting its call site in
`build_corpus` left them all green. This is the fifth can't-fail test on this
branch and the first found by the author rather than the controller. The
generalisation worth keeping: **a build-time invariant needs a test that the
build calls it**, separate from the tests of what it does. The review's own
mutation table covered rules and not wiring, so the review would not have
caught this either.

R38 (concern 3): C2's refusal is silent -- "Bukhari 1:2:13" yields no
reference and no explanation, so the product cannot say "we recognised your
citation and cannot resolve it." Parked as a known gap, not fixed here: it
needs a response field and UI, which is scope this fix round should not grow
into. Silence is the correct failure direction in the meantime. Recorded in
`docs/GAPS.md` rather than left in this ledger, since it is a product gap and
not a branch artifact.

R39 (concern 6): the agent reproduced the mutation-testing hazard in a new
form -- `git checkout -- index.html` to undo a mutation also discarded its
own uncommitted edits, caught only by a before/after hash. Fourth incident on
this branch. Rule tightened for future briefs: **never `git checkout` a file
that has uncommitted changes in order to undo a mutation; restore from a copy
taken before the mutation, and hash-verify.**

## Scoped re-review — APPROVE_WITH_FINDINGS (0 Critical, 1 Important, 7 Minor)

Report: `.superpowers/sdd/2026-09-22-hadith-corpus/fix-rereview-report.md`.
All eight fixes confirmed real. Every item on the controller's verified list
reproduced; none wrong. No Qur'an-path regression (0 ayah<->hadith exact ties
at all three tiers; 400 sampled ayat verify when correctly cited). 20 mutants
killed, 4 survived (3 are findings, 1 equivalent). Tree untouched, restores
hash-verified, no `git checkout` used.

R40 (F1, Important -- FIX, do not park): the wholly-Qur'anic invariant closes
only token-aligned WHOLE-representation containment. `hadith:bukhari:3658`'s
entire matn is `انشق القمر`; Qur'an 54:1 ends `وَٱنشَقَّ ٱلْقَمَرُ`. Controller
reproduced, and found one case worse than reported:

    «انشق القمر» (54:1)            -> WRONG_REFERENCE  bukhari:3658
    «وَٱنشَقَّ ٱلْقَمَرُ» (54:1)      -> NEAR_MATCH       bukhari:3658
    «انشق القمر»                    -> EXACT            bukhari:3658
    «اقتربت الساعة وانشق القمر» (54:1) -> EXACT_ORTHOGRAPHY quran:54:1

The second line is a verbatim Tanzil substring of 54:1, cited correctly, and
Sanad answers with a hadith. That is C1's class -- scripture attributed to a
collection, a correct citation contradicted -- and it is live.

But it is NOT C1's cause, and this is the part that matters. 4575 was a CUT
ERROR: the record should never have been scorable. 3658 is a LEGITIMATE
record -- a Companion's report whose entire matn is "the moon split," one
clitic away from an ayah. R30's remedy ("the cut is in the wrong place, leave
it uncut") has nothing to offer here, so the reviewer is right that this is
the honest blast-radius answer to R30 rather than a second instance of it.
The build invariant is the wrong tool; the fix belongs at verify time.

Requirement, mechanism left to the implementer: when a reader supplies a
Qur'anic reference and the quoted text is contained in that ayah, Sanad must
not answer with a hadith verdict of any kind. Disclosure of the co-occurrence
is better than silence. Cost if wrong: a genuine short hadith matn becomes
harder to reach when someone miscites it as Qur'an -- a recall cost paid to
avoid a false accusation, which is the right direction.

R41 (F2): the fix report justified two claims by citing
`test_a_single_word_is_not_a_span`, which **does not exist in the repo**
(grep, zero hits). `MIN_RUN_CHARS` 6->5 passes all 545 tests and restoring
the engine's deleted literal passes all 105 verify/engine tests, so both are
untested. Recorded as a reporting-integrity failure, not just a coverage gap:
an assertion sourced to a named artifact that is not there is the one kind of
report error that survives review, because the name reads as evidence. Fix
the coverage; the lesson goes to memory.

R42: F3 (`lstrip("0")` untested), F4 (stale comment contradicting the fix in
its own file), F5 (CI "matches a fresh build" fingerprint covers only
`records`, missing `record_variants` and `records_fts`), F7 (`index.html` row
306 says Bukhari ships via OpenITI while row 307 says OpenITI "Not included"
-- contradictory, on the public page) -- all FIX. Cheap, and F7 is public.

R43: F6 parked as to the equivalent mutant -- the gate demonstrably FIRES
(end-to-end run: `false misattributions 1`, GATE FAILED, exit 1; reverting C2
in place produced 2 on the real suite). `main()` being untested is noted and
not worth a test that asserts a print. F8 accepted as designed under R31:
`"al-Bukhari, 2:255"` yielding no reference is silence, not accusation.

## Second fix round — 5 commits, 4e8af6f..1fb226d

Report: `.superpowers/sdd/2026-09-22-hadith-corpus/fix2-report.md`.
F1, F2, F3, F4, F5, F7 done; F6 and F8 stayed parked as ruled.

Controller re-measured:

    «انشق القمر» (54:1)          WRONG_REFERENCE -> NOT_FOUND, also_at [quran:54:1]
    «وَٱنشَقَّ ٱلْقَمَرُ» (54:1)    NEAR_MATCH      -> NOT_FOUND, also_at [quran:54:1]
    «انشق القمر»                 EXACT 3658      -> EXACT 3658, also_at [quran:54:1]
    «اقتربت الساعة وانشق القمر» (54:1)            EXACT_ORTHOGRAPHY quran:54:1
    «الحرب خدعة» (Bukhari 2866)                   EXACT (no regression)
    «الحرب خدعة» (Bukhari 1)                      WRONG_REFERENCE (still flagged)

  The fix discloses rather than merely withholds: a reader who cites 54:1 is
  told the words are at 54:1, not just refused a hadith.

R44 (concern 6 -- the one thing the agent could not verify, now closed):
the agent never ran `sanad-ingest build` this round, so the widened
fingerprint had never been compared against a fresh build. Controller ran it.
Fresh build and committed DB are **byte-identical** at
`ab96d484370fe8a4555a691192886504b95ed07bc1fcf10fabbf0a34ca530083`; tree
clean afterwards, noise report unchanged. Separately probed the widened
fingerprint on a COPY: deleting 237's `record_variants` rows plus an FTS row
now changes it (`True`), which is exactly the deletion that left the old
records-only fingerprint byte-identical. F5 does the job it claims.

R45 (concern 3): F1 costs +176s of CI (~5ms per hadith match, paid ~21,000
times by two corpus sweeps; negligible per request). The agent measured the
alternative -- a partial index on `records(norm_standard, id) WHERE
kind='ayah'`, 0.69ms/call, +0.89MB -- and declined it because it means a
schema change and a NEW PUBLISHED HASH for a 60MB content-addressed artifact.
Accepted. Three minutes of CI is cheap against re-publishing the corpus and
invalidating the documented hash, and the index stays available if CI time
ever becomes the binding constraint. Cost if wrong: slower CI, reversible in
one commit.

R46 (concern 4): `also_at` now carries two distinct relations -- "identical
text at the matched tier" and "the containing ayah". That is overloading, and
a separate `contained_in` field would be cleaner. Not now: it costs a schema,
client and UI change, and **Stage B will touch the API surface anyway**. Do it
there, not in a fix round. Documented in `Match`, `QuotationOut` and
`IsnadTrace` in the meantime.

R47 (concern 5, residual): a bare UNCITED `«وانشق القمر»` still returns
NEAR_MATCH to 3658 -- with `also_at [quran:54:1]`. Accepted. R40's requirement
is about not contradicting a reader's correct citation, and there is no
citation here to contradict; the disclosure carries the honesty. The agent
agreed with the controller's lean on both open questions and said where the
lean ran out, which is the right shape for a disagreement report.

R48 (concern 2): one mutant survived -- removing `corpus_fingerprint`'s row
separator. Not equivalent, but unreachable without injecting control
characters into corpus data. Reported rather than covered by a contrived
test. Correct call: a test that can only fail against data the build cannot
produce documents nothing.

Corpus sweep answer required by R40: **1** -- `hadith:bukhari:3658` in
`quran:54:1`, the only hadith representation contained in an ayah under
substring, clitic-relaxed and aggressive comparison alike (token-aligned
finds 0, which is precisely why the build invariant was blind to it). Now a
test, so a second such matn in a future edition halts the suite rather than
shipping.
