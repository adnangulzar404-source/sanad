# Source register

This document is a human-readable companion to `data/sources.json`. It is part of the submission evidence, not decoration.

## Safe initial corpus

### Qur’an

Use the Tanzil text as the leading candidate for the production Arabic Qur’an layer. Tanzil states that the text is under Creative Commons Attribution 3.0 and requires attribution, a link to Tanzil, preservation of its notice, and no change to verbatim copies. Store the canonical text unchanged; create a separate normalized field for matching.

### Hadith

Do not ship scraped Hadith from a public website merely because it is accessible; accessibility is not a licence. What the production corpus needs for the exact text, edition and metadata is a recorded *basis* — either the work's own public-domain status or a redistribution grant that can actually be pointed at. **Status: shipped.** Sahih al-Bukhari (7,129 records, matn + isnad) and Sahih Muslim (7,460 records, matn + isnad, Task 11) are in the corpus on the first of those; the basis for each is recorded in full below (see **Sahih al-Bukhari: the licensing basis** and **Sahih Muslim: the licensing basis**), and `docs/superpowers/specs/2026-09-22-hadith-corpus-design.md` §4 has the complete source and parsing rationale. Each record carries collection, book, number, edition and provenance, and no grading: modern authenticity gradings are copyrighted scholarly work, and authenticity is not Sanad's to assert.

### Translations and tafsir

Translations, tafsir, explanations, and fiqh books should be treated as separate copyrighted assets. Add them only after confirming the exact license and whether public display, indexing, modification, and redistribution are allowed.

## Sahih al-Bukhari: the licensing basis

This reproduces `docs/superpowers/specs/2026-09-22-hadith-corpus-design.md` §4.2 in full, because the basis for shipping this text is a decision, not a footnote, and it must not be diluted by paraphrase.

### The file

`data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed` in `github.com/OpenITI/0275AH`. The file's own `#META#` header records the edition, which is better evidence than the sidecar `.yml`:

```
040.EdEDITOR    :: د. مصطفى ديب البغا      (Muṣṭafā Dīb al-Bughā)
043.EdPUBLISHER :: دار ابن كثير , اليمامة   (Dār Ibn Kathīr / al-Yamāma)
044.EdPLACE     :: بيروت                    (Beirut)
045.EdYEAR      :: 1407 - 1987
041.EdNUMBER    :: الثالثة                  (3rd edition)
020.BookTITLE   :: الجامع الصحيح المختصر
```

Sibling files in the same directory (`Shamela0001681`, `Shia001715Vols`) carry unfilled placeholder metadata and were rejected on that basis alone — this corpus is vetted per file, never "ingest the repo."

### Why we may ship it — the legal basis

**Basis: the work's own public-domain status.** Muhammad ibn Ismail al-Bukhari died in 870 CE. The matn and the isnad are public domain in every jurisdiction, without qualification.

**Not an OpenITI licence grant, and the distinction is load-bearing.** OpenITI's website states CC BY-SA, but the data repository `OpenITI/0275AH` carries no `LICENSE` file, and the `OpenITI/OpenITI` repository's MIT licence covers their Python tooling, not corpus text. **Verified 2026-09-22.** Citing a grant we cannot point to would repeat exactly the error the Pickthall entry (above) corrects: relying on a distributor's terms instead of examining the basis, and handing a downstream commercial user a problem, since Sanad's code is MIT.

What OpenITI contributes is transcription and structural markup. A faithful mechanical transcription of a public-domain text attracts no new copyright. Their markup is not carried into the corpus — the parser consumes it and discards it, so the stored text is the public-domain text and nothing else. The 1987 al-Bugha edition's own editorial apparatus — introductions, footnotes, indices — was already stripped upstream by OpenITI Clean in 2023 and is likewise absent. What remains is matn and isnad.

**Attribution to OpenITI is given as credit, not as licence compliance.** They are recorded in `sources` with file, edition, commit and retrieval date, and shown in the provenance panel, because a provenance tool that obscured where it got its text would be self-refuting.

**Still to do, non-blocking:** the drafted enquiry (`docs/superpowers/research/2026-09-20-openiti-licence-enquiry.md`) has not been filed as a GitHub issue. If OpenITI replies with terms that change the picture, this basis is revisited. Nothing about the current basis depends on their answer.

### The pinned commit and hash

