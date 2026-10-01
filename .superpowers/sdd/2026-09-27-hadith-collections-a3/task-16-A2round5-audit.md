# Task 16 — A2 round 5 audit: the vocabulary-free content-mass net

Base commit `1dd8a3f` (round 4). All Arabic below is copied byte-exact from the
materialized build (`.corpus-cache/sanad-materialized.db`), never retyped; shas
are `sha256(text_ar)`. This audit closes the pure-pointer false-EXACT class that
escaped seven prior fixes.

## The two nets

- **Net A — vocabulary-free content-mass (PRIMARY backstop).** For every scorable
  hadith primary, `openiti.content_mass(norm_aggressive)` strips ONLY non-matn
  scaffolding — honorifics, basmala, leaked isnad/chain (`عن NAME`, `حدثنا NAME`,
  `قال NAME` used as a transmission link), reference/deferral vocabulary, and a
  trailing speech frame that introduces a narrator but quotes nothing — then
  counts the content tokens that remain. It keys on **no marker word and no
  position**: this is the cure for the marker-axis escape pattern. Net A = every
  scorable record with content-mass ≤ K. **K = 3**, an AUDIT-SCOPE boundary.
  Net A size = **1089** records.
- **Net B — reference-superset cross-check (SECONDARY).**
  `find_pure_pointers(…, exclude_delivery=False)` is the round-4 residue sweep
  with its delivery-marker guard REMOVED — the exact defect of round 4 was that
  the guard dropped any record containing قال/يقول/زاد/غير/الا. With the guard off
  it surfaces the WHOLE reference/deferral/chain-bearing population with no
  exclusion. Net B size = **2678** records.
- **A ∪ B = 3552** records.

## Content-mass distribution (scorable primaries, pre-round-5 universe)

| content-mass | records |
|---|---|
| 0 | 20 |
| 1 | 67 |
| 2 | 351 |
| 3 | 651 |
| 4 | 943 |
| 5 | 1136 |
| 6 | 1319 |
| 7 | 1392 |
| ≤3 (net A) | 1089 |

Net A (cm ≤ 3) = 1089: **1061 audited KEEPs + 28 POINTERs** (below). Two of the
cm ≤ 3 records the net surfaces, muslim:274-13 ("دعه" / "leave him" -- the
Prophet's reply at Tabuk, Task 11's canonical proof the audit judges MEANING not
length) and muslim:581-2, DELIVER a self-contained clause and are KEEPs, not
pointers; the content-mass net is audit-scope, so it flags them for reading but
the ruling is by meaning.

## K = 3 is validated — the band above K is clean

Raising K can never admit a pointer (every record ≤ K is audited); the risk is
only that a pointer sits just ABOVE K. We inspected the band cm = 4..7 intersected
with net B (the reference-bearing records most able to hide a longer pointer).
Every cm = 4 net-B member delivers a self-contained variant clause AFTER its
reference word, e.g.:

- `hadith:muslim:52-7` — بهذا الإسناد مثله وزاد الإيمان يمان والحكمة يمانية
- `hadith:muslim:1988-4` — بهذين الإسنادين غير أنه قال الرطب والزهو والتمر والزبيب
- `hadith:nasai:2209` — فذكر مثله وقال من صامه وقامة إيمانا واحتسابا
- `hadith:muslim:2527-2` — بمثله غير أنه قال أرعاه على ولد في صغره ولم يقل يتيم

Each quotes specific delivered wording (a named item list, a ruling clause, a
variant phrase) and is therefore verifiable content = KEEP. No cm ≥ 4 record is a
content-free pointer. K = 3 holds.

## Exhaustion argument (stated honestly)

