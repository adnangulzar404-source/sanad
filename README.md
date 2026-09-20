# Sanad — Evidence-first Islamic content verification

Sanad is a verification-first prototype for Islamic AI content. It checks quotations against a closed corpus, separates source text from explanation, displays provenance, and hands personal rulings to qualified specialists.

**Competition positioning:** Track 4 — knowledge and verification tools, with Track 1 — reliable dialogue as a secondary track.

## Live demo

`https://adnangulzar404-source.github.io/sanad/`

The Pages site is still the Phase 0 static demo — it does not call the API below and contains only a deliberately tiny demo corpus. `POST /api/verify` and the rest of the endpoints described here are the actual Stage A deliverable and are reached by running the service (locally or via Docker), not by visiting the Pages URL.

## Run locally

```bash
pip install -e ".[dev]"
sanad-ingest build --out data/sanad-quran.db     # verifies against the lockfile
uvicorn sanad.api.app:create_app --factory --port 8000
```

`sanad-ingest build` re-downloads Tanzil's source files and refuses to write a database unless every source's content matches the SHA-256 pinned in `ingest/corpus.lock.toml` — a corpus that cannot be reproduced from the lockfile is not shipped. The database already committed at `data/sanad-quran.db` is the output of exactly this command; running it again is a reproducibility check, not a requirement to get started.

Or with Docker, which copies the already-built corpus into the image (no network access needed at build time or at run time):

```bash
docker build -t sanad . && docker run -p 8000:8000 sanad
```

## What is included

Stage A — the deterministic core:

- The full Tanzil Uthmani Qur'an — 6,236 verses — verified against a
  committed content hash at build time, plus the Pickthall English
  translation (see **Corpus and licensing** below)
- Three-tier Arabic normalization, with the matching tier reported so an
  orthographic variant is never conflated with a textual one
- Verdicts: exact, exact-with-orthographic-variance, near match with a
  character diff, wrong reference, not found
- Claim detection and risk routing, with personal questions directed to a
  qualified person
- `POST /api/verify` — deterministic, no model, no API key
- `GET /api/corpus` — the provenance manifest: sources, licences, hashes
- An adversarial evaluation suite (33 cases) that fails CI if any misquote
  is reported as verified

Not yet included: Hadith (no licence-cleared source yet — see
`docs/superpowers/specs/2026-09-19-sanad-design.md` §14.1) and the Ask
pipeline (Stage B).

## Corpus and licensing

**Qur'an Arabic.** The full Tanzil Uthmani text (1.1), 6,236 verses, used
verbatim under Creative Commons Attribution 3.0. Tanzil's copyright notice
is stored in the corpus database exactly as issued and served at
`GET /api/corpus` — it is never summarized, edited, or removed.

**Qur'an translation.** The Pickthall English translation, distributed by
Tanzil (https://tanzil.net/trans/). The legal basis for bundling it is the
**work's own public-domain status**, not a licence grant from Tanzil:
Marmaduke Pickthall died in 1936, so the translation is in the public domain
worldwide under life+70 rules, and in the US since 1 January 2026 (published
1930, 95 years from publication). This distinction matters because Sanad's
code is MIT — if the translation's inclusion instead rested on a grant from
Tanzil, a downstream commercial user would cross Tanzil's non-commercial
term on translations the moment they relied on Sanad's licence. Relying on
the work's own status instead of Tanzil's grant avoids that. See
`ingest/corpus.lock.toml` for the full reasoning and `docs/superpowers/specs/2026-09-19-sanad-design.md`
§5.2 for the complete legal analysis.

Tanzil's own accuracy disclaimer is carried alongside every rendered
translation, not just in this file:

> No translation of Quran can be a hundred percent accurate, nor it can be
> used as a replacement of the Quran text.

## Known limitations

Sanad is a tool about honesty, so it should not overstate what it does:

- **Multi-āyah quotations are not matched.** The verifier compares a
  quoted span against single-record text only. Two consecutive genuine
  verses quoted together — e.g. Qur'an 112:1 immediately followed by
  112:2 — return `NOT_FOUND`, even though both verses are correct and
  correctly ordered. This is measured and pinned by an eval case on
  purpose, so that sliding-window multi-verse matching (planned for a
  later stage) fails loudly and gets built, instead of the gap silently
  persisting.
- **A mushaf-style paste with a trailing āyah-end marker and its
  Arabic-Indic verse number returns `NEAR_MATCH`, not `EXACT`.** The
  āyah-end mark (U+06DD) is stripped as Qur'anic annotation, but the
  Arabic-Indic digit that follows it is not, because it sits inside the
  same Unicode block as the letters themselves. The exact-match tiers miss
  and the engine falls back to fuzzy scoring (~0.93), which never falsely
  verifies but also never reports `EXACT` for this extremely common way of
  pasting a verse straight out of a printed mushaf.
- **No Hadith corpus is bundled.** `NOT_FOUND` means "not present in this
  corpus" — it never means "fabricated," and it is not a judgment on
  whether a quotation is a genuine, licensed Hadith. See
  `docs/superpowers/specs/2026-09-19-sanad-design.md` §14.1 for why Hadith
  is not yet included.
- **The risk router deliberately over-diverts.** Roughly 15–20% of
  ordinary, non-personal general questions are routed to a human as a
  false positive. That is the chosen direction of error for a system whose
  worst failure mode is a machine answering a personal religious ruling —
  it is not a defect to be tuned away without first re-examining whether
  the trade should shift at all.

## Attribution

Qur'an text from the [Tanzil Project](https://tanzil.net), used verbatim
under Creative Commons Attribution 3.0. The full copyright notice is stored
in the corpus database and served at `GET /api/corpus`. The Pickthall
translation is distributed by Tanzil at https://tanzil.net/trans/ on the
basis of its own public-domain status (see **Corpus and licensing** above).

## Repository map

```text
index.html                 Static Phase 0 prototype and GitHub Pages entry point
api/sanad/                 FastAPI service: corpus, Arabic normalization, verification engine
ingest/sanad_ingest/       Corpus builder: fetch, verify, and load from ingest/corpus.lock.toml
ingest/corpus.lock.toml    Pinned sources and content hashes -- the reproducibility contract
eval/                      Adversarial evaluation harness and cases (CI gate)
data/sanad-quran.db        The committed, hash-verified corpus (Qur'an + Pickthall translation)
tests/                     Unit tests for every module above
docs/superpowers/specs/    Design spec, including the open items in §14
.github/workflows/         CI and GitHub Pages deployment
Dockerfile                 Container image; copies the committed corpus in, builds no network calls
```

## Source policy

The source register is intentionally conservative. A source being publicly
viewable does not automatically mean that its data may be scraped, copied,
bundled, or redistributed. See `docs/superpowers/specs/2026-09-19-sanad-design.md`
§5 and `ingest/corpus.lock.toml` before adding content.

## License

The application code and original documentation in this repository are
released under the MIT License. Third-party source text, translations, and
other assets remain subject to their own licenses (see **Corpus and
licensing** above) and are not relicensed by this repository.