```toml
[[source]]
id               = "openiti-bukhari-jk000110"
kind             = "hadith-arabic"
format           = "openiti-markdown"
title            = "الجامع الصحيح المختصر (Sahih al-Bukhari)"
publisher        = "OpenITI (transcription); Dar Ibn Kathir / al-Yamama, Beirut (edition)"
edition          = "al-Bugha, 3rd ed., 1407/1987; OpenITI JK000110, ara1.completed"
url              = "https://raw.githubusercontent.com/OpenITI/0275AH/47dfd28db9e158c7101c7df1162d4dc99bb70303/data/0256Bukhari/0256Bukhari.Sahih/0256Bukhari.Sahih.JK000110-ara1.completed"
commit           = "47dfd28db9e158c7101c7df1162d4dc99bb70303"
license_id       = "public-domain"
license_url      = "https://github.com/OpenITI/0275AH"
content_sha256   = "69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7"
expected_records = 7129
modifications    = "mARkdown structural markers parsed and discarded; no text altered"
```

`commit` is pinned (unlike the Tanzil entries, which publish stable versioned exports) because OpenITI is a live git repository whose files are re-OCRed in place, so a branch URL is not a real pin. `content_sha256` covers the complete raw file, verified byte-identical (5,524,762 bytes) via an authenticated `gh` session at commit `47dfd28d...` (2025-11-27, "ns update"). See `ingest/corpus.lock.toml` for the authoritative, machine-checked copy of this entry.

## Sahih Muslim: the licensing basis

The second collection ingested (Task 11), on the same basis as Sahih al-Bukhari above, carrying the same one-time numbering-scheme distinction the two editions require: Bukhari's al-Bugha numbering (`bugha-1987`) and Muslim's Muhammad Fu'ad 'Abd al-Baqi numbering (`abdalbaqi`) are recorded per source rather than assumed to be one scheme, because they are not.

### The file

`data/0261Muslim/0261Muslim.Sahih/0261Muslim.Sahih.JK000109-ara1` in `github.com/OpenITI/0275AH`. The file's own `#META#` header records the edition:

```
010.AuthorNAME  :: مسلم بن الحجاج أبو الحسين القشيري النيسابوري
011.AuthorDIED  :: 261                        (AH)
020.BookTITLE   :: صحيح مسلم
040.EdEDITOR    :: محمد فؤاد عبد الباقي        (Muhammad Fu'ad 'Abd al-Baqi)
043.EdPUBLISHER :: دار إحياء التراث العربي     (Dar Ihya al-Turath al-Arabi)
044.EdPLACE     :: بيروت                       (Beirut)
```

Selected the same way Bukhari's file was: the JK-prefixed curated OpenITI version, not a `Shamela*`/`ShamAY*`/`Shia*` scrape.

### Why we may ship it — the legal basis

**Basis: the work's own public-domain status.** Muslim ibn al-Hajjaj al-Qushayri al-Naysaburi died in 261 AH (875 CE). The matn and the isnad are public domain in every jurisdiction, without qualification — the identical basis Sahih al-Bukhari ships on above, restated here rather than assumed, because a basis recorded once for one work is not automatically a basis for a second one by a different author.

**Not an OpenITI licence grant, and the distinction is load-bearing here for exactly the reason it was for Sahih al-Bukhari.** OpenITI is the transcriber, not the rights holder of anything requiring a grant: what they contribute is transcription and structural markup, and a faithful mechanical transcription of a public-domain text attracts no new copyright. Their markup (mARkdown structural markers, page/volume anchors) is not carried into the corpus — the parser consumes it and discards it. 'Abd al-Baqi's editorial apparatus — his introductions, footnotes, and the vowelling/typesetting choices of his edition — is likewise not carried into the corpus; what is ingested is matn and isnad. His **numbering** is a separate matter from his apparatus: a sequential count of units is a fact about how the edition is organized, not a copyrightable expression, and it is recorded as `numbering_scheme = "abdalbaqi"` precisely so it is never confused with al-Bugha's Bukhari numbering or presented as if it were.

**Attribution to OpenITI is given as credit, not as licence compliance**, on the same terms as the Bukhari entry: recorded in `sources` with file, edition, commit and retrieval date, and shown in the provenance panel.

### The pinned commit and hash

