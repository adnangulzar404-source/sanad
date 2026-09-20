# Hadith Source Assessment for Sanad

Scope note: this document assesses candidate sources as *data sources* — their
Arabic text, licensing/provenance documentation, editions, numbering, and
machine-readability. It makes no claim about the authenticity (sahih/da'if)
of any hadith. Where a source states a grading and who assigned it, that is
reported as a fact about the source's metadata, not endorsed as correct.

Research date: 2026-09-19 / 2026-09-20. All sources were fetched live
(via `curl` and `WebFetch`) during this session; verbatim quotes below are
copied from the actual responses, not paraphrased or recalled from training
data.

## 1. Summary

A usable source exists, but it is narrower than "a hadith corpus": it is a
specific subset of files inside the **OpenITI / KITAB corpus**
(`github.com/OpenITI`), where individual version-files of Sahih al-Bukhari
and Sunan Abi Dawud carry inline metadata naming the exact printed edition
(editor, publisher, place, year), the digitizer's initials and date, an
explicit description of what editorial material was stripped, and a link to
a scanned copy of the source printing — which is exactly the class of
provenance a checksummed corpus needs. No other candidate we could reach
comes close on documentation; sunnah.com and dorar.net, the two most-cited
"gold standard" hadith sites, blocked every fetch attempt (HTTP 403) and so
could not be evaluated at all. Most GitHub/Hugging Face repos that claim
permissive or public-domain licenses (Unlicense, CC0) are relicensing text
they scraped from other sites and do not document where that text
ultimately came from — the caution in the task brief about repos relicensing
text they didn't create turned out to be well founded in practice.

## 2. Comparison table

Legend: ✅ documented and quoted below · ⚠️ partially/ambiguously documented ·
❌ not stated · 🚫 could not verify (source blocked/unreachable)

| Candidate | 1. Arabic matn | 2. Licence/terms stated | 3. Edition documented | 4. Numbering scheme | 5. Grader named (per-hadith) | 6. Machine-readable | 7. Digitization provenance |
|---|---|---|---|---|---|---|---|
| **sunnah.com** (site + API) | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **fawazahmed0/hadith-api** (GitHub) | ✅ (18 Arabic editions) | ⚠️ Unlicense on the *code*; underlying text provenance unlicensed/unclear | ⚠️ named per grading-edition (e.g. "abu dawed, albani") but only as a bare link, no publisher/year | ❌ not documented beyond hadith numbers themselves | ✅ named (Albani, Arnaut, Abu Ghuddah, Ahmad Shakir, Bashar Awad Maarouf) but sourced via unverified third-party mirror | ✅ JSON | ⚠️ "References" file lists source URLs, not a digitization method |
| **fawazahmed0/hadith-data** (Hugging Face mirror) | ✅ | ⚠️ declares **CC0 1.0**, but this is a downstream relicense of the above, which itself doesn't own the text | same as above | ❌ | ✅ (same names as above) | ✅ Parquet | ❌ |
| **OpenITI / KITAB corpus** (GitHub org + kitab-project.org) | ✅ full Sahih Bukhari, Sahih Muslim, Sunan Abi Dawud, Sunan Ibn Majah text | ⚠️ org-level Terms of Use states CC BY-SA/AGPL for "the Platform"; unclear if it covers the separately-hosted, unmarked GitHub data repos | ✅ for select versions (e.g. Bukhari: Dar Ibn Kathir/al-Yamama, ed. Mustafa Dib al-Bugha, 3rd ed., 1987); ❌ for other versions of the *same* text (unfilled template) | ✅ inline hadith numbers + chapter (bab) numbers + page markers tied to the print edition's pagination | ❌ not present in the versions inspected (by design — see notes) | ⚠️ plain text w/ OpenITI mARkdown tagging, not JSON/XML natively but documented and scriptable | ✅ for select versions: annotator initials, date, explicit list of what was removed, link to pre-clean version, link to a scanned PDF of the cited print edition |
| **Maktaba Shamela / al-maktaba.org (shamela.ws)** | ✅ (large hadith category, ~1,245 works) | ⚠️/❌ own terms state rights remain with book/edition owners; explicitly forbids "reconstructing the full index"; no redistribution grant | ❌ not found on pages we could reach (couldn't locate a working book page during this session) | 🚫 could not verify at book level (pages 404'd) | ✅ per the fawazahmed0 References list (Albani, Arnaut, etc. attached to specific `al-maktaba.org/book/NNNN` links), but attribution is second-hand | ❌ HTML pages only | ❌ no stated typist/OCR method found |
| **LK Hadith Corpus** (ShathaTm/LK-Hadith-Corpus, Leeds+King Saud Univ.) | ✅ dedicated `Arabic_Matn` column | ❌ no license file (GitHub reports `license: None`) | ❌ not stated which printed edition per book | ✅ Chapter/Section/Hadith number columns | ✅ has `English_Grade`/`Arabic_Grade` columns (source/grader of the *grading itself* not separately named) | ✅ structured (CSV/TSV-style, machine-readable) | ⚠️ documents its own *segmentation* method (Bukhari "manually checked, gold standard"; others auto-segmented, "92% accuracy") but not the underlying text's original source/typist |
| **AhmedBaset/hadith-json** (GitHub) | ✅ `arabic` field alongside English | ❌ no license file found | ❌ not stated | ⚠️ id/chapter/book fields only, no cross-reference to print pagination | ❌ none | ✅ JSON | ⚠️ states "scraped from Sunnah.com," no further detail |
| **dorar.net** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **Hugging Face datasets (general search)** | ⚠️ some yes (e.g. `Dr-AliGomaa/ar-quran-hadith14books-MSA`) | ❌ mostly unstated in search results; individual cards not all checked | ❌ | ❌ | ⚠️ varies | ✅ Parquet/JSON typical | ❌ mostly repackagings of the same fawazahmed0/sunnah.com-derived data |
| **Zenodo** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **King Fahd Complex (qurancomplex.gov.sa)** | 🚫 (site unreachable) | 🚫 | n/a | n/a | n/a | n/a | n/a — this is a Qur'an-printing institution, not a hadith source |
| **OpenITI raw Shamela scrape** (`raw_SHAM19Y` repo, and unfilled-metadata versions inside `0275AH`) | ✅ | ❌ no license, inherits Shamela's own reservation of rights | ❌ template placeholders, unfilled | ⚠️ inherited from source text, unverified | ❌ | ⚠️ raw mARkdown, unannotated | ⚠️ states "scraped... October 2019," no further detail |

## 3. Per-source notes, with verbatim quotes

### sunnah.com (site + `api.sunnah.com`)

Blocked on every attempt from this environment, confirmed independently by
both `WebFetch` and a bare `curl -A "Mozilla/5.0"`:

```
sunnah.com main: 403
api.sunnah.com docs: 403
api.sunnah.com actual: 403
```

I could not read its about/credits page, its API terms, or any statement of
which printed editions or translations it digitizes. This is stated
plainly rather than guessed, per the task's instruction. It should be
retried from a network/IP that isn't blocklisted, or via a maintainer
contact, before being ruled in or out.

### fawazahmed0/hadith-api (GitHub) and its Hugging Face mirror

The repo's `LICENSE` file, fetched verbatim, is the Unlicense:

> "This is free and unencumbered software released into the public domain."

This is a **software** license on the API code. `editions.json` confirms 18
Arabic editions exist (`ara-bukhari`, `ara-muslim`, `ara-abudawud`,
`ara-tirmidhi`, `ara-nasai`, `ara-ibnmajah`, `ara-malik`, plus
diacritics-stripped and two non-canonical variants), each marked `rtl` —
so criterion 1 (Arabic matn) is genuinely satisfied here, unlike most
English-only hadith APIs.

But `References.md`, fetched verbatim, shows the text itself is aggregated
from third-party sites with no license chain established:

```
### References:
Here is a list of websites that helped me either directly or indirectly
in making this possible:
https://al-maktaba.org
https://www.iium.edu.my/deed/hadith/
https://github.com/alQuranBD/Bangla-Hadith-api
https://www.hadithbd.com
https://sunnah.com/
https://www.urdupoint.com
...
https://al-maktaba.org/book/1755  abu dawed, albani
https://fawazahmed0.github.io/maktaba-grades-backup/1755 abu dawed, albani (backup link)
https://al-maktaba.org/book/32832 abu dawed, arnaut
...
https://archive.org/details/noor-book.com-3_20211020 Malik, Salim Al Hilali
```

This confirms named modern graders (al-Albani, Arnaut, Abu Ghuddah, Ahmad
Shakir, Bashar Awad Maarouf) are attached to specific editions — but the
"documentation" is a bare hyperlink to an al-maktaba.org/Shamela book ID,
not a stated edition/publisher/year, and the author maintains a personal
mirror (`fawazahmed0.github.io/maktaba-grades-backup`) of Shamela's content,
which is itself evidence the underlying source's own availability/rights
status is precarious enough to need backing up. The README's own
Contribution section — "Please help by adding new translations to this
repo" — makes clear this is a crowd-aggregated project, not a documented
digital edition.

The downstream Hugging Face dataset `fawazahmed0/hadith-data` declares
**CC0 1.0** (public-domain dedication) over this same data, including the
Albani/Arnaut gradings. This is precisely the pattern the task brief warned
about: a repository cannot relicense text (or 20th-century scholarly
gradings) it did not create, and CC0 is a stronger — and therefore more
questionable — claim than even the Unlicense on the original repo.

### OpenITI / KITAB project — the strongest candidate

OpenITI's GitHub org (`github.com/OpenITI`) buckets texts by century of the
author's death. Al-Bukhari (d. 256 AH) and Abu Dawud (d. 275 AH) are both
findable in the `0275AH` repo:

```
0256Bukhari, 0261Muslim, 0273IbnMaja, 0275AbuDawudSijistani  (folder names, confirmed via GitHub API)
```

Inside `0256Bukhari/0256Bukhari.Sahih/`, there are multiple **version
files** of the same book from different digitization efforts, each with its
own `.yml` sidecar and inline `#META#` header. Quality varies sharply
between versions of the *same text*:

**Version `JK000110-ara1`** (well documented) — the file's own header,
fetched verbatim:

```
#META# 020.BookTITLE	:: الجامع الصحيح المختصر
#META# 040.EdEDITOR	:: د. مصطفى ديب البغا
#META# 041.EdNUMBER	:: الثالثة
#META# 043.EdPUBLISHER	:: دار ابن كثير , اليمامة
#META# 044.EdPLACE	:: بيروت
#META# 045.EdYEAR	:: 1407 - 1987
```

i.e. edited by Dr. Mustafa Dib al-Bugha, published by Dar Ibn Kathir /
al-Yamama, Beirut, 3rd edition, 1987 — a specific, identifiable printed
edition. The `.yml` sidecar adds:

> "80#VERS#BASED####: http://www.worldcat.org/oclc/54146380"
> "80#VERS#COLLATED#: http://www.worldcat.org/oclc/54146380 (2002 reprint)"
> "80#VERS#LINKS####: https://ia800200.us.archive.org/6/items/waq79565/79565.pdf"
> "90#VERS#ANNOTATOR: HRH"
> "90#VERS#DATE#####: 2020-05-15"
> "90#VERS#COMMENT##: ... All paratextual elements (introductions,
> footnotes, indices, ...) removed by HRH and MGR (OpenITI Clean operation,
> 2023). Link to the text file as it was before it was cleaned: ..."

