# What Sanad still needs

The gap list between what Sanad is today and a competition-ready,
production-honest product. Grouped by layer.

Written before any code existed, and revised **2026-09-23**, after the
deterministic verification core, the React frontend and the Bukhārī corpus
shipped. `- [ ]` is open, with a priority; `- [x]` is done; `- [~]` is a
**deliberate non-goal** — something this list once called a gap that we have
since decided not to build, with the reason. Those are the entries worth
reading: a checked box only says we did the work, whereas a tilde says we
understood the item well enough to refuse it.

## 1. Data: text and translation

- [x] Qur'an Arabic, production: Tanzil Uthmani 1.1, imported verbatim from the
      XML export, CC BY 3.0, attributed. 6,236 āyāt.
- [x] Qur'an translation, license-cleared: Pickthall, public domain, via Tanzil.
      Saheeh International was **not** pursued — its rights could not be
      confirmed, and a permissive edition was chosen instead.
- [x] Hadith **text**: Sahih al-Bukhari, 7,129 hadith, OpenITI JK000110
      (`ara1.completed`), from the al-Bughā 3rd edition, Dār Ibn Kathīr /
      al-Yamāma, Beirut, 1407/1987. Basis for use is the
      matn's own public-domain status as a 9th-century work — **not** the
      repository, which carries no licence file; OpenITI's MIT licence covers
      tooling only.
- [ ] Hadith **English translation**: none shipped. No permissively licensed
      translation of Bukhārī has been identified (P1)
- [~] Hadith **grading**: deliberate **non-goal**, not a gap. Modern gradings
      (al-Albānī, d. 1999) are copyrighted, and authenticity is not ours to
      assert. Sanad may say *"this text is in Sahih al-Bukhari"* and must never
      say *"this hadith is sahih."* Revisit only for a collection whose own
      classical gradings are part of its public-domain text — Tirmidhī's are,
      al-Albānī's are not.
- [ ] Tafsir layer: at least one permissioned tafsir, or omit it honestly (P2)
- [ ] Transliteration and word-by-word, only if licensed (P3)

## 2. Metadata and relationships

- [x] Verse numbering scheme noted: surah:ayah, Uthmani, Tanzil's numbering;
      basmala counted as āyah 1 only in al-Fātiḥa.
- [x] Qur'an script variant policy: Uthmani is canonical; Imlaei and IndoPak
      input are reached through the three normalization tiers rather than by
      storing variant texts.
- [x] Hadith `collection`, `book_no`, `chapter_ar` and `hadith_no` per record;
      the edition hangs off the record's `source_id`. `chapter_ar` is empty on
      33 of 7,129, scattered over 14 books in short runs; whether the upstream
      headings are absent or the parser drops them has **not** been checked
      (P3 — it affects display, never matching).
      Grading source is deliberately absent — see the non-goal above.
      Note `hadith_no` is **not unique**: 7,124 distinct numbers over 7,129
      records, so a citation resolves to any record bearing that number.
- [~] Hadith grading authority: **non-goal**, as above. The rule *"never a
      single undated label"* stands if this is ever revisited.
- [ ] **Book-relative hadith citations.** `Book 52, Hadith 268` is USC-MSA /
      sunnah.com numbering — the form most people copy-paste — and this corpus
      is numbered by the al-Bughā edition. We have no mapping between them and
      will not invent one, so such a citation currently resolves to nothing:
      the quotation is still verified on its text, but the reference is
      neither confirmed nor challenged. Reading it as an al-Bughā number
      instead would tell correctly-citing readers they are wrong, which is
      why it does not. Two things are missing: a real concordance, and a way
      for the product to *say* "we recognised this citation and cannot
      resolve it" rather than falling silent (P1)
- [ ] Topic / subject taxonomy to route questions to evidence (P1)
- [ ] Cross-references between Qur'an, hadith, and tafsir (P2)
- [ ] Glossary of Islamic terms with transliteration and disambiguation (P1)
- [x] Narrator chain (isnād) stored per hadith and displayed in the evidence
      card. Rijāl data — who the narrators were, and their reliability — is
      **not** present and is not planned, because it exists to support
      authenticity reasoning, which Sanad does not do.