```toml
[[source]]
id                 = "openiti-muslim-jk000109"
kind               = "hadith-arabic"
format             = "openiti-markdown"
collection         = "muslim"
numbering_scheme   = "abdalbaqi"
title              = "صحيح مسلم (Sahih Muslim)"
publisher          = "OpenITI (transcription); Dar Ihya al-Turath al-Arabi, Beirut (edition)"
edition            = "ed. Muhammad Fu'ad 'Abd al-Baqi; OpenITI JK000109, ara1"
url                = "https://raw.githubusercontent.com/OpenITI/0275AH/44e1c36738a2bf5c14dafa232a6ae1891e6171cd/data/0261Muslim/0261Muslim.Sahih/0261Muslim.Sahih.JK000109-ara1"
commit             = "44e1c36738a2bf5c14dafa232a6ae1891e6171cd"
license_id         = "public-domain"
license_url        = "https://github.com/OpenITI/0275AH"
content_sha256     = "32b8b949d80d22d3db81be52d8749bc191f12510c8afe19868589bc4b08605e8"
expected_records   = 7460
modifications      = "mARkdown structural markers parsed and discarded; no text altered"
```

`commit` is pinned for the same reason as Bukhari's entry: OpenITI is a live git repository whose files are re-OCRed in place. `content_sha256` covers the complete raw file (4,560,879 bytes), computed by the build itself (`sanad-ingest build`, measured-then-pinned per the project's build-measured-placeholder convention) and re-verified green on every subsequent build. See `ingest/corpus.lock.toml` for the authoritative, machine-checked copy of this entry.

### The built corpus

The committed `data/sanad-quran.db` holds 20,825 records: 6,236 ayat (Tanzil Uthmani, CC BY 3.0) + 7,129 Sahih al-Bukhari hadith + 7,460 Sahih Muslim hadith (public-domain bases above). Its whole-file SHA-256 is verified at build time and printed by `sanad-ingest build`; see `README.md` for the currently-committed value and the reproducibility check.

**Product constraint, stated here because it follows directly from the bases above.** Sanad ships no hadith gradings — modern authenticity gradings are copyrighted scholarly work, and authenticity is not Sanad's to assert. Sanad may say "this text is in Sahih al-Bukhari" or "this text is in Sahih Muslim"; it must never say or imply "this hadith is sahih."

## Sunan Abi Dawud: the licensing basis

The third collection ingested (Task 12), on the same basis as Sahih al-Bukhari and Sahih Muslim above, with its own numbering-scheme distinction recorded per source rather than assumed: Muhammad Muhyi al-Din 'Abd al-Hamid's edition numbering is `numbering_scheme = "abdalhamid"`, distinct from Bukhari's `bugha-1987` and Muslim's `abdalbaqi`.

### The file

`data/0275AbuDawudSijistani/0275AbuDawudSijistani.Sunan/0275AbuDawudSijistani.Sunan.JK000142-ara1` in `github.com/OpenITI/0275AH`. The file's own `#META#` header records the edition:

```
010.AuthorNAME  :: سليمان بن الأشعث أبو داود السجستاني الأزدي
011.AuthorDIED  :: 275                        (AH)
020.BookTITLE   :: سنن أبي داود
040.EdEDITOR    :: محمد محيي الدين عبد الحميد  (Muhammad Muhyi al-Din 'Abd al-Hamid)
043.EdPUBLISHER :: دار الفكر                   (Dar al-Fikr)
```

Selected the same way the Bukhari and Muslim files were: the JK-prefixed curated OpenITI version, not a `Shamela*`/`ShamAY*`/`Shia*` scrape.

**Recorded honestly, not papered over:** this edition's `#META#` header leaves `041.EdNUMBER`, `044.EdPLACE`, and `045.EdYEAR` as `NODATA`/`-` — the edition's print run number, place of publication, and year are not recorded in OpenITI's transcription, unlike the Sahih al-Bukhari and Sahih Muslim files above, which carry a place and (implicitly, via the edition line) a year. This does not affect the licensing basis below, which rests on the author's death date rather than on any fact about the printing — but it is a real gap in this file's own provenance metadata, shipped anyway under Stage A3's relaxed-bar SHIP ruling (R-A3-1), and it is recorded here, beside the corpus it describes, rather than silently completed or guessed.

### Why we may ship it — the legal basis

**Basis: the work's own public-domain status.** Abu Dawud al-Sijistani (Sulayman ibn al-Ash'ath) died in 275 AH (889 CE). The matn and the isnad are public domain in every jurisdiction, without qualification — the identical basis Sahih al-Bukhari and Sahih Muslim ship on above, restated here rather than assumed, because a basis recorded once is not automatically a basis for a third work by a third author.