This is a named annotator, a date, a WorldCat catalog record for the exact
print run, a link to a scanned PDF of that printing on archive.org, and an
explicit description of what editorial matter was stripped — with the
pre-clean version left available so the stripping can be audited. The body
text carries inline hadith numbers ("`# 1 حدثنا الحميدي ...`", "`# 2 ...`")
and page markers tied to the print edition ("`PageV01P001`"), so numbering
cross-references the cited printing directly.

**Version `Shamela0001681-ara1`** of the *same book* (poorly documented) —
its `.yml` sidecar, fetched verbatim, is the unfilled template:

```
90#VERS#ANNOTATOR: the name of the annotator (latin characters; please
    use consistently)
90#VERS#COMMENT##: a free running comment here; you can add as many
    lines as you see fit...
90#VERS#DATE#####: YYYY-MM-DD
```

i.e. nobody filled this in. The same pattern held for Sunan Abi Dawud
(`JK000142-ara1`, editor Muhammad Muhyi al-Din Abd al-Hamid, publisher Dar
al-Fikr, year unstated, vs. several `Shamela...`-suffixed sibling versions).
**Consequence: OpenITI cannot be treated as one uniformly-documented
corpus — Sanad would have to hand-pick specific version files (the "JK"
ones, in the cases checked) and reject the rest.**