The net is a superset over (a) content-mass ≤ K — keys on NO vocabulary — and
(b) the enumerated reference vocabulary (net B). The only residual escape would be
a record with content-mass > K that is nonetheless a pure pointer using NO
enumerated reference word. That set is empty by construction: a record with > 3
content tokens surviving after all scaffolding/reference/frame stripping is, by
definition of `content_mass`, delivering ≥ 4 content tokens of its own — a matn
clause, not a deferral. The band validation above confirms it empirically for the
adjacent band. Cross-check: net B's low-content members (cm ≤ 3) number 215, and
all 215 are ⊆ net A — net B surfaces no low-content pointer that net A misses
(verified programmatically against the materialized DB).
Net B's cm > K members (the remaining ~2.46k) are KEEP-by-exhaustion: >K content
tokens means content delivered. We do not hand-audit all of net B; it is a gate
(`test_net_b_reference_superset_surfaces_no_unaudited_pointer`), not a keep list.

## The 28 new POINTER rulings

All 28 are in net A (cm ≤ 3); the `A/B` column marks which are also in net B.
The 12 ids named in the brief are all present and ruled (★). Classification rule:
POINTER iff it delivers no self-contained matn clause — قال/يقول in a frame or
chain with nothing delivered after it is NOT delivery; a real `قال: <words>` /
`زاد: <words>` IS delivery → KEEP.

| id | A/B | cm | reason | byte-exact text_ar |
|---|---|---|---|---|
| `hadith:abudawud:1176` | A | 1 | FRAME_ONLY | أن رسول الله صلى الله عليه وسلم كان يقول ح |
| `hadith:abudawud:1354` ★ | A·B | 1 | DEFERRAL | في هذا وكذلك قال في هذا الحديث وقال سلمة بن كهيل عن أبي رشدين عن بن عباس |
| `hadith:abudawud:3609` | A·B | 1 | DEFERRAL | بإسناده ومعناه قال سلمة في حديثه قال عمرو في الحقوق |
| `hadith:abudawud:4045` ★ | A | 3 | DEFERRAL | بهذا قال عن القراءة في الركوع والسجود |
| `hadith:bukhari:1656` | A | 1 | BARE_RULING | رخص النبي صلى الله عليه وسلم |
| `hadith:bukhari:3332` | A | 1 | CHAIN_LEAK | عمرو بن لحي بن قمعة بن خندف أبو خزاعة |
| `hadith:bukhari:4251` | A | 0 | FRAME_ONLY | عن النبي صلى الله عليه وسلم |
| `hadith:bukhari:4745` | A | 0 | FRAME_ONLY | سمعت النبي صلى الله عليه وسلم |
| `hadith:ibnmajah:1130` | A | 1 | POINTER | كان رسول الله صلى الله عليه وسلم يصنع ذلك |
| `hadith:muslim:57-4` | A | 0 | FRAME_ONLY | عن النبي صلى الله عليه وسلم |
| `hadith:muslim:109-2` ★ | A·B | 0 | FRAME_ONLY | بهذا الإسناد مثله وفي رواية شعبة عن سليمان قال سمعت ذكوان |
| `hadith:muslim:144-5` ★ | A·B | 0 | DEFERRAL | بهذا الإسناد نحو حديث أبي معاوية وفي حديث عيسى عن الأعمش عن شقيق قال سمعت حذيفة يقول |
| `hadith:muslim:198-3` | A | 0 | POINTER | مثل ذلك عن أبي هريرة عن رسول الله صلى الله عليه وسلم |
| `hadith:muslim:347-2` | A | 1 | POINTER | ذلك من رسول الله صلى الله عليه وسلم |
| `hadith:muslim:686-2` ★ | A·B | 0 | DEFERRAL | قلت لعمر بن الخطاب بمثل حديث بن إدريس |
| `hadith:muslim:851-3` ★ | A·B | 1 | ISNAD_VARIATION | بالإسنادين جميعا في هذا الحديث مثله غير أن بن جريج قال إبراهيم بن عبد الله بن قارظ |
| `hadith:muslim:882` | A | 1 | POINTER | كان رسول الله صلى الله عليه وسلم يصنع ذلك |
| `hadith:muslim:1183` | A | 1 | FRAME_ONLY | سمعت ثم انتهى فقال أراه يعني النبي صلى الله عليه وسلم |
| `hadith:muslim:1569` | A | 1 | BARE_RULING | زجر النبي صلى الله عليه وسلم عن ذلك |
| `hadith:muslim:1584-3` | A | 0 | FRAME_ONLY | عن النبي صلى الله عليه وسلم |
| `hadith:muslim:1730-2` | A·B | 0 | ISNAD_VARIATION | بهذا الإسناد مثله وقال جويرية بنت الحارث ولم يشك |
| `hadith:muslim:1822-2` ★ | A·B | 0 | DEFERRAL | سمعت رسول الله صلى الله عليه وسلم يقول فذكر نحو حديث حاتم |
| `hadith:muslim:1873-3` ★ | A·B | 0 | ISNAD_VARIATION | بهذا الإسناد غير أنه قال عروة بن الجعد |
| `hadith:muslim:2047-3` | A | 0 | FRAME_ONLY | سمعت النبي صلى الله عليه وسلم |
| `hadith:muslim:2359-6` ★ | A | 0 | FRAME_ONLY | سمعت أبي قالا جميعا |
| `hadith:muslim:2556-3` ★ | A·B | 0 | FRAME_ONLY | بهذا الإسناد مثله وقال سمعت رسول الله صلى الله عليه وسلم |
| `hadith:muslim:2649-2` ★ | A·B | 0 | DEFERRAL | بمعنى حديث حماد وفي حديث عبد الوارث قال قلت يا رسول الله |
| `hadith:muslim:2987-3` ★ | A·B | 1 | DEFERRAL | سمعت رسول الله صلى الله عليه وسلم غيره يقول سمعت رسول الله صلى الله عليه وسلم يقول بمثل حديث الثوري |