**Not an OpenITI licence grant, and the distinction is load-bearing here for exactly the reason it was for the first two collections.** OpenITI is the transcriber, not the rights holder of anything requiring a grant: what they contribute is transcription and structural markup, and a faithful mechanical transcription of a public-domain text attracts no new copyright. Their markup (mARkdown structural markers, page/volume anchors) is not carried into the corpus — the parser consumes it and discards it. 'Abd al-Hamid's editorial apparatus — his introductions, footnotes, and the vowelling/typesetting choices of his edition — is likewise not carried into the corpus; what is ingested is matn and isnad. His **numbering** is a separate matter from his apparatus: a sequential count of units is a fact about how the edition is organized, not a copyrightable expression, and it is recorded as `numbering_scheme = "abdalhamid"` precisely so it is never confused with al-Bugha's or 'Abd al-Baqi's numbering or presented as if it were.

**Attribution to OpenITI is given as credit, not as licence compliance**, on the same terms as the Bukhari and Muslim entries: recorded in `sources` with file, edition, commit and retrieval date, and shown in the provenance panel.

### The pinned commit and hash

```toml
[[source]]
id               = "openiti-abudawud-jk000142"
kind             = "hadith-arabic"
collection       = "abudawud"
numbering_scheme = "abdalhamid"
format           = "openiti-markdown"
title            = "سنن أبي داود (Sunan Abi Dawud)"
publisher        = "OpenITI (transcription); Dar al-Fikr (edition)"
edition          = "ed. Muhammad Muhyi al-Din Abd al-Hamid; OpenITI JK000142, ara1"
url              = "https://raw.githubusercontent.com/OpenITI/0275AH/44e1c36738a2bf5c14dafa232a6ae1891e6171cd/data/0275AbuDawudSijistani/0275AbuDawudSijistani.Sunan/0275AbuDawudSijistani.Sunan.JK000142-ara1"
commit           = "44e1c36738a2bf5c14dafa232a6ae1891e6171cd"
license_id       = "public-domain"
license_url      = "https://github.com/OpenITI/0275AH"
content_sha256   = "94d6fe547384efd2f8b369879775f617cb6283053482dc672ff04fbb5454292e"
expected_records = 5274
modifications    = "mARkdown structural markers parsed and discarded; no text altered"
```