Licensing: OpenITI's own Terms of Use (`openiti.org/docs/Terms of Use.html`,
dated August 9, 2026), fetched verbatim:

> "most Material available for free via open source (GNU AGPL 3.0) and open
> access (Creative Commons Attribution-Non-Commercial (CC BY-SA) 4.0
> International License) licenses."

(Note: this sentence itself mixes two different CC variants —
"Attribution-Non-Commercial" is CC BY-NC, not CC BY-SA — an inconsistency
in OpenITI's own wording, quoted as written.) The Terms of Use also state,
directly on point for this project's PD-matn-vs-copyrighted-apparatus
distinction:

> "You will excise all material that is covered by copyright from User
> Contributions (for example, the editor's introduction and footnotes)."

This is OpenITI's contributor policy explicitly separating the public-
domain matn from the copyrighted editorial apparatus — the same
distinction this task's brief is built on. However: this Terms of Use
governs "the OpenITI website and portal (the 'Platform')" (§2.1); none of
the corpus GitHub repos we checked (`0275AH`, `RELEASE`, `Annotation`) carry
a repo-level `LICENSE` file (GitHub API reports `license: None` for all of
them). Whether the website's CC BY-SA/AGPL statement legally extends to the
separately-hosted, unmarked GitHub data is not stated anywhere we found —
this is the single largest open question (see Recommendation).

No per-hadith modern grading layer was found in any OpenITI hadith version
inspected — consistent with the project's policy of stripping copyrighted
editorial/critical-apparatus material, which is exactly where such
gradings usually live.

### Maktaba Shamela (shamela.ws) / al-maktaba.org

`al-maktaba.org` 302-redirects to `shamela.ws` — confirmed they are now the
same platform. The homepage confirms a large hadith category ("كتب السنة" —
1,245 works) and states its own non-commercial purpose:

> "يهدف المشروع لجمع ما يحتاجه طالب العلم من كتب وبحوث...وهو مشروع مجاني لا
> يهدف للربح" — "The project aims to gather the books and research a
> student of knowledge needs... it is a free, non-profit project."

That is a mission statement, not a license. The only terms-of-use text we
could reach (`shamela.ws/page/terms`) turned out to describe a **new
"Shamela MCP" service** — a read-only Model Context Protocol research/
citation-checking tool — with a "last updated" date of September 19, 2026.
Its intellectual-property clause, fetched verbatim (Arabic, with the page's
own English translation):

> "٥. الملكية الفكرية: تبقى الحقوق في الكتب والطبعات والمواد لأصحابها حسب ما
> ينطبق. لا تمنحك هذه الشروط حقًا في إعادة استخدام المحتوى خارج ما يسمح به
> النظام أو إذن صاحب الحق."
> "5. Content rights: Rights in books, editions, and other materials remain
> with their respective holders as applicable. These terms do not grant you
> a right to reuse content beyond what the system permits or the rights
> holder's permission."

And on bulk use specifically:

> "محاولة إعادة بناء الفهرس كاملًا بطريقة تتجاوز القيود المعلنة أو تضر
> بتوفر الخدمة" — listed under prohibited uses: "attempting to reconstruct
> the full index in a way that evades published limits or harms service
> availability."

This is decisive: Shamela's own terms state the opposite of a licence
grant — rights remain with book/edition owners, no reuse right is conveyed,
and bulk reconstruction of the index is explicitly forbidden. Even though
the underlying classical Bukhari/etc. matn is independently public domain,
Shamela wraps it in specific printed editions (pagination, editor's
apparatus) that it does not own and explicitly disclaims granting rights
over. Shamela is therefore not, by itself, a source Sanad can point to for
a redistribution right — it can at most be a *pointer* to which printed
edition a given digitization claims to follow (as OpenITI's version
metadata does), not a corpus to ingest wholesale.

I could not locate a working individual book page during this session
(`shamela.ws/book/1755`, the ID cited in fawazahmed0's References.md,
404'd; the site's search endpoint returned only the empty search-UI shell,
not results) — so I could not independently verify edition/typist metadata
on a live Shamela book page. This is noted as unverified, not assumed.

### LK Hadith Corpus (`ShathaTm/LK-Hadith-Corpus`)

A Leeds University / King Saud University academic dataset,
"39,038 annotated Hadiths... more than 10 million tokens," with a dedicated
`Arabic_Matn` column plus `English_Grade`/`Arabic_Grade` columns. Its
documented strength is methodological, not legal: "[Sahih Bukhari] was
manually checked and is considered the gold standard," while the other five
books "were annotated automatically using a Hadith segmentation tool that
segments the Isnad from the Matn with 92% accuracy." GitHub reports
`license: None` for the repo, and we found no statement of which printed
edition of each of the six books was used as the segmentation input.
Useful as a secondary cross-check on isnad/matn boundaries, not as a
primary source of record.

### AhmedBaset/hadith-json

50,884 hadiths across 17 books, dual Arabic/English fields, states it was
"scraped from Sunnah.com." GitHub reports `license: None`. No edition,
numbering-scheme, or grading documentation beyond bare id/chapter/book
fields. Weaker than every criterion OpenITI satisfies.

### dorar.net (al-Durar al-Saniyyah)

Blocked on every attempt (`403`, both via `WebFetch` and `curl`). Could not
verify anything about its licensing, editions, or per-hadith grading
attribution, despite it being commonly cited as a major named-grading
hadith database. Flagged as unverified, not assumed.

### Hugging Face / Zenodo (general search)

Hugging Face dataset search surfaced several hadith datasets
(`arbml/Hadith`, `Dr-AliGomaa/ar-quran-hadith14books-MSA`,
`Ahmed-ibn-Harun/hadiths`, `fawazahmed0/hadith-data`), almost all of which
are repackagings of the same fawazahmed0/sunnah.com-derived data chain
already assessed above, with license tags either absent or (in the CC0
case) an apparent overclaim. Zenodo's search API returned `429 Too Many
Requests` and then `403 Forbidden` ("unusual traffic from your network")
during this session — could not be searched at all; worth retrying from a
different network.

### King Fahd Complex / qurancomplex.gov.sa

The domain timed out (`curl: (28) Connection timed out`) during this
session. Separately, this institution's mandate is the printing/
digitization of the Qur'an (the Uthmani mushaf), not hadith — it is
unlikely to be a hadith source regardless of reachability, and is included
here only because it was on the candidate list.

## 4. Recommendation

**Pursue OpenITI/KITAB**, specifically the fully-annotated ("JK"-prefixed,
in the instances checked) version files of Sahih al-Bukhari, Sahih Muslim,
Sunan Abi Dawud, and Sunan Ibn Majah inside the century-bucketed repos
(e.g. `github.com/OpenITI/0275AH`). It is the only candidate reached during
this research that documents a specific printed edition, a named
digitizer/annotator with a date, an explicit account of what was edited
out, a link to a scanned copy of the cited printing for independent
verification, and a numbering scheme cross-referenced to that printing's
own pagination — while also containing genuine Arabic matn in a scriptable
structured-text format.

Before ingesting anything, three things need confirming, in priority order:

1. **Licence scope.** OpenITI's Terms of Use state CC BY-SA/AGPL for "the
   Platform," but the actual corpus files live in GitHub repos with no
   repo-level `LICENSE` file. This is the single biggest unresolved
   question in this whole assessment (see below) and should be resolved by
   direct correspondence before any ingestion, rather than assumed.
2. **Per-version vetting.** Documentation quality is not uniform across the
   corpus — the raw Shamela-scraped sibling versions of the very same
   Bukhari and Abu Dawud texts have unfilled placeholder metadata. Each
   candidate version file needs to be checked individually against the
   seven criteria before use; "OpenITI" is not a single yes/no answer.
3. **Edition fit.** The specific printings OpenITI documents (e.g. the
   1987 Dar Ibn Kathir/al-Yamama edition of Bukhari edited by Mustafa Dib
   al-Bugha) may use different pagination/numbering than the editions most
   commonly cited elsewhere (e.g. whatever sunnah.com uses, which could not
   be checked here). If Sanad needs to cross-reference against numbering a
   user is likely to type from memory or from another site, this gap needs
   to be measured, not assumed away.

**If corresponding with OpenITI**, the questions worth asking directly are:

- Does the CC BY-SA(-NC)/AGPL statement in the Terms of Use apply to the
  raw text files distributed through the `github.com/OpenITI` organization,
  or only to content served directly through openiti.org?
- For texts whose GitHub repos carry no `LICENSE` file, can they confirm
  that the specific fully-annotated version files (the "JK..." style ones)
  are intended for downstream redistribution, including inside a tool that
  would redistribute checksummed excerpts of the matn?
- Can they confirm that the archive.org PDF linked from a given version's
  metadata (e.g. `ia800200.us.archive.org/6/items/waq79565/79565.pdf` for
  the Bukhari `JK000110` version) is in fact a scan of the specific edition
  named in that same metadata record, so the transcription can be
  independently spot-checked against page images?

**Do not** treat fawazahmed0/hadith-api, its Hugging Face CC0 mirror, or
Maktaba Shamela's own site as sources of a redistribution licence for
hadith text: the first two relicense text neither party created, and
Shamela's own terms explicitly reserve rights to book/edition owners and
forbid bulk index reconstruction.

## 5. What could not be verified

- **sunnah.com** (main site and `api.sunnah.com`): blocked with HTTP 403 on
  every attempt, via both `WebFetch` and direct `curl` with a browser
  user-agent. No claim is made about its licensing, editions, or data
  provenance — this is a gap, not an assumption of either good or bad
  status.
- **dorar.net**: blocked with HTTP 403 on every attempt. Its widely-cited
  role as a named-grading hadith database could not be independently
  checked here.
- **Zenodo**: search API returned `429`/`403` ("unusual traffic from your
  network") during this session; not searched.
- **archive.org Wayback Machine**: also returned `429 Too Many Requests`
  when queried for a cached copy of sunnah.com's about page; could not use
  it as a workaround for the sunnah.com block within this session.
- **qurancomplex.gov.sa**: connection timed out; unreachable from this
  environment. Likely irrelevant to hadith regardless (it is a Qur'an-
  printing institution), but reachability itself is unverified.
- **A live Shamela book page** (e.g. the `shamela.ws/book/1755` URL cited
  by fawazahmed0's References.md): returned 404; the site's search endpoint
  returned only an empty search form. Could not independently confirm
  edition/typist metadata on an actual Shamela book page.
- **Whether OpenITI's Terms-of-Use licence statement legally covers its
  GitHub-hosted corpus repositories** (as opposed to only the openiti.org
  website): the Terms of Use text defines its own scope as "the OpenITI
  website and portal," and none of the GitHub data repos inspected carry a
  repo-level `LICENSE` file. This is flagged as unresolved, not assumed in
  either direction.
- **Whether the archive.org PDF linked in OpenITI's Bukhari metadata is
  genuinely the stated 1987 Dar Ibn Kathir/al-Yamama printing**: the link
  was found and recorded, but the PDF itself was not opened and compared
  page-by-page against the transcription in this session.
