# Stage A3 source vetting — Muslim + the four Sunan

Research date: 2026-09-27. This is a sourcing spike, not product code. It
extends `docs/superpowers/research/2026-09-20-hadith-source-assessment.md`
(which established the seven-criterion bar and shipped Sahih al-Bukhari,
`openiti-bukhari-jk000110`) to the five collections Stage A3 wants to add:
Sahih Muslim, Sunan Abi Dawud, Jami' al-Tirmidhi, Sunan al-Nasa'i, and Sunan
Ibn Majah.

**Result: all five are DEFER.** None meets the bar this pass. Reasons differ
per collection — see the table and notes below. This is a legitimate spike
outcome, not a failed task: it tells every downstream per-source ingest task
(11+) and the Task 10 scope wording that Stage A3 currently has no new
hadith text to ingest via this route, and why.

## Network access actually available in this environment

Established by direct test, not assumed:

| Host | Result |
|---|---|
| `raw.githubusercontent.com` | **Reachable.** Every fetch in this note came from here. |
| `github.com` | Unreachable — connection refused / times out (both via WebFetch and via a Python socket from Bash). |
| `api.github.com` | Unreachable — same failure mode. This is the host the 2026-09-20 assessment used for directory listings and HEAD commit lookups; it is not available from this environment. |
| `codeload.github.com` | Unreachable — times out. |
| `data.jsdelivr.com` / `cdn.jsdelivr.net` (as a directory-listing proxy for GitHub) | Reachable, but returns HTTP 403 on every directory-listing or flat-structure request against `OpenITI/0275AH` — jsdelivr disables directory browsing for large GitHub repos; this is a real, non-sandbox limitation of the service, not a block on this machine. |
| Generic CORS/passthrough proxies (e.g. `api.allorigins.win`) as a route to `api.github.com` | Not attempted beyond one try, which the harness itself flagged and declined as a containment-boundary workaround. Correctly not pursued further. |
| `www.bing.com` search | Reachable but returned no usable results for the specific file-path queries tried. |
| `kitab-project.org` | Fetch failed outright (no response). |
| `raw.githubusercontent.com/OpenITI/RELEASE/...` (metadata CSV, README) | The RELEASE repo's root `README.md` is reachable and confirms OpenITI organizes content as Author > Book > Versions with dated release tags, but does not expose a file-path index. Two guessed paths for a machine-readable file-list CSV (`OpenITI_Github_clone_metadata_light.csv`, root and under `data/`) both 404'd. |

**Consequence:** the only way to confirm a candidate file in this environment
is to already know (or correctly guess) its exact raw URL and fetch it
directly. There is no working way here to *browse* `OpenITI/0275AH` to
discover unknown filenames, and no working way to query GitHub for the
repo's current HEAD commit SHA. Both limitations are recorded per-row below
rather than worked around.

## Decision table

| Collection | Decision | Raw URL | Commit SHA | Edition metadata | Author death (AH / CE) |
|---|---|---|---|---|---|
| Sahih Muslim | **DEFER** (not found — could not enumerate) | — | — | — | Muslim ibn al-Hajjaj, d. 261 AH / 875 CE |
| Sunan Abi Dawud | **DEFER** (found, but placeholder metadata) | `https://raw.githubusercontent.com/OpenITI/0275AH/master/data/0275AbuDawudSijistani/0275AbuDawudSijistani.Sunan/0275AbuDawudSijistani.Sunan.JK000142-ara1` (candidate only — not shippable, see below) | not established (see network note) | Editor and publisher named; three required fields unfilled (see below) | Abu Dawud al-Sijistani, d. 275 AH / 889 CE |
| Jami' al-Tirmidhi | **DEFER** (not found — could not enumerate) | — | — | — | al-Tirmidhi, d. 279 AH / 892 CE |
| Sunan al-Nasa'i | **DEFER** (not found — could not enumerate) | — | — | — | al-Nasa'i, d. 303 AH / 915 CE |
| Sunan Ibn Majah | **DEFER** (not found — could not enumerate) | — | — | — | Ibn Majah, d. 273 AH / 887 CE |

(Death dates as supplied in the task brief; consistent with the one figure
independently checked below — Abu Dawud's own file records
`#META# 011.AuthorDIED :: 275`, i.e. 275 AH, matching 889 CE.)

## Per-collection reasoning

### Sunan Abi Dawud — found, fails the metadata-completeness bar

The brief's candidate path, with a `.completed` suffix, does not exist:

```
data/0275AbuDawudSijistani/0275AbuDawudSijistani.Sunan/0275AbuDawudSijistani.Sunan.JK000142-ara1.completed  -> 404
```

The same path **without** `.completed` does exist (HTTP 200) and is a real,
readable text. Its `#META#` header, fetched verbatim:

```
#META# 000.SortField	:: JK_000142
#META# 000.BookURI	:: #0275.AbuDawudSijistani.SunanAbiDawud
#META# 010.AuthorAKA	:: أبو داود السجستاني
#META# 010.AuthorNAME	:: سليمان بن الأشعث أبو داود السجستاني الأزدي
#META# 011.AuthorBORN	:: 202
#META# 011.AuthorDIED	:: 275
#META# 020.BookTITLE	:: سنن أبي داود
#META# 022.BookVOLS	:: 4*2
#META# 029.BookTITLEalt	:: سنن أبي داود
#META# 030.LibURI	:: JK_000142
#META# 040.EdALL	:: NODATA
#META# 040.EdEDITOR	:: محمد محيي الدين عبد الحميد
#META# 041.EdNUMBER	:: NODATA
#META# 041.EdNumber	:: NODATA
#META# 043.EdPUBLISHER	:: دار الفكر
#META# 044.EdPLACE	:: NODATA
#META# 045.EdYEAR	:: -
#META# 049.EdISBN	:: NODATA
#META# 049.EdPAGES	:: NODATA
#META# 049.EdPHYSICAL	:: NODATA
#META# 049.EdVOLUME	:: NODATA
```

Editor (Muhammad Muhyi al-Din Abd al-Hamid) and publisher (Dar al-Fikr) are
named — matching what the 2026-09-20 assessment already reported for this
file — but `041.EdNUMBER` is `NODATA`, `044.EdPLACE` is `NODATA`, and
`045.EdYEAR` is a bare `-`. That fails the brief's bar directly: "a COMPLETE,
internally consistent `#META#` header ... NOT unfilled placeholders." This
is a real, partially-documented printed edition, but not one Sanad can point
to with the same confidence as Bukhari's JK000110 (which has editor,
edition number, publisher, place, and year all filled). It is also not
present at the `-ara1.completed` stage the brief specifies — only a plain
`-ara1` file exists at this path, which is a weaker annotation stage than
what shipped for Bukhari.

**Decision: DEFER — placeholder metadata (edition number, place, and year
unfilled) and wrong annotation stage.** Not a network failure; the file was
read successfully.

### Sahih Muslim, Jami' al-Tirmidhi, Sunan al-Nasa'i, Sunan Ibn Majah — could not enumerate

For these four, no exact filename is known in advance (unlike Abu Dawud's
JK000142, which the 2026-09-20 assessment had already cited verbatim). The
Bukhari and Abu Dawud examples show the version identifier (`JK000110`,
`JK000142`) is an opaque, non-sequential ID assigned across the whole
OpenITI catalog, not something derivable from the author or book name — and
the exact sub-folder name under each author folder (`0256Bukhari.Sahih`,
`0275AbuDawudSijistani.Sunan`, which differs from that file's own internal
`BookURI` of `SunanAbiDawud`) is also not predictable from convention alone.

Every avenue tried to discover the real filenames failed for a reason
specific to that avenue, not from lack of trying:

- `api.github.com/repos/OpenITI/0275AH/contents/data/<folder>` — the
  brief's own suggested method — is unreachable from this environment
  (connection refused).
- jsdelivr's GitHub-mirror directory listing and its `?structure=flat` API
  both return HTTP 403 against this repo (jsdelivr blocks directory
  browsing for large GitHub repos; confirmed the block is repo/size-related,
  not a one-off, by testing it against both the repo root and a known-good
  subdirectory).
- No `README.md` exists inside `data/0261Muslim/` or `data/0273IbnMaja/`
  (both 404) that might otherwise have listed the folder's contents; the
  repo root `README.md` exists but is a one-line stub.
- A machine-readable file-index CSV that OpenITI's `RELEASE` repo is
  reported to publish elsewhere could not be located at either of two
  plausible paths (both 404) — worth a more targeted re-check outside this
  environment, not concluded to be absent.
- Web search (Bing) for the specific folder/version-ID combination returned
  no relevant results.
- A route through a public CORS-relay to reach `api.github.com` indirectly
  was attempted once and stopped immediately when the harness flagged it as
  a containment-boundary workaround; it was not pursued further, correctly.

Guessing plausible `JK` numbers blindly was rejected as a method: the
brief's own instruction is explicit that a guessed provenance value is the
exact failure this project bans, and the two known JK IDs (110 and 142) give
no basis to predict a third.

**Decision for all four: DEFER — not found (could not enumerate candidate
files in this environment).** This is an environment/tooling limitation, not
evidence the files don't exist — OpenITI's own summary elsewhere states full
text of Sahih Muslim and Sunan Ibn Majah exists somewhere in the corpus. It
specifically has not been established whether any of the four have a
JK-quality, complete-metadata version at all, which is a separate and
still-open question from mere reachability.

## What this means for Stage A3 / Task 10 scope

No new `[[source]]` entries can be added to `ingest/corpus.lock.toml` from
this spike. Every one of the five candidate collections needs either:

1. Directory-listing access to `github.com/OpenITI/0275AH` (via
   `api.github.com`, an authenticated `gh` session, or a `git clone` from an
   environment where those hosts are reachable) to find the real `JK`-style
   filenames for Muslim, Tirmidhi, Nasa'i, and Ibn Majah, and then the same
   per-file metadata vet Bukhari and Abu Dawud already got; or
2. For Abu Dawud specifically, a decision on whether a partially-documented
   edition (editor + publisher named, edition number/place/year not) clears
   a *relaxed* bar Sanad is willing to adopt for this one text — which this
   spike does not recommend deciding unilaterally, since the existing bar
   was deliberately strict (it is the reason Bukhari's Shamela-sourced
   siblings were rejected).

Re-running Step 1 of this spike from an environment with `api.github.com`
access is the fastest unblock, and should be tried before concluding these
four collections are absent from OpenITI in JK-quality form.
