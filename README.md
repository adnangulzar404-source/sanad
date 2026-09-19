# Sanad — Evidence-first Islamic content verification

Sanad is a verification-first prototype for Islamic AI content. It checks quotations against a closed corpus, separates source text from explanation, displays provenance, and hands personal rulings to qualified specialists.

**Competition positioning:** Track 4 — knowledge and verification tools, with Track 1 — reliable dialogue as a secondary track.

## Live demo

After enabling GitHub Pages, the site is available at:

`https://YOUR-USERNAME.github.io/sanad/`

The current prototype is a self-contained static site. It does not call an external API and contains only a deliberately tiny demo corpus.

## Run locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

No build step is required.

## What is included

- Quotation matching and verification
- Exact, near-match, wrong-reference, and not-found states
- Arabic search normalization while preserving canonical display text
- Evidence cards with references, checksums, and provenance notes
- Retrieval-first Q&A demo
- Specialist handoff for personal rulings
- Twenty adversarial test cases
- Corpus and licensing documentation
- GitHub Pages deployment workflow

## Important production limitations

This repository is not yet a production religious knowledge system. Before publishing externally:

1. Import the production Qur’an text from Tanzil verbatim and preserve its license notice.
2. Obtain written permission or a clearly redistributable license for every Hadith edition.
3. Replace demo glosses with a licensed translation or clearly label external links.
4. Add a backend retrieval service, audit logs, human review, and a scholarly advisory process.
5. Do not use real user conversations or personal/sensitive data in development or evaluation.
6. Do not present the system as a mufti or as an authority issuing personal fatwas.

## Repository map

```text
index.html                 Static prototype and GitHub Pages entry point
data/sources.json          Source register and licensing decisions
data/README.md             Data intake policy
docs/SOURCES.md            Human-readable source and license notes
docs/ROADMAP.md            Build plan toward a production MVP
docs/GAPS.md               Gap list: what Sanad still needs
.github/workflows/pages.yml GitHub Pages deployment
```

## Source policy

The source register is intentionally conservative. A source being publicly viewable does not automatically mean that its data may be scraped, copied, bundled, or redistributed. See `docs/SOURCES.md` and `data/sources.json` before adding content.

## License

The application code and original documentation in this repository are released under the MIT License. Third-party source text, annotations, translations, and other assets remain subject to their own licenses and are not relicensed by this repository.
