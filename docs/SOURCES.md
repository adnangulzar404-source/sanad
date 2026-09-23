# Source register

This document is a human-readable companion to `data/sources.json`. It is part of the submission evidence, not decoration.

## Safe initial corpus

### Qur’an

Use the Tanzil text as the leading candidate for the production Arabic Qur’an layer. Tanzil states that the text is under Creative Commons Attribution 3.0 and requires attribution, a link to Tanzil, preservation of its notice, and no change to verbatim copies. Store the canonical text unchanged; create a separate normalized field for matching.

### Hadith

Do not ship scraped Hadith from a public website merely because it is accessible. The production corpus needs written permission or a clearly applicable redistribution license for the exact text, translation, edition, and metadata. Each record should carry collection, book, number, edition, grading source, and provenance.

**Status: shipped.** Sahih al-Bukhari (7,129 records, matn + isnad, no gradings) was added to the corpus under the basis recorded in full below (see **Sahih al-Bukhari: the licensing basis**). See `docs/superpowers/specs/2026-09-22-hadith-corpus-design.md` §4 for the complete source and parsing rationale.

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

### The built corpus

The committed `data/sanad-quran.db` holds 13,365 records: 6,236 ayat (Tanzil Uthmani, CC BY 3.0) + 7,129 Sahih al-Bukhari hadith (public-domain basis above). Its whole-file SHA-256 is verified at build time and printed by `sanad-ingest build`; see `README.md` for the currently-committed value and the reproducibility check.

**Product constraint, stated here because it follows directly from the basis above.** Sanad ships no hadith gradings — modern authenticity gradings are copyrighted scholarly work, and authenticity is not Sanad's to assert. Sanad may say "this text is in Sahih al-Bukhari"; it must never say or imply "this hadith is sahih."

## Source decisions

| Source | Decision | Reason |
|---|---|---|
| Tanzil Qur’an text | Approved candidate | Explicit license and text-specific requirements |
| Quranic Arabic Corpus | Review required | Useful annotations; review license and use conditions |
| Quran.com | Do not bundle | Service terms and third-party content |
| Sunnah.com | Reference only | Source/numbering information is useful, but no redistribution license is assumed |
| OpenITI (general) | Discovery only | Texts have mixed provenance and fidelity; review per text |
| OpenITI `0275AH`, JK000110 (Sahih al-Bukhari) | **Shipped** | Complete, internally-consistent per-file metadata; public-domain basis for the matn (see below), independent of OpenITI's own (absent) repository licence |

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