## 3. Arabic language processing

- [x] Normalization ruleset: three named tiers — `light`, `standard`,
      `aggressive` — covering diacritics, hamza forms, tatweel and alef
      maqsura. Each tier is coupled to the verdict it may produce.
- [x] Canonical vs search text separation with checksums: `text_ar` is stored
      verbatim with a `text_ar_sha256`; normalized forms are derived for the
      FTS index and never written back over the canonical text.
- [x] Verse-boundary and quotation-span detection across Arabic and Latin
      punctuation, including «», "", and bare Arabic runs.
- [ ] Morphological analysis for lemmatized search (P2)
- [x] Codeswitching: an Arabic quotation inside English prose is the primary
      case the extractor is built for, and citations in either script attach
      to the span they sit beside.

## 4. Retrieval and verification

- [x] Lexical retrieval: SQLite FTS5 over the normalized text, plus a direct
      exact lookup per tier. Deliberately no vector retrieval on the verify
      path — verification must be reproducible and offline, and an embedding
      model is neither.
- [ ] Vector retrieval for the **Ask** path only, where recall matters more
      than determinism (P1)
- [ ] Reranker weighting exact matches, collection type, and reference
      agreement — Ask path only (P1)
- [x] Claim extraction: quotations, paraphrases and conclusions separated, in
      `verify/claims.py`.
- [x] Evidence rules: five verdicts, each tied to the normalization tier that
      produced it. Note these grade the **quotation**, not the hadith — see
      the grading non-goal in §1.
- [x] Abstention: `NOT_FOUND` rather than a nearest guess below the near-match
      threshold, and a risk router that diverts personal-ruling and high-risk
      questions to a handoff instead of answering.
- [x] Quotation diff view for near-matches and wrong references
      (`CharDiff.tsx`), character-level, both directions.

## 5. Generation and safety

This whole section is Stage B (Ask). The verify path generates nothing.

- [~] Arabic-capable embedding model and LLM: **wired** (Voyage `voyage-4`
      binary embeddings + Claude `claude-opus-5`), but **not yet smoke-tested
      against a live key** — the API shapes are pinned from published docs, not
      a live response. First check when a key lands (P0).
- [x] Generation constrained to retrieved spans; quotes copied, never invented:
      the server renders every quotation from the database by id and Claude
      never emits Arabic; the deterministic guards reject any cited id outside
      the retrieved candidate set and any Arabic in the prose, and the
      two-sided eval gate fails CI if either direction breaks. Fabrication is
      structural, not policed (P0).
- [x] Risk router: personal ruling, high-risk, disputed and
      insufficient-evidence classes are detected and diverted today, ahead of
      the Ask route that will consume them. Over-diverts ~15–20%, by design.
- [~] Madhhab policy, **partly**: a question naming a school, or naming
      ikhtilāf, is classified `DISPUTED` and labelled as such. It is
      deliberately *not* forced to a handoff — only personal-ruling and
      high-risk are — because flagging disagreement is honest while refusing
      to discuss it is not. Actually *describing* the disagreement needs
      generation, so it lands in Stage B and is still open (P0 there).
- [x] Handoff packet: rendered by `HandoffCard.tsx`. Known flaw — the
      faith-crisis case reuses the personal-ruling copy, which presumes the
      person wants a scholar.
- [ ] Refusal templates in Arabic — English exists, Arabic does not (P1)
- [ ] **Framing fairness has no hard guard** — the deterministic guards block
      grading claims, unanimity claims, Arabic in the prose, and out-of-set
      ids, but they do **not** enforce that the framing or summary is balanced
      or representative; that is left to the stage-5 audit, which is semantic
      (a model judgement) rather than a hard deterministic gate. A refusal of
      record, not an oversight: a deterministic fairness test is not something
      we know how to write honestly yet (spec §5).
- [ ] **Public-demo spend cap unresolved** — the Ask path has no budget
      ceiling on the hosted demo's Anthropic key. Left open deliberately, but
      it is a P0 before any public demo goes live (spec §15).

