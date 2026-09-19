# What Sanad still needs

This is the gap list between the current static prototype and a competition-ready, production-honest product. Grouped by layer, with a priority.

## 1. Data: text and translation

- [ ] Qur'an Arabic, production: Tanzil, imported verbatim, CC BY 3.0, attributed (P0)
- [ ] Qur'an translation, license-cleared: confirm Saheeh International rights, or choose a permissive edition (P0)
- [ ] Hadith text + translation + grading: via sunnah.com API key / offline dump, or a provenance-documented dataset (P0)
- [ ] Tafsir layer: at least one permissioned tafsir, or omit it honestly (P2)
- [ ] Transliteration and word-by-word, only if licensed (P3)

## 2. Metadata and relationships

- [ ] Verse numbering scheme noted (Uthmani vs standard, surah:ayah vs global index) (P0)
- [ ] Qur'an script variant policy (Uthmani / Imlaei / IndoPak) and its effect on matching (P0)
- [ ] Hadith collection, book, chapter, number, edition, and grading source per record (P0)
- [ ] Hadith grading authority recorded — never a single undated label (P1)
- [ ] Topic / subject taxonomy to route questions to evidence (P1)
- [ ] Cross-references between Qur'an, hadith, and tafsir (P2)
- [ ] Glossary of Islamic terms with transliteration and disambiguation (P1)
- [ ] Narrator (isnad/rijal) data, if authenticity reasoning is shown (P2)

## 3. Arabic language processing

- [ ] Normalization ruleset: diacritics, hamza forms, tatweel, alef maqsura (P0)
- [ ] Canonical vs search text separation with checksums (P0)
- [ ] Verse-boundary and quotation-span detection across Arabic and Latin punctuation (P0)
- [ ] Morphological analysis for lemmatized search (P2)
- [ ] Codeswitching handling: Arabic quote inside English prose (P1)

## 4. Retrieval and verification

- [ ] Hybrid lexical (BM25/FTS5) + vector retrieval (P0)
- [ ] Reranker weighting exact matches, collection type, and reference agreement (P1)
- [ ] Claim extraction: separating quotations, paraphrases, and conclusions (P1)
- [ ] Evidence grading rules (P1)
- [ ] Abstention logic and thresholds (P0)
- [ ] Quotation diff view for near-matches and wrong references (P0)

## 5. Generation and safety

- [ ] Arabic-capable embedding model and LLM (P0)
- [ ] Generation constrained to retrieved spans; quotes copied, never invented (P0)
- [ ] Risk router: personal ruling, high-risk, disputed, insufficient evidence (P0)
- [ ] Madhhab policy: describe disagreement, do not flatten it (P0)
- [ ] Handoff packet format for specialists (P1)
- [ ] Refusal templates in Arabic and English (P1)

## 6. Provenance and legal

- [ ] Source register kept current (this repo) (P0)
- [ ] Per-record license and attribution rendering in the UI (P0)
- [ ] Written permission evidence for every bundled asset (P0)
- [ ] Privacy policy and terms of use (P1)
- [ ] PII policy: synthetic or anonymized (P0)
- [ ] Intellectual-property holder / participating entity determined (P1)

## 7. Human and governance

- [ ] Scholar or content advisor on the team (P0)
- [ ] Content review workflow before release (P1)
- [ ] Specialist referral directory (P2)
- [ ] Disagreement and correction process (P2)

## 8. Technical infrastructure

- [ ] Retrieval API service (P1)
- [ ] Vector store (P1)
- [ ] Vector index build + versioning (P1)
- [ ] Authentication, rate limiting, caching (P2)
- [ ] Audit logging (P2)
- [ ] Deployment config and environment setup (P1)
- [ ] GitHub Pages site (done) and any hosted demo (P1)

## 9. Evaluation

- [ ] Gold evaluation set for quotation verification (P0)
- [ ] Adversarial test set wired into CI (P0)
- [ ] Metrics: exact-quote accuracy, wrong-reference detection, fabrication detection, abstention rate (P0)
- [ ] Error analysis report (P1)
- [ ] Reproducibility instructions (P1)

## 10. Submission artifacts

- [ ] Public GitHub repository (P0)
- [ ] Two-minute demo video (P0)
- [ ] Slide deck (P0)
- [ ] Scientific annex (P0)
- [ ] Source and license log (P0)
- [ ] Operating documentation and setup instructions (P0)

## The single hardest dependency

A legally clean, attributable corpus. Everything else is engineering. Resolve the Qur'an translation and the hadith source licenses before writing retrieval code that depends on them.

None of the above is legal advice. Confirm each license with the rights holder for the exact edition you ship.
