# Sanad Stage A2 — Hadith corpus design

**Date:** 2026-09-22
**Status:** approved, pending implementation plan
**Builds on:** `docs/superpowers/specs/2026-09-19-sanad-design.md` — this spec
resolves its §14.1, the open question that kept Hadith out of Stage A
**Depends on:** Stage A (shipped) and Stage C (shipped)
**Blocks:** Stage B (Ask mode), deliberately — see §13

## 1. What we are building

Ṣaḥīḥ al-Bukhārī's Arabic text, ingested into the existing corpus so that
`POST /api/verify` treats a quoted hadith exactly as it already treats a quoted
āyah: match it, name it, show the chain, or say honestly that it is not here.

Nothing about the verification engine changes. The tier→verdict coupling, the
five verdicts, the normalization tiers, the risk router and the handoff are all
corpus-agnostic already. What changes is the corpus, one column on `records`,
the citation parser, and three pieces of product copy that currently promise a
Qur'an-only corpus.

The point of the addition is not coverage for its own sake. A tool named
*Sanad* — "chain of transmission" — that cannot check a hadith is a tool
missing the half of the problem where fabrication is actually common. Nobody
invents āyāt; people invent hadith constantly, and the invented ones circulate
with confident attributions.

## 2. Non-goals

- **No gradings.** Not shown, not stored, not inferred. The `gradings` table
  stays empty. See §9.3 — this is a legal *and* an epistemic boundary.
- **No Hadith translations bundled.** Same rule the Qur'an layer follows for
  anything not public domain. English renderings of Bukhari in circulation are
  either modern (copyrighted) or of uncertain provenance.
- **No second collection in this stage.** Muslim, the four Sunan, the Muwaṭṭaʾ
  all come later or never. One collection, done properly, with the corpus
  boundary stated honestly, beats six ingested carelessly.
- **No isnad analysis.** Sanad displays the chain; it does not evaluate
  narrators, trace them across collections, or comment on continuity. That is
  ʿilm al-rijāl and it is not a string-matching problem.
- **No re-OCR, no text correction.** See §10.

## 3. Decisions taken

| Question | Decision |
|---|---|
| Source | OpenITI `0256Bukhari.Sahih.JK000110-ara1.completed` |
| Legal basis | The matn's own public-domain status, **not** an OpenITI licence grant (§4.2) |
| Storage | Matn in `text_ar`; isnād in a new `isnad_ar` column |
| Matching | Against the matn only; the isnād never enters scoring (§7) |
| Schema | The existing `records` table, `kind='hadith'` — no new table |
| Citation parsing | A second, independent regex family; not a unified grammar (§8) |
| Gradings | Absent, with one explicit on-screen statement that they are absent |
| OCR noise | Flagged at ingest, never silently corrected (§10) |

## 4. The source

### 4.1 What it is

`data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed`
in `github.com/OpenITI/0275AH`. The file's own `#META#` header records the
edition, which is better evidence than the sidecar `.yml`:

```
040.EdEDITOR    :: د. مصطفى ديب البغا      (Muṣṭafā Dīb al-Bughā)
043.EdPUBLISHER :: دار ابن كثير , اليمامة   (Dār Ibn Kathīr / al-Yamāma)
044.EdPLACE     :: بيروت                    (Beirut)
045.EdYEAR      :: 1407 - 1987
041.EdNUMBER    :: الثالثة                  (3rd edition)
020.BookTITLE   :: الجامع الصحيح المختصر
```

**Per-file vetting, never "ingest the repo."** Sibling files in the same
directory (`Shamela0001681`, `Shia001715Vols`) carry unfilled placeholder
metadata. The JK file was chosen because its provenance is complete and
internally consistent; the others were rejected on that basis alone.

The al-Bughā numbering matters beyond provenance: it is the numbering that
English-language references to Bukhari overwhelmingly use, so it is the
numbering a user's citation will be expressed in.

### 4.2 Why we may ship it — the legal basis

**Basis: the work's own public-domain status.** Muḥammad ibn Ismāʿīl
al-Bukhārī died in 870 CE. The matn and the isnād are public domain in every
jurisdiction, without qualification.

**Not** an OpenITI licence grant, and the distinction is load-bearing.
OpenITI's website states CC BY-SA, but the data repository `OpenITI/0275AH`
carries no `LICENSE` file, and the `OpenITI/OpenITI` repository's MIT licence
covers their Python tooling, not corpus text. Verified 2026-09-22. Citing a
grant we cannot point to would repeat exactly the error the Pickthall entry
corrects: relying on a distributor's terms instead of examining the basis, and
handing a downstream commercial user a problem, since Sanad's code is MIT.