## 6. Provenance and legal

- [x] Source register kept current: `docs/SOURCES.md`, one entry per bundled
      text with its licence **basis**, not merely its origin.
- [x] Per-record licence and attribution rendered in the UI, beside the
      evidence rather than buried in a footer.
- [~] Written permission: not obtainable and not required for what is bundled
      — everything shipped is either public domain by age or carries an
      explicit open licence. The obligation this item was really about is
      recording **why** each text may be used, which `SOURCES.md` now does.
      It binds again the moment a text needs permission; at that point, get it
      in writing or do not ship the text.
- [ ] Privacy policy and terms of use (P1)
- [x] PII: none collected. No accounts, no client analytics. The audit log
      records verdicts, record ids and claim kinds — the submitted text and
      the extracted quotations are never written to it
      (`api/sanad/api/routes.py:148`). Nothing to anonymize.
- [ ] Intellectual-property holder / participating entity determined (P1) —
      still open, and the one item here with a real deadline.

## 7. Human and governance

- [ ] Scholar or content advisor on the team (P0)
- [ ] Content review workflow before release (P1)
- [ ] Specialist referral directory (P2)
- [ ] Disagreement and correction process (P2)

## 8. Technical infrastructure

- [x] Retrieval API service: FastAPI — `/verify`, `/records/{id}`, `/search`,
      `/corpus`, `/health` — over a read-only corpus connection.
- [ ] Vector store — Ask path only (P1)
- [ ] Vector index build + versioning — Ask path only (P1)
- [ ] Authentication, rate limiting, caching (P2)
- [x] Audit logging: separate database from the corpus, PII-free as above.
- [x] Deployment: Vercel, with FastAPI serving the React build through a
      SPA-fallback static mount.
- [x] GitHub Pages site, and a hosted demo on Vercel. The demo deploys and was
      verified locally against the same entrypoint; it has **not** been loaded
      from a browser on the development machine, whose network blocks the
      host.

## 9. Evaluation

- [x] Gold evaluation set: 54 cases over six files — exact quotes, character
      mutations, wrong references, fabrications, claim/risk routing, hadith.
- [x] Adversarial set wired into CI: `python eval/runner.py` is a required
      step, alongside pytest and ruff.
- [x] Metrics: pass/fail per case, verdict distribution, and a
      **false-verification count that fails the build at one**. The gate is
      span-budgeted, so a fabrication cannot verify invisibly alongside a
      genuine āyah in the same case.
- [x] Error analysis: `docs/hadith-noise-report.md` for the corpus, and
      `docs/hadith-build-log.md` for the defect record behind it — every
      ruling, including the two that were later overturned and the argument
      that overturned them.
- [x] Reproducibility: the corpus rebuilds byte-identically from cached
      sources, and the build is checksummed. Instructions in `README.md`.

## 10. Submission artifacts

- [x] Public GitHub repository.
- [ ] Two-minute demo video (P0)
- [ ] Slide deck (P0)
- [ ] Scientific annex (P0)
- [x] Source and licence log: `docs/SOURCES.md`.
- [x] Operating documentation and setup instructions: `README.md`, including
      the reproducibility check.

## The single hardest dependency

It **was** a legally clean, attributable corpus — and that is now resolved for
what is shipped: Tanzil under CC BY 3.0, Pickthall in the public domain, and
Bukhārī's matn public domain by age. The pattern that got us there is in
`SOURCES.md`: record *why* a text may be used, never merely where it came
from. "Freely available" is not a licence.

The hardest remaining dependency is human, not legal: **no scholar or content
advisor is on this project** (§7, still entirely open). Every safeguard built
so far is a refusal to overstep — Sanad confirms wording against a printed
edition and declines to grade authenticity — and that holds precisely because
nobody has yet been in a position to say more. The line stops being a design
choice and starts being a limitation the moment the product tries to answer
rather than verify, which is exactly what Stage B does.

None of the above is legal advice. Confirm each licence with the rights holder
for the exact edition you ship.