`commit` is pinned for the same reason as the Bukhari and Muslim entries: OpenITI is a live git repository whose files are re-OCRed in place, and this is the same commit both of those sources are pinned to. `content_sha256` covers the complete raw file, computed by the build itself (`sanad-ingest build`, measured-then-pinned per the project's build-measured-placeholder convention) and re-verified green on every subsequent build. `expected_records` (5,274) is one fewer than the raw file's own count of numbered units: unit "1" in the raw text is a mis-wrapped kitab heading ("kitab al-tahara") that the parser now recognizes as a heading rather than a hadith (see the `_KITAB_WORD` branch in `ingest/sanad_ingest/openiti.py`'s `flush()`). See `ingest/corpus.lock.toml` for the authoritative, machine-checked copy of this entry.

### The built corpus

The committed `data/sanad-quran.db` held 26,099 records before this task: 6,236 ayat (Tanzil Uthmani, CC BY 3.0) + 7,129 Sahih al-Bukhari hadith + 7,460 Sahih Muslim hadith + 5,274 Sunan Abi Dawud hadith (public-domain bases above). Its whole-file SHA-256 is verified at build time and printed by `sanad-ingest build`; see `README.md` for the currently-committed value and the reproducibility check. Adding this third collection was proven not to perturb either of the first two: the Bukhari and Muslim record sets are byte-identical, across every stored column, before and after Task 12.

**Product constraint, stated here because it follows directly from the bases above.** Sanad ships no hadith gradings — modern authenticity gradings are copyrighted scholarly work, and authenticity is not Sanad's to assert. Sanad may say "this text is in Sahih al-Bukhari", "this text is in Sahih Muslim", "this text is in Sunan Abi Dawud", "this text is in Jami at-Tirmidhi", or "this text is in Sunan an-Nasai"; it must never say or imply "this hadith is sahih."

## Jami at-Tirmidhi: the licensing basis

The fourth collection ingested (Task 13), on the same basis as the three collections above, with its own numbering-scheme distinction recorded per source rather than assumed: Ahmad Muhammad Shakir's edition numbering is `numbering_scheme = "shakir"`, distinct from Bukhari's `bugha-1987`, Muslim's `abdalbaqi`, and Abu Dawud's `abdalhamid`.

### The file

`data/0279Tirmidhi/0279Tirmidhi.Sunan/0279Tirmidhi.Sunan.JK000140-ara1.completed` in `github.com/OpenITI/0300AH`. The file's own `#META#` header records the edition:

```
010.AuthorNAME  :: محمد بن عيسى أبو عيسى الترمذي السلمي
011.AuthorDIED  :: 279                        (AH)
020.BookTITLE   :: الجامع الصحيح سنن الترمذي
040.EdEDITOR    :: أحمد محمد شاكر وآخرون       (Ahmad Muhammad Shakir wa-akharun)
041.EdNUMBER    :: NODATA
043.EdPUBLISHER :: دار إحياء التراث العربي     (Dar Ihya al-Turath al-Arabi)
044.EdPLACE     :: بيروت                       (Beirut)
045.EdYEAR      :: -
```

Selected the same way the three preceding files were: the JK-prefixed curated OpenITI version, not a `Shamela*`/`ShamAY*`/`Shia*` scrape — and, uniquely among the four hadith files this project has ingested, the `.completed` processing stage rather than the bare `ara1` stage, meaning OpenITI's own markup pass has finished on this file.

**Recorded honestly, not papered over:** this edition's `#META#` header leaves `041.EdNUMBER` (`NODATA`) and `045.EdYEAR` (`-`) unfilled — the edition's print run number and year are not recorded in OpenITI's transcription. This is, in fact, the strongest metadata of the four files shipped so far: unlike Sunan Abi Dawud's file, `044.EdPLACE` (Beirut) and `043.EdPUBLISHER` are both filled here, and the `.completed` stage is a further sign of transcription maturity Abu Dawud's `ara1`-stage file does not carry. The gap that remains does not affect the licensing basis below, which rests on the author's death date rather than on any fact about the printing — but it is recorded here, beside the corpus it describes, rather than silently completed or guessed, shipped under the same Stage A3 relaxed-bar ruling (R-A3-1) as Abu Dawud's file.

### Why we may ship it — the legal basis

**Basis: the work's own public-domain status.** Abu 'Isa Muhammad ibn 'Isa al-Tirmidhi died in 279 AH (892 CE). The matn and the isnad are public domain in every jurisdiction, without qualification — the identical basis the three collections above ship on, restated here rather than assumed, because a basis recorded once is not automatically a basis for a fourth work by a fourth author.

**Not an OpenITI licence grant, and the distinction is load-bearing here for exactly the reason it was for the first three collections.** OpenITI is the transcriber, not the rights holder of anything requiring a grant: what they contribute is transcription and structural markup, and a faithful mechanical transcription of a public-domain text attracts no new copyright. Their markup (mARkdown structural markers, page/volume anchors) is not carried into the corpus — the parser consumes it and discards it. Shakir's editorial apparatus — his introductions, footnotes, cross-reference numbers (the bracketed `[NNN]` apparatus stripped by `_strip_reference_numbers`), and the vowelling/typesetting choices of his edition — is likewise not carried into the corpus; what is ingested is matn and isnad. His **numbering** is a separate matter from his apparatus: a sequential count of units is a fact about how the edition is organized, not a copyrightable expression, and it is recorded as `numbering_scheme = "shakir"` precisely so it is never confused with the other three editions' numbering or presented as if it were.

**Al-Tirmidhi's own classical grading phrases are retained byte-exact as part of the canonical text, and are not exposed as a grading apparatus.** Modern authenticity gradings are copyrighted scholarly work outside this corpus's basis, exactly as for the 7,129 records of Sahih al-Bukhari and the rest of this corpus. Abu 'Isa's own remarks — "hadha hadith hasan sahih", "wa fi al-bab 'an ...", and the other classical formulas R-A3-19's split moves into `addenda_ar` — are a different thing: part of the primary source text itself, thirteen centuries old, on the same public-domain basis as the matn and isnad around them. They are preserved, byte-exact, and still displayed as part of the record's full printed text; they are simply not scored as the matn, and Sanad never surfaces them as a grading verdict. Sanad confirms wording; it does not grade (R-A3-2).

**Attribution to OpenITI is given as credit, not as licence compliance**, on the same terms as the three entries above: recorded in `sources` with file, edition, commit and retrieval date, and shown in the provenance panel.

### The pinned commit and hash

```toml
[[source]]
id               = "openiti-tirmidhi-jk000140"
kind             = "hadith-arabic"
collection       = "tirmidhi"
numbering_scheme = "shakir"
format           = "openiti-markdown"
title            = "الجامع الصحيح سنن الترمذي (Jami at-Tirmidhi)"
publisher        = "OpenITI (transcription); Dar Ihya al-Turath al-Arabi (edition)"
edition          = "ed. Ahmad Muhammad Shakir wa-akharun; OpenITI JK000140, ara1.completed"
url              = "https://raw.githubusercontent.com/OpenITI/0300AH/01a1544130e0236850ef2698923ad01575c5bd7c/data/0279Tirmidhi/0279Tirmidhi.Sunan/0279Tirmidhi.Sunan.JK000140-ara1.completed"
commit           = "01a1544130e0236850ef2698923ad01575c5bd7c"
license_id       = "public-domain"
license_url      = "https://github.com/OpenITI/0300AH"
content_sha256   = "5bc99d3d942ceaa729a83c11389016d940ae11fb0b641a4e012c743f9e44b647"
expected_records = 3976
modifications    = "mARkdown structural markers parsed and discarded; no text altered"
```

`commit` is pinned for the same reason as the three entries above: OpenITI is a live git repository whose files are re-OCRed in place. `content_sha256` covers the complete raw file, computed by the build itself (`sanad-ingest build`, measured-then-pinned per the project's build-measured-placeholder convention) and re-verified green on every subsequent build. `expected_records` (3,976) is the raw file's own count of numbered units unchanged — unlike Abu Dawud, no unit here is a mis-wrapped kitab heading. See `ingest/corpus.lock.toml` for the authoritative, machine-checked copy of this entry.

### The built corpus

The committed `data/sanad-quran.db` now holds 30,075 records: 6,236 ayat (Tanzil Uthmani, CC BY 3.0) + 7,129 Sahih al-Bukhari hadith + 7,460 Sahih Muslim hadith + 5,274 Sunan Abi Dawud hadith + 3,976 Jami at-Tirmidhi hadith (public-domain bases above). Its whole-file SHA-256 is verified at build time and printed by `sanad-ingest build`; see `README.md` for the currently-committed value and the reproducibility check. Adding this fourth collection was proven not to perturb any of the first three: the Bukhari, Muslim and Abu Dawud record sets are byte-identical, across every stored column, before and after Task 13 — built in an isolated `git worktree add --detach` at the pre-Task-13 commit, with the shared `.venv`'s editable-install package mapping overridden (not merely assumed inert) so the "before" build actually runs the old commit's code rather than silently re-running HEAD's.

## Sunan an-Nasai (al-Mujtaba): the licensing basis

The fifth collection ingested (Task 14), on the same basis as the four collections above, with its own numbering-scheme distinction recorded per source rather than assumed: Abd al-Fattah Abu Ghudda's edition numbering is `numbering_scheme = "abughudda"`, distinct from Bukhari's `bugha-1987`, Muslim's `abdalbaqi`, Abu Dawud's `abdalhamid`, and Tirmidhi's `shakir`.

### The file

`data/0303Nasai/0303Nasai.SunanSughra/0303Nasai.SunanSughra.JK000130-ara1.mARkdown` in `github.com/OpenITI/0325AH`. The file's own `#META#` header records the edition:

```
010.AuthorNAME  :: أحمد بن شعيب أبو عبد الرحمن النسائي
011.AuthorDIED  :: 303                        (AH)
020.BookTITLE   :: المجتبى من السنن
040.EdEDITOR    :: عبدالفتاح أبو غدة           (Abd al-Fattah Abu Ghudda)
041.EdNUMBER    :: الثانية                     (2nd)
043.EdPUBLISHER :: مكتب المطبوعات الإسلامية    (Maktab al-Matbuat al-Islamiyya)
044.EdPLACE     :: حلب                         (Aleppo)
045.EdYEAR      :: 1406 - 1986
```

Selected the same way the four preceding files were: the JK-prefixed curated OpenITI version, not a `Shamela*`/`ShamAY*`/`Shia*` scrape. Unlike Sunan Abi Dawud and Jami at-Tirmidhi, this file's `#META#` header has no gaps at all — `EdNUMBER`, `EdYEAR`, `EdPLACE`, and `EdPUBLISHER` are all filled — the most complete per-file metadata of the five hadith files this project has ingested. The file itself is `…JK000130-ara1.mARkdown`, the third and *richest* of the three OpenITI markup stages this project has now seen: bare `ara1` (Abu Dawud, the least annotated) precedes `.completed` (Tirmidhi, OpenITI's own markup pass finished), which in turn precedes `.mARkdown` (this file), a further, more detailed annotation pass on top of `.completed`. The stage affects only how much of OpenITI's own structural markup has been finished, not the licensing basis below.

### Why we may ship it — the legal basis

**Basis: the work's own public-domain status.** Ahmad ibn Shu'ayb Abu Abd al-Rahman al-Nasai died in 303 AH (915 CE). The matn and the isnad are public domain in every jurisdiction, without qualification — the identical basis the four collections above ship on, restated here rather than assumed, because a basis recorded once is not automatically a basis for a fifth work by a fifth author.

**Not an OpenITI licence grant, and the distinction is load-bearing here for exactly the reason it was for the first four collections.** OpenITI is the transcriber, not the rights holder of anything requiring a grant: what they contribute is transcription and structural markup, and a faithful mechanical transcription of a public-domain text attracts no new copyright. Their markup (mARkdown structural markers, page/volume anchors) is not carried into the corpus — the parser consumes it and discards it. Abu Ghudda's editorial apparatus — his introductions, footnotes, and the vowelling/typesetting choices of his edition — is likewise not carried into the corpus; what is ingested is matn and isnad. His **numbering** is a separate matter from his apparatus: a sequential count of units is a fact about how the edition is organized, not a copyrightable expression, and it is recorded as `numbering_scheme = "abughudda"` precisely so it is never confused with the other four editions' numbering or presented as if it were.

**Al-Nasai's own classical formulas are retained byte-exact as part of the canonical text, and are not exposed as a grading apparatus.** Modern authenticity gradings are copyrighted scholarly work outside this corpus's basis, exactly as for the rest of this corpus. Al-Nasai's own editorial remarks are a different thing: part of the primary source text itself, eleven centuries old, on the same public-domain basis as the matn and isnad around them. Across two fix rounds (R-A3-20, then Task 14's fix round 2 / R-A3-27) the formulas `_NASAI_FORMULA` moves into `addenda_ar` were widened to the full measured set: comparative-isnad critiques ("khalafahu"/"khalafahuma"/"khalafahum", "wafaqahu"/"wafaqahuma", "tabi'ahu", "khtalafa 'ala"/"'alayhi"/"'alayhima"), raising/lowering verdicts ("arsalahu", "rafa'ahu", "waqafahu", "awqafahu", "asnadahu", "mursal", "mawqufan", "lam yasma'(hu)", "lam yarfa'hu"), grading and wording tags ("hadha khata'", "hadha hadith ...", "hadha al-sawab", "wa al-sawab", "mukhtasar", "ghayr mahfuz", "al-lafz li-<narrator>"), and two comparative-citation forms ("lam yadhkur <narrator>", "rawahu"/"rawa <narrator>"). They are preserved, byte-exact, and still displayed as part of the record's full printed text; they are simply not scored as the matn, and Sanad never surfaces them as a grading verdict. Sanad confirms wording; it does not grade (R-A3-2).

**A raised-bar note specific to this collection:** al-Nasai's own kunya, "Abu Abd al-Rahman", is *also* the kunya of the Companion Abdullah ibn Umar, who narrates extensively throughout this collection. R-A3-20 required the compiler-commentary split to be measured against this namesake collision specifically — every candidate boundary was audited by hand so that a narrator being addressed by his own kunya inside a quoted matn (e.g. "ya Aba Abd al-Rahman ...") is never mistaken for the compiler's own voice and cut. This is a fact about the split's precision, not about the licensing basis, but it is recorded here because it is unique to this file among the five ingested so far.

**Attribution to OpenITI is given as credit, not as licence compliance**, on the same terms as the four entries above: recorded in `sources` with file, edition, commit and retrieval date, and shown in the provenance panel.

### The pinned commit and hash

```toml
[[source]]
id               = "openiti-nasai-jk000130"
kind             = "hadith-arabic"
collection       = "nasai"
numbering_scheme = "abughudda"
format           = "openiti-markdown"
title            = "المجتبى من السنن (Sunan an-Nasai)"
publisher        = "OpenITI (transcription); Maktab al-Matbuat al-Islamiyya, Aleppo (edition)"
edition          = "ed. Abd al-Fattah Abu Ghudda, 2nd ed., 1406/1986; OpenITI JK000130, ara1.mARkdown"
url              = "https://raw.githubusercontent.com/OpenITI/0325AH/089e665b4958e0f145a46941987fb81cf3dda1b8/data/0303Nasai/0303Nasai.SunanSughra/0303Nasai.SunanSughra.JK000130-ara1.mARkdown"
commit           = "089e665b4958e0f145a46941987fb81cf3dda1b8"
license_id       = "public-domain"
license_url      = "https://github.com/OpenITI/0325AH"
content_sha256   = "5afdd931303a85babd351afd72063cad455327b13263f16c5de2f6df5f30a4d1"
expected_records = 5769
modifications    = "mARkdown structural markers parsed and discarded; no text altered"
```

`commit` is pinned for the same reason as the four entries above: OpenITI is a live git repository whose files are re-OCRed in place. `content_sha256` covers the complete raw file, computed by the build itself (`sanad-ingest build`, measured-then-pinned per the project's build-measured-placeholder convention) and re-verified green on every subsequent build. `expected_records` (5,769) is the raw file's own count of numbered units. See `ingest/corpus.lock.toml` for the authoritative, machine-checked copy of this entry.

### The built corpus

The committed `data/sanad-quran.db` now holds 35,844 records: 6,236 ayat (Tanzil Uthmani, CC BY 3.0) + 7,129 Sahih al-Bukhari hadith + 7,460 Sahih Muslim hadith + 5,274 Sunan Abi Dawud hadith + 3,976 Jami at-Tirmidhi hadith + 5,769 Sunan an-Nasai hadith (public-domain bases above). Its whole-file SHA-256 is verified at build time and printed by `sanad-ingest build`; see `README.md` for the currently-committed value and the reproducibility check. Adding this fifth collection was proven not to perturb any of the first four: the Bukhari, Muslim, Abu Dawud, and Tirmidhi record sets are byte-identical, across every stored column, before and after Task 14 — built in an isolated `git worktree add --detach` at the pre-Task-14 commit, with the shared `.venv`'s editable-install package mapping overridden (not merely assumed inert) so the "before" build actually runs the old commit's code rather than silently re-running HEAD's.

## Source decisions

| Source | Decision | Reason |
|---|---|---|
| Tanzil Qur’an text | Approved candidate | Explicit license and text-specific requirements |
| Quranic Arabic Corpus | Review required | Useful annotations; review license and use conditions |
| Quran.com | Do not bundle | Service terms and third-party content |
| Sunnah.com | Reference only | Source/numbering information is useful, but no redistribution license is assumed |
| OpenITI (general) | Discovery only | Texts have mixed provenance and fidelity; review per text |
| OpenITI `0275AH`, JK000110 (Sahih al-Bukhari) | **Shipped** | Complete, internally-consistent per-file metadata; public-domain basis for the matn (see below), independent of OpenITI's own (absent) repository licence |
| OpenITI `0275AH`, JK000109 (Sahih Muslim) | **Shipped** | Same basis as Sahih al-Bukhari above: author's death (261 AH) is the public-domain basis, not any OpenITI grant; JK-prefixed curated version |
| OpenITI `0275AH`, JK000142 (Sunan Abi Dawud) | **Shipped** | Same basis as the two collections above: author's death (275 AH) is the public-domain basis, not any OpenITI grant; JK-prefixed curated version; per-file metadata incomplete (EdNUMBER/EdPLACE/EdYEAR unfilled) but shipped under the Stage A3 relaxed-bar ruling (R-A3-1) |
| OpenITI `0300AH`, JK000140 (Jami at-Tirmidhi) | **Shipped** | Same basis as the three collections above: author's death (279 AH) is the public-domain basis, not any OpenITI grant; JK-prefixed curated version, uniquely at the `.completed` processing stage; per-file metadata incomplete (EdNUMBER/EdYEAR unfilled, EdPLACE/EdPUBLISHER filled) but shipped under the Stage A3 relaxed-bar ruling (R-A3-1) |
| OpenITI `0325AH`, JK000130 (Sunan an-Nasai) | **Shipped** | Same basis as the four collections above: author's death (303 AH) is the public-domain basis, not any OpenITI grant; JK-prefixed curated version; per-file metadata fully complete (EdNUMBER/EdYEAR/EdPLACE/EdPUBLISHER all filled); file is at the `ara1.mARkdown` stage, the richest markup pass of the three this project has ingested |

## Review checklist

- [ ] Exact source URL recorded
- [ ] Edition/release recorded
- [ ] Rights holder or licensor recorded
- [ ] Redistribution permission confirmed
- [ ] Attribution text included
- [ ] Changes recorded
- [ ] Checksum generated
- [ ] Scholar/content reviewer assigned
- [ ] No personal or sensitive data included
