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

`sanad-ingest build` re-downloads the pinned source files (Tanzil's Qur'an exports and OpenITI's Sahih al-Bukhari) and refuses to write a database unless every source's content matches the SHA-256 pinned in `ingest/corpus.lock.toml` — a corpus that cannot be reproduced from the lockfile is not shipped. The database already committed at `data/sanad-quran.db` is the output of exactly this command; running it again is a reproducibility check, not a requirement to get started.

Or with Docker, which copies the already-built corpus into the image (no network access needed at build time or at run time):

```bash
docker build -t sanad . && docker run -p 8000:8000 sanad
```

## The live demo

The verification engine runs at the Vercel deployment; GitHub Pages serves the
Phase 0 prototype only, because Pages cannot run Python.

Run the full stack locally:

```bash
SANAD_AUDIT_DB=/tmp/sanad-audit.db \
  uvicorn sanad.api.app:create_app --factory --port 8000 &
cd web && npm install && npm run dev
```

The API's interactive documentation is at `http://localhost:8000/docs`.

## What is included

Stage A — the deterministic core:

- The full Tanzil Uthmani Qur'an — 6,236 verses — verified against a
  committed content hash at build time, plus the Pickthall English
  translation (see **Corpus and licensing** below)
- Sahih al-Bukhari — 7,129 hadith, matn and isnad both stored, matn-only
  matching, **no gradings shipped** (see **Corpus and licensing** below)
- Three-tier Arabic normalization, with the matching tier reported so an
  orthographic variant is never conflated with a textual one
- Verdicts: exact, exact-with-orthographic-variance, near match with a
  character diff, wrong reference, not found
- Claim detection and risk routing, with personal questions directed to a
  qualified person
- `POST /api/verify` — deterministic, no model, no API key
- `GET /api/corpus` — the provenance manifest: sources, licences, hashes
- An adversarial evaluation suite (54 cases) that fails CI if any misquote
  is reported as verified

Not yet included: the Ask pipeline (Stage B).

**Sanad does not grade hadith authenticity.** A `Sahih al-Bukhari <n>` result
means the quoted text is present in that collection, nothing more. Modern
authenticity gradings are copyrighted scholarly work and are not shipped;
Sanad may say "this text is in Sahih al-Bukhari" and must never say or imply
"this hadith is sahih."

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

**Hadith Arabic.** Sahih al-Bukhari, 7,129 records, from OpenITI's
transcription of the al-Bugha 3rd edition (Dar Ibn Kathir / al-Yamama,
Beirut, 1407/1987), file `JK000110`, pinned to OpenITI/0275AH commit
`47dfd28db9e158c7101c7df1162d4dc99bb70303`. The legal basis is **the matn's
own public-domain status** — al-Bukhari died in 870 CE — not a licence grant
from OpenITI: their `0275AH` data repository carries no `LICENSE` file, and
their organisation-wide MIT licence covers tooling, not corpus text
(verified 2026-09-22). OpenITI's structural markup is parsed and discarded
at ingest, so what is stored is the public-domain matn and isnad and nothing
else; attribution to OpenITI is given as credit, not as licence compliance.
Full reasoning, the pinned commit, and the content hash are in
`docs/SOURCES.md` and `ingest/corpus.lock.toml`.

Each hadith stores its matn (`text_ar`, scored) separately from its isnad
(`isnad_ar`, shown for context, never scored). The 1987 edition appends
secondary narrations after the primary matn; 392 records were cut at a
detected secondary-narration boundary, with the removed text preserved
verbatim in `addenda_ar`. 391 of those are indexed under *two* scored
representations — the primary matn and the full printed text — so that
either the intended quotation or the full printed hadith verifies, and
neither an over-cut nor an under-cut costs a verification. 17 records whose
matn is an editorial pointer (e.g. `بهذا`, `مثله`, `نحوه`) or a bare incipit
are excluded from scoring (`unscorable_reason` set) but remain reachable by
reference lookup. That exclusion is scoped to the *primary* matn, which is
the string the audit actually read: one of the 17 (hadith 237) also carries
an addendum, and its full printed text — the longest in this edition — is
indexed and scorable while its primary is not.

**Corpus totals.** 13,365 records: 6,236 ayat + 7,129 hadith. The committed
`data/sanad-quran.db` currently hashes to
`ab96d484370fe8a4555a691192886504b95ed07bc1fcf10fabbf0a34ca530083`
(whole-file SHA-256, printed by `sanad-ingest build` and re-checked by
rebuilding from the pinned, cached sources — see **Run locally** above).
This hash changes whenever the corpus is rebuilt with different inputs;
treat the value printed by your own build as authoritative, not this line.

## Known limitations

Sanad is a tool about honesty, so it should not overstate what it does:

- **Multi-āyah quotations are not matched.** The verifier compares a
  quoted span against single-record text only. Two consecutive genuine
  verses quoted together — e.g. Qur'an 112:1 immediately followed by
  112:2 — return `NOT_FOUND`, even though both verses are correct and
  correctly ordered. This is measured and pinned by an eval case on
  purpose, so that sliding-window multi-verse matching (planned for a
  later stage) fails loudly and gets built, instead of the gap silently
  persisting. A quotation that opens with a surah's Bismillah followed by
  a verse that is **not** that surah's own first āyah falls into the same
  gap. Most such pairings return `NOT_FOUND` — including 111 of At-Tawbah's
  129 verses, the one surah with no Bismillah of its own — but where the
  appended verse is long enough, the aggressive-tier fuzzy fallback can
  instead report `NEAR_MATCH` with a character diff: a Bismillah prepended
  to Ayat al-Kursi scores 0.91, and the remaining 18 (longer) verses of
  At-Tawbah cross the same 0.86 fuzzy threshold and get `NEAR_MATCH` too.
  Neither outcome is a verified verdict, so no misquote is ever certified
  — but the quotation itself is not recognised as the two verses it
  actually contains.
- **A mushaf-style paste with a trailing āyah-end marker and its
  Arabic-Indic verse number returns `NEAR_MATCH`, not `EXACT`.** The
  āyah-end mark (U+06DD) is stripped as Qur'anic annotation, but the
  Arabic-Indic digit that follows it is not, because it sits inside the
  same Unicode block as the letters themselves. The exact-match tiers miss
  and the engine falls back to fuzzy scoring (~0.93), which never falsely
  verifies but also never reports `EXACT` for this extremely common way of
  pasting a verse straight out of a printed mushaf.
- **A wrong-direction hamza on an alef reports as orthographic variance,
  not as a wrong word.** The `standard` tier folds `آ أ إ ٱ` to plain `ا`
  so that omitting a hamza seat entirely — a very common, legitimate way
  to type Arabic — still verifies as `EXACT_ORTHOGRAPHY` rather than
  falling all the way to `NEAR_MATCH`. The same fold cannot tell that
  omission apart from a hamza pointed the *wrong way*: Qur'an 18:71's
  `إِمْرًا` ("a grievous thing") and `أَمْرًا` ("a matter") fold to the
  same normalized form, so quoting one in place of the other reports as
  orthographic variance even though the word itself changed. See
  `docs/superpowers/specs/2026-09-19-sanad-design.md` §6 for the full
  trade-off analysis.
- **`NOT_FOUND` never means "fabricated."** It means "not present in this
  corpus." A quotation can be a genuine hadith from a different collection,
  or genuine but paraphrased, and still return `NOT_FOUND`.
- **No hadith gradings are shipped, by design.** A match only says the text
  is present in Sahih al-Bukhari — never that the hadith is authentic
  (sahih). Modern gradings are copyrighted scholarly work and are not
  Sanad's to assert.
- **42 records (0.6% of 7,129) still hold a narration verb followed by
  chain material inside the scored matn.** The secondary-narration cut
  could not separate these cleanly; they still verify correctly against
  their own printed text, but a quotation of *only* the true matn, stopping
  exactly before the trailing narration verb, may not match.
- **About 98 primaries carry chain residue at the end of the matn,
  display-only.** This does not affect verification outcomes; the residue
  is part of what a user pasting from this edition would actually see.
- **Hadith 342 and 3164 (the Isra'/Mi'raj narration) are split
  mid-narration**, not at a narration boundary. Both the primary matn and
  the full printed text are indexed and verify correctly, so this costs no
  verification, but the split itself is wrong and known to be wrong.
- **The `MarkedText` accessibility fix is unverified against a real screen
  reader.** Verdict-diff spans carry an `aria-label` (not just a `title`
  attribute) so the verdict is announced rather than silently omitted. This
  is an improvement, confirmed only by unit tests asserting the attribute is
  present — it has not been checked against actual assistive technology.
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

Sahih al-Bukhari text transcribed by [OpenITI](https://openiti.org) from the
al-Bugha 3rd edition (Dar Ibn Kathir / al-Yamama, Beirut, 1407/1987), file
JK000110 in `github.com/OpenITI/0275AH`, used on the basis of the matn's own
public-domain status (see **Corpus and licensing** above). Attribution to
OpenITI is given as credit, not as licence compliance — see `docs/SOURCES.md`.

## Repository map

```text
index.html                 Static Phase 0 prototype and GitHub Pages entry point
api/sanad/                 FastAPI service: corpus, Arabic normalization, verification engine
ingest/sanad_ingest/       Corpus builder: fetch, verify, and load from ingest/corpus.lock.toml
ingest/corpus.lock.toml    Pinned sources and content hashes -- the reproducibility contract
eval/                      Adversarial evaluation harness and cases (CI gate)
data/sanad-quran.db        The committed, hash-verified corpus (Qur'an + Pickthall translation + Bukhari)
docs/hadith-noise-report.md  OCR damage found in the Bukhari source -- review artifact, never a filter
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