What OpenITI contributes is transcription and structural markup. A faithful
mechanical transcription of a public-domain text attracts no new copyright.
Their markup is *not* carried into the corpus — the parser consumes it and
discards it (§5), so the stored text is the public-domain text and nothing
else. The 1987 al-Bughā edition's own editorial apparatus — introductions,
footnotes, indices — was already stripped upstream by OpenITI Clean in 2023 and
is likewise absent. What remains is matn and isnād.

**Attribution to OpenITI is given as credit, not as licence compliance.** They
are recorded in `sources` with file, edition, commit and retrieval date, and
shown in the provenance panel, because a provenance tool that obscured where it
got its text would be self-refuting.

**Still to do, non-blocking:** file the drafted enquiry
(`docs/superpowers/research/2026-09-20-openiti-licence-enquiry.md`) as a real
GitHub issue, so a definitive answer exists on the record. If OpenITI replies
with terms that change the picture, we revisit. Nothing about the current basis
depends on their answer.

### 4.3 Lockfile entry

A third `[[source]]`, replacing the `NOT YET RESOLVED` comment at the foot of
`ingest/corpus.lock.toml`:

```toml
[[source]]
id             = "openiti-bukhari-jk000110"
kind           = "hadith-arabic"
format         = "openiti-markdown"
title          = "الجامع الصحيح المختصر (Ṣaḥīḥ al-Bukhārī)"
publisher      = "OpenITI (transcription); Dār Ibn Kathīr / al-Yamāma, Beirut (edition)"
edition        = "al-Bughā, 3rd ed., 1407/1987; OpenITI JK000110, ara1.completed"
url            = "https://raw.githubusercontent.com/OpenITI/0275AH/<commit>/data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed"
commit         = "<40-char git commit SHA>"
license_id     = "public-domain"
license_url    = ""
content_sha256 = "<measured at build>"
expected_records = 0   # measured at build, then pinned; never guessed
modifications  = "mARkdown structural markers parsed and discarded; no text altered"
```

Three deviations from the Qur'an entries, each deliberate:

**`format = "openiti-markdown"`** extends the required-`format` enum. The field
exists because an implicit default is how the wrong Tanzil export was chosen
silently; a third value must be as explicit as the first two.

**`commit`** is new and required for this source. Tanzil publishes stable
versioned exports; OpenITI is a live git repository whose files are re-OCRed
and corrected over time. A branch URL is not a pin. The raw URL therefore
embeds the commit, and the commit is recorded separately so it is greppable.

**`content_sha256` covers the complete raw file**, unlike the Qur'an sources
where it covers the verse payload only. That exclusion exists solely because
Tanzil's copyright block embeds the current year and would churn the hash
annually. OpenITI's file has no volatile block, so hashing everything is both
simpler and stronger — the `#META#` header is itself provenance we want pinned.
The differing convention is stated in the lockfile comment so nobody
"harmonises" the two later and breaks the check.

**`expected_records` is measured, then pinned.** No count is written into this
spec. Published figures for al-Bughā's numbering vary with how repeated hadith
are counted, and a number typed from memory into a provenance contract is the
exact failure this project keeps finding. The first build reports the parsed
count; a human checks it against the edition; the checked value is committed.

## 5. Parsing OpenITI mARkdown

New module `ingest/sanad_ingest/openiti.py`, parallel to `tanzil.py` and with
the same contract: pure function, file bytes in, structured records plus
attribution plus content hash out. No network, no database.

| Marker | Meaning | Treatment |
|---|---|---|
| `#META# …` → `#META#Header#End#` | header block | parsed into attribution; not text |
| `### \|` | kitāb (book) division | sets current `book_no`, `chapter_ar` |
| `### \|\|` | bāb (chapter) division | sets current chapter within the kitāb |
| `# 1 حدثنا…` | one hadith, al-Bughā number | starts a record; number → `hadith_no` |
| `~~` | soft-wrap continuation | joined to the previous line |
| `PageV01P003` | print pagination | stripped |
| `@QB@ … @QE@` | Qur'anic quotation inside a hadith | **markers stripped, text kept** |
| `*` | isnād/matn boundary | splits the record; see §7 |

Two of these deserve their reasoning recorded.

**`@QB@…@QE@` markers are discarded but the quoted text is kept.** A hadith
that quotes an āyah contains that āyah, and a user quoting the hadith may well
be quoting the Qur'anic part of it. Dropping the text would make a genuine
quotation unverifiable; keeping the markers would leak transcription apparatus
into text we claim is the edition's. Strip the markers, keep the words.

