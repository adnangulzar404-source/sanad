# Source register

This document is a human-readable companion to `data/sources.json`. It is part of the submission evidence, not decoration.

## Safe initial corpus

### Qur’an

Use the Tanzil text as the leading candidate for the production Arabic Qur’an layer. Tanzil states that the text is under Creative Commons Attribution 3.0 and requires attribution, a link to Tanzil, preservation of its notice, and no change to verbatim copies. Store the canonical text unchanged; create a separate normalized field for matching.

### Hadith

Do not ship scraped Hadith from a public website merely because it is accessible. The production corpus needs written permission or a clearly applicable redistribution license for the exact text, translation, edition, and metadata. Each record should carry collection, book, number, edition, grading source, and provenance.

### Translations and tafsir

Translations, tafsir, explanations, and fiqh books should be treated as separate copyrighted assets. Add them only after confirming the exact license and whether public display, indexing, modification, and redistribution are allowed.

## Source decisions

| Source | Decision | Reason |
|---|---|---|
| Tanzil Qur’an text | Approved candidate | Explicit license and text-specific requirements |
| Quranic Arabic Corpus | Review required | Useful annotations; review license and use conditions |
| Quran.com | Do not bundle | Service terms and third-party content |
| Sunnah.com | Reference only | Source/numbering information is useful, but no redistribution license is assumed |
| OpenITI | Discovery only | Texts have mixed provenance and fidelity; review per text |

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