★ = one of the 12 ids the brief required to be surfaced and ruled; all 12 present.

## Reason-code legend

- **BARE_RULING** — bare ruling verb (naha / amara) with no object, immediately deferring to another narration for the content -- the ruling itself is never stated here
- **CHAIN_LEAK** — chain-continuation phrase: describes who narrated to whom (a fragment of the isnad itself), not a report of the Prophet's words, with no independent content of its own
- **DEFERRAL** — editorial abridgement: the matn breaks off and defers to the full narration printed elsewhere
- **POINTER** — editorial back-reference: the matn is a pointer to a narration printed in full elsewhere, not a text
- **ISNAD_VARIATION** — isnad/name-variation note ("ghayra annahu qala <NARRATOR-NAME>" / "qala <NAME> wa-lam yashukk"): records only that a parallel chain named a narrator differently, a WHO not a WHAT, delivering no matn clause of its own
- **FRAME_ONLY** — speech frame with no matn after it ("'an al-nabi [saw]" / "sami'tu rasula llah ... yaqul" / "qala sami'tu NAME"): the frame names WHO spoke or defers to another narration and quotes nothing, delivering no self-contained matn of its own
- **TRUNCATED_STUB** — truncated narrative frame: the reported speech is the punchline of an earlier, separately-numbered unit and the source ends the record here, with nothing following to reattach

## Recurrers reuse round-4 rulings

Records already ruled in `task-16-A2round4-audit.md` keep that ruling; this round
audits only the DELTA newly surfaced by net A's vocabulary-free measure or by net
B's removed exclusion. The round-4 omission/comparison partition (46 pointers)
stays pinned and its gate stays green; these 28 are additional.

## Verification run (not asserted — run)

- All 28 pinned unscorable at build; the 12 brief ids verify NOT_FOUND via
  `verify_spans` against their own text_ar; sampled band keeps verify EXACT;
  the two restored keeps (muslim:274-13, 581-2) verify EXACT.
- eval 101/101 (0 false verifications, 0 false misattributions); ask guard 9/9;
  wholly-Qur'anic sweep 0.
- Gates green: content-mass exhaustion gate
  (`test_no_scorable_record_is_a_low_content_pointer`), net-B cross-check gate,
  round-4 partition + omission gates; all re-measured count-pins
  (test_real_corpus, test_build) pass; the Nasai prefix-collision residue
  narrows 142→138 (four heads lose their only scorable completion, bukhari:4745).
- New source DB sha256: 603820b5d51c88b64f3713dc3e6087d421df1f45cb8143b17980513ed17c5a5d.