**A record with no `*` keeps its whole text as matn, with `isnad_ar` NULL.**
Not every unit in the file is a narration with a chain — chapter headings and
quoted verses appear as their own units. Guessing where an absent boundary
"should" be would be inventing a chain, which is worse than admitting the file
does not mark one.

## 6. Schema

Stage A built the full spec schema so that this stage needs no migration, and
that held: `records` already has `kind`, `collection`, `book_no`, `chapter_ar`,
`hadith_no`, and `numbering_scheme`, all nullable and all unused so far.

**One column is added:**

```sql
ALTER TABLE records ADD COLUMN isnad_ar TEXT;   -- NULL for every Qur'an record
```

It is added to `SCHEMA_SQL` rather than applied as a migration — the corpus is
rebuilt from the lockfile, never patched in place. `Record` in
`corpus/models.py` gains the matching `isnad_ar: str | None = None`.

**Field usage on a Hadith record:**

| Column | Value |
|---|---|
| `id` | `hadith:bukhari:<hadith_no>` — the convention in the Stage A spec |
| `kind` | `hadith` (Qur'an records use `ayah`) |
| `collection` | `bukhari` |
| `book_no`, `chapter_ar` | kitāb number and bāb heading from the `###` markers |
| `hadith_no` | al-Bughā number, stored as TEXT (the existing column's type) |
| `numbering_scheme` | `bugha-1987` |
| `text_ar` | **the matn**, verbatim |
| `isnad_ar` | the chain, verbatim, or NULL |
| `norm_*` | derived from `text_ar`, i.e. from the matn only |
| `reference_display` | e.g. `Ṣaḥīḥ al-Bukhārī 1` |
| `surah`, `ayah`, `bismillah`, `surah_name_*` | NULL |

`records_fts` needs no schema change: it indexes `norm_standard` and
`norm_aggressive`, which now derive from the matn for Hadith rows. The isnād is
deliberately absent from the FTS index as well as from scoring.

## 7. Matching: the matn, never the isnād

**This is the decision the whole stage turns on.**

`similarity.ratio` scores across the entire stored string. A user quoting
*innamā al-aʿmālu bi'l-niyyāt* types roughly 40 characters. The full first
hadith of Bukhari is roughly 300, most of it narrator names. Scored against the
whole, that match lands near 0.13 — against a `NEAR_THRESHOLD` of 0.86. The
single most quoted hadith in Sunni Islam would return `NOT_FOUND`, and so would
almost every other real quotation, because people quote the Prophet's words and
not the chain that carried them.

Storing the matn in `text_ar` makes the existing engine correct with no change
to its logic. Nobody quotes an isnād; they quote a matn and cite a collection.

The isnād is not discarded — it is stored, and it displays (§9.2). It is
excluded from *scoring*, which is a different thing.

This is structurally the same defect as the Bismillah bug: a storage decision
that silently breaks matching for exactly the most-quoted texts, invisible in
any test whose fixtures were built from the same wrong storage. That is why it
is settled here, in the spec, before a line of parser code exists.

## 8. Citation parsing

`Reference` is Qur'an-shaped (`surah`, `ayah`). Hadith citations look nothing
alike:

> `Bukhari 1` · `Sahih al-Bukhari, no. 1` · `Ṣaḥīḥ al-Bukhārī 1:1` · `al-Bukhari, Book 1, Hadith 1`

**Two independent regex families, dispatched by which matches — not one unified
grammar.** A merged pattern risks a Qur'an citation resolving as a hadith
number or the reverse, and the cost of that is a confidently wrong
`WRONG_REFERENCE`, the most damaging output the tool can produce. `references.py`
already treats a spurious reference as worse than a missed one and guards
accordingly; the same asymmetry applies here.

`Reference` becomes a tagged union — a `HadithReference(collection, hadith_no,
raw, start)` alongside the existing verse form, with `nearest_reference`
returning either. `verify_spans` compares a match's `kind` against the
reference's kind: a Hadith record cited as `2:255`, or an āyah cited as
`Bukhari 1`, is `WRONG_REFERENCE` — a genuinely useful verdict, since
mis-attributing an āyah to Bukhari is a real and common error.

**Bare "Bukhari" with no number does not resolve**, by the same rule that
rejects a bare "Maryam". It names a collection, not a text.

Two ambiguities, resolved explicitly:

- `Bukhari 1:1` is read as **kitāb 1, hadith 1** — not as a Qur'anic
  surah:ayah — because the collection name governs.
- Where a number could be either a kitāb-relative or an absolute al-Bughā
  number, it is read as **absolute**, because that is what English-language
  citation overwhelmingly means. A number exceeding the corpus maximum does not
  silently fall back to the other reading; it is out of range, and the verdict
  says so.

## 9. Product surface

### 9.1 The corpus-scope caveat

The constant at `api/sanad/api/routes.py:31` currently reads *"This corpus
contains the Qur'an only…"*. It becomes:

> This corpus contains the Qur'an and Ṣaḥīḥ al-Bukhārī. Absence of a quotation
> here does not establish that it is fabricated — it may be authentic and
> simply outside what Sanad currently checks.

The second sentence carries more weight now than it did. When the corpus was
the Qur'an alone, a `NOT_FOUND` on Arabic prose was unsurprising. With one
hadith collection present, a reader may take absence as a verdict on
authenticity — that is precisely the misreading the caveat exists to prevent,
and it becomes more likely, not less, as coverage grows.

Rendering is unchanged (Ruling R25): body serif at `--step-0`, cinnabar rule on
the leading edge, not the `.data` register. It is a scribe's gloss, not an
alarm. The pinning test that asserts it is not `.data` still applies. Four test
files hold the old string as a literal and are updated with it.

### 9.2 The isnād displays, always

Not behind a toggle, not truncated, not "show chain ▸". The tool is called
Sanad; hiding the chain would be self-defeating.

It renders in the `.data` register — small mono, the apparatus voice — directly
below the matn, which keeps its large Arabic serif treatment. The distinction
is the point: the matn is what was verified, the isnād is what you consult
once you trust the wording. Same typographic logic that separates a checksum
from a verse.

`IsnadTrace` is unchanged. It traces *our* chain of evidence — quoted →
normalized → matched → cited → source — which is a different chain from the
hadith's own, and conflating the two would be a pun, not a design. The narrator
chain belongs to the record and renders inside `EvidenceCard` with the matn.

### 9.3 Gradings: absent, and said so

One line, once per result, whenever any Hadith record appears — the pattern
just established for the translation-accuracy disclaimer, which was rendering
once per citation until it was fixed:

> Sanad confirms wording against this printed edition. It does not grade
> authenticity (ṣaḥīḥ/ḍaʿīf); that requires a scholarly source.

Two reasons this sentence is required rather than nice to have. Modern gradings
(al-Albānī, d. 1999) are under copyright, so we could not ship them. And the
distinction is genuinely substantive: *"this wording is in Bukhari's text"* and
*"this hadith is sound"* are different claims, and a verification tool that let
users slide from the first to the second would be doing the harm it was built
to prevent. Sanad may say the former. It must never imply the latter — including
by silence, which is why the absence is stated rather than merely observed.

Note the asymmetry with the Qur'an: for an āyah, matching the wording settles
authenticity, because the text is the thing. For a hadith it does not, and the
UI must not let the visual similarity of the two verdicts suggest otherwise.

### 9.4 Frontend changes

Small, and confined to the evidence card:

- `EvidenceCard` renders `isnad_ar` when present, in the `.data` register
- the gradings line renders once in `Verify.tsx`, conditioned on any Hadith
  record being present
- `RecordOut` in `api/sanad/api/schemas.py` gains `isnad_ar`, `collection`,
  `hadith_no`; `web/src/api/types.ts` is regenerated, not hand-edited
- the provenance panel picks up the third source automatically

## 10. OCR noise

OpenITI's own `.yml` flags "random characters" in this file. Expect damage.

**The text is ingested exactly as published. Nothing is corrected.** Editing
the source text would make Sanad a silent corrector of scripture, which its
non-goals forbid in the first sentence, and would break the reproducibility
claim: `content_sha256` is only meaningful if what we ship is what we fetched.

Instead, ingest runs a noise scan and writes a report — records containing
characters outside Arabic, Arabic punctuation and whitespace, flagged with
their id and the offending codepoints. The report is a build artifact for human
review, **not** a filter. Every record is ingested regardless.

A garbled record simply scores badly and returns `NOT_FOUND` or `NEAR_MATCH`,
which is honest: the engine is reporting that the stored text does not match,
and it does not. The report exists so that (a) nobody selects a corrupt record
as an eval case and calibrates against it, and (b) the scale of the problem is
a measured number rather than a vague worry.

## 11. Evaluation

Hadith cases join `eval/`, in the same adversarial style as the existing 35,
under the same CI gate: **zero false verifications, no exceptions.** A false
`EXACT` on a hadith is worse than on an āyah, because the reader has no
memorised text to catch it with.

Required cases:

1. **`innamā al-aʿmālu bi'l-niyyāt`, quoted bare.** Must verify. This is the
   §7 regression test — it fails if anyone ever stores the full text in
   `text_ar`. The most-quoted hadith in the collection is the right canary.
2. **A hadith containing an inline Qur'anic quotation.** Verifies that stripping
   `@QB@` markers did not strip the words between them.
3. **A real hadith with a wrong al-Bughā number.** Must return
   `WRONG_REFERENCE`, not `EXACT` — the number is wrong even though the text
   is right.
4. **A hadith authentic in Muslim but absent from Bukhari.** Must return
   `NOT_FOUND` *with* the reworded caveat. Tests that the caveat does not read
   as an accusation, which is the whole reason for the rewording.
5. **A fabricated hadith in circulation.** `NOT_FOUND`, no near-match
   over-reach.
6. **A personal-ruling question containing a hadith quotation.** Handoff still
   suppresses every mark and every verdict. Stage C shipped this defect once
   (`marksWithheld`); a new corpus is a new chance to reintroduce it.
7. **An āyah cited as "Bukhari 1".** `WRONG_REFERENCE` via the §8 cross-kind
   check.
8. **A matn quoted with its isnād included.** Realistic copy-paste from a
   website. Should still resolve — a documented outcome either way, since a
   long isnād prefix drags the score down; if it cannot verify, it must
   `NOT_FOUND` rather than near-match onto a different hadith.

Case 8 is the one whose behaviour is least predictable in advance. It is
specified as a case precisely so the answer is measured and recorded rather
than assumed.

## 12. Files

```
ingest/
  corpus.lock.toml                    third [[source]] replaces the NOT-YET-RESOLVED note
  sanad_ingest/openiti.py             NEW — mARkdown parser
  sanad_ingest/build.py               dispatch on format; noise report
api/sanad/
  corpus/schema.py                    + isnad_ar
  corpus/models.py                    + isnad_ar
  verify/references.py                + hadith reference family
  verify/engine.py                    cross-kind reference check
  api/schemas.py                      + isnad_ar, collection, hadith_no
  api/routes.py                       reworded corpus_scope
web/src/
  components/EvidenceCard.tsx         isnād block
  screens/Verify.tsx                  gradings line, once
  api/types.ts                        regenerated
eval/cases/hadith.yaml                NEW — the eight cases above
docs/SOURCES.md                       the §4.2 basis, in full
```

## 13. Why this precedes Stage B

Ask mode's value scales with corpus coverage — an Ask pipeline that can only
ground answers in the Qur'an would be rebuilt and re-evaluated the moment
Bukhari lands underneath it. Its eval suite in particular is expensive to
recalibrate, and calibrating it against a corpus we know is about to change
would waste most of that work.

There is a second reason. Stage B's verifier stage *is* this engine. Every
defect the Hadith layer surfaces — a matching threshold that does not transfer,
a citation form that parses wrong — is a defect Ask mode would otherwise
inherit and obscure behind a generated answer, where it is far harder to see.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Full text stored in `text_ar`, breaking short-quote matching | Eval case 1 is exactly this regression, and it is the most-quoted hadith in the collection |
| OCR noise read as verification failure | Measured at ingest, reported, and excluded from eval-case selection; never silently corrected |
| A reader takes `NOT_FOUND` as "fabricated" | Reworded caveat, tested; and eval case 4 exists to keep it honest |
| A reader takes a match as a grading | §9.3 line stated once per result, not inferable from silence |
| Hadith and Qur'an citation grammars collide | Two independent regex families, cross-kind check, bare collection names rejected |
| OpenITI re-OCRs the file and the pin drifts | Commit-pinned URL plus whole-file hash; ingest refuses to build on mismatch |
| The licence question reopens | Basis is the work's own public-domain status and does not depend on OpenITI's answer; enquiry filed anyway |

## 15. Open items

1. **`content_sha256`, `commit`, and `expected_records` are measured at first
   build**, then committed. They are deliberately left unfilled here rather
   than guessed.
2. **The OpenITI licence enquiry** is drafted and unsent. Non-blocking (§4.2).
3. **Transliteration of `reference_display`.** `Ṣaḥīḥ al-Bukhārī 1` with full
   diacritics, or plain `Sahih al-Bukhari 1`? Cosmetic, decided at
   implementation against how the surah names already render.
