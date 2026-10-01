"""Per-collection audit lists and tuning constants for the OpenITI parser.

Moved out of `openiti.py` so the parser is collection-agnostic: each entry
below is a judgement made by hand about one specific edition's printed text,
pinned to it by digest, and keyed under the collection it was read for.
Porting to a new collection means re-measuring the tuning constants and
re-reading the candidates, not reusing these values -- see the comments
inline.
"""
from __future__ import annotations

# --- tuning constants, measured per edition ---------------------------------

# Attribution must sit within this many characters of the verb. MEASURED, not
# chosen by taste: 25 is the largest distance a one-to-three-token attribution
# ever spans in this file (the observed range is 8..24).
ATTRIBUTION_WINDOW = 25

# No single cut may move more than this much text. The edition sometimes
# breaks off mid-narration for a sub-narrator's aside and then RESUMES the
# same story -- 2581 (Hudaybiyya), 2782 (Heraclius), 2880 (Khubayb) -- so the
# text behind the marker is matn, not an addendum. Those three are the only
# cuts on this file that would exceed 1,000 characters, and all three were
# read by hand. This is a cap on blast radius, not a claim about Arabic: a
# rule this simple does not get to move a kilobyte on its own say-so.
#
# THE NUMBER IS EDITION-SPECIFIC AND MUST BE RE-MEASURED PER EDITION. On this
# file the distribution has a clean gap: the largest genuine addendum the rule
# cuts is 869 characters, the next three candidates are 1,001 / 3,406 / 4,279
# and all three are interrupted narrations rather than addenda. 1,000 sits in
# that gap. Nothing guarantees Muslim or the Sunan have a gap in the same
# place -- or a gap at all -- so porting this parser means re-running that
# measurement and reading the candidates above the cap by hand, not reusing
# this constant.
MAX_ADDENDUM = 1000

# --- do-not-cut audit --------------------------------------------------------

# THERE IS DELIBERATELY NO MINIMUM PRIMARY LENGTH HERE.
#
# Round 5 tried one -- 32 characters, measured from the only gap in the lower
# quartile of the cut-primary distribution (18 19 20 20 21 21 22 25 25 | 32 32
# 33 34 ...) -- and it was removed the same round, because the measurement
# that justified the gap also showed the rule cannot work. Length does not
# separate a stub from a short hadith in EITHER direction: "la tuki fa-yuka
# 'alayki" (1366) is eighteen characters and a complete saying of the Prophet,
# while 632's "the Prophet passed by a man" is thirty-two and names nothing.
# A floor at 32 refused nine correct cuts -- every one of them read in the raw
# source, every one a genuine matn followed by a fresh full chain -- and still
# did not reach the two records it was introduced for.
#
# The same question was settled for the pointer records in R13 and has the
# same answer here: what is quotable is a judgement about meaning, so it is
# made by hand, one record at a time, and recorded in `_NEVER_CUT` below.
#
# Records where the cut is textually correct -- the edition really does print
# a short primary and then a second chain -- but the primary it leaves is a
# content-free narrative opener: it names no act, no ruling and no speech, so
# the entire narration lives in the addendum. Scoring such a primary is the
# `_UNSCORABLE` defect in a new costume: "the Prophet passed by a man" is an
# everyday sentence of hadith literature, present verbatim in many narrations
# across many collections, and answering it with EXACT 1.0 / Sahih al-Bukhari
# 632 fabricates a citation out of a commonplace.
#
# The remedy is to leave the record UNCUT, not to mark it unscorable: the
# hadith itself is perfectly quotable, and an `unscorable_reason` would take
# its full printed text out of the corpus too. Uncut, the record has exactly
# one representation -- the whole printed text -- which still verifies, while
# the opener on its own no longer does.
#
# An AUDIT, like `_UNSCORABLE`: a closed list of records read in the source,
# keyed to the sha256 of the uncut matn so a changed text stops the build
# rather than inheriting a judgement made about a different string. The scan
# that produced it is in the round-5 report -- every cut primary ranked by how
# many tokens it holds outside the honorific frame ("the Prophet", "may God
# bless him and grant him peace", "from", "that"). These two rank first and
# second on all 395 with one and two content words; the third (466, "the
# Prophet interlaced his fingers") names a specific act and was ruled genuine.
_STUB_OPENER = ("narrative opener: the primary matn names no act, ruling or "
                "speech of its own, the narration itself beginning in the "
                "appended second chain")

# The second kind of bad cut, found by the whole-branch review rather than by
# the round-5 scan, and invisible to it: unit 4575 sits under the bab
# "fa-kana qaba qawsayni aw adna", and the edition prints the AYAH the chapter
# comments on and then the narration about it. The cut fires at the second
# chain, which is a defensible boundary, and leaves a primary matn that is
# nothing but Qur'an 53:9-10 -- so Sanad stamped "Sahih al-Bukhari 4575" on
# two verses of scripture, and told a reader who quoted them and cited
# "(53:9)" that their reference was wrong.
#
# Round 5's scan ranked cut primaries by how many tokens they hold outside the
# honorific frame, looking for stubs. A primary made of scripture is dense
# with content words and ranks at the very bottom of that list: the metric was
# built to find emptiness and cannot see this. The corpus-wide invariant in
# `materialize._reject_wholly_quranic_representations` is what closes the class;
# this entry corrects the one record.
_QURANIC_PRIMARY = ("Qur'anic primary: the cut leaves a matn that is nothing "
                    "but the ayah the chapter comments on, the narration that "
                    "makes the unit a hadith beginning in the appended chain")

# --- hand-corrected cuts (Task 12 fix round 1, ruling R-A3-18) --------------
#
# `_split_secondary`'s single-level backward walk sometimes finds an INNER
# "qala <name>" attribution but misses an OUTER one immediately in front of
# it -- nested reported speech -- and leaves the outer "qala <name>" stranded
# at the end of the primary. See `_apply_cut_override`'s docstring in
# openiti.py for why this is a hand-read list rather than a generalised
# extension of the walk: the same token shape is, on a case-by-case reading,
# sometimes complete narrative content (454, 3988 -- not on this list) and
# sometimes a dangling fragment (the eleven records below). The value is
# (sha256-of-the-uncorrected-primary, count-of-trailing-tokens-to-move); sha
# values are computed directly from the pre-fix build's text_ar (never
# hand-typed), which for every record below equals `_split_secondary`'s own
# output since none of them carry Abu Dawud's "qala Abu Dawud" marker.
CUT_OVERRIDE: dict[str, dict[str, tuple[str, int]]] = {
    "abudawud": {
        # "... qala bin al-Muthanna" | addendum "qala 'Amr wa-haddathani ...":
        # Ibn al-Muthanna's own attribution, stranded outside the addendum
        # that reports what he said.
        "hadith:abudawud:506":
            ("b5c4c68e8eaad29dd82044ef93579f85dcdfd67535f6ff57ac1c0c074215a0a2", 3),
        # "... qala Hajjaj" | addendum "wa-qala Hammam wa-haddathana ...".
        "hadith:abudawud:736":
            ("cf69fed768fced5a221c5879ff89b0960abfb70a8271db19dff0d721e68c91ab", 2),
        # "... wa-qala Sulayman" | addendum "qala haddathani Yahya ...".
        "hadith:abudawud:907":
            ("bc3f3d628440a47b09b110cfd5a9494b726cdfdff55717fac0d802d6ef65937e", 2),
        # "... qala Za'ida" | addendum "qala haddathani Hussein 'an 'Umara ...".
        "hadith:abudawud:1104":
            ("5c90c8df6ee07f9c2a51d6251531ada824dccd26c22c4941f0053ca8bf946e6d", 2),
        # "... qala Sufyan kana bin Jurayj" | addendum "akhbarana 'anhu ...":
        # the cut also landed mid-clause -- "kana bin Jurayj" is the start of
        # what Sufyan said, not part of the genuine matn in front of it -- so
        # all five trailing tokens move, not just the bare attribution.
        "hadith:abudawud:2016":
            ("ad7af02a7ea94a816ab73664c7fb671eb3c9044c45efdd3bdc8b3b7982a36fcd", 5),
        # "... qala Abu Bakr" | addendum "qala alladhi haddathani ...".
        "hadith:abudawud:2365":
            ("599940886eeca8d1f9af2ab32e8ed58950628e69043453c595fc37e6b6d6bff0", 3),
        # "... qala Musaddad" | addendum "qala akhbarani 'Abd Allah ...".
        "hadith:abudawud:3255":
            ("7a1ad97bd454d2698a3a5d915e13f1bb021f138320e36aaec7f6acd0c879e8b7", 2),
        # "... qala fa-man a'da al-awwal qala Ma'mar" | addendum "qala
        # al-Zuhri fa-haddathani rajul ...": the genuine rhetorical question
        # ("so who infected the first one?") stays; only the trailing "qala
        # Ma'mar" is the dangling fragment.
        "hadith:abudawud:3911":
            ("c466e10735aa1f1732a83a4c8d7544778ce78cbd828b220bba80b511d6e635b5", 2),
        # "... qala Nasr" | addendum "qala haddathani bin Jurayj ...".
        "hadith:abudawud:4586":
            ("71969ed518e9f59560b02f9491252e2cf057ae27471a3848e7512b08954ea554", 2),
        # "... hatta yu'mina bil-qadar thumma" | addendum "qala haddathani
        # 'Umar bin al-Khattab ...": the dangling fragment is the bare
        # conjunction "thumma" ("then"), not a name -- the backward walk
        # stops on it because it is a closed-class word (_NOT_A_NAME), the
        # same reason it correctly stops on real conjunctions elsewhere.
        "hadith:abudawud:4695":
            ("57f840b08dcd90f434c63ccf62f6d41c163e22905be3c18c25569c590c74aace", 1),
        # "... qala Yahya bin Zakariyya" | addendum "qala abi fa-haddathani
        # Abu Ishaq ...": a three-token name, at the walk's own ceiling.
        "hadith:abudawud:4717":
            ("6aa221babdadd6164037803e0103ae0d88d694657936399e870205100a27a59a", 4),
    },
}

# --- hand-corrected cut, second stage (Task 12 fix round 2, ruling R-A3-22) -
#
# Widening `_ABUDAWUD_COMMENTARY` to a one-token gap (see `openiti.py`'s
# `_ABUDAWUD_COMMENTARY_NEAR`) finds hadith:abudawud:4129's marker -- "qala
# LANA Abu Dawud" -- but that alone is not enough: the source prints TWO more
# "qala <name>" attributions in front of it, an isnad-linked narrator vouching
# for Mu'awiya's reliability and then a further transmitter, neither of them
# introduced by a chain-transmission verb `_split_secondary` would ever
# anchor on ("qala wa-kana Mu'awiya la yuttaham fi l-hadith 'an Rasul Allah
# ... qala lana Abu Sa'id qala lana Abu Dawud ..."). Left alone, the near-miss
# cut still leaves "la tarkabu l-khazz wa-la l-nimar QALA WA-KANA MU'AWIYA LA
# YUTTAHAM ... QALA LANA ABU SA'ID" as the scored matn -- the well-known
# Prophetic saying plus two more narrators' asides fused onto it, which is
# the SAME defect this whole fix round exists to close, one level further
# back. This is exactly `CUT_OVERRIDE`'s "nested reported speech" shape
# above, at a different call site (after `_split_compiler_commentary`, not
# after `_split_secondary`), which is why it is a separate dict: its digest
# is of the matn as it stands after that split, not before it, and reusing
# one dict keyed by the same record id at two pipeline stages with two
# different expected digests would make one of the checks raise every build.
# The value has the same shape as `CUT_OVERRIDE`: (sha256-of-the-primary-
# after-the-compiler-commentary-split, count-of-trailing-tokens-to-move).
#
# hadith:abudawud:1234 (Task 12 fix round 3, ruling R-A3-23) is the same
# shape one call site later: "sami'tu ACC-kunya" ("I heard Abu Dawud say")
# is a case `_split_compiler_commentary`'s nominative-only markers can never
# reach, so `_split_heard_commentary` exists to catch it -- but 1234 prints
# "... qala 'Uthman 'an 'Abd Allah ibn Muhammad ibn 'Amr ibn 'Ali SAMI'TU ABA
# DAWUD yaqulu ...": a narrator's own attribution ("Uthman said, on the
# authority of ...") stands in front of the "sami'tu" that introduces Abu
# Dawud's remark, and `_split_heard_commentary`'s own marker only reaches the
# "sami'tu" itself. Left alone, the primary matn would still end "... ANNAHU
# kana rasulu Llahi ... yasna'u QALA 'UTHMAN 'AN 'ABD ALLAH IBN MUHAMMAD IBN
# 'AMR IBN 'ALI" -- the genuine hadith plus a dangling, unrelated narrator's
# name -- the exact defect this whole fix round exists to close. Its digest
# is of the matn as it stands after `_split_heard_commentary`, one call site
# later than 4129's own entry above; both entries share this one dict
# because each is checked against its OWN record id, so a different pipeline
# stage per entry is safe as long as no record ever appears twice.
NEAR_MISS_CUT_OVERRIDE: dict[str, dict[str, tuple[str, int]]] = {
    "abudawud": {
        "hadith:abudawud:4129":
            ("f5638b9dd3517aabb7a92e055bb6ad366aa01371bd6e3e533cda4eb8a3dc294e", 18),
        "hadith:abudawud:1234":
            ("29dd1c200736cb6d27f5b1de7641c061e46e66b541670e4e0d422dad37d4f0f0", 11),
    },
    # Tirmidhi (Task 13). "fath al-Qustantiniyya ma'a qiyam al-sa'a QALA
    # MAHMUD" -- Mahmud ibn Ghaylan, the FIRST narrator in this unit's own
    # isnad (not the compiler Abu Isa), inserts his own attribution after the
    # genuine matn ("the conquest of Constantinople is [a sign] of the
    # establishment of the Hour"), and the edition never gives the content of
    # what he said -- it goes straight into "hadha hadith gharib ...", the
    # tail `_TIRMIDHI_FORMULA`'s "hadha hadith" arm already cuts correctly.
    # `_COMPILER_MARKERS`'s kunya-based patterns can never reach a different
    # narrator's bare name, so the dangling "qala Mahmud" is a boundary
    # correction of the same "nested attribution" shape as Abu Dawud's own
    # entries above, applied one call site later (after
    # `_split_compiler_commentary` has already made its own cut, per the
    # module docstring above `NEAR_MISS_CUT_OVERRIDE`).
    "tirmidhi": {
        "hadith:tirmidhi:2239":
            ("1291e1e8e9ac6535dd9957c465370fe0f947d346e96b60b62aee61192dfbb5e8", 2),
    },
    # Nasai (Task 14). Two records where `_NASAI_FORMULA`'s "هذا حديث" arm
    # finds the right marker but the wrong boundary, leaving a dangling
    # fragment on the primary -- the same nested-attribution shape as the
    # entries above, one call site later.
    #
    # hadith:nasai:5583: "... kullu muskirin haramun wa-kullu muskirin khamrun
    # QALA AL-HUSAYN QALA AHMAD wa-hadha hadith sahih" -- after the formula
    # cuts at "wa-hadha hadith sahih", "qala al-Husayn qala Ahmad" (a
    # sub-narrator relaying Ahmad ibn Hanbal's own grading remark, not
    # al-Nasai's voice at all) is left dangling on the genuine Prophetic
    # saying. 4 trailing tokens moved.
    #
    # hadith:nasai:5707: "... kana al-nabidhu alladhi yashrabuhu 'Umar ibn
    # al-Khattab qad khallala WA-MIMMA YADULLU 'ALA SIHHATI hadha hadith
    # al-Sa'ib" -- the formula's "hadha hadith" arm cuts at "hadha", but
    # "hadha" here is the grammatical subject of "wa-mimma yadullu 'ala
    # sihhati" ("and among what indicates the correctness of THIS is..."),
    # not the start of the editorial remark -- the remark itself (a
    # cross-reference to a corroborating report) begins 4 tokens earlier, at
    # "wa-mimma". Left uncorrected, the primary ends on an incomplete clause
    # ("... qad khallala wa-mimma yadullu 'ala sihhati", "... had turned [to
    # vinegar] and among what indicates the correctness of") rather than the
    # genuine, complete report that Umar's nabidh had turned to vinegar.
    #
    # The remaining 11 entries below are all from the Task 14 fix round
    # (R-A3-25), covering the sibling comparative-isnad verbs `_NASAI_FORMULA`
    # gained beyond "خالفه"/"هذا حديث" -- see `openiti.py`'s own comment above
    # `_NASAI_FORMULA` for the full family measurement. Each is the same
    # dangling-attribution shape as 5583/5707 above: the formula's verb cuts
    # correctly, but a further nested "qala <name>"/"rawahu <name>" clause (or
    # a bare name) sits between the genuine matn and the verb, undetected by
    # any single-verb marker.
    "nasai": {
        "hadith:nasai:5583":
            ("88bd4d59e6f70b2019aed435ffdafb19ca8510c2d7c53920e2d372388fbd9c11", 4),
        "hadith:nasai:5707":
            ("f54c94f1c7ef194405c64ce6d7165aa0ace69f259d4bfe56d87910dbcd6c33ea", 4),
        # hadith:nasai:3892's own entry ("... bi-dhahabin aw fiddatin
        # WA-RAWA AL-ZUHRI AL-KALAM AL-AWWAL 'AN SA'ID fa-arsalahu") was
        # REMOVED in fix round 2 (R-A3-27): `_NASAI_FORMULA` now has a bare
        # "روى" arm too (alongside "رواه", found by the prefix-collision
        # detector's own probe on 1777/3881/3894 -- see `openiti.py`'s
        # comment above `_NASAI_FORMULA`), an EARLIER match than "أرسله"
        # here, reaching "... bi-dhahabin aw fiddatin" in one step with no
        # dangling attribution left to correct.
        # "... al-mar'a al-ha'id wal-kalb QALA YAHYA rafa'ahu Shu'ba" -- the
        # "رفعه" arm cuts at "رفعه", but "قال يحيى" (Yahya introducing the
        # remark) is left dangling. 2 trailing tokens moved.
        "hadith:nasai:751":
            ("81cc008dcf609754fa0f12364da09c208cbfafbf3d56693484dcfbc927552336", 2),
        # "... al-ta'un wal-mabtun wal-ghariq wal-nufasa' shahada QALA
        # WA-HADDATHANA ABU 'UTHMAN MIRARAN wa-rafa'ahu marratan ila al-nabi"
        # -- the "رفعه" arm cuts at "ورفعه", but "قال وحدثنا أبو عثمان مرارا"
        # (a narrator's own remark on how often he heard it from Abu
        # 'Uthman) is left dangling. 5 trailing tokens moved.
        "hadith:nasai:2054":
            ("4ad0b8a3b92219627f3d4964ff3285f06c7ed41f99f26e35682b5d229d5559cb", 5),
        # hadith:nasai:3901's own entry ("... dhalika fard al-ard RAWAHU
        # YAHYA IBN SA'ID 'AN HANZALA IBN QAYS wa-rafa'ahu kama rawahu Malik
        # 'an Rabi'a") was REMOVED in fix round 2 (R-A3-27) for the same
        # reason as 1792's and 3900's, both below: `_NASAI_FORMULA`'s new
        # bare "رواه" arm is an EARLIER match than "رفعه" here and reaches
        # "... dhalika fard al-ard" in one step, with no dangling attribution
        # left to correct.
        # hadith:nasai:1792's own entry ("... aw ka'annahu adrakahu RAWAHU
        # HUMAYD IBN 'ABD AL-RAHMAN IBN 'AWF mawqufan") was REMOVED in fix
        # round 2 (R-A3-27): `_NASAI_FORMULA` now has its own bare "رواه"
        # arm, which is an EARLIER match than "موقوفا" here and reaches the
        # correct boundary ("... أو كأنه أدركه") in one step, with no
        # dangling attribution left to correct -- this override's own
        # sha256 stopped matching (the intermediate string it corrected no
        # longer occurs), confirmed by re-deriving the cut from scratch
        # rather than widening the pin.
        # "... fa-salla kullu insanin minhum li-nafsihi rak'atan wa-sajdatayn
        # QALA ABU BAKR IBN AL-SUNNI AL-ZUHRI SAMI'A MIN IBN 'UMAR
        # HADITHAYN wa-lam yasma' hadha minhu" -- Ibn al-Sunni (al-Nasai's
        # OWN transmitter, a different person from al-Nasai himself, so
        # `tight` never fires) relays that al-Zuhri heard two hadiths from
        # Ibn 'Umar but not this one; the "لم يسمع" arm cuts at "ولم يسمع",
        # leaving the whole introducing clause dangling. Found by this fix
        # round's own sweep, not named in the review's 7-record list -- one
        # further member of the same family found by continuing to measure
        # past it. 11 trailing tokens moved.
        "hadith:nasai:1541":
            ("24ff4b809c86e725320da7d9ed86f17ceac69bfd4b890ac4804e46daf1f9f2dd", 11),
        # "... min wara' al-nas 'URWA lam yasma'hu min Umm Salama" -- the "لم
        # يسمع" arm cuts at "لم يسمعه", but "عروة" (the narrator's bare name)
        # is left dangling. 1 trailing token moved.
        "hadith:nasai:2926":
            ("2e7af25d5eaa9f65b062dd814bd222ae315de499230d792b4e7a5a215c2a1df9", 1),
        # "... kaffaratu al-yamin WA-QILA INNA AL-ZUBAYR lam yasma' hadha
        # al-hadith min 'Imran ibn Husayn" -- the "لم يسمع" arm cuts at "لم
        # يسمع", but "وقيل إن الزبير" is left dangling. 3 trailing tokens
        # moved.
        "hadith:nasai:3844":
            ("b6608aab417bb4b1e3889160a6979bf62cd452f34f38c6f51f399f7725cf1174", 3),
        # "... aw li-yamnahaha WA-MIMMA YADULLU 'ALA ANNA TAWUSAN lam
        # yasma' hadha al-hadith" -- the "لم يسمع" arm cuts at "لم يسمع", but
        # "ومما يدل على أن طاوسا" is left dangling. 5 trailing tokens moved.
        "hadith:nasai:3872":
            ("71f96f8731d23fbdf97139e0fabde02d62cc98f99cf309dd9813650555c275d3", 5),
        # "... illa an tu'lama WA-FI RIWAYATI HAMMAM IBN YAHYA KAL-DALIL 'ALA
        # ANNA 'ATA'AN lam yasma' min Jabir hadithahu 'an al-nabi ... man
        # kanat lahu ardun fal-yazra'ha" -- the "لم يسمع" arm cuts at "لم
        # يسمع", but "وفي رواية همام بن يحيى كالدليل على أن عطاء" is left
        # dangling. 9 trailing tokens moved.
        "hadith:nasai:3880":
            ("54a46414a3f9b8733ffaee94495f2534c44db26e5a08c642da291ef3fcaa8944", 9),
        # "... wa-kariha kira'aha wa-ma siwa dhalika AYYUB lam yasma'hu min
        # Ya'la" -- the "لم يسمع" arm cuts at "لم يسمعه", but "أيوب" (the
        # narrator's bare name) is left dangling. 1 trailing token moved.
        "hadith:nasai:3895":
            ("506c3706588766fa03c988c05704564b4ed18887cacb882decbaa3918820e22e", 1),
        # "... wal-sukr min kulli sharab IBN SHUBRUMA lam yasma'hu min
        # 'Abdillah ibn Shaddad" -- the "لم يسمع" arm cuts at "لم يسمعه", but
        # "بن شبرمة" is left dangling. 2 trailing tokens moved.
        "hadith:nasai:5683":
            ("8fc0107b13a849d77c0e844d11e88f9939bd1da957f245d2513b2721100306ea", 2),
        # hadith:nasai:3900's own entry ("... fala ba's RAWAHU SUFYAN
        # AL-THAWRI RADIYA LLAHU 'ANHU 'AN RABI'A wa-lam yarfa'hu") was
        # REMOVED in fix round 2 (R-A3-27) for the same reason as 1792's,
        # immediately above: `_NASAI_FORMULA`'s new bare "رواه" arm is an
        # EARLIER match than "لم يرفعه" here and reaches "... fala ba's" in
        # one step, with no dangling attribution left to correct. This is
        # also R-A3-27's own required resolution of the 3900/3891/3896/3925
        # inconsistency -- all four now cut via the same "رواه" family
        # (3900 here; 3891 via its own override below; 3896/3925 need no
        # override at all, see `openiti.py`'s comment above `_NASAI_FORMULA`).
        # --- Fix round 2 (R-A3-27): the six vocabulary-free shapes the
        # prefix-collision detector's own probe found, none of which any
        # prior round's marker table named -- see `openiti.py`'s comment
        # above `_NASAI_FORMULA`'s widened definition.
        #
        # "... fa-bala qa'iman QALA SULAYMAN FI HADITHIHI wa-masaha 'ala
        # khuffayhi wa-lam yadhkur Mansur al-mash" -- the isnad names BOTH
        # Sulayman and Mansur as co-narrators from the same chain; the "لم
        # يذكر" arm cuts at "ولم يذكر", but "قال سليمان في حديثه ومسح على
        # خفيه" (Sulayman's own variant addition, introduced the same way a
        # "قال <name>" narrator-note always is elsewhere in this family) is
        # left dangling in front of it. 7 trailing tokens moved.
        "hadith:nasai:28":
            ("eeddaf5e63484d367597a9847deb5c1ca07b6780556d5784ef869c6fc4b3d83b", 7),
        # "... ma qadara 'alayhi ILLA ANNA BUKAYRAN lam yadhkur 'Abd al-Rahman
        # wa-qala fi al-tib wa-law min tibi al-mar'a" -- the "لم يذكر" arm
        # cuts at "لم يذكر", but "إلا أن بكيرا" (introducing which narrator's
        # version is being compared) is left dangling. 3 trailing tokens
        # moved.
        "hadith:nasai:1375":
            ("34753524ce2e349526677f367845fa17d536b3e9c1f417f68101ecf3c8274531", 3),
        # "... yamshuna bayna yaday al-janaza BAKRUN WAHDAHU lam yadhkur
        # 'Uthman" -- the "لم يذكر" arm cuts at "لم يذكر", but "بكر وحده"
        # (naming which of the isnad's several co-narrators is meant) is left
        # dangling. 2 trailing tokens moved.
        "hadith:nasai:1945":
            ("dbb7079a8978b3ebf1742e56ccb7f241cb5ef22814f5113f6c0df440c57b4f46", 2),
        # "... la nakhafu fi Llahi lawmata la'im QALA SHU'BA SAYYAR lam
        # yadhkur hadha al-harf haythuma kana wa-dhakarahu Yahya ..." -- the
        # "لم يذكر" arm cuts at "لم يذكر", but "قال شعبة سيار" (introducing
        # whose wording is being compared) is left dangling. 3 trailing
        # tokens moved.
        "hadith:nasai:4154":
            ("a6d23146f2765b73c77ded80a84b3960f5a264c200f6e99abc3b9760e231bea8", 3),
        # "... illa al-ma' wal-sawiq GHAYRA ANNAHU lam yadhkur al-nabidh" --
        # the "لم يذكر" arm cuts at "لم يذكر", but "غير أنه" (the
        # subordinating connective introducing the remark) is left dangling.
        # 2 trailing tokens moved.
        "hadith:nasai:5755":
            ("17ab2f7c8c4013b2fd60c35e83cefa45f4ccc75cd282129c541f15a5ae43eecb", 2),
        # "... nahy 'an al-muhaqala QALA SA'ID FADHAKARAHU NAHWAHU rawahu
        # Sufyan al-Thawri 'an Tariq" -- the bare "رواه" arm cuts at "رواه",
        # but "قال سعيد فذكره نحوه" (Sa'id's own remark that he narrated it
        # similarly) is left dangling. 4 trailing tokens moved.
        "hadith:nasai:3891":
            ("4f452c258e7febce457533dc4032fb20d93668ba7484b0b94f17b0c0dd0ae22f", 4),
        # The bare "روى" arm (added alongside "رواه" once the prefix-
        # collision detector's own probe found this pair of records) cuts at
        # "روى", but "وقد" (attached as "WA-QAD", not "WA-ROWA" -- Arabic's
        # "qad" proclitic-of-a-different-word, not this word's own proclitic)
        # is left dangling in front of it on both. 1 trailing token moved on
        # each.
        "hadith:nasai:3881":
            ("e9b38344ebedfe330225620fffffe87129c56709c006f3707575e11b96285771", 1),
        "hadith:nasai:3894":
            ("032ed54cc99e2709c095b8af41fde795deadef6979aa5d53f8fec814546cd5bc", 1),
        # "... ghayyiru al-shayba wa-la tashabbahu bil-Yahud WA-KILAHUMA
        # ghayru mahfuz" -- the "غير محفوظ" arm cuts at "غير محفوظ", but
        # "وكلاهما" (naming WHICH TWO things the grading applies to) is left
        # dangling. Found by the prefix-collision detector's own probe. 1
        # trailing token moved.
        "hadith:nasai:5074":
            ("a4a42a24f467447d13f4b9fd88428d8141653b49698d75e8b001cccc11729ed3", 1),
    },
    # Ibn Majah (Task 15). Two records where a compiler-commentary/formula
    # arm cuts at the right verb but a nested attribution sits between it
    # and the genuine matn, same dangling shape as every entry above.
    #
    # hadith:ibnmajah:1385: "... yaa Muhammad inni qad tawajjahtu bika ila
    # rabbi fi hajati hadhihi li-tuqda Allahumma fa-shaffi'hu fiyya QALA ABU
    # ISHAQ hadha hadith sahih" -- `_IBNMAJAH_FORMULA`'s "hadha hadith" arm
    # cuts at "hadha", but "qala Abu Ishaq" (the narrator introducing the
    # grading remark that follows, not Ibn Majah's own voice) is left
    # dangling on the genuine supplication. 3 trailing tokens moved.
    #
    # hadith:ibnmajah:2162: "... wa-a'tahu ajrahu TAFARRADA BIHI IBN ABI
    # 'UMAR WAHDAHU qalahu Ibn Majah" -- "qalahu Ibn Majah" ("Ibn Majah said
    # IT") refers BACKWARD to the isnad-uniqueness remark that precedes it,
    # not forward -- the opposite order from every other collection's
    # "qala <compiler> ..." shape, so `_IBNMAJAH_FORMULA`'s own marker
    # anchors correctly on "قاله بن ماجة" but the remark it is attributing
    # sits entirely in front of the anchor. "tafarrada bihi ... wahdahu" is
    # unambiguously isnad apparatus (who alone narrated this from his
    # peers), never narrative content about a cupping fee. 6 trailing tokens
    # moved.
    "ibnmajah": {
        "hadith:ibnmajah:1385":
            ("49ed8c2312567636d05865c1cdde27df4f3eea7120dc2d5b5eae935022595f65", 3),
        "hadith:ibnmajah:2162":
            ("439436a5a20ca69f2e7646a82c5a8dd4785f4230c039a4ca568d90dfdab84d9e", 6),
    },
}

# --- Abu Ali al-Lu'lu'i's own voice: the one do-not-cut exception -----------
# (Task 12 fix round 2, ruling R-A3-22)
#
# A dedicated dict, not a reuse of `NEVER_CUT` below: `NEVER_CUT` is checked
# by `_audited_never_cut` against the matn as it stands BEFORE
# `_split_secondary` runs, but this entry's digest is of the matn as it
# stands AFTER `_split_compiler_commentary` has already run (see
# `openiti.py`'s `flush()`) -- a different string at a different pipeline
# stage. Reusing one dict keyed by the same record id for both checks would
# make one of the two raise a spurious "text has drifted" error every build.
#
# hadith:abudawud:4068: "qala rani rasul Allah ... qala Abu Ali al-Lu'lu'i
# arahu wa-'alayya thawb musbagh bi-'usfur mawrad fa-qala ma hadha
# fa-intalaqtu fa-ahraqtuhu ..." -- Abu Ali's remark sits IN THE MIDDLE of a
# single narration, glossing which colour word the garment was described
# with, not commenting on the hadith after it ends. The narration's own
# continuation ("the Prophet said: what did you do with your garment? I
# said: I burned it. He said: why didn't you give it to some of your family
# instead?") only makes sense with Abu Ali's clause still attached -- cutting
# here would leave "the Messenger of Allah saw me" as the entire scored matn
# and discard the rest of the hadith into addenda. Read by hand against the
# source; excluded, not patched around.
_LULUI_MID_NARRATION = (
    "mid-narration parenthetical: Abu Ali al-Lu'lu'i's remark sits inside a "
    "single narration, not after it, and the narration's own continuation "
    "depends on the clause the naive cut would discard")

LULUI_NEVER_CUT: dict[str, dict[str, tuple[str, str]]] = {
    "abudawud": {
        "hadith:abudawud:4068":
            ("31e484c9d5b9cf0d8706075599f8a2e2f1136fa8efc848f9e5725e17dbd6b77a",
             _LULUI_MID_NARRATION),
    },
}

# --- Nasai's "extra" formula do-not-cut exception (Task 14) -----------------
#
# A dedicated dict, not a reuse of `NEVER_CUT` below, for the same reason
# `LULUI_NEVER_CUT` is its own dict: `NEVER_CUT` is checked by
# `_audited_never_cut` inside `_split_secondary`, against the matn as it
# stands BEFORE `_split_compiler_commentary` ever runs; this entry's digest is
# of the matn as it stands immediately BEFORE `_split_compiler_commentary`'s
# OWN search (after `_split_secondary` and `CUT_OVERRIDE` have already run) --
# a record that also happened to be on `NEVER_CUT` would otherwise have its
# digest checked against two different strings under one key.
#
# hadith:nasai:3047: "... wa-inna rasula Llahi sallallahu 'alayhi wa-sallam
# KHALAFAHUM thumma afada qabla an tatlu'a al-shams" ("... and the Messenger
# of Allah DIFFERED FROM THEM [the pre-Islamic practice of waiting for
# sunrise] and hastened [from Muzdalifah] before the sun rose"). `_NASAI_
# FORMULA`'s "khalafahu/khalafahuma/khalafahum" arm reads as al-Nasai's own
# comparative-isnad note ("so-and-so differed from him in the narration") on
# every one of the other 76 measured occurrences, immediately followed there
# by a narrator's name -- but here the same verb form is genuine narrative
# describing the Prophet's own act, immediately followed by "thumma" (a
# narrative connective), never a name. Cutting here would truncate the
# hadith's own point (he acted before sunrise, unlike the Jahiliyya) into
# addenda. Read by hand against the source; excluded, not patched around.
_NASAI_GENUINE_KHALAFAHUM = (
    "genuine narrative: \"he differed from [a practice]\", describing the "
    "Prophet's own act, not al-Nasai's comparative-isnad note \"so-and-so "
    "differed from him [in narrating it]\" -- the same verb form, a "
    "different sense, immediately followed by a narrative connective rather "
    "than a narrator's name")

# --- Fix round 1 (R-A3-25): the rest of the comparative-isnad family's own
# genuine-narrative exceptions --------------------------------------------
#
# Every reason string below documents a verb that ALSO has a genuine
# narrative sense identical in surface form to al-Nasai's critique sense --
# see `openiti.py`'s own comment above `_NASAI_FORMULA` for the full family
# measurement each of these was found against.
_NASAI_GENUINE_ARSALAHU_MESSENGER = (
    "genuine narrative: \"he SENT [a messenger] to her\", not al-Nasai's "
    "\"so-and-so transmitted it mursal\" -- the same verb, a different "
    "object (a person sent, not a report transmitted)")
_NASAI_GENUINE_ARSALAHU_PROPHETIC_SPEECH = (
    "genuine narrative: the Prophet's own reported speech \"LET HIM GO, "
    "Umar\" (arsilhu ya 'Umar), not al-Nasai's \"so-and-so transmitted it "
    "mursal\" -- an imperative addressed to 'Umar, not a third-person "
    "isnad remark")
_NASAI_GENUINE_ARSALAHU_RAIN = (
    "genuine narrative: Allah SENDING DOWN rain (\"thumma arsalahu\"), not "
    "al-Nasai's \"so-and-so transmitted it mursal\"")
_NASAI_GENUINE_ARSALAHU_RELEASED = (
    "genuine narrative: he PARDONED and RELEASED the killer (\"fa-'afa "
    "'anhu fa-arsalahu\"), not al-Nasai's \"so-and-so transmitted it "
    "mursal\"")
_NASAI_GENUINE_RAFA_AHU_HANDS = (
    "genuine narrative: RAISING the hands out of prostration (\"wa-idha "
    "rafa'ahu fal-yarfa'huma\"), not al-Nasai's \"so-and-so attributed it "
    "marfu'\"")
_NASAI_GENUINE_RAFA_AHU_REWARD = (
    "genuine narrative: Allah RAISING him a degree in reward (\"rafa'ahu "
    "Llahu biha darajatan\"), not al-Nasai's \"so-and-so attributed it "
    "marfu'\"")
_NASAI_GENUINE_RAFA_AHU_BROUGHT = (
    "genuine narrative: BRINGING a person before the Prophet (\"fa-rafa'ahu "
    "ila al-nabi\"), not al-Nasai's \"so-and-so attributed it marfu'\"")
_NASAI_GENUINE_RAFA_AHU_CUP = (
    "genuine narrative: RAISING a cup to one's mouth (\"fa-rafa'ahu ila "
    "fihi\"), not al-Nasai's \"so-and-so attributed it marfu'\"")
_NASAI_GENUINE_AWQAFAHU_STOOD = (
    "genuine narrative: he made the pardoned man STAND before the Prophet "
    "(\"hatta awqafahu 'ala al-nabi\", part of the Fath Makka story), not "
    "al-Nasai's \"so-and-so attributed it mawquf\"")
_NASAI_GENUINE_MURSAL_MID_MATN = (
    "genuine narrative: \"مرسل\" sits MID-matn here, describing the isnad "
    "status of only the opening clause of a composite report that "
    "continues for ~600 further characters (the Makhzumiyya-thief story), "
    "not a tail classification tag")
_NASAI_GENUINE_LAM_YASMA_FIRST_PERSON = (
    "genuine narrative, first-person object (\"he did not hear a sound "
    "FROM US\", falam yasma' lana hassan, part of the 'Ali/Fatima "
    "night-prayer story), not al-Nasai's third-person isnad-critique shape "
    "\"so-and-so did not hear it FROM so-and-so\"")

# --- Fix round 2 (R-A3-27): "لم يذكر <name>" family's own genuine exceptions
_NASAI_GENUINE_LAM_YADHKUR_DIALOGUE = (
    "genuine narrative: first-person dialogue (\"fa-in lam yadhkur\", \"and "
    "if he does not mention [Allah]\"), not al-Nasai's third-person "
    "narrator-omission note \"so-and-so did not mention <name/detail>\" -- "
    "no name follows the verb here at all")
_NASAI_GENUINE_LAM_YADHKUR_QURAN = (
    "genuine narrative: a literal Qur'an quotation (6:121, \"wa-la "
    "ta'kulu mimma lam yudhkar ismu Llahi 'alayhi\"), not al-Nasai's "
    "narrator-omission note -- cutting here would truncate the ayah itself")
_NASAI_GENUINE_BARE_RAWA_QADI_DIGRESSION = (
    "the bare \"روى\" arm (added alongside \"رواه\" once the prefix-collision "
    "detector's own probe found hadith:nasai:1777/3881/3894 sharing the "
    "same isnad-comparison shape without the attached object pronoun) finds "
    "a match here too, but 322 characters TOO LATE: the genuine matn is only "
    "the opening clause (\"none of you truly believes until he loves for "
    "his brother what he loves for himself\"); everything from \"qala "
    "al-qadi\" onward is a QADI's own manuscript/isnad-transmission "
    "digression (about a possible scribal error, \"hafs ibn 'Umar\" vs "
    "\"hafs ibn 'Amr\", and an unrelated hadith of Anas), a much larger, "
    "differently-shaped defect this fix round's six named shapes were never "
    "meant to reach -- cutting at the LATE \"روى\" this arm finds would still "
    "leave the entire digression fused onto the scored matn. Left for a "
    "dedicated future fix (its own marker, \"qala al-qadi\"), not patched "
    "around by narrowing this arm.")
_NASAI_GENUINE_LAM_YADHKUR_CONTINUING = (
    "genuine editorial remark, but embedded MID-matn with substantial "
    "further genuine narrative continuing after it (Mu'awiya and 'Ubada's "
    "exchange), not at the tail -- cutting at this occurrence of \"لم "
    "يذكر\" would discard real content, unlike every other member of this "
    "family")

COMMENTARY_NEVER_CUT: dict[str, dict[str, tuple[str, str]]] = {
    "nasai": {
        "hadith:nasai:3047":
            ("993c3a1202f4590f223cddad0911b9267750260fe0447510fa0246245c18bcb7",
             _NASAI_GENUINE_KHALAFAHUM),
        "hadith:nasai:164":
            ("c926e9136bdce839d68395394756a09626a1a20bb1b4c34daea84244bdb7b38b",
             _NASAI_GENUINE_ARSALAHU_MESSENGER),
        "hadith:nasai:938":
            ("db2a3f58b60319b05f47a429d026d93ca01ceb0b174fb43702b2619fb9e68ed7",
             _NASAI_GENUINE_ARSALAHU_PROPHETIC_SPEECH),
        "hadith:nasai:1526":
            ("9add02ca615d5ecc91f52062223f7c2315713df66706dd3c9f4e2ae594eea139",
             _NASAI_GENUINE_ARSALAHU_RAIN),
        "hadith:nasai:4723":
            ("f873debb53e1543a240cfc340883dda01a3a6f86abab7d58c8e12655673bf891",
             _NASAI_GENUINE_ARSALAHU_RELEASED),
        "hadith:nasai:1092":
            ("121967403b477209305e0f6f685593a06f59a3283ecc8894f1d472a2f824b0ce",
             _NASAI_GENUINE_RAFA_AHU_HANDS),
        "hadith:nasai:1139":
            ("72f21fd010b530222d08e7a3247daa75c17d50512cf343da7279fb03b01e6623",
             _NASAI_GENUINE_RAFA_AHU_REWARD),
        "hadith:nasai:3144":
            ("90cd4eb9436f46ef6046b27adb7b7e3384a441a0ebcb3de3db1ba66d8d86654f",
             _NASAI_GENUINE_RAFA_AHU_REWARD),
        "hadith:nasai:4878":
            ("09bec266e1bbfa7fe5d723dc06ab9441f0de58c76e59da5b089fc62a5416f54a",
             _NASAI_GENUINE_RAFA_AHU_BROUGHT),
        "hadith:nasai:4879":
            ("a6833b673a668a633ce92192166eec7cadf06b8ff26ebc0ba4eb17c9ce134a42",
             _NASAI_GENUINE_RAFA_AHU_BROUGHT),
        "hadith:nasai:5694":
            ("d0fa5b49a8c23d182846ecf2064ef25391677f0572674d3fdb16aaf0606d28d3",
             _NASAI_GENUINE_RAFA_AHU_CUP),
        "hadith:nasai:4067":
            ("0ca3aebb899ff72b9948c20bffbd15a4c95f0f99e6ec538c5979bafcef7b42cf",
             _NASAI_GENUINE_AWQAFAHU_STOOD),
        "hadith:nasai:4903":
            ("d4e2cfd6d0e43cf568e016d27ef7082f711a7fde602ca7e3db74053ca2b40983",
             _NASAI_GENUINE_MURSAL_MID_MATN),
        "hadith:nasai:1612":
            ("8003dafed7913961cb6d0900ecef9e8aac61bf6d45eee224795e4c3c9508e88c",
             _NASAI_GENUINE_LAM_YASMA_FIRST_PERSON),
        "hadith:nasai:4081":
            ("2c1709396c3299dc15fbcdac86d93ec6fa5cd5c9072a346c0a5c8150818616b1",
             _NASAI_GENUINE_LAM_YADHKUR_DIALOGUE),
        "hadith:nasai:4437":
            ("a0e501e9149737b2850fd1da70da6ec8679cd1c80c3815e8478eddf7d0167cf0",
             _NASAI_GENUINE_LAM_YADHKUR_QURAN),
        "hadith:nasai:4566":
            ("f0414f38ae4b2521e9028968d4746aea5f49507ab3cf4bbbc46e898c40e28326",
             _NASAI_GENUINE_LAM_YADHKUR_CONTINUING),
        "hadith:nasai:5039":
            ("bb7d1c5bbdcab2c79a95127aa256e4e619f582af6b270a2e972288688a97dac5",
             _NASAI_GENUINE_BARE_RAWA_QADI_DIGRESSION),
    },
}

NEVER_CUT: dict[str, dict[str, tuple[str, str]]] = {
    "bukhari": {
        # "The Prophet passed by a man." The man praying two rak'as after the
        # iqama, and the Prophet's "the dawn prayer in four?", are the addendum.
        "hadith:bukhari:632":
            ("7ec7ade079723e6da94065206461a9c5f530cb9dc4eddcdd37f22f1af4c32908",
             _STUB_OPENER),
        # "The Prophet had a she-camel." Al-'Adba' being outrun, and "God raises
        # nothing of this world without lowering it", are the addendum.
        "hadith:bukhari:6136":
            ("50bdf6cc60a370e998897b39f17dc707af23d4022a52e45aa33a82998d54821f",
             _STUB_OPENER),
        # "So he was at a distance of two bow-lengths or nearer, and revealed to
        # His servant what He revealed" -- Qur'an 53:9-10, verbatim. Ibn Mas'ud's
        # report that the Prophet saw Gabriel with six hundred wings is the
        # addendum, and is the whole of what makes this unit a narration.
        "hadith:bukhari:4575":
            ("86e0300ecb069cd2cd368656cfe256e667974b1ca965e3a7cd61a4b3ea0eab03",
             _QURANIC_PRIMARY),
    },
    # Ibn Majah (Task 15). "... fa-qala rasulu Llahi salla Llahu 'alayhi
    # wa-sallam: hal biha wathan? Qala: la" ("... is there an idol there? He
    # said: no") is immediately followed, with no separating word at all, by
    # a SECOND complete isnad ("... QALA awfi bi-nadhrik HADDATHANA Abu Bakr
    # ibn Abi Shayba ..."), whose own chain looks enough like a real isnad
    # (a run of narrator names ending "'an al-nabi ... * bi-nahwih") that
    # `_split_secondary`'s forward check treats it as one, which under R-A3-18's
    # own rule lets a BARE "qala" with no name in front of it count as the cut
    # point too (`min_name=0`, since the chain behind the verb already settled
    # the question). But this bare "qala" is not a narrator opening a second
    # chain -- it is the Prophet's own reply, "Fulfil your vow", the genuine
    # conclusion of THIS narration's own story (a man's father asks the
    # Prophet about a vow to sacrifice at Buwana; was there an idol there? No;
    # then fulfil it). Cutting here would leave the primary ending on the
    # story's own question-and-answer about the idol, with its actual
    # punchline moved into the addendum alongside an unrelated second chain.
    # Left uncut entirely, per this file's own rule that leaving a bug we
    # already have (an oversized primary) is always preferable to a boundary
    # that discards genuine content: none of `_IBNMAJAH_COMMENTARY`/`_FORMULA`
    # match anywhere in what follows ("Abu Bakr ibn Abi Shayba" is not al-Qattan,
    # not Ibn Majah's own kunya, not his name), so the whole unit stays intact.
    "ibnmajah": {
        "hadith:ibnmajah:2131":
            ("6fb9495add12f726140601f4cf7b6d242e7fbd807aad2928e6eed096deadfcf0",
             "bare qala swallowed a second, unrelated isnad's forward-chain "
             "check: the primary's own genuine punchline (the Prophet's "
             "reply) sat past a bare 'qala' that only looks like a narrator "
             "opening a second chain because a real isnad happens to follow "
             "it"),
    },
}

# --- matns that are editorial apparatus, not quotable text -----------------
#
# Where a narration repeats one already given in full, this edition prints a
# pointer instead of the text: "bi-hadha" ("with this"), "mithlahu" ("the like
# of it"), "nahwahu" ("something like it"). The source marks the isnad/matn
# boundary exactly as it does everywhere else, so the pointer lands in the
# scored text and Sanad answered the everyday Arabic phrase "bi-hadha" with
# EXACT 1.0, Sahih al-Bukhari 1379 -- inventing a hadith citation out of a
# commonplace, which is the precise failure this product exists to prevent.
#
# The list below is an AUDIT, not a heuristic. Length is emphatically not the
# rule: "al-harb khud'a" (war is deceit, 2866) is 10 characters and genuine,
# and Qur'anic records go down to 2. Three scans over all 7,129 units produced
# the candidates -- every matn of 9 characters or less (14 records, all
# apparatus); every matn whose every token is pointer or deferral vocabulary
# at any length (13 records, 11 of them already in the first set); and every
# matn holding a standalone "ha" chain-transfer mark (1 record, 237). Every
# matn up to 24 characters (92 records) and every matn containing a deferral
# phrase at any length (32 records) was then read in the source and
# classified. 17 are listed here; everything else was ruled genuine, record by
# record, in .superpowers/sdd/2026-09-22-hadith-corpus/task-4-fix-3-report.md.
#
# The value is a (sha256-of-matn, reason) pair. Pinning the text is what makes
# the entry an audit rather than a standing verdict on a number: the
# classification was made by reading one specific string, and if a future
# edition prints something else under that number the build stops and the
# record gets read again.

_POINTER = ("editorial back-reference: the matn is a pointer to a narration "
            "printed in full elsewhere, not a text")
_DEFERRAL = ("editorial abridgement: the matn breaks off and defers to the "
             "full narration printed elsewhere")
_INCIPIT = ("editorial abridgement: the edition prints the opening word in "
            "place of the narration")
_TAHWIL = ("chain-transfer fragment: the matn is a subordinate clause ending "
           "at the tahwil mark, the narration itself following in the addendum")

# Muslim-specific reasons (Task 11). Sahih Muslim's editorial convention groups
# parallel chains under a repeated back-reference far more densely than
# Bukhari's: reading every matn of 30 characters or fewer (403 distinct
# strings across 902 records) found 240 distinct pointer/deferral/attribution
# strings covering 726 records -- roughly 40x Bukhari's 17-entry list by
# count, though the SAME three reasons (_POINTER, _DEFERRAL, and the two new
# ones below) cover it; nothing Muslim-specific needed inventing except these
# two. Every one of the 240 strings was read for meaning, not matched by a
# length or frequency rule: genuine short hadith at this length (e.g. "al-harb
# khud'a", "al-'ayn haqq", the Prophet's two-word "da'hu" reply at 274) sit in
# the SAME length band as the apparatus and are deliberately left off this
# list. The 31-60 character band was scanned for the same vocabulary as a
# spot check (459 further distinct candidate strings, overwhelmingly the same
# small set of templates with a different narrator's name substituted) but was
# NOT individually read and is NOT included here -- see the task-11 report for
# the residual-risk note this leaves for a follow-up pass.
_ATTRIBUTION_NOTE = ("attribution note: the matn answers a question about "
                      "whether the narration is raised to the Prophet "
                      "(marfu') rather than reporting his words")
_TRUNCATED_STUB = ("truncated narrative frame: the reported speech is the "
                    "punchline of an earlier, separately-numbered unit and "
                    "the source ends the record here, with nothing following "
                    "to reattach")

# Abu Dawud-specific reasons (Task 12). Three new phenomena not seen in
# Bukhari or Muslim, each individually reasoned, not pattern-matched:
_LEXICAL_GLOSS = ("lexical gloss: a narrator's explanation of a word's "
                   "meaning used in an earlier, separately-numbered hadith, "
                   "not a report of the Prophet's own words")
_ISNAD_COMMENT = ("isnad-quality remark: one narrator's comparison of two "
                   "transmitters' reliability or memory, not a report of "
                   "the Prophet's words")
_EDITORIAL_DISCUSSION = ("editorial discussion: the compiler's own numbered "
                          "remark about how a hadith's isnad or wording was "
                          "transmitted differently by other narrators, not "
                          "itself a narration")
_QURANIC_QUOTE = ("wholly Qur'anic matn: the unit reports a Qur'an-reading "
                   "(qira'a) variant, but the entire printed matn is nothing "
                   "but the ayah's own wording, with no narrative content of "
                   "its own and no addendum to reattach")

# Nasai-specific reasons (Task 14). Al-Mujtaba's own pointer convention
# ("nahwahu"/"mithlahu"/"mursal"/etc.) is the same PHENOMENON already seen in
# Bukhari/Muslim/Abu Dawud, reusing _POINTER for the plain cases, but three
# further shapes turned up under hand review of every candidate (54 read,
# in context, isnad and addenda included; 53 confirmed unscorable, one --
# hadith:nasai:4129 "la tarji'u ba'di kuffaran" -- rejected from this list
# because it is a genuine, complete, independently-quotable imperative with
# only a trailing "mursal" classification tag, unlike the rest of this group):
_CHAIN_LEAK = ("chain-continuation phrase: describes who narrated to whom "
               "(a fragment of the isnad itself), not a report of the "
               "Prophet's words, with no independent content of its own")
_CLASSIFICATION_TAG = ("bare isnad-classification term (e.g. \"mursal\", "
                        "\"mawquf\"), not narrative content")
_TRUNCATED_OPENING = ("truncated opening clause missing the sentence's "
                       "predicate or ruling -- compare the fuller parallel "
                       "matn printed elsewhere in this collection -- with no "
                       "independent quotable meaning on its own")

# A2 round 4 (Task 16). Two shapes that the position-independent residue sweep
# (find_pure_pointers) structurally cannot reach, surfaced by an independent
# editorial-omission/comparison sweep and hand-audited exhaustively (see
# task-16-A2round4-audit.md): the sweep's `غير`/`الا`/`قال`/`زاد` delivery
# guard -- there to protect genuine `وزاد Y` additions -- also hides apparatus
# records that use `غير أنه لم يذكر` / `الا قوله X فانه لم يذكره` / a bare
# `لم يذكر X` with no reference anchor. These deliver NO narration: they only
# state what a DIFFERENT narration omits, or defer a bare ruling verb.
_OMISSION_NOTE = ("omission note: records only what another narration LACKS "
                   "(\"lam yadhkur X\" / \"laysa fi hadith X\" / \"illa "
                   "qawlahu X fa-innahu lam yadhkurhu\"), delivering no "
                   "self-contained narration of its own")
_BARE_RULING = ("bare ruling verb (naha / amara) with no object, immediately "
                 "deferring to another narration for the content -- the ruling "
                 "itself is never stated here")

# A2 round 5 (Task 16). The vocabulary-free content-mass net (openiti.content_mass)
# surfaced a class the round-4 sweep structurally could not: a pointer whose
# entire matn is a speech FRAME ("'an al-nabi [saw]", "sami'tu rasula llah
# yaqul fa-dhakara ...", "qala sami'tu NAME") with nothing delivered after it,
# or an isnad/name VARIATION note ("ghayra annahu qala <NARRATOR-NAME>"). The
# round-4 `find_pure_pointers` EXCLUDED these because they carry a qala/yaqul
# token (its `_PP_DELIVERS` guard); content_mass keys on no marker, counts what
# is LEFT after the frame + the name it introduces, and finds nothing.
_FRAME_ONLY = ("speech frame with no matn after it (\"'an al-nabi [saw]\" / "
               "\"sami'tu rasula llah ... yaqul\" / \"qala sami'tu NAME\"): the "
               "frame names WHO spoke or defers to another narration and quotes "
               "nothing, delivering no self-contained matn of its own")
_ISNAD_VARIATION = ("isnad/name-variation note (\"ghayra annahu qala "
                    "<NARRATOR-NAME>\" / \"qala <NAME> wa-lam yashukk\"): records "
                    "only that a parallel chain named a narrator differently, a "
                    "WHO not a WHAT, delivering no matn clause of its own")

UNSCORABLE: dict[str, dict[str, tuple[str, str]]] = {
    "bukhari": {
        # Pointer only -- "bi-dhalika", "bi-hadha", "mithlahu", "nahwahu",
        # "bi-nahwihi". Nothing of the narration is present.
        "hadith:bukhari:127":
            ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        "hadith:bukhari:394":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        "hadith:bukhari:549":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:bukhari:557":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        "hadith:bukhari:1379":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        "hadith:bukhari:2483":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:bukhari:3457":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:bukhari:3750":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:bukhari:4540":
            ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        "hadith:bukhari:5454":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:bukhari:5837":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        # Breaks off mid-sentence into a deferral. 335 is "I witnessed Umar, and
        # Ammar said to him --" with no reported speech at all; 3801 and 3957 are
        # deferral phrases end to end ("and he mentioned the hadith of the ifk",
        # "the story was mentioned").
        "hadith:bukhari:335":
            ("6ee90378f5b44749f8eceb8ab8df58e6d111a3aff1b347170e2618cc6688002b", _DEFERRAL),
        "hadith:bukhari:3801":
            ("4b9d1fad31b2db451efc1b8da5126228579e4b4c502d598146df5dd664d6a616", _DEFERRAL),
        "hadith:bukhari:3957":
            ("ce978d7770d5c1c95852945608a5bfe28bfa168ad4fd374541dba93f42cfc4cf", _DEFERRAL),
        # --- Task 16 A2: non-length-capped pointer/deferral sweep. ---------
        # hadith:bukhari:587 "مثله إلى قوله وأشهد أن محمدا رسول الله" -- "the
        # like of it, up to his saying '... and I bear witness that Muhammad
        # is the Messenger of Allah'". A partial-quote deferral: it names WHERE
        # the abridged version stops, delivering no narration of its own. At 38
        # characters it escaped Task 4's 30-char audit floor purely because the
        # endpoint phrase pads its length -- the exact hazard
        # [[sanad-editorial-pointer-false-exact]] records. The seed case the
        # Task 16 brief named for this sweep; the only Bukhari record it found.
        "hadith:bukhari:587":
            ("3590c48e6494062171e333b6fec50f92e6360312507368bc8df38df357c54352", _DEFERRAL),
        # One word standing for the whole narration, the part marker "\ 1 \"
        # following it immediately in the source.
        "hadith:bukhari:1915":
            ("eef9aff2b8eb9c9b7bf8b1dad3573aafc7ebd62765e1eaa436d27b43d5ec3020", _INCIPIT),
        "hadith:bukhari:3777":
            ("e8f7569bb6d6c846a67e3d7a7d8235e04ae9b9340ffd4694f0de8028de0c1295", _INCIPIT),
        # "while the Messenger of God was prostrating -- ha" : a "bayna" clause
        # with no main clause, ending on the chain-transfer mark. The narration it
        # introduces is the second chain, which is in this record's addendum.
        "hadith:bukhari:237":
            ("990234ea283424988b4c8932d69ec68bd0d99f4d0d635dab14cb919338bce0f3", _TAHWIL),
        # --- A2 round 3 (Task 16): position-independent whole-string
        # sweep. find_pure_pointers() flags scorable records whose entire
        # matn reduces to back-reference/chain-meta/deferral/omission
        # scaffold with no quotable content, regardless of token position.
        # Every id below was hand-read in context (isnad + addendum) and
        # carries no Prophetic/narrative clause of its own.
        'hadith:bukhari:3746': ("0528f05488144b164b16f0f7bf372b436d5c09c29c0f2512697c8a1a9533c4cd", _POINTER),
    },
    "muslim": {
        # See the module-level comment above _ATTRIBUTION_NOTE/_TRUNCATED_STUB
        # for the scan methodology and scope. sha256 values were computed
        # directly from parse_openiti(raw, collection="muslim")'s matn_ar for
        # each id (never hand-typed), the same value build.py stores as
        # text_ar before materialize hashes it -- these records have no
        # addenda, so text_ar == matn_ar.
        #
        # "rafa'ahu" (626-2): Sufyan is asked whether the narration is raised
        # to the Prophet; the matn is his one-word answer "he raised it",
        # not a report of anything the Prophet said.
        # "marra bi-rajulin min al-ansari ya'izu akhahu" (36-2): a second
        # chain for unit 36 reports only that the Prophet "passed by a man of
        # the Ansar admonishing his brother" -- the actual saying ("shyness is
        # part of faith") is unit 36's own primary matn, not repeated here,
        # and the source starts a new numbered unit immediately after. There
        # is no addendum to reattach, so this is _TRUNCATED_STUB, not a
        # NEVER_CUT candidate.
        # "ma sha'a Allah" (719-2): "... with this chain, like it, and Yazid
        # said [just the words] 'ma sha'a Allah'" -- a narrator's wording note
        # against the fuller "wa-yazidu ma sha'a Allah" ("and adds what God
        # wills") given at 719. Also, coincidentally, verbatim Qur'anic
        # phrasing (18:39): this is the record that tripped
        # materialize._reject_wholly_quranic_representations before this
        # entry existed. Listed as _POINTER on its own merits -- the wording
        # note, not the Qur'an collision, is why it is not independently
        # quotable -- with the collision noted here since it is what first
        # surfaced the record.
        # 'بهذا الإسناد مثله' (108 records)
        'hadith:muslim:90-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:120-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:276-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:307-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:381-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:442-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:445-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:447-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:463-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:596-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:656-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:672-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:673-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:707-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:710-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:715-23': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:719-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:723-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:773-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:821-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:879-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:979-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1066-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1085-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1106-10': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1190-9': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1223-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1317-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1340-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1352-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1353-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1374-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1408-10': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1446-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1460-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1539-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1542-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1543-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1548-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1554-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1556-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1568-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1575-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1582-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1588-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1599-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1622-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1635-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1640-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1643-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1672-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1676-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1684-6': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1690-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1691-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1696-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1706-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1707-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1713-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1767-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1839-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1842-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1857-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1872-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1890-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1896-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1933-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1934-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1957-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1960-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1969-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1979-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1979-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1987-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:1988-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2003-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2064-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2068-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2069-10': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2076-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2093-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2100-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2119-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2121-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2169-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2177-5': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2191-7': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2195-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2199-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2210-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2321-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2344-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2395-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2398-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2444-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2444-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2447-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2486-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2549-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2597-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2602-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2623-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2741-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2798-4': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2877-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2947-3': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:2959-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        'hadith:muslim:3022-2': ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        # 'بمثله' (100 records)
        'hadith:muslim:52-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:55-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:55-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:64-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:66': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:93-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:169-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:224-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:237-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:240-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:274-10': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:278-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:387-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:410-5': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:414-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:422-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:506-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:515-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:522-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:523-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:568-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:578-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:597-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:672-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:713-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:721-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:732-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:799-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:799-6': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:844-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:850-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:851-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:852-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:852-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:982-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:991-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1047-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1092-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1098-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1163-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1164-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1164-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1336-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1345-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1378-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1386-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1395-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1395-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1408-6': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1438-12': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1452-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1469-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1477-6': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1493-5': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1511-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1522-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1534-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1536-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1543-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1562-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1564-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1568-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1575-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1576-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1625-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1673-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1710-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1828-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1860-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1874-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1918-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1989-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:1995-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2032-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2060-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2110-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2124-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2226-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2242-7': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2302-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2309-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2318-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2369-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2411-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2425-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2433-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2609-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2616-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2624-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2640-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2672-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2672-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2684-4': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2747-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2823': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2914-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2916-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2991-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:2998-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        'hadith:muslim:3002-3': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        # 'بهذا الإسناد' (87 records)
        'hadith:muslim:176-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:190-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:200-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:388-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:440-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:453-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:546-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:589-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:603-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:627-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:660-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:674-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:715-25': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:737-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:807-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:819-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:848-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:878-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:916-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:921-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:962-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:962-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1008-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1096-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1097-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1153-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1162-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1198-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1283-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1333-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1394-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1395-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1412-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1412-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1433-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1494-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1512-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1586-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1666-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1691-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1714-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1749-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1757-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1802-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1858-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1876-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1892-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1893-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1929-7': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1941-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1942-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1956-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:1975-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2055-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2075-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2089-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2107-11': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2113-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2121-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2168-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2170-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2184-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2250-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2263-8': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2265-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2341-6': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2353-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2412-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2487-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2506-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2509-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2522-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2568-5': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2572-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2610-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2681-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2684-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2728-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2734-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2737-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2753-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2758-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2812-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2945-2': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:2987-4': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:3019-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        'hadith:muslim:3030-3': ("1f875708ac1573793db825379318cb8615e4977e010a73401c1456162cc83c02", _POINTER),
        # 'بهذا الإسناد نحوه' (72 records)
        'hadith:muslim:389-7': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:412-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:430-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:432-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:436-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:537-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:538-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:539-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:663-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:688-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:694-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:695-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:884-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:884-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:940-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:971-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:989-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1024-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1053-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1073-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1082-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1290-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1341-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1376-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1456-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1456-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1474-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1476-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1495-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1504-9': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1525-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1542-6': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1543-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1547-14': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1563-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1587-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1591-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1609-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1617-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1628-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1674-4': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1698': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1760-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1812-8': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1840-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1844-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1878-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1938-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1954-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1954-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:1977-6': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2064-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2170-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2221-3': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2284-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2308-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2336-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2420-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2438-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2449-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2567-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2611-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2669-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2704-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2759-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2776-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2876-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2885-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2891-5': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2907-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2913-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        'hadith:muslim:2948-2': ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        # 'مثله' (23 records)
        'hadith:muslim:358-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:380-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:578-5': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:588-5': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:588-6': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:743-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:784-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:808-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:808-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:933-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:933-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1207-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1211-17': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1350-3': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1511-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1511-4': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1579-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:1961-6': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2172-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2485-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2683-2': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2737-4': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        'hadith:muslim:2817': ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        # 'بنحوه' (13 records)
        'hadith:muslim:207-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:559-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:651-4': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:677-9': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:1047-3': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2078-5': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2191-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2323-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2586-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2601-4': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2639-7': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2647-4': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        'hadith:muslim:2775-2': ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        # 'في هذا الإسناد بمثله' (12 records)
        'hadith:muslim:631-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1001-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1129-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1132-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1157-4': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1161-5': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1201-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:1916-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2234-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2389-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2920-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        'hadith:muslim:2938-2': ("a8eb81eafb84545f371475446041707d4d15f72500d3204cb72f67d75edf99eb", _POINTER),
        # 'بنحو حديثهم' (8 records)
        'hadith:muslim:8-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:288-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:1669-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:1831-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2125-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2218-11': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2218-12': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        'hadith:muslim:2492-4': ("6e19759783a20be509c2b622cecb43ef25d0c5b280613b20a7b10b70b2776341", _POINTER),
        # 'بهذا الحديث' (8 records)
        'hadith:muslim:132-2': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:487-2': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:1017-8': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:1148-3': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:1735-2': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:2036-3': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:2639-8': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        'hadith:muslim:2688-4': ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        # 'في هذا الإسناد' (8 records)
        'hadith:muslim:1002-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:1441-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:1997-15': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2053-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2404-3': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2514-3': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2702-3': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        'hadith:muslim:2719-2': ("a1e333f6a2665d85a3c386287842789faf88393629c7d89e7b0280e7ee01dbd6", _POINTER),
        # 'نحو حديثهم' (7 records)
        'hadith:muslim:1029-3': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:1540-4': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:1550-3': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:1835-5': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:2243-4': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:2471-4': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        'hadith:muslim:2652-6': ("6ba9b3b97e1e30ebf5cbb9264169547fa096dbb69ab1b874d61771967691e4b3", _POINTER),
        # 'نحوه' (7 records)
        'hadith:muslim:874-2': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:895-3': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:1851-2': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2078-6': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2511-2': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2586-5': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        'hadith:muslim:2704-4': ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        # 'بمثل حديثهم' (5 records)
        'hadith:muslim:1833-3': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:1835-6': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:2062-2': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:2085-4': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        'hadith:muslim:2951-4': ("83fa614b5e3b1c52541bb77efe3be30f5b921e7d992fb37653dd082ab4f403cf", _POINTER),
        # 'بمثل حديث مالك' (4 records)
        'hadith:muslim:1349-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        'hadith:muslim:1621-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        'hadith:muslim:1664-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        'hadith:muslim:2559-2': ("77cce206e9cf9e225e7d50a987c2b89acd7ddc1b4cf6e2c7d809a13a0fbdd2f3", _POINTER),
        # 'مثل ذلك' (4 records)
        'hadith:muslim:1929-9': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        'hadith:muslim:2264-2': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        'hadith:muslim:2480-3': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        'hadith:muslim:2801': ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        # 'بإسناد يونس نحو حديثه' (3 records)
        'hadith:muslim:2218-7': ("b6a7660b96b1fea3e266415b4f7c6bd99978de4e581e6c09747065f64b3d0d94", _POINTER),
        'hadith:muslim:2391-2': ("b6a7660b96b1fea3e266415b4f7c6bd99978de4e581e6c09747065f64b3d0d94", _POINTER),
        'hadith:muslim:2392-2': ("b6a7660b96b1fea3e266415b4f7c6bd99978de4e581e6c09747065f64b3d0d94", _POINTER),
        # 'بذلك' (3 records)
        'hadith:muslim:356-2': ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        'hadith:muslim:2120-4': ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        'hadith:muslim:2242-3': ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        # 'بمثل هذا الحديث' (3 records)
        'hadith:muslim:13-2': ("fae02d64b5cfdd6882f14790ed860fb9eab0fc48fab0e2ece2d2db8bf29ba957", _POINTER),
        'hadith:muslim:1988-6': ("fae02d64b5cfdd6882f14790ed860fb9eab0fc48fab0e2ece2d2db8bf29ba957", _POINTER),
        'hadith:muslim:2372-3': ("fae02d64b5cfdd6882f14790ed860fb9eab0fc48fab0e2ece2d2db8bf29ba957", _POINTER),
        # 'بمثله بسم الله الرحمن الرحيم' (3 records)
        'hadith:muslim:900-2': ("7ef13e9272e4017b6ad7f5c37f8a48959a514678ee0290e347680879d5889e69", _POINTER),
        'hadith:muslim:1710-5': ("7ef13e9272e4017b6ad7f5c37f8a48959a514678ee0290e347680879d5889e69", _POINTER),
        'hadith:muslim:2064-5': ("7ef13e9272e4017b6ad7f5c37f8a48959a514678ee0290e347680879d5889e69", _POINTER),
        # 'بمثله سواء' (3 records)
        'hadith:muslim:615-2': ("52c3ae71011b05e9c595509614df1362d7ae33ac695712c5f325aa598343367a", _POINTER),
        'hadith:muslim:1835-4': ("52c3ae71011b05e9c595509614df1362d7ae33ac695712c5f325aa598343367a", _POINTER),
        'hadith:muslim:1883-2': ("52c3ae71011b05e9c595509614df1362d7ae33ac695712c5f325aa598343367a", _POINTER),
        # 'بمثله في هذا الإسناد' (3 records)
        'hadith:muslim:1126-2': ("134a6997d373b52fb12f8d40572d420befa9d50614ec5158fed3f25f95ab3183", _POINTER),
        'hadith:muslim:1684-2': ("134a6997d373b52fb12f8d40572d420befa9d50614ec5158fed3f25f95ab3183", _POINTER),
        'hadith:muslim:1943-4': ("134a6997d373b52fb12f8d40572d420befa9d50614ec5158fed3f25f95ab3183", _POINTER),
        # 'بهذا' (3 records)
        'hadith:muslim:1731-4': ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        'hadith:muslim:1807-2': ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        'hadith:muslim:2951-3': ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        # 'بهذا الإسناد سواء' (3 records)
        'hadith:muslim:942-2': ("d93d334876ddddf4049faad3d50377a6190130cf210197862e4975426d1a425e", _POINTER),
        'hadith:muslim:1449-2': ("d93d334876ddddf4049faad3d50377a6190130cf210197862e4975426d1a425e", _POINTER),
        'hadith:muslim:2373-2': ("d93d334876ddddf4049faad3d50377a6190130cf210197862e4975426d1a425e", _POINTER),
        # 'بمثل حديث أبي عوانة' (2 records)
        'hadith:muslim:1048-2': ("cf614dc38194d0f7f532b36b6050a8e5d1ee3f41fe7f93e868703526d8062488", _POINTER),
        'hadith:muslim:1717-2': ("cf614dc38194d0f7f532b36b6050a8e5d1ee3f41fe7f93e868703526d8062488", _POINTER),
        # 'بمثل حديث الليث' (2 records)
        'hadith:muslim:95-3': ("bd3d511c717ed3d79b2d9f3a84e264b1fc33b07581b6e27992225ea8ed20ad1a", _POINTER),
        'hadith:muslim:1970-2': ("bd3d511c717ed3d79b2d9f3a84e264b1fc33b07581b6e27992225ea8ed20ad1a", _POINTER),
        # 'بمثل حديث بن جريج' (2 records)
        'hadith:muslim:1670-3': ("24b422c81e27c297dabb5561411a4b911fd5ee98cef7a88e1cfa09c7cec7aa70", _POINTER),
        'hadith:muslim:2059-2': ("24b422c81e27c297dabb5561411a4b911fd5ee98cef7a88e1cfa09c7cec7aa70", _POINTER),
        # 'بمثل حديث جرير' (2 records)
        'hadith:muslim:1652-4': ("7350102d9e6ecb3748d5e68b246b27d61f87d8f92e8f38266df738f8997e521a", _POINTER),
        'hadith:muslim:2069-6': ("7350102d9e6ecb3748d5e68b246b27d61f87d8f92e8f38266df738f8997e521a", _POINTER),
        # 'بمثل حديث عبيد الله' (2 records)
        'hadith:muslim:2003-8': ("4d15c35d235ac6b6ad9b171d74af5e9ab1d53e947cd6176620a640113f41641b", _POINTER),
        'hadith:muslim:2299-4': ("4d15c35d235ac6b6ad9b171d74af5e9ab1d53e947cd6176620a640113f41641b", _POINTER),
        # 'بمثل حديث معاذ' (2 records)
        'hadith:muslim:1226-4': ("eab6b9519c8be0bbd66b98299f687d1edc697f647ba78aa64870d6c5822c5151", _POINTER),
        'hadith:muslim:1944-2': ("eab6b9519c8be0bbd66b98299f687d1edc697f647ba78aa64870d6c5822c5151", _POINTER),
        # 'بمثل معناه' (2 records)
        'hadith:muslim:649-7': ("f7714310c99793eb578a41a4f2530c07a1b78584e5c34c73eb163176612b4f82", _POINTER),
        'hadith:muslim:2242-2': ("f7714310c99793eb578a41a4f2530c07a1b78584e5c34c73eb163176612b4f82", _POINTER),
        # 'بمعنى حديث شيبان' (2 records)
        'hadith:muslim:2802-2': ("786c489e40a54d570f545b3927db6f627a5a105d97c4cc60b352038dded82020", _POINTER),
        'hadith:muslim:2848-2': ("786c489e40a54d570f545b3927db6f627a5a105d97c4cc60b352038dded82020", _POINTER),
        # 'بنحو هذا' (2 records)
        'hadith:muslim:649-12': ("2575864e26a32ba81792fb024f5b84b18de2fbf84d95d70788775c1e8f35f76a", _POINTER),
        'hadith:muslim:2088-2': ("2575864e26a32ba81792fb024f5b84b18de2fbf84d95d70788775c1e8f35f76a", _POINTER),
        # 'بهذا الإسناد بمثله' (2 records)
        'hadith:muslim:1430-2': ("4fbc5934fec81451caf8980249343b03952d4fcf24a82e372972e1b10ec696ec", _POINTER),
        'hadith:muslim:1833-2': ("4fbc5934fec81451caf8980249343b03952d4fcf24a82e372972e1b10ec696ec", _POINTER),
        # 'بهذا الإسناد مثله سواء' (2 records)
        'hadith:muslim:1337-3': ("2297df7ae3c09b93e16a83fb920f561f608908f498034ff3b0880534fb65f742", _POINTER),
        'hadith:muslim:1468-2': ("2297df7ae3c09b93e16a83fb920f561f608908f498034ff3b0880534fb65f742", _POINTER),
        # 'بهذا الإسناد نحو حديث جرير' (2 records)
        'hadith:muslim:598-2': ("5ae4d5b7e2bc76092ed5f729f23de8d411e46e5653c6d2a2d4de4c9d1554d7c1", _POINTER),
        'hadith:muslim:1639-4': ("5ae4d5b7e2bc76092ed5f729f23de8d411e46e5653c6d2a2d4de4c9d1554d7c1", _POINTER),
        # 'بهذا الإسناد نحو حديثهم' (2 records)
        'hadith:muslim:1542-8': ("b265fb4c787886fc74ded06df550146bfc3f6192fa65b155b52908a238b9dc04", _POINTER),
        'hadith:muslim:1622-3': ("b265fb4c787886fc74ded06df550146bfc3f6192fa65b155b52908a238b9dc04", _POINTER),
        # 'بهذا المعنى' (2 records)
        'hadith:muslim:1829-5': ("249aa60f3ed7e1e671c834449b283328428d364b68e7b3a664d0ead31d270082", _POINTER),
        'hadith:muslim:2098-2': ("249aa60f3ed7e1e671c834449b283328428d364b68e7b3a664d0ead31d270082", _POINTER),
        # 'فذكر مثله' (2 records)
        'hadith:muslim:1038-2': ("3ba4c7bb513d553cc6c2786b91ea02d71d14d50c44872354f8d220ae4a2391b1", _DEFERRAL),
        'hadith:muslim:1612-2': ("3ba4c7bb513d553cc6c2786b91ea02d71d14d50c44872354f8d220ae4a2391b1", _DEFERRAL),
        # 'في هذا الإسناد مثله' (2 records)
        'hadith:muslim:567-2': ("d2fed8725e4642ec46fd6d06a07d3b4d765822afec8f02dce69a410a58599971", _POINTER),
        'hadith:muslim:1709-6': ("d2fed8725e4642ec46fd6d06a07d3b4d765822afec8f02dce69a410a58599971", _POINTER),
        # 'في هذا الإسناد نحوه' (2 records)
        'hadith:muslim:1221-2': ("4eee7b48727853faddb6bc4c784a84bffaf51c679233b4296b98005b0112bb5d", _POINTER),
        'hadith:muslim:2700-2': ("4eee7b48727853faddb6bc4c784a84bffaf51c679233b4296b98005b0112bb5d", _POINTER),
        # 'مثله سواء' (2 records)
        'hadith:muslim:26-2': ("1689c6318ec9c6db4fbe987b4477218c0855c4fbae2c69e357bf7a5909856513", _POINTER),
        'hadith:muslim:2311-2': ("1689c6318ec9c6db4fbe987b4477218c0855c4fbae2c69e357bf7a5909856513", _POINTER),
        # 'نحو حديثه' (2 records)
        'hadith:muslim:2380-4': ("8e0910fb17972104067535af03d80a243856b409f4bf667a53906cd3c60199f5", _POINTER),
        'hadith:muslim:2662-3': ("8e0910fb17972104067535af03d80a243856b409f4bf667a53906cd3c60199f5", _POINTER),
        # 'إذا دخل رمضان بمثله' (1 record)
        'hadith:muslim:1079-3': ("37360a7067bbf309b4461e32b133d41517afa0d68f7efd6a223096d82d7316b8", _POINTER),
        # 'اقرؤوا القرآن بمثل حديثهما' (1 record)
        'hadith:muslim:2667-3': ("019c1733410f7212bd0c5d5923f9beeea77a080d532b3dd36f95a9d77f5cdb1b", _POINTER),
        # 'الإسناد وفي حديثه' (1 record)
        'hadith:muslim:1915-3': ("d1b3525b48073595d854834512726a3f502ac233795eeae7d9cb5e2f61dc2246", _POINTER),
        # 'الجنة والنار فذكر نحو حديثهما' (1 record)
        'hadith:muslim:2750-3': ("96321180729669565b57749a077ac24fb5d22e66e4f0e61abc25e04997256cb8", _POINTER),
        # 'الحديث نحوه' (1 record)
        'hadith:muslim:2669-3': ("680a1c893dd7ee569cbece0d5ec0aa5ec31965256c784be922b7b2e0dd504af5", _POINTER),
        # 'بإسناد الليث ومعنى حديثه' (1 record)
        'hadith:muslim:1638-2': ("bf470add99bea4d3e36f0bef97fe213f414a6eff4f9023b1ba212f2def7c1fb2", _POINTER),
        # 'بإسناد بن جريج نحو حديثه' (1 record)
        'hadith:muslim:2218-5': ("a04fce3aa5def39fd08a5b798e5058f7e4564f5726b4616ef28608e39bdda17c", _POINTER),
        # 'بإسناد جرير مثل حديثه' (1 record)
        'hadith:muslim:2570-2': ("186634dce29b22f39167ce68b76efde4f73292a03747eb1cab422a2f5196a1a7", _POINTER),
        # 'بإسناد جرير نحو حديثه' (1 record)
        'hadith:muslim:2356-2': ("ecf135060c57e426e6cd8971a7125154bcc6c72de661f60a75991442932ccf88", _POINTER),
        # 'بإسناد حديث الليث مثل روايته' (1 record)
        'hadith:muslim:1490-2': ("bc7037fa6e4c40e16f4cefd86b12614a566223de6343ce2521399693ef3c8fe1", _POINTER),
        # 'بإسناد سفيان' (1 record)
        'hadith:muslim:2020-2': ("1c017e64889ce9d0a99ac405cce3ced6d03c48f45d2bc0629804b7d526c241ca", _POINTER),
        # 'بإسناد سفيان ومعنى حديثه' (1 record)
        'hadith:muslim:2918-2': ("ff6c8ba3472db436b2e72f7bbc10c415482faf2d9552295739cb401d8c176f75", _POINTER),
        # 'بإسناد معمر كمثل حديثه' (1 record)
        'hadith:muslim:2537-2': ("4fb69bea4e4c315792773b7127156a694e8ec0e4123f89e1263a783ed79dbb4a", _POINTER),
        # 'بإسناد يونس عن الزهري سواء' (1 record)
        'hadith:muslim:2769-2': ("6db5c046e31ee155cf52a5f2e8e86c009eced77aa5f9c17b5e29f2d6e2310dad", _POINTER),
        # 'بإسناد يونس كنحو حديثه' (1 record)
        'hadith:muslim:510-2': ("2fd6c2263882a08d9866f8d937da4828cec33a53be467e649f4a7c042621d259", _POINTER),
        # 'بإسناد يونس ومعنى حديثه' (1 record)
        'hadith:muslim:1027-2': ("e0f9b3c0e593138fce6ded64c2d99ef6a7fa21d98a5e457d67f0332be0d33034", _POINTER),
        # 'بالإسنادين جميعا مثل حديث عقيل' (1 record)
        'hadith:muslim:2349-2': ("fec7f308b4d910a9f35f8731ab9e629f2b6d0842322217e3f55919a2a11542b4", _POINTER),
        # 'بالإسنادين جميعا مثله' (1 record)
        'hadith:muslim:2538-4': ("6ab6a40959f43b26fe2a4289f0d3c4ed24a26e0cb0445c41dc4ea5e682e43ab1", _POINTER),
        # 'بقصته' (1 record)
        'hadith:muslim:1480-15': ("0975e075433293873890ec59ae4134515adafcd5852ea8c75fa91cd5c6f0e76d", _POINTER),
        # 'بمثل حديث أبي الزناد سواء' (1 record)
        'hadith:muslim:2963-2': ("d30af37036f77ee1c532d73c7d7d568819479c3e874e95d0e91d26994d12345b", _POINTER),
        # 'بمثل حديث إسماعيل' (1 record)
        'hadith:muslim:1039-3': ("65123ede99e74b21edd4e606a22ac73e550e50de3cffde20ac8c4d7d7373bba9", _POINTER),
        # 'بمثل حديث إسماعيل عن أبي حيان' (1 record)
        'hadith:muslim:1831-2': ("46776ded02cc999284ce41e0b3f8e903c4d38773bfaf64d5c4c3f73ea9d4801d", _POINTER),
        # 'بمثل حديث الأعمش' (1 record)
        'hadith:muslim:2319-2': ("26628feb84a11519f023b9c64a2130f4f0cbf20bbfec204bd66f709e27f4081b", _POINTER),
        # 'بمثل حديث الربيع' (1 record)
        'hadith:muslim:216-2': ("7640805e376a9c0a4c91600b66e4fb35218dfb7f91c8b27b79e0d849dab86b9b", _POINTER),
        # 'بمثل حديث بشر وعبد العزيز' (1 record)
        'hadith:muslim:2995-4': ("37cc22647fe68227db501f4e86aac0d80d96dca2b708a524767485a6656b2f7b", _POINTER),
        # 'بمثل حديث بن علية' (1 record)
        'hadith:muslim:2834-2': ("996ab11d670f55ebee2a8d9f2dde42945f7b4474675884ccbc4deebd4d6e49e5", _POINTER),
        # 'بمثل حديث بن علية وإسناده' (1 record)
        'hadith:muslim:2427-2': ("6d3666093c1ee350c20a794ce303e422ed6c833f3abea5f5c1595680dde484fa", _POINTER),
        # 'بمثل حديث بن علية وحماد' (1 record)
        'hadith:muslim:1668-3': ("b6a6d89e1f36d84c297eb296fb27bce476f195dd9b1be5788cc1d360523054fb", _POINTER),
        # 'بمثل حديث بن عيينة' (1 record)
        'hadith:muslim:979-3': ("83fa7e937615467d19db232f71bf049befbd5112f741e38e754d330e83245f11", _POINTER),
        # 'بمثل حديث بن نمير' (1 record)
        'hadith:muslim:715-12': ("3ec9b37f3117ea087fdee181147f1b534cf709a7cbfd529d280ebaabb8af2fe7", _POINTER),
        # 'بمثل حديث بن نمير عن عبيد الله' (1 record)
        'hadith:muslim:1517-2': ("a8ad86d20574068ae1b72272258db54624eddf27ba86cf0d5498857826a1bf52", _POINTER),
        # 'بمثل حديث بن نمير وزهير' (1 record)
        'hadith:muslim:2394-2': ("b0fa44b372595fcb73067cb736268ccbca7a09877c301af323b4ca97eb0b876f", _POINTER),
        # 'بمثل حديث زهير عن هشيم' (1 record)
        'hadith:muslim:1480-10': ("7064639f468da76e84b70a22cdb8ebcf59c77295f49aea3dae067f00bcc63158", _POINTER),
        # 'بمثل حديث شعبة عن واقد' (1 record)
        'hadith:muslim:66-3': ("ee933fe60bce594dac4d9b36a38da9930daaa03a71cae2900f9948a79370e968", _POINTER),
        # 'بمثل حديث شعبة وسفيان' (1 record)
        'hadith:muslim:49-2': ("ae2ec4fd79a14adb31e452d2d08d0b8ad5e601b7c85f588aa4b76c238f947d4a", _POINTER),
        # 'بمثل حديث عبد الوهاب' (1 record)
        'hadith:muslim:1534-5': ("5af268a710b298db8b18f9bef62c56f713b962b206dc10c00ea292a2f06cbe32", _POINTER),
        # 'بمثل حديث عقيل عن الزهري' (1 record)
        'hadith:muslim:2402-2': ("f3e652f3f80ad30bc836a1cc3d83bfe60fd1d92d1ab63b7ba3e84aac51c06156", _POINTER),
        # 'بمثل حديث مالك عن زيد بن أسلم' (1 record)
        'hadith:muslim:608-2': ("3aa58f31e404204b6c4c075f3eedc9332124d76d9426d2596bd37d3a166fbc01", _POINTER),
        # 'بمثل حديث مالك عن نافع' (1 record)
        'hadith:muslim:1871-2': ("252e016940bf385b86e0aee979d4f140ccfbd1b307d505ee049880f2ef37c234", _POINTER),
        # 'بمثل حديث مالك وعبيد الله' (1 record)
        'hadith:muslim:1534-6': ("0ff916c12fa069c053e253a6429b296212d935f99b8ffbef644819223c1cb49e", _POINTER),
        # 'بمثل حديث مروان سواء' (1 record)
        'hadith:muslim:1921-2': ("2b84880fb3583cafe4b3f7822c861ccbee8d9f143e54b44abf063968ab7b3dd7", _POINTER),
        # 'بمثل حديث معمر هذا سواء' (1 record)
        'hadith:muslim:2527-6': ("19110e1194291d6cd4fa6022b055c1af85bab61afadd13b4649adae394e513d5", _POINTER),
        # 'بمثل حديث منصور والأعمش' (1 record)
        'hadith:muslim:593-4': ("9a2a5ba24738914798a0056933b14751b69f53d4b30f1f4e71d829b2c85a901b", _POINTER),
        # 'بمثل حديث هشام بن عروة' (1 record)
        'hadith:muslim:2673-3': ("a02a8cb3f67c5ecf3411f81d37d9fba87bcc30aca103398f41abbd6a11df1698", _POINTER),
        # 'بمثل حديث هشيم' (1 record)
        'hadith:muslim:693-2': ("47aa112bfabb028e82d8e8a4641dd3dd04967ebc9d645bf51bf95feee30afc9e", _POINTER),
        # 'بمثل حديث وكيع وبن نمير' (1 record)
        'hadith:muslim:2672-2': ("f01969ba175ab25ddc0d6a75f7274419d445117fb7b08d02397e0d492bac6027", _POINTER),
        # 'بمثل حديث يحيى القطان' (1 record)
        'hadith:muslim:1399-4': ("058a1e40c1a704c4c886e647e37c92af20cc8a3313f417022df5e2fde3c8ba3b", _POINTER),
        # 'بمثل حديثهما' (1 record)
        'hadith:muslim:2447-2': ("776ec6880c1b9f094c479ae77b58b3ffcf7b544a6163e71536a70b4703ed6753", _POINTER),
        # 'بمثل حديثهما ولم يذكر ضحى' (1 record)
        'hadith:muslim:2941-3': ("df5d507887f4e303f0f5baf4a0fbf14a59d8d6877607d4211a79e46d790dff03", _POINTER),
        # 'بمثل ذلك' (1 record)
        'hadith:muslim:1075-3': ("769ce066220566f0a2b9bab157034b61d51fba37d4b148d41a2b26ee7756f3b0", _POINTER),
        # 'بمثل ما حدث عروة عن عائشة' (1 record)
        'hadith:muslim:902-2': ("2b9f2cae237260d60526d7baf722f192fcae44a7232c3bb9802ab09c0d8ee2ec", _POINTER),
        # 'بمثل معنى حديث حفص بن ميسرة' (1 record)
        'hadith:muslim:2598-2': ("4091eed207cafe2de26375feffd32f068083f8deb569cc51995be234d34a92c2", _POINTER),
        # 'بمثله 5' (1 record)
        'hadith:muslim:844-3': ("5107a5a5ba4d5151019143633c78970c273b3ee5a4477bc89ad2312e236ac683", _POINTER),
        # 'بمثله غير أنه قال بدهم أو بسوء' (1 record)
        'hadith:muslim:1387-2': ("7f1a2eb4c0f696ec3b3b28cc6337cf027eebe2b1fc932c63e3e4ce521ccb837a", _POINTER),
        # 'بمثله غير أنه قال فقولوا وعليك' (1 record)
        'hadith:muslim:2164-2': ("7252d55fc7a72f3f166ad0679be1404fe3ed5603a449af0db16bea55a09de1ce", _POINTER),
        # 'بمثله غير أنه قال كان لا يدخل' (1 record)
        'hadith:muslim:1928-2': ("b5e9fa021ea658fa0489c37ce150717a65db91da797d1f1f09a55547d839f3db", _POINTER),
        # 'بمثله غير أنه قال من ضر أصابه' (1 record)
        'hadith:muslim:2680-2': ("988cff708549875e5f50c248a8a7569ea8fff210d0f5b4e284f9a36339b0d785", _POINTER),
        # 'بمثله غير أنه قال ينبعث' (1 record)
        'hadith:muslim:157-13': ("84a46f54d5cddd2bd0a80eb077f22136f9b58c24791fac27717349431f58952c", _POINTER),
        # 'بمثله في المعنى' (1 record)
        'hadith:muslim:2176-2': ("0c15a3b07eceba44af88d5770e3783c21812fba6b1b79557238213794eab1211", _POINTER),
        # 'بمثله وزاد في الصلاة' (1 record)
        'hadith:muslim:422-3': ("af9c84e8d4bd45bf5d6a1209956f5faa775dcd66fdfdfc16154033fc7703c496", _POINTER),
        # 'بمثله وزاد لا يقطعها' (1 record)
        'hadith:muslim:2826-2': ("7f70dd69ce8fe841b13fd08071b15e22812bb9e8ba82c51316eaf049a3d7e74f", _POINTER),
        # 'بمثله وزاد وأبشروا' (1 record)
        'hadith:muslim:2816-8': ("361f983f6a8409f2417f99e3c23579b6521deb987c6669f0248845d44a769f15", _POINTER),
        # 'بمثله وقال في الإناء' (1 record)
        'hadith:muslim:2028-3': ("8d1324b7a36269f725fce91966bd43e8503855173822835fde39638ebc1cff90", _POINTER),
        # 'بمثله ولم يذكر الحج' (1 record)
        'hadith:muslim:693-4': ("a8aa20ab31b1de3eb8e30d035515a428087d432286470408751a8d60f3cfdee9", _POINTER),
        # 'بمثله ولم يذكر بن عمر' (1 record)
        'hadith:muslim:2061-2': ("a11a88268f89aad417c2e0086c0a892d6cc33d7f91776308af4139aa3ebaa618", _POINTER),
        # 'بمثله ولم يذكر قول قتادة' (1 record)
        'hadith:muslim:2024-3': ("5373a09356939d868c305cebc0f3d63ab2540d2ae44023cd8dc8c765a30bf1f5", _POINTER),
        # 'بمثله ولم يقل في رمضان' (1 record)
        'hadith:muslim:1102-3': ("01ab0df5121b7f3b3ff846c105c14a3d99fe9dabf116db51c49a128ba890394c", _POINTER),
        # 'بمثله يعني حديث يحيى بن يحيى' (1 record)
        'hadith:muslim:366-2': ("1c6dca989a2d9ac6a49683cd08f8a17950ce700553885dab99690abbee534705", _POINTER),
        # 'بمعناه' (1 record)
        'hadith:muslim:2675-10': ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        # 'بمعنى حديث أبي سنان' (1 record)
        'hadith:muslim:977-2': ("535647499809b6a637382ee9348d321eba8c81a5d41d9446cc6c13e6015be3fe", _POINTER),
        # 'بمعنى حديث المقبري' (1 record)
        'hadith:muslim:1885-3': ("dc680b41fe835f5ec78199c62eedbf42f39c30da93fb5de35aab501a0eda6dc6", _POINTER),
        # 'بمعنى حديث بن عيينة' (1 record)
        'hadith:muslim:2415-2': ("893397769cc198dbbf573f24d2e0a921904feaa4192ff9eee2c974d6d333e2a0", _POINTER),
        # 'بمعنى حديث جويرية' (1 record)
        'hadith:muslim:2242-5': ("d247a7a03b2dc6e3445bd75d4e625829973b49327f271a826030be97ce5153e1", _POINTER),
        # 'بمعنى حديث سمي' (1 record)
        'hadith:muslim:409-2': ("af0a7193124c54e7bce68f10d894d418dc715986de39e5373bcfb20f2c0c3bed", _POINTER),
        # 'بمعنى حديث شعبة' (1 record)
        'hadith:muslim:2218-10': ("4cd0a9d1ea4fb4be3792987ad8f0c4bc79a5712b5d7a2f9583c6510181d2ae8a", _POINTER),
        # 'بمعنى حديث مالك' (1 record)
        'hadith:muslim:2183-2': ("e1fa631f9520e9e0d18a2f5b2ffd30bc78d9e92f2b4724fc8ff35fb498e4298f", _POINTER),
        # 'بمعنى حديث مالك عن نافع' (1 record)
        'hadith:muslim:1501-2': ("bf93899d25779821c12b677b0cefab936c65f814e82c39bd83615d383d5582b1", _POINTER),
        # 'بمعنى حديث من ذكرنا' (1 record)
        'hadith:muslim:2067-6': ("661baed1d1b2293a014afb0c43ab3a6f9371922c4fd173bfdb83c27a0e58581a", _POINTER),
        # 'بمعنى حديث نافع عن بن عمر' (1 record)
        'hadith:muslim:1851-3': ("b815118e26886a2cb5dac8ae7dc174c166da13ee896fed6854aa917b2824ee9e", _POINTER),
        # 'بمعنى حديث هشام بن عروة' (1 record)
        'hadith:muslim:2243-3': ("56c0e365ccddab02885861d720ea5f281580fa3e232e3e7032b8d13884759adc", _POINTER),
        # 'بمعنى حديث يونس عن الزهري' (1 record)
        'hadith:muslim:151-5': ("3a42c1e607c1e92f898c6dfe33748d9066509843bc707b17faf29693b986a074", _POINTER),
        # 'بمعنى حديثهم' (1 record)
        'hadith:muslim:1490-4': ("27fbf905463e3bef776c513b4a5f5da968cd4022c7337169ce3dd64d7af4ad87", _POINTER),
        # 'بمعنى حديثهما' (1 record)
        'hadith:muslim:2808-3': ("82a77373a6ea74593399f784680eea8cb7e850690823fdd6125d848618f4b0fb", _POINTER),
        # Task-16 C0 (A2-residue): 4 more pure 'بمعنى حديث X عن Y' singletons
        # that slipped A2's fix-round duplicate-string grouping (each is a
        # unique string, so it never grouped with another occurrence) but are
        # the same class as the 19 'بمعنى حديث' entries already above. No
        # matn wording of their own -- pure back-references.
        # 'بمعنى حديث أبي زرعة عن أبي هريرة' (1 record)
        'hadith:muslim:1302-2': ("527d5cc6c1537fcd3de46f50ca14f1ca11188636eecf78782c0911fa708ddd92", _POINTER),
        # 'بمعنى حديث الليث عن أيوب بن موسى' (1 record)
        'hadith:muslim:1913-2': ("d7cd54667083bfdc3f632edf9b03641599afc8bed0c65d6f133bfa47d3280efc", _POINTER),
        # 'بمعنى حديث معاذ عن محمد بن عمرو' (1 record)
        'hadith:muslim:1977-8': ("776f2d382e2abbacae025d6238d6fdd3531d5103220d662b9a82cef6d70b075f", _POINTER),
        # 'بمعنى حديث بشر بن مفضل عن أبي مسلمة' (1 record)
        'hadith:muslim:2153-5': ("5c5ca64f2966e26e0d8a83a9026d2dd14cbd858a261328197b707fe5c2d5f62a", _POINTER),
        # Task-16 C0: adjudicated muslim:1704-2 ('بمثل حديث مالك والشك في
        # حديثهما جميعا في بيعها في الثالثة أو الرابعة'). Not just a pointer:
        # it also carries a narrator's-doubt remark about which numeral
        # (third/fourth) the parallel narrations used. Read against its own
        # isnad (1704-2's chain is Zuhri's, distinct from 1704's Malik chain)
        # and its parent 1704 (the full a'ma matn), the clause delivers no
        # narrative content of its own -- it is a back-reference plus an
        # editorial remark on how the isnad's wording was transmitted with a
        # numeral uncertain, not a report of the Prophet's words.
        # 'بمثل حديث مالك والشك في حديثهما جميعا في بيعها في الثالثة أو الرابعة' (1 record)
        'hadith:muslim:1704-2': ("fe7b80297e4bfbb09b4c230aabdcd97b568ed2e1fad229c63f0f2ff21d7fa5d6", _EDITORIAL_DISCUSSION),
        # 'بنحو حديث أبي عوانة' (1 record)
        'hadith:muslim:209-3': ("82d7dc20cc94334b9c03553b1f3f9fd80a66a1f9aa46f7753b601dc673bd50d9", _POINTER),
        # 'بنحو حديث زهير' (1 record)
        'hadith:muslim:2013-2': ("d510e25bc9e86aa0ed3cf900ca4b0be4aae89f464336b5e148af3f0d1df65d81", _POINTER),
        # 'بنحو حديث مالك' (1 record)
        'hadith:muslim:2068-2': ("0e8c98e629b218befa55fb0e98ab8134aa965dd47dceb96faa33eee27c924ba5", _POINTER),
        # 'بنحو هذا أو بمثله' (1 record)
        'hadith:muslim:2468-2': ("3f83bb7f2fe693caf336ee8dd3c175108a03aa976769e59fc03e7f770aca976a", _POINTER),
        # 'بنحو هذا الحديث أيضا' (1 record)
        'hadith:muslim:963-2': ("99df1e94d46698b31a4f579130b9d6498a11bf0fbe8d42100e802b04a59e8390", _POINTER),
        # 'بهذا الإسناد بنحو رواية يونس' (1 record)
        'hadith:muslim:363-3': ("33b53263b5c26bc98175d88db893cb2aa8dff93ff59f98d336fb77151ec1d11a", _POINTER),
        # 'بهذا الإسناد بنحوه' (1 record)
        'hadith:muslim:663-2': ("131dfd1a935755e55d6761d44d73783945f8a9e6704d27277a07579d9ad2a845", _POINTER),
        # 'بهذا الإسناد كما قال مالك' (1 record)
        'hadith:muslim:723-2': ("ff743b2add2eb87f90df6a06a9aeab5f92456e122b51e0016cab58365e2c14b8", _POINTER),
        # 'بهذا الإسناد مثل حديث بن بكر' (1 record)
        'hadith:muslim:1333-8': ("5fd7c331b0c3eed6756d1a93d35020fca0aa0162bae8d6535a085f03bd30a82b", _POINTER),
        # 'بهذا الإسناد مثل حديث بن مهدي' (1 record)
        'hadith:muslim:979-7': ("01a1d2a8f3f61862416c104c8c48852b966688676821a63f1c428a123359a4a6", _POINTER),
        # 'بهذا الإسناد مثل حديث بن نمير' (1 record)
        'hadith:muslim:286-3': ("e93fc873ed5b7885890f6713e0843328b4c2c65fe0e946f1753b576f8008931b", _POINTER),
        # 'بهذا الإسناد مثل معناه' (1 record)
        'hadith:muslim:2608-2': ("47fb780242934f7b76168686d54428b7135dc56daf31ec99488e46291dd6d14b", _POINTER),
        # 'بهذا الإسناد مثله وزاد فصاعدا' (1 record)
        'hadith:muslim:394-4': ("bb8ca137a326d6c100615c4c92dbfe75f4a2558db7a7ed85e3db0fdc5eb1f980", _POINTER),
        # 'بهذا الإسناد مثله ولم يقل حق' (1 record)
        'hadith:muslim:2225-5': ("81136122d6e18547971f8a7394db19613469e26571a358cce52ed21771a5546c", _POINTER),
        # 'بهذا الإسناد نحو حديث بن عيينة' (1 record)
        'hadith:muslim:1111-6': ("088a6f38bac04b0160a2fd5b856812c932f8eb263f7de0c1fd8d055254a8f45a", _POINTER),
        # 'بهذا الإسناد نحو حديث عبثر' (1 record)
        'hadith:muslim:2685-2': ("b4b6b4d08695a4ab0ccf013bcd23f8947ae434dd137701674f89c5909f927f91", _POINTER),
        # 'بهذا الإسناد نحو حديث مالك' (1 record)
        'hadith:muslim:2327-3': ("356a9e275818cc88b76f1761eec97e6b5d6bf56b6d0a9a2bc9d4a9980bad144a", _POINTER),
        # 'بهذا الإسناد نحو حديثهما' (1 record)
        'hadith:muslim:1797-3': ("2deede7add4ae0f9d34e236a253baa055e3b0c56ea717b931dad7ab7d5590fc1", _POINTER),
        # 'بهذا الإسناد هذا الحديث' (1 record)
        'hadith:muslim:1619-2': ("5d6b53c85fa39cfd4a67e2d2fb242893c4ab5262038ccab6e3aaa76839bd962e", _POINTER),
        # 'بهذا الإسناد وزاد فأدعها' (1 record)
        'hadith:muslim:2083-3': ("f99057ae34e7bb5160e2c10483e4e31380515db165409f72313cce208b84ce02", _POINTER),
        # 'بهذا الإسناد وساق الحديث' (1 record)
        'hadith:muslim:987-4': ("e1a1d472991daff1b3a36dc22114835200572977a291202356229f22cd6df8ab", _POINTER),
        # 'بهذا الإسناد وقال حتى ترجع' (1 record)
        'hadith:muslim:1436-2': ("edd4a1e1f1aa38a884eb33ac9a93f20ca0f68418ed254aa550906cb3e45b20ae", _POINTER),
        # 'بهذا الإسناد وقال سبع غزوات' (1 record)
        'hadith:muslim:1952-3': ("521eca1bc745ad5a5d6518d34278b2ef1613fb6d08df66538793eb8ab1527688", _POINTER),
        # 'بهذا الإسناد وقال صوم شهرين' (1 record)
        'hadith:muslim:1149-4': ("f09ea2c2786b3e58d283769a418c141f9f643d72e354897398d4d6e33e80fe7a", _POINTER),
        # 'بهذا الإسناد وقال عبدا حبشيا' (1 record)
        'hadith:muslim:1838-2': ("7df75d3f5ed4088f940a7a63a0ed732b79d7d0e64597943878af93222e0fdbca", _POINTER),
        # 'بهذا الإسناد وقال ونفهت النفس' (1 record)
        'hadith:muslim:1159-9': ("5a0777490edeafc374b668c2b87feb0b1cc22bdaa546e144cda0aaf0a990bc5e", _POINTER),
        # 'بهذا الإسناد وقالا وشق ودعا' (1 record)
        'hadith:muslim:103-2': ("7d9a4fd3104b077fbddad94edbefc825524da15072df7b3edc7aca28bb58a993", _POINTER),
        # 'بهذا الإسناد ولم يذكر في السفر' (1 record)
        'hadith:muslim:2076-2': ("c3ca5f39b25df5d0e9db07d23940935337b0c756f655c941b7433b64e0b753d0", _POINTER),
        # 'بهذا الإسناد ولم يذكر وأبشروا' (1 record)
        'hadith:muslim:2818-2': ("fa95a5a09f82bde9c998d3ee8c800f2f3382b8e15c71525d854f154f84c5f430", _POINTER),
        # 'بهذا الإسناد ولم يذكر يدا بيد' (1 record)
        'hadith:muslim:1588-2': ("be1ae5026cc4568421881fca2fb26a6305c50a0e57195486e408c790629cf16c", _POINTER),
        # 'بهذا الإسناد ولم يذكروا أم كعب' (1 record)
        'hadith:muslim:964-2': ("e4aa5c86684558b72222af9f3656f9dfc786c48b67d9951c35811739016f05b1", _POINTER),
        # 'بهذا الإسناد ولم يقولا حسنا' (1 record)
        'hadith:muslim:670-3': ("1b5dcefa287d4966f25a037541363a15e5ea78929da1436aeb075e4c4a1dd974", _POINTER),
        # 'بهذا الحديث يزيد بعضهم على بعض' (1 record)
        'hadith:muslim:677-7': ("642eb78115f8f322ce8e43637bdaa39c46debbe0917a3ab1d663b75d65998528", _POINTER),
        # 'بهذا مثل حديث الليث عن نافع' (1 record)
        'hadith:muslim:1829-3': ("dd2ec52059081995aa10e20b601e116d0469429edf44faff8bd8b235df3a4f7e", _POINTER),
        # 'بهذا ولم يذكر الأجر والمغنم' (1 record)
        'hadith:muslim:1873-5': ("d55a881957ac57dafea86f93534aecbd16adb7f86102ca00c35f8ea6e21beb38", _POINTER),
        # 'بهذا ولم يذكر عن عمه ظهير' (1 record)
        'hadith:muslim:1548-6': ("845ee553a2b40f069a17ec4ab9d6433a8f62ea59af6b77ee6ba313f4898d104d", _POINTER),
        # 'بهذا ولم يقولوا أبيض قد شاب' (1 record)
        'hadith:muslim:2343-2': ("be5613763597884a0ac7fe187bdd053c5a84288c52997428d3dc29dd98678e7d", _POINTER),
        # 'بهذه القصة نحو حديث يزيد' (1 record)
        'hadith:muslim:2144-3': ("5eb1192ebd764d241567a49e263a59a19296e4856c62a51357a06f84bcad8cae", _POINTER),
        # 'حماد ولم يذكر الركعتين' (1 record)
        'hadith:muslim:875-2': ("8323cb807d2a444e54f2afe03a222eb04debdd7dcbafb3bfe26b1deb8ea8f172", _POINTER),
        # 'ذكر نحوه' (1 record)
        'hadith:muslim:411-2': ("c1efe1d128aaada4dd59dbcb80769d57de8da5623f39466e8fd948e17948a614", _DEFERRAL),
        # 'ذلك' (1 record)
        'hadith:muslim:1651-4': ("75d350ce684c85e31b4f9cd299e8a7c6f875724cbefd6c86e1fddae07a24e31b", _POINTER),
        # 'رفعه' (1 record)
        'hadith:muslim:626-2': ("fb95a9828d7585d8ec476cf8e597bb65efaef0eabe0ad303290386ad968313ac", _ATTRIBUTION_NOTE),
        # 'سألت أنسا بمثله' (1 record)
        'hadith:muslim:555-2': ("07dc0aad5c717c41caace80fcb6e3dc823b6c9e0919b1bec3f0e15a9da7e0dbc", _POINTER),
        # 'سمع أنس بن مالك يذكر ذلك' (1 record)
        'hadith:muslim:399-4': ("217f18cf7aa0728b4411cb6309abbda2d9aecad39e718a4058045331a43086ba", _DEFERRAL),
        # 'سمعت العلاء بهذا الإسناد' (1 record)
        'hadith:muslim:2761-4': ("46f528abd471e082b941de1edd1522989980ac5b8dc9bf42d5cf60324fa8eb6e", _DEFERRAL),
        # 'سمعت معمرا بهذا الإسناد' (1 record)
        'hadith:muslim:608-4': ("29611bc21b89c9ee3f862018b3f20d9519d9c709536c39c46ed8766aac0ec8ef", _DEFERRAL),
        # 'على معنى حديث صالح عن الزهري' (1 record)
        'hadith:muslim:150-6': ("cda618323a7fd613763d8eec597224b3d74a5dc2ba42d67b88fcd33425ff7da0", _POINTER),
        # 'عليك بالرفق ثم ذكر بمثله' (1 record)
        'hadith:muslim:2594-2': ("41131a7f5fa08da505f17a43cff453c32ddbe034330fb1c9f744768eda809501", _POINTER),
        # 'فذكر بمثل حديث بن علية' (1 record)
        'hadith:muslim:824-4': ("3bf208ee6d5f9606e8478858a85911f19f6775904d503ca4a3ab893e08cde720", _DEFERRAL),
        # 'فذكر بمثل حديث همام' (1 record)
        'hadith:muslim:2958-2': ("c3c9495f11c0e048c95f5d8bdef38ddc9d916a747c4c095fee1dc8e4a72abb00", _DEFERRAL),
        # 'فذكر بمعنى حديث مالك' (1 record)
        'hadith:muslim:507-2': ("8873c21a50c1f771af613db7bb213c4486c28c2b5bdecc0dec1e5cbf40e4514d", _DEFERRAL),
        # 'فذكر نحو حديث قتادة عن أنس' (1 record)
        'hadith:muslim:200-4': ("2c339423ca0070f0e05296df653068097525d0d2b1bfb8f8a1b0953f5dd2c9db", _DEFERRAL),
        # 'فذكر نحوه' (1 record)
        'hadith:muslim:521-2': ("edc5862bd004c3bef89e0e4e3c8f0e64f1fa71d9a89a676789dd728c9d23ff4a", _DEFERRAL),
        # 'فذكر نحوه ولم يقل يوم القيامة' (1 record)
        'hadith:muslim:2067-3': ("c8e5a76c863bf86b001b74a0f7a0cc72d4edddf0ca02cb3af62266c0eb39ede6", _DEFERRAL),
        # 'فذكر هذا' (1 record)
        'hadith:muslim:1094-5': ("f88da58d894bb254adb240946c307233d661d9893b7159237aeb448b9f0db303", _DEFERRAL),
        # 'فذكرا نحوه غير أنهما قالا تنقز' (1 record)
        'hadith:muslim:795-3': ("f81f5a25041bc9869ddcae1d526d738e8a6ddbeb206e8e0b483fa6ca130686c4", _DEFERRAL),
        # 'فذكروا الحديث بطوله' (1 record)
        'hadith:muslim:2577-3': ("ee40b92ca7636557d437595772b0d6aef6686ee5caa4db079b84097de244858c", _DEFERRAL),
        # 'في الحرير بمثله' (1 record)
        'hadith:muslim:2069-4': ("607b59933897dfede5c01289ebbc9dabe4015177c4b7c68a613ff74bb9592fb4", _POINTER),
        # 'في حديثه إزارا غليظا' (1 record)
        'hadith:muslim:2080-2': ("5c1e1171155a67a66e96d4e49707abdfc5a68c5490df3670722d89fb88fcc120", _POINTER),
        # 'في حديثه هذا يهودي ورائي' (1 record)
        'hadith:muslim:2921-2': ("8aaa9d6e86c8d2b96b96bb6704c276ccda320b8d7192be8c3eabcae7a66187f9", _POINTER),
        # 'في خاتم الذهب نحو حديث الليث' (1 record)
        'hadith:muslim:2091-3': ("9d96a226ab440bc807f0653bcac3790529ea7eadf1ac897a47dd199596cca5d7", _POINTER),
        # 'في روايته يعني معاوية' (1 record)
        'hadith:muslim:1225-2': ("af8e30b24855d8b9dc35e9d339f221d2329fb223228fff950c60506b6845eebb", _POINTER),
        # 'في طعام أبي طلحة نحو حديثهم' (1 record)
        'hadith:muslim:2040-9': ("00f49ab02c825d9f40ae7f6aaad4efc6ecda23e787d7c8d65a9d60697245d038", _POINTER),
        # 'في هذا الإسناد بمثل حديث هشيم' (1 record)
        'hadith:muslim:466-2': ("4a6c075eef23ca957546e3ee82944481e0f1c7e139a8cf0e39e03e3f5a3d0a34", _POINTER),
        # 'في هذا الإسناد بمعنى حديثهما' (1 record)
        'hadith:muslim:1086-3': ("988a4a13e067b9506f3366c09315c87cf3cd881684d6ac8a9ffe0983f879a5bf", _POINTER),
        # 'في هذا الإسناد في معناه' (1 record)
        'hadith:muslim:2917-2': ("60efcf3fd2ce1f80f7d1c199a1baa533210ca2145810445c6e0de504447fd290", _POINTER),
        # 'كرواية روح' (1 record)
        'hadith:muslim:2012-7': ("879e0b4b9683a4aff4ab4f9dc2a73cca6bad2b7e7171919c5b91de17e287ea75", _POINTER),
        # 'كرواية عقيل بالإسنادين جميعا' (1 record)
        'hadith:muslim:951-3': ("a9d0d6b2db226d0cd6aa5b1c4ee7b63063ab23daf2cc06424eab9ccdb0149b4f", _POINTER),
        # 'كرواية يونس بإسناده' (1 record)
        'hadith:muslim:818-3': ("702086c2c60fe1cb389b20d5b1c1142fd0d0233169a4a58aaece4e0947ea668b", _POINTER),
        # 'كنا نصلي المغرب بنحوه' (1 record)
        'hadith:muslim:637-2': ("9c2ede2775e3b3b704cce8e1d653c82065893c263d4064f4b54354d32c014dcb", _POINTER),
        # 'لكأني أنظر بمثل حديث وكيع' (1 record)
        'hadith:muslim:1190-4': ("29dd0bd472cde6316ac8975959c725489807a30327f5a36b684dd89dfde8d076", _POINTER),
        # 'ما شاء الله' (1 record)
        'hadith:muslim:719-2': ("dfd9695ee60f9294b80a2d025d6745fd2da438ed486d673f9a250f510ed46c58", _POINTER),
        # 'مثل حديث الليث عن نافع' (1 record)
        'hadith:muslim:1829-2': ("b4d98627b87929bb81a2575bb1b6f5ef9e622103141f17bbae3753f8ef51ac07", _POINTER),
        # 'مثل حديث ثابت' (1 record)
        'hadith:muslim:1809-2': ("903ab15e51987de74796fff046c23e23ec421110ca68e557a9c598a2beb09dbc", _POINTER),
        # 'مثل حديث هؤلاء عن بن عمر' (1 record)
        'hadith:muslim:2518-3': ("7ae7f5a268a5d4f113fc625cb44d571a82e145b007dd34c24e1b5182edfbacfe", _POINTER),
        # 'مثل حديث يونس' (1 record)
        'hadith:muslim:523-3': ("c2f1fc255d652607247777c9bc86809ab1882d66449378f8ffc847dffd72f0fb", _POINTER),
        # 'مثل حديثه' (1 record)
        'hadith:muslim:1710-2': ("12f33147cf153fa305d34ec6cb86d4a966cfa3bee5a27b5d6cb1328df0546eff", _POINTER),
        # 'مثله أو نحوه' (1 record)
        'hadith:muslim:1654-3': ("2a763ad27e558cac7f6e08250950c22bea6bef04c914bfd273f66ccc4bbe52fa", _POINTER),
        # 'مثله إلا أن فيه زكاة وأجرا' (1 record)
        'hadith:muslim:2602': ("74532fe35e8b75bb2413e81c1b49bcb6bd91e50f30cab919d43cb55d3491803e", _POINTER),
        # 'مثله غير أنه قال ثيابه' (1 record)
        'hadith:muslim:2085-6': ("d04968e961eade65c08a44d07085a7544c2b13d70f34bef6259e407fbd90331d", _POINTER),
        # 'مثله وقال بدل أتمها أحسنها' (1 record)
        'hadith:muslim:2287-2': ("5cd4bc7de20c182a8d97f35b7e0172f628475307df0b336d0d19ad7952db057f", _POINTER),
        # 'مثله ولم يذكر من حديد' (1 record)
        'hadith:muslim:1603-4': ("432171abe36426661f0ec2e4993504c4818564a1f41f209ab435c19d8319b853", _POINTER),
        # 'مثلي ومثل النبيين فذكر نحوه' (1 record)
        'hadith:muslim:2286-4': ("926a980d49eb9d6dd69047bec55eeafe0aa7861bcf14ef7e7d99d03d28eee6c9", _POINTER),
        # 'مر برجل من الأنصار يعظ أخاه' (1 record)
        'hadith:muslim:36-2': ("91245e01d0f3bdc558d93a52c2a108c15a8ca7934a237e94605fef271b8179f2", _TRUNCATED_STUB),
        # 'من شحم ولم يذكر الطعام' (1 record)
        'hadith:muslim:1772-3': ("b60bb8ef936f08c0152b3c3bfdc6c0906793e2fa2e3189a490479c50c4ec8c13", _POINTER),
        # 'من وحد الله ثم ذكر بمثله 9' (1 record)
        'hadith:muslim:23-2': ("549ce9fb424755f500ac19cdde5819b1509ed1bf469c0742ddf14b6cbe0fdcbe", _POINTER),
        # 'نحو حديث أيوب مرفوعا' (1 record)
        'hadith:muslim:1066-5': ("74af21104e12b429589e780dc654c3dc47d31d780a39594800f6a2abc18792f8", _POINTER),
        # 'نحو حديث الأعمش ومغيرة' (1 record)
        'hadith:muslim:2297-4': ("4bb1b854b48a27fd316af8132ad7a0e3713bcbcb1dfe5bf4f8632338357ae1a6", _POINTER),
        # 'نحو حديث الليث ويونس' (1 record)
        'hadith:muslim:2156-3': ("277889f908dbd59a3dca52b7a0ad6482d48d83bb5f7fddf7ff7851ea8595bf6b", _POINTER),
        # 'نحو حديث بن أبي عروبة' (1 record)
        'hadith:muslim:1786-2': ("3dc707cafc75d1788d0639827e0d38ce9a9047f84a89432799f70a32cc9c4652", _POINTER),
        # 'نحو حديث بن عيينة' (1 record)
        'hadith:muslim:1234-2': ("05e1cbb2d6c6e20d0af8083524fc0e6b15acae4f537e6ad99160667c86d375bf", _POINTER),
        # 'نحو حديث شيبان' (1 record)
        'hadith:muslim:2967-2': ("cd73752b46976c5a26b7af118b8f5c2fd69b32fcbeaa24ae56a382cd8899b6e7", _POINTER),
        # 'نحو حديث مالك عن نافع' (1 record)
        'hadith:muslim:1531-2': ("dd5aaa67b29632b6a95b731bf5d293c1f364bf9e292849b2403f25049281b9f0", _POINTER),
        # 'نحو حديث يعقوب عن سهيل' (1 record)
        'hadith:muslim:1014-4': ("74e2bc032e01523688167d0c0679e41794778093e94d3346d525b9db146b99b1", _POINTER),
        # 'نحو ذلك' (1 record)
        'hadith:muslim:1432-3': ("cf1f22d38f2ded3b02c6f04ec674d178a304af4ca4dafdb6c7adc37c7721b697", _POINTER),
        # 'نحو هذا' (1 record)
        'hadith:muslim:206-2': ("b2133cd31847e4d6a1dbdcf8e39425d27513e8a2c945867b902e622191a40b08", _POINTER),
        # 'نحو هذه القصة' (1 record)
        'hadith:muslim:1471-20': ("c3ea67a787ea1ff1ab863eedcb3dbc9078bf751420284f19d6f4359954a6fd62", _POINTER),
        # 'واقتص الحديث' (1 record)
        'hadith:muslim:1751': ("8355edd78515744c43cc6a8b37ab04ebe9f02eb42589aa7bbd61d18d8151daef", _DEFERRAL),
        # 'والذي نفسي بيده بمثل حديثهما' (1 record)
        'hadith:muslim:1252-3': ("76c4d05f4e3ea23198421ce9c4218b5158b73b703825d3224da782b7da84dfe9", _POINTER),
        # 'وذكر اللقمة نحو حديثهما' (1 record)
        'hadith:muslim:2033-6': ("5dc6d4cd550766342e42875d48d082a354f3edaca34d05d6f09656b891dd6f0e", _POINTER),
        # 'وساق الحديث' (1 record)
        'hadith:muslim:1751-2': ("3fb9392ed9b90344141c4b038fe5ce3f29b57822de50f91565aa7919044bb98a", _DEFERRAL),
        # 'وفي حديث وكيع قال يرفعه بمثله' (1 record)
        'hadith:muslim:278-2': ("1b0a668294b153dd021117a61f1f4a54e8495e41a11d753a4fe02f2617b71c81", _POINTER),
        # 'ولم يذكر حاد حسن الصوت' (1 record)
        'hadith:muslim:2323-6': ("6c1ab8076ebb58cf1f9820d0198a0cc1aea0a8f19040d710ae1aee6cb1963093", _POINTER),
        # 'ولم يذكر في السجود' (1 record)
        'hadith:muslim:480-6': ("c7041685d43a6271b533d163f834890c60f1165306e272a36a045a04d556d02b", _POINTER),
        # 'ولم يذكر لا كفارة لها إلا ذلك' (1 record)
        'hadith:muslim:684-2': ("cddc94e64bfe9119a24f1485a18c8773d50bbd932a2262f057f5e43e1987e301", _POINTER),
        # 'يا رسول الله بمثله' (1 record)
        'hadith:muslim:2369-2': ("ab41a99e99f93506aa7accb1ab4c4c105028149dcfd1971a47294602731441c0", _POINTER),
        # 'يا رسول الله مالك لم تحل بنحوه' (1 record)
        'hadith:muslim:1229-2': ("6eb6bcb3e91ef400cc66d2307876f7b509003245f14249d687e82d37032fe6f0", _POINTER),
        # 'يصدر الناس بنسكين فذكر الحديث' (1 record)
        'hadith:muslim:1211-19': ("7e45b0e2abcd79a670db1d6ead161b006ef2133d63d1339dc99b94ddf36031d4", _POINTER),
        # 'يعوده نحو حديث الحسن عن معقل' (1 record)
        'hadith:muslim:142-8': ("76d549465aafab4d14b57bf519e4d1e25f316d69313db4f34eab7696205eb0e4", _POINTER),
        # 'يقول فذكر بمثله' (1 record)
        'hadith:muslim:2671-3': ("dc3f8465471a490603837d07a0bf56f2d5927537d0a458f12969d573d7b876f3", _POINTER),
        # --- Task 16 A1: pointer/deferral remainders EXPOSED by the compiler-
        # commentary split. Each opened with a "بهذا الإسناد"/"بمثله" deferral
        # in the source, but escaped Task 11's 30-char audit floor because
        # Muslim's own trailing "قال مسلم ..." biographical/variant gloss padded
        # the total length past it -- the exact "trailing commentary padded the
        # length" hazard [[sanad-editorial-pointer-false-exact]] and Task 12's
        # 58 Abu Dawud records document. Now that the A1 split moves the gloss
        # to addenda_ar, the genuine remainder stands revealed as a bare
        # deferral with no independently-quotable narration; sha256 recomputed
        # from the POST-SPLIT matn (parse_openiti(raw, collection="muslim")).
        # 1532-2's "بمثله" also tripped materialize's wholly-Qur'anic gate once
        # exposed -- it is a pointer, not scripture; the gate fires on any
        # scorable matn whose norm collides with an ayah representation, and
        # marking it unscorable is the correct remedy (the cut is right, the
        # remainder is simply not a text).
        'hadith:muslim:1532-2': ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        # 'بهذا الإسناد وقال إن أبا العباس الشاعر أخبره' -- chain deferral + an
        # isnad detail, no matn.
        'hadith:muslim:1159-7': ("e75db96f3f4a50edfac123077924824c872b3aae057732cc01cca29121b4f713", _DEFERRAL),
        # 'بهذا الإسناد فأما عبد الرحمن ... وأما بن جعفر فقال قال شعبة' -- chain
        # deferral + a narrator-wording comparison note, no matn.
        'hadith:muslim:1238-2': ("09dde6d821139d5b477e2e4d75be490361374021bdfba8a228f478fd83346813", _DEFERRAL),
        # 'بهذا الإسناد وحديث معمر مثل حديث يونس غير أنه قال ...' -- chain
        # deferral + a cross-narrator wording comparison, no independent matn.
        'hadith:muslim:1647-2': ("fb41679686838b940def6b37e80fa2431531910ec4437483a07ae22a889592d9", _DEFERRAL),
        # 'بهذا الإسناد وقال رزيق مولى بني فزارة' -- chain deferral + a dangling
        # attribution fragment, no matn.
        'hadith:muslim:1855-3': ("1b08d44873f6ef75aac86c2bfaf2721b003f67097bdb37f8a991a6027298fdde", _DEFERRAL),
        # --- Task 16 A2: non-length-capped pointer/deferral sweep. ---------
        # The partial-quote deferral class Task 16's brief named (seed
        # muslim:450-2): a chain-pointer ("بهذا الإسناد"/"بمثله"/"نحو حديث X")
        # followed by an endpoint locator ("إلى قوله Y"/"حتى Y"/"انتهى عند
        # قوله Y"/"إلى قصة الشاة") and usually "ولم يذكر ما بعده" -- it names
        # WHERE another version stops, delivering NO narration of its own. Each
        # escaped Task 11's 30-char floor only because the endpoint phrase pads
        # its length, the [[sanad-editorial-pointer-false-exact]] hazard.
        # Found by three sweeps over the post-A1 matns (pointer-opener + endpoint
        # marker; the "لم يذكر ما بعده" signature; and non-opener "وساق/فذكر ...
        # إلى قوله" deferrals), then read ONE AT A TIME. Records that instead
        # DELIVER wording via "وزاد Y"/"وقال فيه Y" or that OPEN with a real matn
        # clause before deferring were ruled SCORABLE and left off (e.g. 1370-2
        # "وزاد فمن أخفر مسلما ..."; 2052-3/2847/334-3/675-4/901-3/1370 open with
        # genuine narration; abudawud:3967/nasai:4026 deliver via زاد/وقال) --
        # see the Task 16 report for the full scorable/unscorable disposition.
        # sha256 of the POST-A1-split text_ar (parse_openiti(raw,
        # collection="muslim")); 1669-6 alone also carries an A1 addendum, so
        # its excluded primary keeps a scorable "full" representation, like 237.
        'hadith:muslim:183-2': ("bf775fc94fce854706886052ceba131a9cfb38b4920ca09f895c9f59392b56ba", _POINTER),
        'hadith:muslim:185-2': ("65b6540a0eaed2c4dad2463adb947b9a7fcfbf0cadc644acdd92485c1927782d", _DEFERRAL),
        'hadith:muslim:450-2': ("ca2655c1b365a5156ba9708879aee7f6999c2babb83742312f979df4cdb31a03", _DEFERRAL),
        'hadith:muslim:450-4': ("8918b132c6b3560e6a6c37bc75cadac0b6d7fcf138724501d9ac8abfea5774ef", _DEFERRAL),
        'hadith:muslim:478-2': ("8dc2a9073b8bf31cc88252962f7d873415517228f9d6a0d247556a534974d969", _DEFERRAL),
        'hadith:muslim:535-2': ("c0aa0a8bdef963e66ac1c7eed855c478d0b92c3c82f2878333da92e51b0c53ac", _DEFERRAL),
        'hadith:muslim:675-2': ("893993424dab42932975e422d4d9b4617c538eee64064c1dc860ac10869e8046", _DEFERRAL),
        'hadith:muslim:945-2': ("cb0224d37d1f4d7bf8ee0a07c92ede819220a5c274dd2c8d1a99fb26a7473d92", _DEFERRAL),
        'hadith:muslim:1534-4': ("d44c338e9e6edee62b3bd64821c37937ffec32e6f05ece6578a39c50eab6bd09", _DEFERRAL),
        'hadith:muslim:1632-2': ("5ba317ca09342d61d2ad62182a690496aadc576ae0df5e66c74aeaa82b9cbe37", _DEFERRAL),
        'hadith:muslim:1669-6': ("e863fec6a34a16f23343c306f591d7b588b055c0d4a4061fde994aacfdbcf0ea", _DEFERRAL),
        'hadith:muslim:1700-2': ("4c9115715e017c0f4f3ee5f3f00c054dfbfea679bc18b3e8de6fc6a93d2bf8e0", _DEFERRAL),
        'hadith:muslim:1781-2': ("6e8a62b1263af5a68af5f2f06f39846b52241a17c5df93c73ab6bc7b845c323d", _DEFERRAL),
        'hadith:muslim:2033-5': ("e51995d6ff1ac8dcb19b19f4c13ea3432795c1a022d0ed7d9379699cb33f6171", _DEFERRAL),
        'hadith:muslim:2327-5': ("97211d5648ee6e627118ea475188fba24a909d23cc13435286818554c2387118", _DEFERRAL),
        'hadith:muslim:2435-3': ("b491ba917b06e9952298382da1f44474a2aebd5c04baf56d56c8b50ac29fbe17", _DEFERRAL),
        'hadith:muslim:2439-2': ("cb34cf072986ffd9b7d3d4f6e500f590d72db87b63447cdd8e7f2c7a4ed52f93", _DEFERRAL),
        'hadith:muslim:2492-2': ("c9962eedfbfee57caab5257c61333119729e1df7c4b5862e5e6aeecb02100ef9", _DEFERRAL),
        'hadith:muslim:2605-3': ("1d2475508072e4a102c7b7d62541123694e9310671f22a3d88f30bbc28a42682", _DEFERRAL),
        'hadith:muslim:2688-2': ("3c952cef391186c28f8a985f2e88f5705546de5b99bc2f556d1545f79f8e0336", _DEFERRAL),
        'hadith:muslim:2835-2': ("a51995c704a0edd11687e67af7b3b6dee554c59630e455be29089d0343acff6a", _DEFERRAL),
        'hadith:muslim:2887-2': ("7433d7995166de083878b118eeb64505253f8967c15eae1fcd2f6d50e817de80", _DEFERRAL),
        'hadith:muslim:2888-3': ("9f5d66db2d4d1b727491e8f04518782f52fe201138ef4314bc3ad377d091b535", _POINTER),
        'hadith:muslim:2891-3': ("cfad0e0668009fc0a43b7cc32f1f8804caa5772870ac566c99a510c6c0cfc59c", _DEFERRAL),
        # --- Task 16 A2 fix round (R-A3-review Finding 1): Muslim
        # back-reference / meta-comment / omission sweep. A2's endpoint-locator
        # sweep (إلى قوله / حتى / انتهى عند قوله) left a large Muslim population
        # that opens with a pointer head (بهذا الإسناد / بمثله / مثل حديث X /
        # نحو حديث X / عن النبي صلى الله عليه وسلم بمثله) and then delivers NO
        # narration of its own: a bare back-reference to a narration printed in
        # full elsewhere (_POINTER), a meta-comment on transmission
        # (يزيد بعضهم على بعض / حديث فلان أتم وأطول / واللفظ قريب من ألفاظهم) or
        # an omission note (ولم يذكر X / وليس في حديث فلان X) -- both
        # _EDITORIAL_DISCUSSION -- or pure isnad scaffold (وقالا عن فلان)
        # -- _CHAIN_LEAK. Every candidate was read in context one at a time
        # against the discriminator A2's own commit stated: a record that DOES
        # deliver added wording (وزاد Y / وقال Y / غير أنه قال Y / a genuine
        # matn clause) was left SCORABLE, even a one-word variant, because
        # marking a genuine-wording record unscorable is a MISS. sha256 of
        # text_ar recomputed from the build (never hand-typed). This resolves
        # the 1644-3-vs-1532-2 inconsistency the review named: 1644-3
        # (بهذا الإسناد مثل حديث عبد الرزاق) is the identical pure back-reference
        # class A1 already marked 1532-2 (بمثله) unscorable for.
        'hadith:muslim:1040-2': ("f12ee83b5a91fd2b8ebe0ddbd07008062fa099fe98f244de1b0f68500a9f11d9", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1060-3': ("46d976a92d8c6c60bfc2dc69c39301cab1fb4e4e145813477cba820714fa0005", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1066-3': ("531a3b370c91a1a46e5fe2a22c881579151f95164b70262fe1eaf6f1c0bde10c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1080-15': ("73ce1bdf6f42eee61bc844a1f18dc417752c5f9421585b410973b1cab8a7019a", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1107-2': ("3028f9f24527b2e434069461db782a9d086f9adf0dd91bf96576286e85bc0de5", _POINTER),
        'hadith:muslim:1123-2': ("a4b7239158012663fa6aac7b3bf3630ba8545f4edd3e4f4663cbd5fdd638c248", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1130-4': ("a8c817f91e0ddcfa9a18573bc55e2aefbf960f82109527bdc469f6b4a178aaf4", _CHAIN_LEAK),
        'hadith:muslim:1146-4': ("484aefc7f9e99d4f94bdb0e3793e22cc2c8acf8c708f3c2cc9f241161238ae88", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1199-4': ("14aa443d3baf343d69b15e0d0364286f84562fba76b305277633d3d164738eac", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1211-34': ("179b1ad4f3c47741c66725ef6987b1c305e0588d0fa88f39407fa4504972c24e", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1321-13': ("d796e4ade2127e7d93ae6d3803ee4b4901c52a634bbadafe771d71e50d6f9216", _POINTER),
        'hadith:muslim:1341-3': ("d14d701a63bd2eb1b20f8e156b82351b80b93df84fe1ecbbc017388b1281ab5c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1360-2': ("81fe3bd1304455da9f68c0c1f3b071c3ccc5ba769f14b8e6f235ced72e42e792", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1398-2': ("84bc6df18274306bda1a5673e75fc795a3cf73a03b8f9721a6de163ad33b6cd8", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1399-9': ("c86187faa85e615228623a899840c88ea6276ba52fbf8be5abeb79f54fee4451", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1416-2': ("ac66d24b2d434f44a4adadfcc09e12e2e80538413b9f27c649359435faf2ce1b", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1419-2': ("bed17a10c3673ef6bd0d7aec941537e8e55a6e104ebf0285212bef016e54bbf0", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1423-2': ("40e880b319c413098d2174ddd5b8ffb7b12d8eafb4f988e82047aeb8be2c6f96", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1433-7': ("9f164bd16372b50ccfa923bc3accf3d5f4d89c501e56d07f00fec774d1a3d8d4", _CHAIN_LEAK),
        'hadith:muslim:1444-3': ("f647250b801bcb1ecdd530a23511326c759c757d2c5b717774f01ce96b188b2d", _POINTER),
        'hadith:muslim:1500-4': ("ca0aedbfade66a8c02c7822f26afeab3695d02a965055e146ec26868f3d83d94", _POINTER),
        'hadith:muslim:1506-2': ("9bb987ad7a164b88263c45b6a99e1a0adbcca3ded2ab7d9ed92b501fbb77667a", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1533-2': ("14db54741ef00cc6c87aaa9d01ef7375cd7b8530f8b1664513e8feba3e576982", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1536-9': ("412041bde31ec1ba9423d011f1ebfb45dc60c2a7055300ef9b4d1e3fbd0e0145", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1547-9': ("ae976c973c67aa13602150423b29ee5c8592b4581bb1b903a5ccbe55281f624f", _CHAIN_LEAK),
        'hadith:muslim:1548-4': ("0396463d5986bb56250cf535eabe80291a4afe4cca6cc9a66f252dbd2dd203f2", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1567-2': ("f74c8676eea3537e68b718fe96a3d465851df8e6fac030f55079c6012fd357ba", _CHAIN_LEAK),
        'hadith:muslim:157-7': ("d03d0221b26ee253f8f658054f05efecd9488c555fc6eb7c1edc31637c139673", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1599-3': ("faf05a01c20c66fe258da31716c68bc4d33291a7e7f637fd7eff57f0bec709c2", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1604-3': ("a8fb78d0a594be61043989f8907dba4d5aec7c23f50da332cb196c3671e78203", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1615-4': ("380bf068b945ec8c65680b7c7a28ccee5760cba770c494ab3ec564ebb7dc658e", _POINTER),
        'hadith:muslim:1620-4': ("5cfa9cfeaf32896002160238eed421bd4588bab802fcf0396880308db7ebd0fa", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1627-5': ("368b73390fc627ec03eb02b19e9c47f9b4f6ae03197b0aba0da4556e3ea53212", _POINTER),
        'hadith:muslim:1628-5': ("f958c5b14f4dbddff028528c4ddb78b8644b1170c6fae5c892b4c064b73736cd", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1644-3': ("54a833e06828e493942f6e3e059ae53b4c9b2f6ad8a1be6dad7693dc30afae62", _POINTER),
        'hadith:muslim:1646-5': ("196ca9a81f6b79f2493ac467a5b555cc8e4e9e4b444af434e79971b5126fa132", _POINTER),
        'hadith:muslim:1652-2': ("f8292237693eb8df412e143dce12f416aade7ec9e4b6c9ff4d68b73875687d07", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1659-5': ("5f7e736d2d4f532fc23b489aa3560b073b63fab9240f25c445e8a09fac4cd786", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1665-2': ("6228f1c101484392bc139506c660a76d9ccde10013e0df8cc50cbb60e321e12b", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1682-3': ("0c6aee5f0c785f23ee397b1923717ebd5643dbed66211004255c29aa4b629d02", _POINTER),
        'hadith:muslim:1691-6': ("bb84c7966b95162494384739e3deaa479561fa51d6ff2c05990405bfcfb0d353", _POINTER),
        'hadith:muslim:1716-3': ("e51beab3ac9eeca23319e474ac13ba44501d0a333f6c6d1e3ee69ae221636c68", _POINTER),
        'hadith:muslim:1720-2': ("22fbbc13270e176c0e6308875a2668b9bdf42567dc19a63b085b7a5d16bf3d63", _POINTER),
        'hadith:muslim:1762-2': ("6cd375666344d93aee90e4e992b1101ac5ee44d5cdeb00274751ec0e1404581f", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1766-2': ("fd38295d96b5e942ffa7a2f9bf77e322abda7ff85e472a719841a36c92f743cf", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1821-3': ("6948f8fab32882ba5f4eb1a2b7dced0a8c2efc8e0fddb8f86bcfda5d9335920b", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1835-2': ("755a4c316b879068445d4d35da1032658261012054bf18632fe55141b52dee14", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1845-3': ("c37076686fce0f35f7d43647488f9b48885fe3281173f0d46e224de49be259f7", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1854-4': ("638119f1f899f147830b03c062ccb8d264289d1c2972f189c20d24ac30aa039c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1875-3': ("a682be8aaf75641172a3f71260213538bf86046d8f99bd1d24b4c0fcf4666638", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1930-2': ("e4b11469c20eedc647d912752fd68bb9d7b6a292055db98b4a48f203c630d13d", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1961-10': ("06f8ab4cfaab46b0707543b7c97c4d5d6a6d3f76555f8cfcc8ac2f44b7756c2c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1975-4': ("85cc648f64adcc3b98983e1b76e7ae5fc82eaa9b84687247f23b500d3b59d0f4", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1997-4': ("82877f360dd22bfae5669f30417af864399ef924f0700202124b0bab17f605df", _EDITORIAL_DISCUSSION),
        'hadith:muslim:204-2': ("7be4b101ca4a03b18494fb8d52576f9037764fbbdb135261ee992dcb3c792ba5", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2042-2': ("74eeef472ab72c6a483311224f1c74fc628a67c32cb8e009a976decd2f0c5cf2", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2045-2': ("680b80d48a712ef3bb5a9d3b24137492f2cdd75585c0cdf9cff5e15299479d08", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2069-8': ("38e29d8dc7ef20d8e95b01648d3f85cb73da75b13c0a530d7c985eca1a8d623d", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2077-2': ("f3c6eb1266da8ee18ff5611a44d41c3768cd5121e138f22a1c755ef4ad4de9ea", _CHAIN_LEAK),
        'hadith:muslim:2094-3': ("75b268f45e67e718e0454586eab4b60852f534860c8aed9a0bbf9d690592d8c7", _POINTER),
        'hadith:muslim:2106-3': ("992edb6b0e5c579a97886b80094cbfc676892360d97b76075f498f2875a1f1f3", _POINTER),
        'hadith:muslim:2107-5': ("d8735569c887840c61cddc304d8865066d3d12cebd43c290df84f9afb1e57bd9", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2108-2': ("f2ab295351a5ef58fa83c147d84221151875cfc718032ca998cdb6349732c7d8", _POINTER),
        'hadith:muslim:2120-2': ("e43ea0d50b718e595a237b75ac24c7879def893b08cba96fa3ee29ba72ff256b", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2130-2': ("389e2608b69e7ce7fc0d646e5ca8fac12f2e261a85b27a0f912a69025b27d7d2", _POINTER),
        'hadith:muslim:2133-3': ("8799fb17f2ed12d8da8358cdc026574ad3503cf22528c60314f07a60e063223a", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2133-9': ("cd6cd6a4fbad13d4cc8ace7fc7e36df27f19659011397660da24312de37c40f7", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2152-2': ("785961ec23262733e70de1a12493cf870e8d863479abf20a0280cee845832403", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2153-7': ("5c29f1e8d42423e71f6e95ae220f28864fdbf40ae4d31bcd4c4e16ad691fce8c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2159-2': ("d9268f99fbce5899cf9ccac2696dcdbac96fbcac426e27511f05435843933614", _POINTER),
        'hadith:muslim:2203-2': ("acd4bfcce614f9fa4906b6b589fcf7a757996f2551ba60f7edb0e5dd1e741a3b", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2207-2': ("4312f3dacd2a6b1765fa43c1a5d7665bcc8a0848463ed8ca7733f1d02e23baeb", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2218-9': ("04cd409f40505df63d9c40ccacd7afe7da22ec0b3df39794004d738cce994a36", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2228-3': ("1813c1697251f5b49bb51321cb9fbc8f1c49fa1f30b768a0e982430d3795cc9b", _POINTER),
        'hadith:muslim:2261-2': ("17562090fd5759762c9c36e40ee2386f60869810a4ccb2acd29b4b3ce79f5c86", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2263-9': ("582cbdb4031572bbe3b35a05151785fb50c400ebe016cf53b81c74dd9d9519e7", _POINTER),
        'hadith:muslim:2289-2': ("3028f9f24527b2e434069461db782a9d086f9adf0dd91bf96576286e85bc0de5", _POINTER),
        'hadith:muslim:2297-2': ("b779afd1c3a8eac4423a9cf0d965285a2a22c2c4396499997f3950a6f950620c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2297-3': ("1b738166870923dcdada6dec9e8c551a136953623e1f7b5b8e00514bb8c5a3a5", _CHAIN_LEAK),
        'hadith:muslim:2328-2': ("7178086b2a75d7eeba9550b1e2d9670eb3f94959c61c1723545cd1fd620bc776", _EDITORIAL_DISCUSSION),
        'hadith:muslim:235-2': ("72c67b582e199967c2fd0dfffe7c966dcfe5d3a10387d13d5705644846043709", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2353-2': ("dbddb1e59081741085469399174384d2a886045097f773b85034442aa413b023", _POINTER),
        'hadith:muslim:2388-2': ("1ad75397a61947fbe478489ca5436c80edb13b6d9c03b88da569ef3bfbb842d0", _EDITORIAL_DISCUSSION),
        'hadith:muslim:241-2': ("ed13e759ceecc1b55a259e5043ec22bed9d3d0d454b86e50f30c2c2ca16ed62b", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2446-2': ("b1400b29da281fe27518ce3f628b1eacdaba0ab48a097410b6ce05e78f80ef30", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2468-3': ("446b394d87f9bd6b208b3a793bd374a54a9ade9f19f8578e7a92c6c5b705a366", _POINTER),
        'hadith:muslim:2471-3': ("fa19b11353cb9117e2597e3ea24397a6429e6b59477aab856270ac8c08d1ba25", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2511-3': ("cce8f49248b631a6666729d9bff17d1ba8aad3e7f7b682d22f81111282ecd632", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2538-2': ("65a7700793aa533e3b40831b2684ac7629495d078499d306a2090a4dbdec3072", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2577-2': ("46c939541eb638c7de3ece90d8223498d4f98482ea314ba960ff57a39a5620fc", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2637-2': ("60c44483fa83849632dce9e518c652235b9b660258ecd15e69e85c48ddcd1da4", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2675-2': ("994225445f10242ac889b70d340bf2b4db7552f45babbdf9030d79540d432b73", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2675-6': ("2f7946ebaaf4b590c14315a39187c6aa1d5ced4ede7a985bb958a41c99f3dfb8", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2699-2': ("05c0c60eea4d6d87dd5ba2d25ee97f35eed28c1973fbdccca684a87029370a46", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2730-2': ("182a6548952fb16575cc46803b92ba65841993edf7baef31d0d14a70872832ea", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2732-3': ("9873add7b51432e13ba888a9bbd99eb1a63a31fbb8bef1d10e45946cfaf6258b", _CHAIN_LEAK),
        'hadith:muslim:2761-2': ("6fc6bee3e70e476baa2b6c5b9a233d64b035df1c13dbc1f9e103736844f0fb6d", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2767-3': ("d570e28ec7b2d83021121415da431c7b1174e8ced37796c516f988921e25a214", _CHAIN_LEAK),
        'hadith:muslim:279-2': ("a07b755624bf476265a5bd56fade9304cd26abdfaaa0bce1e77fa23e5d5c538f", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2859-2': ("7d2902c5734d45b6b09f8c64569e08a334f82c42350a1466d957df55546dbe2d", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2865-2': ("07829445eb4b1630fc5c43da48532eccc0e959440500acd0dae5fd810ef2a182", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2878-2': ("cc5b5d55306ccc4713e516e2cccb9168a62b0c251b801299e3f5fbfd92e48908", _CHAIN_LEAK),
        'hadith:muslim:2880-4': ("60cb96f9fa538b1a4431dcfcc3c87e1c114c94e76be4e845a32f9d31f28a6a42", _POINTER),
        'hadith:muslim:291-2': ("7e41f51474561602627c3c26f224698c757578bad9e6478634b266811ffb4488", _POINTER),
        'hadith:muslim:305-3': ("df059a3c26e4d28cd461939c77940cf1c16738c8f15808d57ade1a9574f1b405", _CHAIN_LEAK),
        'hadith:muslim:360-2': ("3c8cabda07574ae5066c03be84da05d6a9fcab55fea015f4c902b8f4fbf90467", _POINTER),
        'hadith:muslim:402-2': ("2b304e604dce4007d247d6b46565079b7cae06392727d757d86260cfd8c0684e", _EDITORIAL_DISCUSSION),
        'hadith:muslim:406-2': ("4b7c03e54bc2cba31886b14f4270a6358437d637fcd9604e6173f1f0adae6c3f", _EDITORIAL_DISCUSSION),
        'hadith:muslim:426-2': ("a9d6738bc1bdae2a2153fbd6d1b084da51f94440223f0454173d4dbb82247a8e", _EDITORIAL_DISCUSSION),
        'hadith:muslim:52-10': ("ad700f3a9e208b289076f3cf9a4652feaad53e2fb39b04d87ba99a93ef088a79", _EDITORIAL_DISCUSSION),
        'hadith:muslim:558': ("ca831edfcbd40db31ef8e318ea501ebb93659d3d1caba097146f2481fed49c68", _POINTER),
        'hadith:muslim:560-2': ("a34145de06b861cdd9fd0d9e9212276618143b99e59908ab12b692bddc4ec117", _EDITORIAL_DISCUSSION),
        'hadith:muslim:578-7': ("cd53673c03dd99f0238a5ebf5f376e18eed01a687b410375a9a106ccd74d4df4", _EDITORIAL_DISCUSSION),
        'hadith:muslim:593-3': ("247de002e07e2464f32ccbf7c579f004557afcfc63683299ce6c298f94896cf7", _EDITORIAL_DISCUSSION),
        'hadith:muslim:638-2': ("00f25fe5f6fe940c6987fce2dfccde8bd6a9299da1f546730167666e496219b2", _EDITORIAL_DISCUSSION),
        'hadith:muslim:640-3': ("42549fd45b26ab66b8b1c4734da5780057266e9e1a06fccf2eb6cb5c9a1598ce", _EDITORIAL_DISCUSSION),
        'hadith:muslim:699-3': ("958c7663f790345073f8ececbdcdfd631c6b400bf1ccea97f39e9fbe30344dcc", _EDITORIAL_DISCUSSION),
        'hadith:muslim:709-2': ("3112bfc360bec947446a40f5069b327aa90fe3bf4344032718586e11de6e41e7", _EDITORIAL_DISCUSSION),
        'hadith:muslim:735-2': ("4cccbdf2b0df47a4b1877d1d6c8d41e00dc976ec0f3372a293a3ed64aa7e8582", _CHAIN_LEAK),
        'hadith:muslim:736-3': ("c72a5eca478944abcf5a48a949b81773af95b4bbf8fff269330c07606bbc7a86", _EDITORIAL_DISCUSSION),
        'hadith:muslim:758-7': ("a882d03d0fa6811819d0ee2318b2c16d631e9d2235723434cf95295870c62e16", _EDITORIAL_DISCUSSION),
        'hadith:muslim:762-3': ("7d9d00d230b08854ccc7098da6ea5d504bb700e14f96f07017685f9a2420c43c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:769-3': ("c1425868eedb74280c87631dfd412b2fbaa852aa7c9b17be0dad264f71673a3b", _EDITORIAL_DISCUSSION),
        'hadith:muslim:80': ("ac64b673986af50d5daf9aa20a92b05dddf6fab565a707c9154cce54bd0138ea", _POINTER),
        'hadith:muslim:801-2': ("0a4367156b7b32651a809b0fcbb7f1467b4b73afc2fa30e8fb46e4eb5ce1f370", _EDITORIAL_DISCUSSION),
        'hadith:muslim:817-2': ("74de6722ad7ca542dd6fb232718356d91549991ae8b38641db8d4356136247f9", _POINTER),
        'hadith:muslim:892-7': ("1be57b7590276b38f70e393584866dfad6b3e4cd1ccb8b052a38b8958f7394a1", _EDITORIAL_DISCUSSION),
        'hadith:muslim:923-2': ("531156c7015781d069b6f3e776ad805e76e23dd9f6554108a3e9b5db9a7f88c0", _EDITORIAL_DISCUSSION),
        'hadith:muslim:932-2': ("39b59fbe9629b4ec9218e25d5f341f3eac1895d8095d092838eb7bdf5fb520cb", _EDITORIAL_DISCUSSION),
        'hadith:muslim:941-3': ("783d964c4a7b013fbd805d12668c8409f2912ac97b9ce7b97b48452bcb2a1aca", _EDITORIAL_DISCUSSION),
        'hadith:muslim:954-2': ("87d9347046dd9e2ed9a7dcde8c78840255283e98bf68f3040e26e88cb6410167", _EDITORIAL_DISCUSSION),
        'hadith:muslim:954-3': ("24e308c04735b5ef8dc5c13a17d7cd4ddc8adc486efbc5be6eca4ece550eaaf8", _EDITORIAL_DISCUSSION),
        # --- A2 round 3 (Task 16): position-independent whole-string
        # sweep. find_pure_pointers() flags scorable records whose entire
        # matn reduces to back-reference/chain-meta/deferral/omission
        # scaffold with no quotable content, regardless of token position.
        # Every id below was hand-read in context (isnad + addendum) and
        # carries no Prophetic/narrative clause of its own. The seven ending
        # in a bare pointer after sami'tu/kana/naha/an rasul (524-3, 1515-5,
        # 1622-2, 2191-5, 2919-3) share the exact shape of 137-2/970-2/1299-3/
        # 1590-2 already above -- the whole-string sweep caught what the
        # earlier first-token passes left scorable.
        'hadith:muslim:137-2': ("a4ac37bcd6ce3f62a45f8835025f1218f5a182787e7484be404a660cfb291661", _POINTER),
        'hadith:muslim:144-6': ("d14a284c0e70e066c02ff7a43a8d9c6b64bec789303d3f1133185f8b621824be", _DEFERRAL),
        'hadith:muslim:316-2': ("90ac34e332ba7f22b6fcbce1d7a6d87c94c34223a9f7105ab228f39214aada83", _EDITORIAL_DISCUSSION),
        'hadith:muslim:524-3': ("566f33daa057a14e77be125dcba5505f5ef17636e775a98fc57c5b4207f9bedb", _POINTER),
        'hadith:muslim:635-2': ("191ccce4db67395d6391c9d38be13358323ff59b4d93bc68c4b7fcbac0daacaf", _EDITORIAL_DISCUSSION),
        'hadith:muslim:727-3': ("967845751d8691a13e0f632957053ee2688ea364fd920dce31a67daef9156771", _POINTER),
        'hadith:muslim:903-2': ("d0e4629d03a2196027fd9f91ecd21f5c2a459f3314c6a27fb5ca9bc903888059", _POINTER),
        'hadith:muslim:963-3': ("24ce653eeca60248a55d04d883fda2113235d86e3e00ea48ee5cf89b8894f8fb", _POINTER),
        'hadith:muslim:970-2': ("f881767369c6e52d892026711d97e06c65a0a2f9792c70d531ebc6e2f23eee63", _POINTER),
        'hadith:muslim:997-5': ("a1fea0c1b6d0ba398bedfcffcfd230c542906e78e99df7a2731e5156f8edaf68", _POINTER),
        'hadith:muslim:997-6': ("5dd852207bb52463eeebc1590704d13a1e75e77433d31e1cbb14bb7477f33b30", _POINTER),
        'hadith:muslim:1092-5': ("c2b56be58b7ec4444b2ae4246e1f6831d258bdb2229f632cb0b5ac6b18b78c41", _POINTER),
        'hadith:muslim:1299-3': ("56cc63740994bc22e21b65432027134268600c7e277c9bee0ee327dbf5142fcc", _POINTER),
        'hadith:muslim:1317-3': ("b62c40b949e0bda6213575448410b76833d652a914fc037e8f38e866b4c5f50c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1515-5': ("39e18a891419cdeb4ed17a62d5b9ef66b4404244bfd146ee000faa871cec13fb", _POINTER),
        'hadith:muslim:1590-2': ("4625a8ebefda5a84954a58d67ad577a20aae1466db31110308a876dc1cee83d5", _POINTER),
        'hadith:muslim:1622-2': ("360da5c251cfe4ae95fa5f34953aa9f9f5d0923272d77e7cb09d10cc67e08485", _POINTER),
        'hadith:muslim:1649-5': ("b4c314f720edaf7ff4f79c4c8a6d3c4ff9372fdcb26e5b376e29320dd69e4373", _DEFERRAL),
        'hadith:muslim:1897-2': ("7248357ff3701c53afc8a935c9814db5c517c1c51afa7cad20d514e0b799eae2", _POINTER),
        'hadith:muslim:1905-2': ("cf96bd146e5d0cd876bbe7506064198c0f01836e81234343e88027b4300bc343", _DEFERRAL),
        'hadith:muslim:1934-4': ("b3180c1f073a0508cdfed856f0d4d940ee3352cbb1488439cf8cc5a320ea8549", _POINTER),
        'hadith:muslim:1955-2': ("fb71ebe16bf14dcb03c3b39516aa7f80a0f236a5ca5b160413195fc8cb9eef1d", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1977-9': ("5f718bd1e301ed0a116318b83f0e3415935e7bb86ed20af3c7daa6480676cdba", _POINTER),
        'hadith:muslim:2036-2': ("356c0a783de02a04f8bea9361fca16525dc236c30596d8400bae01a7fed574e7", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2116-2': ("5a356de71a02304a1ede0f8c97560bf444d2b36591a3d65a26ceb091d78a3b9b", _POINTER),
        'hadith:muslim:2120-3': ("90d39917db3b061af4ff5d5b41ca53c69f1e007ceae267b513adcccf0ce9fb7c", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2191-5': ("97046c8e3edad983341ebfc59b80d91a4c220eca2ab7c04240dea3b71d603045", _POINTER),
        'hadith:muslim:2267-2': ("e51942bfd87da598aca24e7cfd87773957d004f2db31db105edce5026e362c3e", _DEFERRAL),
        'hadith:muslim:2291': ("0f18c7fc381b378d3b15ffecd504788163a96b5e26860f729918c48dbed1bc42", _POINTER),
        'hadith:muslim:2408-2': ("3a1dfd26488d6f86e5c5de5634ed1906e074416e885b9b13e6da639f0339435c", _DEFERRAL),
        'hadith:muslim:2461-3': ("470a302b3b04c77f0498df800af5e35da9920a1e8108c3befd447b7910ea7fd1", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2645-2': ("d7154516451f0f81d5bedf849d255c14701ea05b917f313b620ff3216fe4edca", _DEFERRAL),
        'hadith:muslim:2652-5': ("25892d0e6a0e1b264992566d1c9035b048a526f68a2ca033c41e8e9c0484bfc7", _POINTER),
        'hadith:muslim:2817-2': ("e331a4ae881e65bbe834dcfa9d8013f16a6aa138536d31ae6cc39c4085c1d21a", _POINTER),
        'hadith:muslim:2821-2': ("9a19f95d72b519a215d38d90306d6f7add5c16cd94d2849a22ac32a61e445fab", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2831-2': ("f98016d68839a0a60f6f6acf3570d25934c213109bbc8c464a195dcd4df24825", _POINTER),
        'hadith:muslim:2880-2': ("c32691f4770524333d7e3a82c3e156c37dc13902bf3d8a3e6f36d08cad3a73ea", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2919-3': ("c1e4e0c700868aab6487d214cb06732f3849cad364d00debdd0c0b8c7dc0d9aa", _POINTER),
        # --- A2 round 4 (Task 16): editorial omission/comparison sweep.
        # Pure-apparatus records the residue sweep could not reach (its
        # delivery guard hid them); every id hand-audited in
        # task-16-A2round4-audit.md as delivering no narration of its own.
        'hadith:muslim:1162-4': ("cf5e0614033eaca29e26420ee88917eae6e13dc99bc50340693d00004061c912", _EDITORIAL_DISCUSSION),
        'hadith:muslim:1178-3': ("2ccc0203cd04696b5d45c2dd8d423e1209722fcf74a864264b33381d490f1578", _ISNAD_COMMENT),
        'hadith:muslim:127-3': ("9217dafbe5ede8c3a8422311a9e87653456bf1d41a644ee66889fe02477a368b", _POINTER),
        'hadith:muslim:1306-3': ("075dd8af83cff35bebdad70595f5b48a4b5252c04d6858928a550f014d9427b4", _POINTER),
        'hadith:muslim:1315-2': ("36ff06876eecdc664778f2ef4dd827a81e31995387827d2a5f9e472eaf18966b", _POINTER),
        'hadith:muslim:1317-5': ("3a5addf9fe0031a2800dfc7b2d1774d11fadf4c9157d46153d03b83fda9f8c11", _BARE_RULING),
        'hadith:muslim:143-2': ("f9d436402de04d5a52fab48624400c4eccf7ca8d7649f666a3e355ba55576458", _POINTER),
        'hadith:muslim:1530-2': ("a19873a47a7b49e201da91d74d132db05a7deb28b4876545573e7e85311ab030", _OMISSION_NOTE),
        'hadith:muslim:1676-4': ("5a2702611ff60cab05a025576dc15290a6661090fd87088db9e5325fbd9202a9", _OMISSION_NOTE),
        'hadith:muslim:168-3': ("37d5d80b361287faf3401731422e07663a82cc46b5f3edeacc4067978186287c", _OMISSION_NOTE),
        'hadith:muslim:1733-2': ("01958a49319f3e30869dd94ea62296d0e7f007a8ab29078abe0ce2f5d7895d80", _OMISSION_NOTE),
        'hadith:muslim:1736-2': ("ee058ccaf4bc37865be85d13d87b86c54235a88bd820af788225559b6a668f77", _ISNAD_COMMENT),
        'hadith:muslim:1774-2': ("15a65340aa1d1d6ed9424e29ff304d5eaed85de0b4c49e109d6280b3826a96fd", _OMISSION_NOTE),
        'hadith:muslim:1774-3': ("f22d238c2ff1ea0cac838fd6e82d76f211c696ee3c80f1376e7ba093329fc41d", _OMISSION_NOTE),
        'hadith:muslim:1873-4': ("9f342a4619f626a9eab34de7f74f5fc44d8793d5ef2ded56492282bd3c3d48ec", _OMISSION_NOTE),
        'hadith:muslim:1990-2': ("ba390747c455089a6c6cadabe8b64e224e7b6083af77b30d8ddd56a19001dae3", _OMISSION_NOTE),
        'hadith:muslim:2092-2': ("6492b548f1ba17ac8e716fd193ee8a9ecdd7bd33215dd0247398df36516ee012", _OMISSION_NOTE),
        'hadith:muslim:2137-2': ("d8efe40adc92a3354bb61133a6102b728a9b3d63e8801052d2bd7191f7bdf4d7", _ISNAD_COMMENT),
        'hadith:muslim:2203-3': ("1788a2702cf38efe04b5b67b869932fe1a86493f33968865156c41a2806f756f", _POINTER),
        'hadith:muslim:2263-4': ("390747560eabc215f2c7f63857053e6db384f491cd811997fde2f8408f284498", _EDITORIAL_DISCUSSION),
        'hadith:muslim:2298-2': ("cb2f0a829423b5bd068c992ff4d15d45b42cafe0de1e7c60f291be9da2101e19", _OMISSION_NOTE),
        'hadith:muslim:2327-2': ("58120880d802da2e42c05fbec4b763733efe0e43371704bada5143ba953e05eb", _POINTER),
        'hadith:muslim:2533-3': ("490cf0e86c59c0885e786ab23d954a679bc71c24d466aafa53ba0a50a952fef2", _OMISSION_NOTE),
        'hadith:muslim:2541-2': ("ba4de82bd9ffa50c8b39a168cc04545e32f4a1d4542238e9f4ff307d1e9a58b2", _OMISSION_NOTE),
        'hadith:muslim:2639-5': ("c69c4beafbfdda27bb3aa5b621cedc835d650bd3c4cf70ac6c7f1f3c5627da0b", _OMISSION_NOTE),
        'hadith:muslim:2653-2': ("f758ec7a87419b5027db8f02c51f45f0bc5332cc9d833c1c076bec74d2e89175", _OMISSION_NOTE),
        'hadith:muslim:2706-2': ("cf187d94b6534be6e39cd69183736e762c0b7d2cd93d5b9ab643441b117fa5dc", _OMISSION_NOTE),
        'hadith:muslim:2804-2': ("1f72cdc002805016eb9245c02030ef77ea23b7b16184c7a6501f80293460aa55", _OMISSION_NOTE),
        'hadith:muslim:2805-2': ("9daf0dbff72095747e26a45aa06aaad1272ba05720f9f4769e502984d0d32f99", _OMISSION_NOTE),
        'hadith:muslim:3000-3': ("da26dbae61f34fa6bbff74812042d56d9d41e7b742ac85127e727ba91f1b2058", _OMISSION_NOTE),
        'hadith:muslim:410-2': ("f5a4fbed8c7e7f7d42d83b2d3b02b98978a4eb83cb42753603b799408c31a81f", _OMISSION_NOTE),
        'hadith:muslim:537-4': ("fb80665c02e035e22a71108f0bfcaf73a786a5fd426e7b21dbf1e7121d02392a", _EDITORIAL_DISCUSSION),
        'hadith:muslim:57-3': ("aa5f90ff058ac75d083139e27dc7e57b14a80585263969f78f1b397c48c71063", _OMISSION_NOTE),
        'hadith:muslim:657-3': ("fc1af4f5b4ebf21bb794fa3ca3461e244e7bc2b57e2bbca9875f4af460a7fd53", _OMISSION_NOTE),
        'hadith:muslim:679-3': ("6c8f4de91761577470b8c13e6b317fe76a50a8c494217fee7c951e63b0c44722", _OMISSION_NOTE),
        'hadith:muslim:715-28': ("01bb41f85ab76fb0a2a01cb9e7a357b99b3055999ccc2e1f2ab0396e4871807e", _OMISSION_NOTE),
        'hadith:muslim:792-4': ("5cd4f059939f0b89b26f3c3bbc3a7aa87396f496963c42f9567c252bd1f1e556", _OMISSION_NOTE),
        'hadith:muslim:852-6': ("b0d47c70487a0e889e7a1449d99f63f37169d4954711b23643ea663b4f06c059", _OMISSION_NOTE),
    },
    "abudawud": {
        # Methodology (Task 12): every matn of 30 characters or fewer was
        # read for meaning against its raw-file context -- 267 records / 218
        # distinct strings. Two further records (2331, 4817) were added
        # after being found, while reading context for a candidate already
        # inside that 30-character net, to carry the SAME editorial pattern
        # at slightly greater length (mirrors Task 11's own note that its
        # 31-60 character band was not exhaustively read; this task's
        # 30-character boundary is the same kind of stated scope limit, not
        # a silent one). 103 records / 6 reasons total. Every sha256 below
        # is computed directly from `parse_openiti(raw, collection="abudawud")`'s
        # matn (never hand-typed), the same value build.py stores as text_ar
        # before materialize hashes it -- none of these 103 records carry an
        # addendum, so text_ar == matn_ar for all of them.
        #
        # 23 of the 85 _POINTER entries below are load-bearing, not merely
        # editorial: `materialize._reject_wholly_quranic_representations`
        # raised MaterializeError for all 23 before this list existed,
        # because a short pointer word ("مثله", "مثل ذلك", "بهذا الحديث")
        # is trivially a substring of *some* ayah once reduced to bare
        # letters -- the guard cannot tell a false collision from a real
        # one, so the record must be marked unscorable on its own editorial
        # merits (which it independently has) before the guard is satisfied.
        # _POINTER group (85 records)
        "hadith:abudawud:34":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:99":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:174":
            ("4987e970bbba69c24ba678fb498a4987180f72759e1bb3dc86882b42ef3652d5", _POINTER),
        "hadith:abudawud:183":
            ("562bd1fb62bb39003928fbb19c6e2d6bcd804359beaabf3fc822bd700a8cc39c", _POINTER),
        "hadith:abudawud:387":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:390":
            ("7ef13e9272e4017b6ad7f5c37f8a48959a514678ee0290e347680879d5889e69", _POINTER),
        "hadith:abudawud:463":
            ("f7ad27f58ecd8feb1f0191fca64c47d0358735d09c6fff4cae679228ec47e73d", _POINTER),
        "hadith:abudawud:476":
            ("960f14283ed989f42a5548aa5680943afff5f4cf5397c8aa4927161a323060a8", _POINTER),
        "hadith:abudawud:483":
            ("1e919fee2fe220e6794c016f24ebb380ccaf0bf537d5598abc51e30524167196", _POINTER),
        "hadith:abudawud:518":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:546":
            ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        "hadith:abudawud:865":
            ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        "hadith:abudawud:895":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:1103":
            ("06cdc939309c2c2733561594395473f43dad501f28bdc2b33b24bf04ac6ed9a2", _POINTER),
        "hadith:abudawud:1470":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:1553":
            ("59276395eab845e9666188597474d1730fe7167d893ff55dae8645efd2356b21", _POINTER),
        "hadith:abudawud:1577":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:1654":
            ("011c8c4f11804f7caa3847fb88f6384aed645b0e9b248cb7a74ec1453e9dd12f", _POINTER),
        "hadith:abudawud:1666":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:1680":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:1824":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:1839":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:1908":
            ("171e40f4d98dc34ea3d52604cfe7cbb4db5e476b15149653757a5eca9fcfd9ec", _POINTER),
        "hadith:abudawud:1918":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:2077":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:2091":
            ("4ae17f52150046848fd2ef021532f96a5c88d465e869ad22873ccbaff647f2e4", _POINTER),
        "hadith:abudawud:2127":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:2207":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:2220":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:2223":
            ("f985d6cb15daee1b15c477afdbe417d30f8df090d7b3d1a3f6c37900f1cf67d5", _POINTER),
        "hadith:abudawud:2224":
            ("b9ebbe78cd59dc81a6adf2ce4a9d540e3613418b875beede54ba136b6e83cd39", _POINTER),
        "hadith:abudawud:2242":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:2368":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:2621":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:2657":
            ("769ce066220566f0a2b9bab157034b61d51fba37d4b148d41a2b26ee7756f3b0", _POINTER),
        "hadith:abudawud:2720":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:2754":
            ("7c27ebbd459940143d35e6dd7a50f902bdbb974b7380d1f824e89ba9f78b4f72", _POINTER),
        "hadith:abudawud:2908":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:2989":
            ("3154d5d06ed75a0395800ee89174508258aa58dc83e9e7ddf422b1e944617091", _POINTER),
        "hadith:abudawud:3031":
            ("9a3f7958e121b8d9140d0dde1e31d3eb1d62023b538738307b40cd5449bac618", _POINTER),
        "hadith:abudawud:3039":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:3059":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:3217":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:3240":
            ("34d9ecf6cebb537239f918181d5720d6fa3cb2ec129e6ac0ba2689705695a9a2", _POINTER),
        "hadith:abudawud:3260":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:3294":
            ("7c27ebbd459940143d35e6dd7a50f902bdbb974b7380d1f824e89ba9f78b4f72", _POINTER),
        "hadith:abudawud:3324":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:3385":
            ("f0117b02a79b48c1ba9fb868397fb56bf4205cae7e6aa1fd0b3815a01abf137e", _POINTER),
        "hadith:abudawud:3396":
            ("129d0229f2453d0b382440f6f3c5cd164354f09b13098d67a24a180475997af4", _POINTER),
        "hadith:abudawud:3419":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:3431":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:3432":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:3549":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:3554":
            ("25ceb28df0ffd5bf83fb0e2de8e885e9c633293c3e5df6cd7bb335ec475b22ea", _POINTER),
        "hadith:abudawud:3564":
            ("bd241fabc40159813339dbc5f40ab0ed37b13709c579c4f1fde719fca9da15e8", _POINTER),
        "hadith:abudawud:3614":
            ("7c27ebbd459940143d35e6dd7a50f902bdbb974b7380d1f824e89ba9f78b4f72", _POINTER),
        "hadith:abudawud:3642":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:3739":
            ("7c27ebbd459940143d35e6dd7a50f902bdbb974b7380d1f824e89ba9f78b4f72", _POINTER),
        "hadith:abudawud:3775":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:3843":
            ("2b4686b26cc4202cf7a22de5fc105b1785b5d9aae6c667e54d6f260baa4a9a46", _POINTER),
        "hadith:abudawud:3939":
            ("230dcebff35520a3dc5fa98de41d45942d5cda9a3a62e158a294280800fa5398", _POINTER),
        "hadith:abudawud:3944":
            ("7d2d60d378a9809fddd99e366d826228d50d80dde313972d18f8b46102eedf5a", _POINTER),
        "hadith:abudawud:4007":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:4021":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:4046":
            ("839ea07db23450e0db1aed334b3e385e94da9a1e7f93749a8eebc7fc2a9cf59b", _POINTER),
        "hadith:abudawud:4053":
            ("f2dbb8f214752f88be9563cadb3f2c50eb9bd59d39540201b8e509cbfd6993e0", _POINTER),
        "hadith:abudawud:4103":
            ("7c27ebbd459940143d35e6dd7a50f902bdbb974b7380d1f824e89ba9f78b4f72", _POINTER),
        "hadith:abudawud:4108":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:4234":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:4269":
            ("43fe57a28c9bd7b6ad824cebeaa9d16a9d430d12b08b9bcc4832ad65c4e6a417", _POINTER),
        "hadith:abudawud:4288":
            ("ee3d3e414ba5622f39572107003dd7c445dd0774a79dfcf490ba76df3e677568", _POINTER),
        "hadith:abudawud:4436":
            ("112c317e8aaf5a973cc9e9bff9f41cae2614e19b8d246a09905b23a1ccd4c56b", _POINTER),
        "hadith:abudawud:4454":
            ("cf1eee3eda8aa1c5c95acb0c8cc64387011dc721d91ea17f8711d3a570239723", _POINTER),
        "hadith:abudawud:4500":
            ("7c27ebbd459940143d35e6dd7a50f902bdbb974b7380d1f824e89ba9f78b4f72", _POINTER),
        "hadith:abudawud:4665":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:4724":
            ("7c27ebbd459940143d35e6dd7a50f902bdbb974b7380d1f824e89ba9f78b4f72", _POINTER),
        "hadith:abudawud:4725":
            ("4a33bbd4fec648e3c3d33d97525be97d819ae524286c33009e39ece02d567d07", _POINTER),
        "hadith:abudawud:4816":
            ("e18fe8efa200a0d1651efa5b86290a43a3fb08b503aad1bf5d4b47006d652bdc", _POINTER),
        "hadith:abudawud:4817":
            ("a816a50f42300ed7b4b64662fdb2b10c07f096074d5c649fdba48eaceaa05e1f", _POINTER),
        "hadith:abudawud:4824":
            ("a8a7c73812255580c0acd078b018fbbb3e0a95f610fc961c5d0310109ab4831b", _POINTER),
        "hadith:abudawud:4858":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:4879":
            ("4b95e162ba2e6ba57ab9d047d7eba3c5a3a7a25bbf2f245e9e866c367d2a3609", _POINTER),
        "hadith:abudawud:5089":
            ("d5ff5b365b56218b8c770736d8e06c9da312ef6fd6a4bd27affe484f7a840c86", _POINTER),
        "hadith:abudawud:5133":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:5240":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        # _DEFERRAL group (12 records)
        "hadith:abudawud:511":
            ("f5bea57322d67f17d124dce20564a7f4813a52cd2de9f97cd251412adb57dac6", _DEFERRAL),
        "hadith:abudawud:765":
            ("c1efe1d128aaada4dd59dbcb80769d57de8da5623f39466e8fd948e17948a614", _DEFERRAL),
        "hadith:abudawud:1090":
            ("0eff6ed445c5080cfbcb8d830c7edf3d96b24b8de85a747e187c50ac9b89a4c7", _DEFERRAL),
        "hadith:abudawud:1137":
            ("0869e94302b129f22fcfb3a34e5b60276a5f209e1205e3d79e4b8615aca3bd6b", _DEFERRAL),
        "hadith:abudawud:1491":
            ("edc5862bd004c3bef89e0e4e3c8f0e64f1fa71d9a89a676789dd728c9d23ff4a", _DEFERRAL),
        "hadith:abudawud:1725":
            ("c693d4e655dd943275f62c4d048324fa1867e844eacc8cf7bf817b01a664ed25", _DEFERRAL),
        "hadith:abudawud:2115":
            ("74609cf2ea279ebf5df7cb60d8a5b4f4a684f632ffd63e0c21a4af64726492c8", _DEFERRAL),
        "hadith:abudawud:2661":
            ("e4febdddd176592181e48db22b5695190c110f8581d9677530f68c7f2c46f829", _DEFERRAL),
        "hadith:abudawud:4492":
            ("5d0f73d954547dac47c03935a09eb56b918d12e1ede03524ef72cc9968a26265", _DEFERRAL),
        "hadith:abudawud:4540":
            ("ce106a5e74858e3ba8e8ddb512f07928e54fb74674ca719ee42cbb0a9b3ef22b", _DEFERRAL),
        "hadith:abudawud:4754":
            ("edc5862bd004c3bef89e0e4e3c8f0e64f1fa71d9a89a676789dd728c9d23ff4a", _DEFERRAL),
        "hadith:abudawud:4831":
            ("f9ba6ccd5adb1731900bb4177c62aef557801e581d5211a3dee70e326170bc9d", _DEFERRAL),
        # _LEXICAL_GLOSS group (3 records)
        "hadith:abudawud:1472":
            ("879b7fa43b098b3e8d87f7fb33b2e31ac9e02971424e9aabd558d0bf62ebd886", _LEXICAL_GLOSS),
        "hadith:abudawud:2330":
            ("fde6d268e0ad23881ecb9891224a9b423d96cedcd7bb56330e0c74d5877d41df", _LEXICAL_GLOSS),
        # Fix round 1 (R-A3-18): re-hashed, not reclassified. This matn
        # always ended on the compiler's own remark about a wording variant
        # ("qala Abu Dawud: wa-qala ba'duhum ... wa-qalu akhirahu") fused
        # onto the gloss with no addendum recorded; the compiler-commentary
        # split now cuts it into an addendum, same as everywhere else in
        # this collection, leaving the audited judgement about the gloss
        # itself unchanged but the string it is pinned to shorter.
        "hadith:abudawud:2331":
            ("fde6d268e0ad23881ecb9891224a9b423d96cedcd7bb56330e0c74d5877d41df", _LEXICAL_GLOSS),
        # _ISNAD_COMMENT group (1 records)
        "hadith:abudawud:3339":
            ("984ed17408172c47bebde49b241fcd6aa34b1a956b2cd5dfe49d443877ef2894", _ISNAD_COMMENT),
        # _EDITORIAL_DISCUSSION group (1 records)
        "hadith:abudawud:2225":
            ("4962a4a5d9de063d9ae14dfcfd01add40587995affa8ea9ab65ab2edfbf0e7e3", _EDITORIAL_DISCUSSION),
        # _QURANIC_QUOTE group (1 records)
        "hadith:abudawud:3979":
            ("4e22b391af1063beb15250b34a5f3a305c7e5988566ea1277d5927406cbeb778", _QURANIC_QUOTE),

        # Fix round 1 (R-A3-18). Once the compiler-commentary split (see
        # _split_compiler_commentary in openiti.py) cuts Abu Dawud's own
        # "qala Abu Dawud ..." remark away from the matn it follows, 806
        # records' primaries change -- most remain genuine narration or a
        # genuine short hadith/legal maxim in their own right (no length
        # floor: "khayrukum alyanukum manakiban fi al-salah", 29 characters,
        # is a complete Prophetic saying, same principle as the module-level
        # note above). This is the SAME 30-character-or-fewer methodology
        # applied to the new post-split primaries: every one of the 59 was
        # read against its own context, not matched by a length rule; 35
        # carry no independent content and are listed below, 24 were ruled
        # genuine and are NOT listed (e.g. 644, 672, 1056, 2085, 2371, 3949,
        # 4965 -- famous complete hadith/maxims that merely happen to be
        # short). sha256 values are computed directly from the fixed
        # parser's post-split matn (never hand-typed).
        # _POINTER group (26 records)
        "hadith:abudawud:180":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:263":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:308":
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:abudawud:300":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:960":
            ("450b81376543cf334f12e425e9ad8c000d8fb69893f8b9705d3b95da70db9d6f", _POINTER),
        "hadith:abudawud:1302":
            ("913d1207fb420a8c9f47970049e9b6b85ea18aa7f51d1fbceb44dd39ddaa6927", _POINTER),
        "hadith:abudawud:1405":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:1604":
            ("79e8dd47cfb13b6383da93d14d689791fbf478c920f2902e89882153f164ad4e", _POINTER),
        "hadith:abudawud:1636":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:1948":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:2084":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:2097":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:2397":
            ("3e2719391b26ba384c79ae0a238838189cda2b512e8f99444f8aad6574c1c069", _POINTER),
        "hadith:abudawud:2468":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:abudawud:2580":
            ("6ce00316c764b2675f1ceace463f844cb4c5466e4d98f0c7c8239b2e1dad9f81", _POINTER),
        "hadith:abudawud:3162":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:3226":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:3291":
            ("68fb1c5a26ec091db95c9d939e6f8ccacb80fb0745c12f8fd661bc481eba118b", _POINTER),
        "hadith:abudawud:3434":
            ("028333e66a88ac6b39f8cdebd0648f2e7c33cc553b5566dfb18629aac195a5ce", _POINTER),
        "hadith:abudawud:3552":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        "hadith:abudawud:3952":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:abudawud:4013":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        "hadith:abudawud:4022":
            ("79e8dd47cfb13b6383da93d14d689791fbf478c920f2902e89882153f164ad4e", _POINTER),
        "hadith:abudawud:4118":
            ("2e7ada394e710687300baa23caa51ff5d56288fdaa3b409b3db1a90546ed05da", _POINTER),
        # "bi-hadha al-hadith wa-qala tis'a sinin": the pointer carries a
        # terse numeric-variant note ("and he said: nine years"), too short
        # to be independent content on its own -- still no report of the
        # Prophet's words.
        "hadith:abudawud:4287":
            ("3d3e0784397e009665e591deb424070a2ac8166a85233768365991c2fdb2ad58", _POINTER),
        "hadith:abudawud:4571":
            ("c62d9ff34bb102eff56b0eb3aadfa788def273b576972b6983018a65cc6efbae", _POINTER),
        # _DEFERRAL group (7 records)
        "hadith:abudawud:209":
            ("cc41df59fa86232d6a530172c552a0fc497d209482df305027d8fab0084019f6", _DEFERRAL),
        "hadith:abudawud:533":
            ("edc5862bd004c3bef89e0e4e3c8f0e64f1fa71d9a89a676789dd728c9d23ff4a", _DEFERRAL),
        "hadith:abudawud:1200":
            ("07c48d0353117fb7115d8882083ff3a081f2f5385cf474cab28f6f2581b37ea8", _DEFERRAL),
        "hadith:abudawud:2585":
            ("6c84810d07e033d654598d893f5ae7eb7df13fa700eff615961df3fd7f2ecc7f", _DEFERRAL),
        "hadith:abudawud:3100":
            ("9caaeec483d7366df3a9ee275daadb599a957f557fa8d1430d2dcbc5496b46a4", _DEFERRAL),
        "hadith:abudawud:3604":
            ("5d0f73d954547dac47c03935a09eb56b918d12e1ede03524ef72cc9968a26265", _DEFERRAL),
        "hadith:abudawud:4897":
            ("bf220a6dbea3f2402f6837ba6214511e5e24ed6de1ac1072691fdfd8dfc32897", _DEFERRAL),
        # _EDITORIAL_DISCUSSION group (1 record)
        # "bi-ma'nahu lam yadhkur al-kharif": a pointer plus Abu Dawud's own
        # note that one narrator omitted a word from the wording -- his
        # remark about transmission, not narration.
        "hadith:abudawud:3099":
            ("39d67a28336b3c7f5b25a7a40a76f46d84898a2a2b3f0de523c33cb3ccb9f0da", _EDITORIAL_DISCUSSION),
        # _QURANIC_QUOTE group (2 records)
        # "fa-yawma'idhin la yu'adhdhibu": the qira'a-variant hadith's matn
        # is the opening of Qur'an 89:25 and nothing else -- same pattern as
        # 3979 above, verified against the shipped ayah text.
        "hadith:abudawud:3997":
            ("c5bdd233228644e105944a03bda42b7429d57cf47a02a91e71c7014daa82e881", _QURANIC_QUOTE),
        # "bi-fadli llahi wa-bi-rahmatihi fa-bi-dhalika fal-yafrahu": 33
        # characters, one over this task's own 30-character scan boundary --
        # found not by that scan but by materialize.py's
        # _reject_wholly_quranic_representations gate, which is exactly what
        # it exists for. Verbatim Qur'an 10:58; the addendum "bi-l-ta'"
        # ("with a ta'") is Abu Dawud noting which letter a variant reading
        # uses.
        "hadith:abudawud:3980":
            ("ce73cb2280b432685a1dcceba0c6ad25b279a1b71ba51d49f271f4dbe71e3fc5", _QURANIC_QUOTE),
        # --- Task 16 A2 fix round: the same broad back-reference / meta /
        # omission class, swept across the other five collections. Abu Dawud:
        # 6 records, each a pointer (نحوه / بهذا الحديث) delivering no narration
        # -- an omission (لم يقل هو حرام / لم يذكر ...), a bare back-reference
        # (نحوه عن النبي صلى الله عليه وسلم / وذكر الصلوات مثل معناه), or a
        # truncation/meta note (وليس في تمام حديثهم). Read on full text; records
        # delivering added wording via قال/زاد were left scorable.
        'hadith:abudawud:1349': ("20728f511a6814286bd5b3db32062f05013906a688d621ad746d1da0ce2bdac5", _EDITORIAL_DISCUSSION),
        'hadith:abudawud:3487': ("3b50c8277c32f34071788b97d8e5c0170f092dc80d9c3c97bb0712c0d49eec9b", _EDITORIAL_DISCUSSION),
        'hadith:abudawud:4322': ("a78def8ffb780e43f18f281dbbb897c982331f449fbc388892f117a14e3d7fae", _POINTER),
        'hadith:abudawud:4453': ("70387aefa94fdb0b4c76c56f49060dd05119202e7e83019e487c23bac1cbca92", _EDITORIAL_DISCUSSION),
        'hadith:abudawud:5032': ("62d458cbb29ee914992f0684067b44bae31c8aee4862d53d88da19bdd87730bd", _POINTER),
        'hadith:abudawud:5175': ("8ce13b6c9fb62a1df9c251cde1f2f2e690cf0d96388863e6f767d034c8bec2f2", _POINTER),
        # --- A2 round 3 (Task 16): position-independent whole-string
        # sweep. find_pure_pointers() flags scorable records whose entire
        # matn reduces to back-reference/chain-meta/deferral/omission
        # scaffold with no quotable content, regardless of token position.
        # Every id below was hand-read in context (isnad + addendum) and
        # carries no Prophetic/narrative clause of its own.
        'hadith:abudawud:1695': ("f336406aba711cb7652fcb29ef295ca2deea466d32401eb40b32372155ea0852", _POINTER),
        'hadith:abudawud:4548': ("aabd01ea97ab4eb0d840ae39d993606e7ba18ec0ef254279319af67f528b8fee", _POINTER),
        'hadith:abudawud:4555': ("bc4abff7dd321a6196a80d6ae54ba3ef5eac3908feac9e78262b9c0d9fee95ec", _DEFERRAL),
        'hadith:abudawud:4589': ("aabd01ea97ab4eb0d840ae39d993606e7ba18ec0ef254279319af67f528b8fee", _POINTER),
        'hadith:abudawud:5035': ("792d286677822c8d8a766ab89d4890e4adb24ed6c6b2ec65e56ce66f1f1c7e0f", _POINTER),
        'hadith:abudawud:5244': ("dc6a7e4c78b582727cbd94782fd4bcb26afda5782b964f757ef1bdf63b40adf6", _EDITORIAL_DISCUSSION),
        # --- A2 round 4 (Task 16): editorial omission/comparison sweep.
        # Pure-apparatus records the residue sweep could not reach (its
        # delivery guard hid them); every id hand-audited in
        # task-16-A2round4-audit.md as delivering no narration of its own.
        'hadith:abudawud:2011': ("16bb85b8ca946bc693c660280e6d10ad3076da15f444f6a9b555dc21a57fb9e7", _OMISSION_NOTE),
        'hadith:abudawud:3355': ("c8eac92c22a04707b6dc701b4ca1252ada6cd278631bdd6cfa1c62a3f172021c", _OMISSION_NOTE),
        'hadith:abudawud:3379': ("02ecb1f3d297906ac0f26c3f847a11ac0af56e3ec59c6d72028220a221b32136", _BARE_RULING),
        'hadith:abudawud:3945': ("6e46b91b2b12b8ae87efe6ffc6bbd58cd8fa779de32628aac0c4710efa1de151", _OMISSION_NOTE),
        'hadith:abudawud:3959': ("2a8d8ad6f8eb36f0fb834a8d9804ac95e9b4b640c8552b689d109f1c70081e4d", _OMISSION_NOTE),
    },
    # Tirmidhi (Task 13, ruling R-A3-19). Every record whose matn, after every
    # cut above has already run, is 40 characters or fewer (429 records) was
    # read by hand against its own isnad and addendum -- not a length rule,
    # the same "al-harb khud'a" (10 characters, hadith:tirmidhi:1675) and
    # "la nikaha illa bi-wali" (16, 1101) genuine short hadith left off this
    # list on purpose. No reason above needed inventing: Shakir's edition
    # reuses the same four shapes Bukhari/Muslim/Abu Dawud already produced --
    # _POINTER: a bare deferral word ("mithlahu", "nahwahu", "bi-hadha",
    # "bi-dhalika", "nahwa hadha", and their bi-/mithl- combinations) with
    # nothing else, or (1195) a forward-looking frame ("with these three
    # hadiths") whose narration is the three SEPARATELY numbered units that
    # follow it, never repeated inside this one.
    # _DEFERRAL: the same pointer vocabulary plus one further clause that adds
    # no content of its own -- an isnad-quality verdict ("wa-hadha asahh"), a
    # narrator-name correction ("wa-qala Ibn Abi 'Amra"), an isnad-variant
    # note ("wa-lam yarfa'hu"), a wording-variant note whose replacement
    # clause has no subject once the pointer is removed (2570, 704: "similar
    # to it, except he said: it uncovers a mountain of gold" -- the referent
    # of "it" is the narration this one points to, not present here), or the
    # bare truncation stub "... al-hadith" (3078) that Bukhari's and Muslim's
    # own lists already carry as _TRUNCATED_STUB's sibling.
    # _QURANIC_QUOTE: 2934, a qira'a-variant hadith whose entire matn is
    # Qur'an 18:86's own wording ("fi 'aynin hami'a") -- same pattern as Abu
    # Dawud's 3979/3997/3980 above, and required here too: left scorable, it
    # is exactly what would fail materialize.py's
    # _reject_wholly_quranic_representations gate. 2929 is the same hazard
    # from `sanad-hadith-quranic-matn-hazard` directly: the isnad says the
    # Prophet "qara'a" (recited) and the matn that follows is verbatim Qur'an
    # 5:45's own retaliation-law clause ("al-nafsa bi-l-nafsi wa-l-'ayna
    # bi-l-'ayn") -- plausible as reported Prophetic speech in isolation,
    # which is why the ≤40-char hand-audit judged it a genuine hadith the
    # first time through; `_reject_wholly_quranic_representations` caught what
    # the by-hand read missed, exactly the "verify, don't assert" case this
    # gate exists for.
    # _EDITORIAL_DISCUSSION: three records (46, 249, 566) whose printed unit
    # is, in its entirety, Abu Isa's own remark introducing a further isnad
    # for a hadith already given under an earlier number -- "narrated via
    # [this chain], the like of the hadith of ..." with no matn of its own.
    # `_split_compiler_commentary`'s own "do not cut to empty" rule correctly
    # declines to touch these (see openiti.py), which is why they still carry
    # their full printed text rather than an empty string, and why they need
    # a hand entry here rather than falling out of the marker mechanism.
    #
    # hadith:tirmidhi:2239's own dangling narrator aside ("... qala Mahmud",
    # a transmitter's own remark whose content the edition never gives) is
    # NOT on this list: it is a boundary correction, not an unscorable
    # judgement, and lives in `NEAR_MISS_CUT_OVERRIDE` below instead, leaving
    # a clean, genuine, scorable primary.
    "tirmidhi": {
        # _POINTER group (40 records)
        # Both are bare Shakir cross-reference brackets -- "[161]", "[3631]"
        # -- with nothing else. `_strip_reference_numbers` never empties a
        # matn (build._hadith_records hard-fails on an empty text_ar), so the
        # pinned text is the UNSTRIPPED bracket, not an empty string.
        "hadith:tirmidhi:162":
            ("dd8c4c7ac5796fac483a03d1b344867602c3f1191640ac6202087f19f1dea292", _POINTER),
        "hadith:tirmidhi:3615-2":
            ("befae85932abcc89bc4cd9b412eb00c271fe4f9da3d14be9b19bfdb4e23436c7", _POINTER),
        "hadith:tirmidhi:111":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:tirmidhi:119":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:1328":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:1630":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:166":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:196":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:226":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:2282":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:2533-2":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:2568-2":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:26":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:tirmidhi:280":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:285":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:30":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:tirmidhi:329":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:343":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:tirmidhi:434":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:tirmidhi:441":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:504":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:529":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:535":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:574":
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:tirmidhi:599":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:612":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:615":
            ("f37eece410fe51d360c813f1409b278f7563cb4aebf08205852977fbdef0267b", _POINTER),
        "hadith:tirmidhi:634":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:636":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:654":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:701":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:709":
            ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        "hadith:tirmidhi:717":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:tirmidhi:971":
            ("3811c0b1eb530bdb1a7c08825f4b9c06c44f77f6d879aa7d7b2a6a6e0e73de6d", _POINTER),
        "hadith:tirmidhi:3435-2":
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:tirmidhi:540":
            ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        "hadith:tirmidhi:648":
            ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        "hadith:tirmidhi:148":
            ("b2133cd31847e4d6a1dbdcf8e39425d27513e8a2c945867b902e622191a40b08", _POINTER),
        "hadith:tirmidhi:444":
            ("b2133cd31847e4d6a1dbdcf8e39425d27513e8a2c945867b902e622191a40b08", _POINTER),
        "hadith:tirmidhi:1195":
            ("133dc743e7adc67eeb3a1eecea01b82ac6e3808104f545874a1aba22f5eeb413", _POINTER),

        # _DEFERRAL group (35 records)
        "hadith:tirmidhi:569":
            ("952f49cfc7679210e241351804a33a669578006d2d27becb50eab4ba2178f4e4", _DEFERRAL),
        "hadith:tirmidhi:127":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:1662":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:1697":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:2864":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:347":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:403":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:722":
            ("2a763ad27e558cac7f6e08250950c22bea6bef04c914bfd273f66ccc4bbe52fa", _DEFERRAL),
        "hadith:tirmidhi:349":
            ("9cafc6ac54d0691e900340952d8a3adb37441bcab63db7a7971c5860c8c30237", _DEFERRAL),
        "hadith:tirmidhi:163":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _DEFERRAL),
        "hadith:tirmidhi:836":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:1104":
            ("7f4c7b361b8296286c513c1e9b2a05cc8544e6329848d9505c15335137ae66b7", _DEFERRAL),
        "hadith:tirmidhi:2286":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:2543-2":
            ("6a44880c915055249f1fedad16de116a8726995c8be432d696b1ab3cdbb552a2", _DEFERRAL),
        "hadith:tirmidhi:2573-2":
            ("7f4c7b361b8296286c513c1e9b2a05cc8544e6329848d9505c15335137ae66b7", _DEFERRAL),
        "hadith:tirmidhi:915":
            ("2731e8750415cbc8c35815e68f179af234dab31a8183f62a6e618cb33b7ab32f", _DEFERRAL),
        "hadith:tirmidhi:786":
            ("d7bb1292d8849ba7da0eb5a7bf086ab18bfdd6d3bb9cba70bba3d69b6386df20", _DEFERRAL),
        "hadith:tirmidhi:2296":
            ("eff77cdd27792fcd090341bf6864e509ac6a58a84f48fd5e6b75b1932d766637", _DEFERRAL),
        "hadith:tirmidhi:872":
            ("74c95b13fc9442236a047adaf9a09e4b0081752313997002cc6332e0c795647d", _DEFERRAL),
        "hadith:tirmidhi:2534":
            ("e45e8ea2aa903d7a53c510c3b1a75aef0dd8d663cb9ed7051bc2bd443f2953df", _DEFERRAL),
        "hadith:tirmidhi:1904-2":
            ("3efae21042b4f9f23b477cb51ccb0b24a57f13b52021b31df7e30735cd2f8634", _DEFERRAL),
        "hadith:tirmidhi:2534-2":
            ("e99f0d712966dc46f4df5faa1b5e9ceb49035be1ff8833aee00e8a0d6531bec5", _DEFERRAL),
        "hadith:tirmidhi:1605":
            ("ad27f9b3ca9c9a8de22387554bbc7fdb6f7ebc3832f87c5c6a2c6c8a0ca0c882", _DEFERRAL),
        "hadith:tirmidhi:256":
            ("75b202b2abd02fa9bf405f01a3399a07f5b097e843545724a56bcca2cecdbf11", _DEFERRAL),
        "hadith:tirmidhi:627":
            ("ff968258beac2fe70aa52b4301a087ab925f0322e20f109fbeec3ce24ad2e69b", _DEFERRAL),
        "hadith:tirmidhi:800":
            ("c251799df781a6b71b10b6fc9d7e2a6677a3db0e6b3d17062a7da650e020023d", _DEFERRAL),
        "hadith:tirmidhi:968":
            ("11472162f6b5f127b1c363e64f918c65d168f3f05bf32994cb07c33155e43426", _DEFERRAL),
        "hadith:tirmidhi:559":
            ("021d860371750a7b9b2a696d9f1eaeecf9f442555d6f10af002ee16e2453183e", _DEFERRAL),
        "hadith:tirmidhi:299":
            ("8c7c1fabf8075c2ecafcbb008f6fe05dea55b61fd084702a6113a2b2f28474c2", _DEFERRAL),
        "hadith:tirmidhi:2570":
            ("1684b88bebef8c5a151ada8a12d35de706d522d80f2af5f310cc690e8d5803ce", _DEFERRAL),
        "hadith:tirmidhi:704":
            ("8d1dd89bb995494709ed418d7e5fef911a676dc8ffed3282cbd12144a4aefc5c", _DEFERRAL),
        "hadith:tirmidhi:1873":
            ("c26859c508c8f7af7ae1dce9d28cc6e23c53a34e058c16ce727502e3a94e1290", _DEFERRAL),
        "hadith:tirmidhi:3078":
            ("28561a7a20b9e9f36a0fb711c591a38648b081e5878cc3ea185ef15e009336f1", _DEFERRAL),
        "hadith:tirmidhi:1051":
            ("181b8166bf8b887f83fc7555f26ceba3df06de7d7b80976d4e24172801f11984", _DEFERRAL),
        "hadith:tirmidhi:926":
            ("7d5dd509f18fdfef45eeb57c97730c3b673ecf22d0ad58e1d4ec44c0ba92380f", _DEFERRAL),

        # _QURANIC_QUOTE group (2 records)
        "hadith:tirmidhi:2934":
            ("2f921886db7f8406767b7661f848a3842c835f2ec83495f66636d0fa67888b5c", _QURANIC_QUOTE),
        "hadith:tirmidhi:2929":
            ("a87bf29a20740ac98366e42c9b176e375e40240bf0ba4c5263887ff8e4b6a094", _QURANIC_QUOTE),

        # _EDITORIAL_DISCUSSION group (3 records)
        #
        # 46 and 566's pins changed in R-A3-25's fix round even though this
        # group is Tirmidhi's, not Nasai's: `_split_compiler_commentary`'s
        # own empty-head-candidate bug (see that function's comment) used to
        # pick the EARLIEST "qala Abu 'Isa" match, find its head empty (both
        # records open on that exact phrase), and abort the whole cut --
        # leaving the full, uncut string as the audited matn. The fix makes
        # it try the next later candidate instead of aborting, which is
        # exactly what these two records have: a SECOND "qala Abu 'Isa"
        # deeper in the string, at a genuine, correct cut point. Both are
        # still al-Tirmidhi's own chain-comparison discussion end-to-end --
        # the category is unchanged -- only shorter now that the tail past
        # the second "qala Abu 'Isa" is correctly excluded (moved to
        # `addenda_ar`) instead of staying fused into the audited string.
        # 249 is untouched: measured, its cut point did not move.
        "hadith:tirmidhi:46":
            ("c2c2026ab5fccc85c7f20301d8e23faf0fa93927b8de8e6f98d9dc161109276a", _EDITORIAL_DISCUSSION),
        "hadith:tirmidhi:249":
            ("188208f2268639f9f177ab03f3dd14872c21233f730975f3f617f293c0df07cc", _EDITORIAL_DISCUSSION),
        "hadith:tirmidhi:566":
            ("22d9ace384a4a58ada3e8b35e2cf26470ae18df6563d612d3b8c691b08eacf40", _EDITORIAL_DISCUSSION),
        # --- Task 16 A2 fix round: the broad pointer class in Tirmidhi.
        # 13 records opening نحوه / مثله / بمثله / بهذا الحديث whose entire
        # scored matn is a back-reference plus al-Tirmidhi's own
        # isnad-criticism / fiqh discussion (والصواب حديث سفيان / ولا يعرف ...
        # أصل / وهو قول ... الأوزاعي والشافعي), an isnad-continuation
        # (حدثنا بذلك إسحاق بن منصور -- _CHAIN_LEAK), or an omission note --
        # no Prophetic narration of its own. More than the review's tight
        # estimate of 1: Tirmidhi appends this apparatus to a pointer far more
        # often, and the tight "no قال" filter excluded the قال محمد / قال يحيى
        # isnad-attribution shapes. Every one re-read on full text (addenda
        # included); records delivering matn were left scorable.
        'hadith:tirmidhi:1389': ("b592c1b05ac119adb502c771335a5cffdaf4006fa9758d89d18a37841d85bd02", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:1452': ("598505d28bf55c641b43226e726806b2fdb28782d688856495fa81790140b508", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:2261-2': ("7a752e4643072206057ebc61f0e6fd81f8be41642d723b9d6ba9b1c59bcccaf1", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:2824-2': ("b6a9c5caae9e9af17b2e8bb5fc202e6c9d14dc0ff2fb68c6e405af87cdb9b438", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:328': ("205e69bd24f7d130217902b3af0bf0006f910043e741e6fedbfb3e078d712abe", _POINTER),
        'hadith:tirmidhi:3799-3': ("434c9cf8d4a477ad0079018122df76136bb683160fd4ccb08e9b8b58bb4268ad", _POINTER),
        'hadith:tirmidhi:3832': ("5eda8538001fc3942f968d0d59fd04088c671918c506a770f29377764697819e", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:493': ("8e4856a65fd14c7e73dc7b9c6db857f296be87131b109ffe0811e00063fc8e36", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:554': ("8e8321c544b796576ff5e5600231b13a554040c1508d22bbbcd9cd7e0765e804", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:83': ("ca1ec75ee8a6445f333c78d463e43427e95d96e8767f73fbd219b6470f185ef9", _CHAIN_LEAK),
        'hadith:tirmidhi:84': ("78f1c288a42d3a75236cd6d66bfe33c78cf37343b3b93c9171c91c9fb3bbfb2e", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:888': ("ae63e794262afc492a95fbdad3d2fea4214303b1aa46d9d86350b930417153c4", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:985': ("7614d1f07488ae1f82f05eae91b936a70a6dae93d2c6ac2564e63de703810e7c", _EDITORIAL_DISCUSSION),
        # --- A2 round 3 (Task 16): position-independent whole-string
        # sweep. find_pure_pointers() flags scorable records whose entire
        # matn reduces to back-reference/chain-meta/deferral/omission
        # scaffold with no quotable content, regardless of token position.
        # Every id below was hand-read in context (isnad + addendum) and
        # carries no Prophetic/narrative clause of its own.
        'hadith:tirmidhi:890': ("b82185e8cd91ceac6d883994d99eeb88ce2b1cd08eeb2c6c3350c83c9b31f4c5", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:1299': ("4c90ab94bf05f0ebb4330697f0535ba2eaf1b4f19a72060891e51c87ec977725", _POINTER),
        # --- A2 round 4 (Task 16): editorial omission/comparison sweep.
        # Pure-apparatus records the residue sweep could not reach (its
        # delivery guard hid them); every id hand-audited in
        # task-16-A2round4-audit.md as delivering no narration of its own.
        'hadith:tirmidhi:1096': ("10df6cfce62b829eb74c36c4353c49861af484e936f621fe4842caf8304d8d9b", _EDITORIAL_DISCUSSION),
        'hadith:tirmidhi:595': ("304b76b37f3f15eb5cae6a279f169be9a27291acd534c58278eb7de0d9aa6c4c", _BARE_RULING),
    },
    "nasai": {
        # _POINTER group (42 records) -- plain pointer
        "hadith:nasai:65":  # "مثله"
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:nasai:272":  # "بهذا الإسناد مثله"
            ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        "hadith:nasai:278":  # "مثل ذلك"
            ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        "hadith:nasai:384-2":  # "بهذا الإسناد مثله"
            ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        "hadith:nasai:434":  # "وساق الحديث"
            ("3fb9392ed9b90344141c4b038fe5ce3f29b57822de50f91565aa7919044bb98a", _POINTER),
        "hadith:nasai:568":  # "بنحوه"
            ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        "hadith:nasai:648":  # "بهذا الإسناد نحوه"
            ("86a89cb71072246742402d58cdfdf1b83745b04c8829f5624f04e58c0d081b2a", _POINTER),
        "hadith:nasai:651":  # "مثل ذلك"
            ("dc1e0c484c2c70fa0bd9beeb65693afd93fecb6cb65d45c0b131fc2bae48f273", _POINTER),
        "hadith:nasai:720":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:796":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:863":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:964":  # "مثله"
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:nasai:1197":  # "بمثله"
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:nasai:1198":  # "بمثله"
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:nasai:1234":  # "بمثله"
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:nasai:1786":  # "فذكر نحوه"
            ("edc5862bd004c3bef89e0e4e3c8f0e64f1fa71d9a89a676789dd728c9d23ff4a", _POINTER),
        "hadith:nasai:1990":  # "بنحو ذلك"
            ("7faf342a441621b016c7a953470c422704b1aa214fabea432840e64df9722305", _POINTER),
        "hadith:nasai:2270":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:2278":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:2398":  # "وساق الحديث"
            ("3fb9392ed9b90344141c4b038fe5ce3f29b57822de50f91565aa7919044bb98a", _POINTER),
        "hadith:nasai:2412":  # "نحوه" ("مرسل" now cut to addenda_ar, R-A3-25)
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:2496":  # "بمثله"
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:nasai:2636":  # "مثله"
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:nasai:2724":  # "بهذا الإسناد مثله"
            ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        "hadith:nasai:3357":  # "مثله"
            ("314cca838007660a1698a16457b10ca72a652448eb8fbf995ad46bf924011bcd", _POINTER),
        "hadith:nasai:3419":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:3505":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:3598":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:3617":  # "قوله"
            ("679bd6365682eb58b61672e51ee004259253fe08f00e9cd3c8b4c180fed190b7", _POINTER),
        "hadith:nasai:4033":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:3492":  # "أن ثلاثة نفر اشتركوا في طهر فذكر نحوه" ("ولم يذكر زيد بن أرقم ولم يرفعه ..." now in addenda_ar, R-A3-25 then R-A3-27's own "لم يذكر" arm)
            ("ecd5f84bdf40c9b08c23f87359eee690f30914159780421ede9594ddbb15def4", _POINTER),
        "hadith:nasai:4098":  # "بهذا الإسناد مثله" ("ولم يرفعه" now in addenda_ar, R-A3-25)
            ("6171d4fcec64e9b37d51c524f9249b44aa576d350ab174931c8f4283b55d0bb5", _POINTER),
        "hadith:nasai:4176":  # "فذكر نحوه"
            ("edc5862bd004c3bef89e0e4e3c8f0e64f1fa71d9a89a676789dd728c9d23ff4a", _POINTER),
        "hadith:nasai:4271":  # "بمثل ذلك"
            ("769ce066220566f0a2b9bab157034b61d51fba37d4b148d41a2b26ee7756f3b0", _POINTER),
        "hadith:nasai:4360":  # "نحوه" ("ولم يرفعه" now in addenda_ar, R-A3-25)
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:4588":  # "بمثله"
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:nasai:4725":  # "بمثله قال يحيى وهو أحسن منه"
            ("66f2f531a87bce408c7920c65f87125c62f4d7a97919d3fc77d76ebfd9feee8b", _POINTER),
        "hadith:nasai:4831":  # "مثله سواء"
            ("1689c6318ec9c6db4fbe987b4477218c0855c4fbae2c69e357bf7a5909856513", _POINTER),
        "hadith:nasai:4929":  # "مثل الأول"
            ("b6615f8324b43210cf4f06e08ecc0eaea99ef2191bc94e6e114d7bb2b518ac39", _POINTER),
        "hadith:nasai:5070":  # "بمثله"
            ("92d5f662cd531946a72590d721c4870f84847ca45e91a1907882dd20701105de", _POINTER),
        "hadith:nasai:5123":  # "نحوه"
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
        "hadith:nasai:5194":  # "مرسل"
            ("756615880a6aeadc073a731bc5c11aa883370710596aafc33d0cbbf0cd3b8b2f", _POINTER),
        "hadith:nasai:5695":  # "بنحوه"
            ("836f144960a6a13399d667fd9bbbc4f02fcf5f21465d6261bcf0ee4ef02eb8ff", _POINTER),
        # New in the Task 14 fix round (R-A3-25): has no genuine matn at all
        # (a transmission-route note, same shape as the rest of this group).
        # Its own "مرسل" sits at position 0, so `_split_compiler_commentary`'s
        # empty-head guard leaves it uncut -- this entry does not change what
        # the family regex extension cuts, it was simply never audited before.
        "hadith:nasai:1738":  # "مرسل وقد رواه عطاء بن السائب عن سعيد بن عبد الرحمن بن أبزي عن أبيه"
            ("c039a74f182bb44ef1c423accb629f6f2ddb3d78a9d31d218336dcf38e6b6f00", _POINTER),

        # _CHAIN_LEAK group (2 records) -- chain-continuation leak
        "hadith:nasai:2259":  # "سمع جابرا نحوه"
            ("bd98eef6ecc633d7976c0044674e035f002bcefd8b02563446eaf5edb34477f0", _CHAIN_LEAK),
        "hadith:nasai:4893":  # "حدثه نحوه"
            ("a738ddc43000c877a0cabbdb44a928e7f50447a84e54174080f4bb04155c97d7", _CHAIN_LEAK),
        # Fix round 2 (R-A3-27): these two have no isnad line at all -- their
        # ENTIRE text_ar is an isnad-continuation pointer ("Qutayba informed
        # us again ...") with a al-Nasai's new "لم يذكر" marker fused
        # straight onto it, zero narrative predicate either side. Pinned
        # POST-cut (the "لم يذكر" arm has already moved "ولم يذكر جعفرا"/
        # "ولم يذكر فيه جعفر بن ربيعة" to addenda_ar by the time this check
        # runs), matching 2232/2295/4787's own "مرسل now in addenda_ar"
        # convention above.
        "hadith:nasai:207-2":  # "أخبرنا قتيبة مرة أخرى" ("لم يذكر جعفرا" now in addenda_ar)
            ("a49c409d1ebbcb7272e675464e0db72c32a25e2c4837edb94483d865137bdc65", _CHAIN_LEAK),
        "hadith:nasai:353":  # "أخبرنا به قتيبة مرة أخرى" ("لم يذكر فيه جعفر بن ربيعة" now in addenda_ar)
            ("1671e0304da33a47f49d7dae621023b7d2e08c3e87b55aa702f45987267906a5", _CHAIN_LEAK),

        # _CLASSIFICATION_TAG group (4 records) -- bare classification tag
        "hadith:nasai:1788":  # "موقوفا"
            ("c1ce4bf5f715409da01f67c1ec732c54f2ec6f7fed1d5c81e2e227b810e08dcd", _CLASSIFICATION_TAG),
        "hadith:nasai:2114":  # "مرسل"
            ("756615880a6aeadc073a731bc5c11aa883370710596aafc33d0cbbf0cd3b8b2f", _CLASSIFICATION_TAG),
        "hadith:nasai:2115":  # "مرسل"
            ("756615880a6aeadc073a731bc5c11aa883370710596aafc33d0cbbf0cd3b8b2f", _CLASSIFICATION_TAG),
        "hadith:nasai:4952":  # "مرسل"
            ("756615880a6aeadc073a731bc5c11aa883370710596aafc33d0cbbf0cd3b8b2f", _CLASSIFICATION_TAG),

        # _TRUNCATED_OPENING group (5 records) -- truncated opening clause.
        # 2232/2295/4787's sha256 pins were updated in the Task 14 fix round
        # (R-A3-25): "مرسل" now cuts to addenda_ar via the widened
        # `_NASAI_FORMULA`, so the pinned matn is shorter than before, but the
        # disposition is unchanged -- what remains is still a genuine
        # non-quotable pointer/missing-predicate fragment, read again to
        # confirm, not carried over unread.
        "hadith:nasai:2232":  # "دخل مطرف على عثمان نحوه" ("مرسل" now in addenda_ar)
            ("e1b9f021cfffe2f5bc5fe13e289242bd571657b4ae93625cb755ef919ff94de9", _TRUNCATED_OPENING),
        "hadith:nasai:2295":  # "يا رسول الله مثله" ("مرسل" now in addenda_ar)
            ("2ed100f438f0785b29de54e87d3b648b8753919d3ef091aa2732d034d464c5de", _TRUNCATED_OPENING),
        "hadith:nasai:3965":  # "فقدته من الليل وساق الحديث"
            ("5d379693b857be4d28f1c08179e6ba0b6ff1a0d8f53cf770ee985f03a56b642c", _TRUNCATED_OPENING),
        "hadith:nasai:4787":  # "من قتل له قتيل" ("مرسل" now in addenda_ar)
            ("1f15e9a2272fc4fbd2abb016fda7bf1dc8838a25731334d5e300c4dc07190b5a", _TRUNCATED_OPENING),
        "hadith:nasai:5100":  # "المتفلجات وساق الحديث"
            ("00dfb08ebae7ef777b409116f0088d0ed1be7c420040f51869cee3b692455d3c", _TRUNCATED_OPENING),
        # --- A2 round 3 (Task 16): position-independent whole-string
        # sweep. find_pure_pointers() flags scorable records whose entire
        # matn reduces to back-reference/chain-meta/deferral/omission
        # scaffold with no quotable content, regardless of token position.
        # Every id below was hand-read in context (isnad + addendum) and
        # carries no Prophetic/narrative clause of its own.
        'hadith:nasai:3088': ("ea9a7c0b764886c0784dd24727c94b631a559c654a0087d54024569e960c805e", _POINTER),
        'hadith:nasai:3903': ("8fee098cde1296cdffd008b90eab2b417e508349724e2cc741d6e8503d092828", _POINTER),
        'hadith:nasai:5182': ("5667b3bca4736d32bf5642adf135d3a621784150dbdada694605582bf3fb2c66", _DEFERRAL),
        # --- A2 round 4 (Task 16): editorial omission/comparison sweep.
        # Pure-apparatus records the residue sweep could not reach (its
        # delivery guard hid them); every id hand-audited in
        # task-16-A2round4-audit.md as delivering no narration of its own.
        'hadith:nasai:4337': ("541a303a1147da166ae8256e8ec5c85c942c39ff450c9023f74dbe15c7aee44a", _OMISSION_NOTE),
    },
    # Ibn Majah (Task 15). Every matn of 3 tokens or fewer was read in
    # context (56 measured); the other 55 are genuine, complete, terse
    # Prophetic sayings ("al-harbu khad'ah" -- war is deceit; "al-'aynu haqq"
    # -- the evil eye is real -- and the like). Only one is a bare pointer:
    # hadith:ibnmajah:413's own matn is the single word "نحوه" ("similarly to
    # it"), referring back to 412's fuller wording two units earlier -- the
    # same _POINTER phenomenon already on Bukhari's own list, and (measured)
    # the identical sha256 as Bukhari's own "نحوه" occurrences, since the
    # digest is of the matn string alone, not the record id.
    "ibnmajah": {
        "hadith:ibnmajah:413":
            ("da5b06f32a8be960e4896498557c3a5abf0318f6aa354cf9a2f1cdff8bc7dcbe", _POINTER),
    },
}

# --- A2 round 5 (Task 16): vocabulary-free content-mass net ------------------
#
# The pure-pointer class escaped SEVEN closures, each a narrowing filter whose
# exclusion the next pointer walked through (round 4: the qala/yaqul/zada
# `_PP_DELIVERS` guard hid every pointer wrapped in a speech frame). Round 5
# keys on NO marker: `openiti.content_mass` strips scaffolding (honorific,
# basmala, isnad/chain names, reference/deferral vocabulary, and a frame verb
# plus the narrator name it introduces) and counts what is LEFT. Every scorable
# hadith primary with content-mass <= 3 (the audit-scope boundary K, validated
# by auditing the clean band above it) was read one record at a time in
# task-16-A2round5-audit.md; the 28 below deliver no self-contained matn and are
# pinned unscorable. The other 1,061 in the band deliver a clause/ruling/scene
# and stay scorable (pinned in tests/ingest/test_real_corpus.py) -- including the
# two one/two-word genuine matns the content-mass net surfaces but that DELIVER
# (muslim:274-13 "da'hu" and muslim:581-2), which are keeps, not pointers. These
# 28 each carry a qala/yaqul/sami'tu or ghayra-anna token, which is exactly why
# the round-4 residue sweep could not see them. sha256 is of text_ar, computed
# directly from the source build (never hand-typed); equal shas are equal matn
# strings (e.g. the commonplace frame "'an al-nabi [saw]" recurs verbatim).
_A2R5_CONTENT_MASS_POINTERS: dict[str, dict[str, tuple[str, str]]] = {
    "abudawud": {
        "hadith:abudawud:1176":
            ("4e1f1945786b748b87fc6cdc5b3bf186ba75dfd67869ec5d246aff851ea2e0af", _FRAME_ONLY),
        "hadith:abudawud:1354":
            ("4b9af8e3f84d7a87399c616aad7dd7afb71b73e5cf9cf36ceed9ce8ba352773d", _DEFERRAL),
        "hadith:abudawud:3609":
            ("fcad70db5a26dc065b6cf39b8ba8adfa93874fdf6808039059c2c1056d2f034f", _DEFERRAL),
        "hadith:abudawud:4045":
            ("7b2b9d9a4d18d2c6304527d705c7358c5acf6ddd07e8e39fc348a699fe7d2b2c", _DEFERRAL),
    },
    "bukhari": {
        "hadith:bukhari:1656":
            ("9a01fb95bee94e0a81804633536470dd41d684dc26a12aeb5d8bdc757bc87370", _BARE_RULING),
        "hadith:bukhari:4251":
            ("4efc1ba41a2d7e71ca7778453f8e973a32c99597dca1ac07e1bd219febb553cc", _FRAME_ONLY),
        "hadith:bukhari:4745":
            ("4d8112edb3d1a5d2621569b2b5b5926492ee0966c9c8a2daf4685021242fc431", _FRAME_ONLY),
    },
    "ibnmajah": {
        "hadith:ibnmajah:1130":
            ("1e0310f569e3207f84456d8070170dcbcca5478f0d2471f384548aa87a4590f8", _POINTER),
    },
    "muslim": {
        "hadith:muslim:57-4":
            ("4efc1ba41a2d7e71ca7778453f8e973a32c99597dca1ac07e1bd219febb553cc", _FRAME_ONLY),
        "hadith:muslim:109-2":
            ("49a0af5584b320ff7cfbe1fb908abb8a416ed47b51269aa383c75a4bba06ba88", _FRAME_ONLY),
        "hadith:muslim:144-5":
            ("ee8590818b79d67dc5ed2250395202952dd81155cc73754338db3fb9cac04a2b", _DEFERRAL),
        "hadith:muslim:198-3":
            ("9998025c424b8a508c5e26f333a65cd7a2f5f408590771a70e5487f3183a6951", _POINTER),
        "hadith:muslim:347-2":
            ("cc2db9c6f6e82e141cda73433a5c656afb0870479eb8ab8032ed685978fd7a94", _POINTER),
        "hadith:muslim:686-2":
            ("861c8bb96e04ec0a9f471f35253d79b3a678a9f9cbc82d71f0da5bb81d2ebce2", _DEFERRAL),
        "hadith:muslim:851-3":
            ("d67b0a1b0d3c34292bc0c6aa5e8b9b85c262778b7b5c8a687a4f52aa820b134a", _ISNAD_VARIATION),
        "hadith:muslim:882":
            ("1e0310f569e3207f84456d8070170dcbcca5478f0d2471f384548aa87a4590f8", _POINTER),
        "hadith:muslim:1183":
            ("884cb430b48248ca20c348ab02bb46ab8ec55846d8424fb2f291734955625ddb", _FRAME_ONLY),
        "hadith:muslim:1569":
            ("01403388d0e8bf494489211179d59f030ddebb2b51b685a33d7733c619940cb0", _BARE_RULING),
        "hadith:muslim:1584-3":
            ("4efc1ba41a2d7e71ca7778453f8e973a32c99597dca1ac07e1bd219febb553cc", _FRAME_ONLY),
        "hadith:muslim:1730-2":
            ("7799b1db98722e2ebb1dbd0dfb45c2e466c70c74879a26d217297377cb249410", _ISNAD_VARIATION),
        "hadith:muslim:1822-2":
            ("c59125ec79f6c2bedfbd430d4a7f11abeceef8155761015e0008fb477dc50d75", _DEFERRAL),
        "hadith:muslim:1873-3":
            ("13b0eea493e8130fa5600b1fcb32b6312616193c8065947e67c68ab5b2773209", _ISNAD_VARIATION),
        "hadith:muslim:2047-3":
            ("4d8112edb3d1a5d2621569b2b5b5926492ee0966c9c8a2daf4685021242fc431", _FRAME_ONLY),
        "hadith:muslim:2359-6":
            ("742723ef528d4994842f59c9806a10d79a486d1438bac25b067e211e8ab218df", _FRAME_ONLY),
        "hadith:muslim:2556-3":
            ("6a442e7e61a8d501c9ca5ef64189dc31f56278bb93eb2eef4c29bdb5a93f8355", _FRAME_ONLY),
        "hadith:muslim:2649-2":
            ("b413fe035e021d7ce7192482de78cd85fd3a6df3d069316498e680ad8af87f27", _DEFERRAL),
        "hadith:muslim:2987-3":
            ("857c89e4dc9a4ec241eb4f2d686e334aee7f7c6a8e10665c10d712f717d12dac", _DEFERRAL),
    },
}

for _coll, _entries in _A2R5_CONTENT_MASS_POINTERS.items():
    UNSCORABLE.setdefault(_coll, {}).update(_entries)

# --- A2 read sweep (Task 16): the pinned read-sweep ground truth --------------
#
# Every scorable hadith in the bounded population P (content_mass <= 7, or
# carrying a reference/deferral token; see openiti.in_pointer_sweep_population)
# was read by hand, at 66de6f0. Every POINTER/UNSURE was read a second time
# blind, every KEEP carrying a reference token was read again, a random sample
# of the other KEEPs was read again, and disagreements were adjudicated. The
# rulings are .superpowers/sdd/2026-09-27-hadith-collections-a3/sweep/
# FINAL-RULINGS.tsv (8,721 rows: 495 POINTER, 8,226 KEEP); the committed copy
# the gate reads is tests/ingest/data/pointer_sweep_rulings.tsv. The 495
# POINTERs are pinned below. The entries were generated mechanically from the
# rulings plus the built DB (sha256 of text_ar), never typed; the reason
# constant was chosen from each ruling's recorded reason.
_SEGMENT = ("narration segmented into addenda_ar; text_ar is only a frame; "
            "unscorable until the split is repaired")
_FRAGMENT_VARIANT = ("variant note delivering only a fragment, not a complete "
                     "clause")

_A2_READ_SWEEP_POINTERS: dict[str, dict[str, tuple[str, str]]] = {
    "bukhari": {
        "hadith:bukhari:102":
            ("10f93c98e362c23bed62ab4fe4df3d940d807d39bddec6da82ac477d3fd49a66", _ISNAD_COMMENT),
        "hadith:bukhari:218":
            ("386ff8cf3f4e2ee5e7a48658b413effb28f030408f6b6e76074b79801d2e2864", _FRAME_ONLY),
        "hadith:bukhari:1171":
            ("8abe360582b05b36dd1baf5569601df6c396f5d58f60ccbe3dcfd4a010ada191", _DEFERRAL),
        "hadith:bukhari:1620":
            ("5d12be11992a4265e474a962e4f129b47c44ce0d133708069e80e8a3c19fbdd5", _FRAME_ONLY),
        "hadith:bukhari:1651":
            ("aa2b2d27bc6c66e2423508a1eab4a55e03b8bbe6482ecda56f568325f58168b9", _DEFERRAL),
        "hadith:bukhari:1653":
            ("fa0d6509e0ef34565dbcedcbf3f565b4e66341b8be11e64e0eb2d53198d891f7", _FRAME_ONLY),
        "hadith:bukhari:1657":
            ("9f2c743de19e068a94fb9a81e75c64a7794a1514824d911c8792a5cc394f7fa9", _BARE_RULING),
        "hadith:bukhari:1663":
            ("66aee602227f038358d3703288e55746c46361f4ede3f1e49ad4b539d8896831", _SEGMENT),
        "hadith:bukhari:2101":
            ("38839dd73355b213976af8868910e772a3da3358b3fc75c2f77471f811851f20", _FRAGMENT_VARIANT),
        "hadith:bukhari:2117":
            ("b63949e4499d230375ffa434109bc99dea6af2649c1f911c063a1dbb7d8b74c5", _POINTER),
        "hadith:bukhari:2390":
            ("91ca0314c533d0fc72e4b181bfd725927995f61a268ab8e51197db0a293051ca", _DEFERRAL),
        "hadith:bukhari:3901":
            ("d157611367b3e49d7727a20979cee4cc505414d92ccdb8326ba84fe8cb249237", _ISNAD_COMMENT),
        "hadith:bukhari:3905":
            ("020c812f5e7fc329b7ed42ae9f24e402cf4e61746e31f97762c56957f52bf568", _FRAME_ONLY),
        "hadith:bukhari:4446":
            ("a6d413d083de0ec78e90d687f72f031bba7174652d84f2c369874d1e4fd76900", _POINTER),
        "hadith:bukhari:4562":
            ("d67ec633c15b1620fd2b6d5d99f83930aed2f8656f0a4ee08ae47eac116a69f0", _OMISSION_NOTE),
        "hadith:bukhari:4662":
            ("6e532279fc604e52c41a6559af63d5f9cf69aa0aef154bf1f7e912a50889c333", _FRAME_ONLY),
        "hadith:bukhari:5018":
            ("321a89c3eb89edc2d04b6ea2a0dea8ac8b5740edad645f9ae993769d7afec43b", _POINTER),
        "hadith:bukhari:5090":
            ("a7ec84089989bbbba9780352777c1e6303e2153a8d1197379c79efc7a00c1f2a", _FRAME_ONLY),
        "hadith:bukhari:6068":
            ("c0700f12c3c6a4cc2e6f70f79ba0604749a6c6b84e3c16666aa5482f6e574729", _FRAME_ONLY),
        "hadith:bukhari:6599":
            ("86d46987eff346a4cd0947b5c53c5083f3e627bf3ba7de377d8551eaeedb40f0", _ISNAD_COMMENT),
        "hadith:bukhari:6831":
            ("049530466da4ed503fce8fc10519280d97cc5f35f29efdc6c8c4a8ab2e12250b", _DEFERRAL),
        "hadith:bukhari:6906":
            ("1061d003b813872de7918d6da3c2e3ef8c8a67e8e081dbe26135c9316c381b2a", _FRAME_ONLY),
        "hadith:bukhari:6907":
            ("3b14df8d831704ce3e34bb1e208aced3a88adc606fffd89b0bef647696ceb4cc", _FRAME_ONLY),
        "hadith:bukhari:7070":
            ("4ae8a16047e53fa7a38b114fec6d5e8524312fa5b40f067427dffc4bf133120d", _FRAGMENT_VARIANT),
        "hadith:bukhari:7093":
            ("46528029b7f0ee8c61575772e9c8e7c775513a1b18b97101c06c7ebb9ad01ca7", _DEFERRAL),
    },
    "muslim": {
        "hadith:muslim:8-2":
            ("98def1c82f8379184cf83ce8290ab1e984de071e1cac7d3ec3607964556ad6cd", _OMISSION_NOTE),
        "hadith:muslim:8-3":
            ("cc3375c4dc0b8c5284acbd050e5fdc82a4824c7fe1524fe69cc2729e67e0f620", _OMISSION_NOTE),
        "hadith:muslim:9-2":
            ("bb0ca8d5445dd15497704751fca126a04580ba398fb3bdc1c90c4b851936026e", _FRAGMENT_VARIANT),
        "hadith:muslim:21-3":
            ("068ed2cf18877ddcf45738f81f8262ca416d2a57d45c293f476061c8b702f52e", _DEFERRAL),
        "hadith:muslim:37-3":
            ("e198cdd1afab6dd3aaeddfbbee158b1b4543999f119ed91fcec4894e8b53c2de", _POINTER),
        "hadith:muslim:43-3":
            ("816f2c002b5a650340978a4575443211fa17436d404df18462ade18a8f2e10c4", _FRAGMENT_VARIANT),
        "hadith:muslim:57-2":
            ("d820328947bd010777ef303009e538d3a5b6c8111c99bec0db1f90987ec0fc28", _DEFERRAL),
        "hadith:muslim:57-7":
            ("438d3a093c414108191132facb6909ad5a6c8b79eb42d8e25069227fd71ca8fc", _DEFERRAL),
        "hadith:muslim:59-4":
            ("e7774467ab253c7bc754cd0f637710f3df6adb1f23ee93fde989dd6655488df8", _FRAGMENT_VARIANT),
        "hadith:muslim:85-4":
            ("abcc22c53a3016f1aec1e14dfd77ebe5101c40c81b38aad2145a6a53b3b1e96e", _FRAGMENT_VARIANT),
        "hadith:muslim:108-2":
            ("da87be02677701e9b5a837a7adbc1b2cb9485e0f1aa6fdd24b9344e27958f44b", _FRAGMENT_VARIANT),
        "hadith:muslim:124-2":
            ("95dcbd67112acdff4d156eb8ea7feeaee9629ed62ae57483b9ce86e13cf428ea", _ISNAD_COMMENT),
        "hadith:muslim:136-2":
            ("7abf159561da5f76c69de70e20ea6d0dfc2391b8fe3d25dd8321a013a7d69600", _OMISSION_NOTE),
        "hadith:muslim:151-3":
            ("cc87edcb4ea6ca8edd595a8afa50175e85760d9f80fc2ce790223843e71f6e6d", _POINTER),
        "hadith:muslim:200-3":
            ("066f657c8ef71892e7afaf030c24548aab8062f8ae856de5a8095b524f73c750", _OMISSION_NOTE),
        "hadith:muslim:227-2":
            ("388fadbacba8b90bb735248593aabcb50fcde388dfacbe7e7453cf4883881744", _FRAGMENT_VARIANT),
        "hadith:muslim:234-2":
            ("d4ad3408eda84d04b5a7eb52da8dda2837a579904a7501de1d29a8a76716789f", _FRAGMENT_VARIANT),
        "hadith:muslim:240-4":
            ("fc991458d61753767db6be92687879cb33730c933231ec5de443cb8ee8409ee9", _FRAME_ONLY),
        "hadith:muslim:251-2":
            ("3f64f3a8863dcb653d68cf10c6dc93bf59b05c2e39faf345a63f59483b3142a3", _POINTER),
        "hadith:muslim:255-2":
            ("c5a1efe4cd95b0f5e8b506141ffff7917eea1dda8a14cc308c18acd47a535d30", _DEFERRAL),
        "hadith:muslim:261-2":
            ("378fca70af2af0c33b001793f6c0cf0e2e759b2add3b2c1c99d04af71177cf14", _ISNAD_COMMENT),
        "hadith:muslim:278-5":
            ("8b3db1fe93f3bb2e6994b13154ad42dea959c18e969d984995db5e4c2f5a7fd8", _EDITORIAL_DISCUSSION),
        "hadith:muslim:288-3":
            ("638b201178a397314605368677830d9ba6f4bd9328b52b647b81e65f368187fc", _DEFERRAL),
        "hadith:muslim:315-2":
            ("37f36c9b82c03106a14332461650e3471cd93834ec69405fa93e1d5a70fc8dbb", _FRAGMENT_VARIANT),
        "hadith:muslim:317-2":
            ("559b8adff396740f06a1811b63c1bfe3c8641436122e30da36ef41e276693a32", _OMISSION_NOTE),
        "hadith:muslim:338-2":
            ("4609dc950a1d09dbdecac77002335b3d2448bc61b6d78ba68722cca18e90a96b", _FRAGMENT_VARIANT),
        "hadith:muslim:348-2":
            ("8cc7ad25cc32a02a2f2ceadadde1d74af3f79ca6f5ba93c12848af219cac5226", _FRAGMENT_VARIANT),
        "hadith:muslim:359-2":
            ("842dc0bb4417d8620178c5b4cb3e7f8e8bade07fa31e5d43e9cb8f761d3b5292", _OMISSION_NOTE),
        "hadith:muslim:389-5":
            ("79b46defaac52ad539d4461f1b3f9c9559119babf4de80bf27baf0882648f518", _FRAGMENT_VARIANT),
        "hadith:muslim:391-3":
            ("04efe8cc792332c158384119a4f3ff8026cd56f549fe9aa21558be9433d9cd1f", _FRAGMENT_VARIANT),
        "hadith:muslim:392-6":
            ("7de40ab5d852bfe2a9a6eda8f855a049818432939906aa1d42cbb86354dd0708", _POINTER),
        "hadith:muslim:395-2":
            ("ee8349a89a17533a69cb2bf5a27cb25c17999902e32e05b867b86d7453915ae7", _FRAME_ONLY),
        "hadith:muslim:399-2":
            ("20c74020607c0e8f6426352e382fcd72d3900041f6bb64344ff2eef3b73c3b55", _ISNAD_COMMENT),
        "hadith:muslim:419-3":
            ("451f9ee137a1076d6b8802ebe5343d7e4d6c3b2f7359f4ad08b4bb7cb8547c9d", _DEFERRAL),
        "hadith:muslim:427-3":
            ("f70763fd8c67322efd7780d4a2799a9b5c3181a9d44d0d8103baebc83595a697", _FRAGMENT_VARIANT),
        "hadith:muslim:467-4":
            ("b2b232821bda3cd35db09d2ed412ed8b3583663aa09fa1066bd6966d164af02b", _FRAGMENT_VARIANT),
        "hadith:muslim:476-4":
            ("63e7cb9dff55bfd1675563ae7ea05acb5f33909e803634d7f412eb12345035bb", _FRAGMENT_VARIANT),
        "hadith:muslim:504-4":
            ("40edc1386ca5a09a6e541bbc401608d4c0ccd8a18fa20d2edac8118d96fbf81e", _FRAGMENT_VARIANT),
        "hadith:muslim:517-2":
            ("886fc0cd856733d10c4a544f8c7abd0123bfa7248aa747c3903145a80563eef8", _FRAGMENT_VARIANT),
        "hadith:muslim:518-2":
            ("8830931961f433d4e09d2ca4c1052fc84a24454df24c03f7c95125eda79e3a39", _FRAME_ONLY),
        "hadith:muslim:519-2":
            ("5e0132c0a00c2e12470526be8a2ed1ccf5505c898f0e790b62223af8e8b3b818", _FRAGMENT_VARIANT),
        "hadith:muslim:526-2":
            ("83ea80f714f418608a18ac3a24dc6edd7558b31e9fb54e445ee3f4fdae2975d6", _DEFERRAL),
        "hadith:muslim:540-4":
            ("a75fa881b791971a3e65ab1099453d4caddeafd3f1359193914fca36cbab2a06", _DEFERRAL),
        "hadith:muslim:541-2":
            ("3760a53e2c4e303ffcad81ac3c478ee02d71efdf8b0dd180dfbba7d2dfeeaeea", _FRAGMENT_VARIANT),
        "hadith:muslim:543-4":
            ("33332ce318d76e47c939ccb9cc2c53c82ae4eb437be6cc33c6a8696119508fca", _OMISSION_NOTE),
        "hadith:muslim:544-2":
            ("2dbcfc76826e48cae69927247731e66845a56746f98cf0cbe9e6569551db0ea5", _DEFERRAL),
        "hadith:muslim:573-2":
            ("866619826471fc22a814f33ea29ef7ab5ac5d2b31708b5d64cedfd008bba7c81", _DEFERRAL),
        "hadith:muslim:578":
            ("35437beb0fac6466a24a0d0bd9645856f66045a8a72869c592997f20dc35c270", _POINTER),
        "hadith:muslim:580-4":
            ("3f1eab6f56b2cf481def9309e1d8703d7aabf21643aaa18e1d4f43d41e3cfce2", _ISNAD_COMMENT),
        "hadith:muslim:581":
            ("af5b7f5e267906effb6dcd6fd6cf2e88efedefdbc641dec984b3e5809f7f5518", _POINTER),
        "hadith:muslim:592-2":
            ("237a3e357590e1ce1c13ff34d9d14b8f526033d5b2bee99a4c4fe6fdcda9bc67", _FRAGMENT_VARIANT),
        "hadith:muslim:592-3":
            ("fc05be24f610360eeec047eafed3117e92483fc05658bf313a205f2b7198dd87", _FRAGMENT_VARIANT),
        "hadith:muslim:593-2":
            ("94a68237bc2a6e1cabbb554c355ce23de5345ef85b05a78d99b18358e3ffbde8", _ISNAD_COMMENT),
        "hadith:muslim:594-3":
            ("0117869514af37312adf811a6a26560baa73546b1439ee6f6e0d1a7752c3811d", _DEFERRAL),
        "hadith:muslim:594-4":
            ("400200952975b0de7cbf97877d278e460e030a7350469a513139d26226583c95", _POINTER),
        "hadith:muslim:604-2":
            ("53ff296bc4f76c1ec45263a00291091cf3909434cd0900b37ff0ad0e34adf5f7", _FRAGMENT_VARIANT),
        "hadith:muslim:607-3":
            ("0ca29705c1706085b9f669226fa91bc029bec73e4c4c41d6e5d2bbe1ed36ef87", _FRAGMENT_VARIANT),
        "hadith:muslim:612-3":
            ("d3358e3936b3276720d0c421e345f9a73be3af808aa1e65429c29eadb738e0ee", _ISNAD_COMMENT),
        "hadith:muslim:621-2":
            ("d65fa03337aec2d0cf9611fb567516b431d9571ba560ee007daf28d7b00f5be6", _DEFERRAL),
        "hadith:muslim:627-4":
            ("877ade2f50d8fb554189a86952fa5f2020192c37334f19a1998c3f546a95dc60", _FRAGMENT_VARIANT),
        "hadith:muslim:649-3":
            ("2ae95ae39e67f4c50d06c86ac4dc40f03bc06d4e3fd1d419e3b5e5351e6f22dc", _FRAGMENT_VARIANT),
        "hadith:muslim:650-3":
            ("fe577672afc9f05723695bc9cc51eaf2179e97e397b76f38e5c0e4cc399a3049", _FRAGMENT_VARIANT),
        "hadith:muslim:650-4":
            ("8f3d75129ee3b162016509f2bad36e306a77a7bd3d46f35c746b7031f566dab4", _FRAGMENT_VARIANT),
        "hadith:muslim:693-3":
            ("cf3f941eac175567db68e5046c80a139b8593c638ba50766cc3551c1f96a2923", _FRAME_ONLY),
        "hadith:muslim:694-2":
            ("50eb04ab0c1e9e36b1f525f9b44f9e38d4a93514d841965429979ad0545328a8", _FRAGMENT_VARIANT),
        "hadith:muslim:710-4":
            ("d9c0cdfd23d948a9605c96e2ed1e2bc88e91fa5041f84e49fa3d7b6a57137e82", _ISNAD_COMMENT),
        "hadith:muslim:724-2":
            ("48eb846b987989b3c215672a2d8fcb8233accbe1b6ae5eedb511ae6a76ee3204", _FRAGMENT_VARIANT),
        "hadith:muslim:728-4":
            ("0a779b5f370590b8af26619bdbe9b1d4d432efadb327fb689ff7951fbc01d953", _DEFERRAL),
        "hadith:muslim:733-2":
            ("7cefa402cd0e70f1cd06d4bc71dd9f88d3f3ee5433d367b9799f1d54bd0cea57", _FRAGMENT_VARIANT),
        "hadith:muslim:738-3":
            ("de45f9e941dae93c68bad2335c23acadc021e739f0ca82c6d3396a4854b65b77", _FRAGMENT_VARIANT),
        "hadith:muslim:749-5":
            ("2816ac34b26feb15b8be0d6cab9cdb696e21af219b2957fb5172d37540980b7b", _OMISSION_NOTE),
        "hadith:muslim:769-2":
            ("a4c0fdbda7e2ed30137feb135bdb2423852ac624354ee42ab2a7536b9f1a5427", _ISNAD_COMMENT),
        "hadith:muslim:792-2":
            ("06d4574a27e769b2b9806c08a1c0cd93a04a66aaf544d8bcd9e0bc077e13354d", _FRAGMENT_VARIANT),
        "hadith:muslim:792-6":
            ("4b38a8ed5e0e3cc0d4da61c88a1a243bc19eaf623575182717981286188e0a89", _FRAGMENT_VARIANT),
        "hadith:muslim:797-2":
            ("887c050cd14f5da677f34b2b7898729ef367050ed14221529630c4bd0d964ac7", _FRAGMENT_VARIANT),
        "hadith:muslim:804-2":
            ("6f220b8533416dbf653ebc22f98d83a25cea89432200bc12754ccd5e5d1ff29c", _FRAGMENT_VARIANT),
        "hadith:muslim:809-2":
            ("0880f473ea9fe8b4b80f206f0ef5cbde39da970d1a5f529c8bf52a1dbb70b05d", _FRAGMENT_VARIANT),
        "hadith:muslim:814-3":
            ("550b14bff7703f68fd4bc9ffc3660b73df8909ce950a9d7526e77b8f802aa0ec", _ISNAD_COMMENT),
        "hadith:muslim:820-2":
            ("12a233106546091680fac78d2b229c5a33fe34cec2e3ca17cede94d4deee9a88", _DEFERRAL),
        "hadith:muslim:824-2":
            ("dcd62f4d1bd3e6c1165d7cea485c9a5d43540cd63e02120b9f0436a102d7404f", _DEFERRAL),
        "hadith:muslim:826-2":
            ("e032f07a8dcb1c4f0bc1dbcb2b78db4766d32819dd801a33988da5e9f6443006", _FRAGMENT_VARIANT),
        "hadith:muslim:830-2":
            ("3216d81c05123bde69a3d23cc6f239cb7be7e5b79c8141bea3854e73159e073a", _DEFERRAL),
        "hadith:muslim:838-2":
            ("04862b2e8fc28f5f24caff90847146ca82e06098a36bf58673d62927ea1a2826", _FRAGMENT_VARIANT),
        "hadith:muslim:863-2":
            ("2e6440a2f482215ab0df6871bbf1b8b0c3619c2a91d2308517d134b13408d8f1", _FRAGMENT_VARIANT),
        "hadith:muslim:872-2":
            ("2bdaa698ec047b3e8e303689908d0869ec9bffeb27e64ab5b66e3f855c8fdd8c", _ISNAD_COMMENT),
        "hadith:muslim:879-3":
            ("a7f072383bfe50924d8ed0c47a0dbc042c9b3838d6bed66f73b98263e45bf8e3", _ISNAD_COMMENT),
        "hadith:muslim:944-2":
            ("1be9482ad2f04ada34f80dab9ae562285d2c75be356b97281b7ecf50b83e7d9d", _ISNAD_COMMENT),
        "hadith:muslim:945-3":
            ("b01801500ddfea70de91b2292b09174c31dce09e1945922892538bbbd251d581", _FRAGMENT_VARIANT),
        "hadith:muslim:949-2":
            ("cab65c0faad042c312d874d03434e76cd7c5ae12a1ac5bd41a67b5e50dd66404", _EDITORIAL_DISCUSSION),
        "hadith:muslim:957":
            ("24de8122d61dcbce4c79a0545dfc155ba447475a6b1cdceb84fcf54fe651dc22", _POINTER),
        "hadith:muslim:961-2":
            ("83b5e05362d3f1270520198d1b0cc8ffc25573039feae8e9550903e0e8a62ddf", _FRAGMENT_VARIANT),
        "hadith:muslim:969-2":
            ("258ab6766b3b47679773574d3a73899f1806f33d7c4a8f4a5cea32bfba4c6429", _FRAGMENT_VARIANT),
        "hadith:muslim:979-8":
            ("4d68764274471b9224cfdfacd1a982e031178439334b9ce22a82d2ac574e89f1", _FRAGMENT_VARIANT),
        "hadith:muslim:987-6":
            ("29c0b167eda8c642ba31c691e0b1dbd04e3435786379cb08519cd8ba24783928", _DEFERRAL),
        "hadith:muslim:1007-2":
            ("4f29640a9e76e1325deaeb24f3f9167380f39688f5126f1c2df9ece195c541eb", _FRAGMENT_VARIANT),
        "hadith:muslim:1007-3":
            ("3878f59ae7ae4b9a3665d120bbde53a97f70cacb90a28bbd1cf5c5c626296cbb", _FRAGMENT_VARIANT),
        "hadith:muslim:1014-3":
            ("d806b3c83e50218b7ea6b21c5663a817db699ca5af4473017cab1cca807e0cf3", _FRAGMENT_VARIANT),
        "hadith:muslim:1024-2":
            ("891dbc3974dc6308513370ed012f7f391c17b01eaecbbbf2ff58b40e6635a144", _FRAGMENT_VARIANT),
        "hadith:muslim:1031-2":
            ("9704c50a59ae17837bf6df03e69d2fe0d5bd0ab2867094bfce87a510e7bec303", _FRAGMENT_VARIANT),
        "hadith:muslim:1042-2":
            ("3feae95d784d91dccad44551fbd3304faa3076c50d0636d22d8b9678685809fe", _DEFERRAL),
        "hadith:muslim:1045-3":
            ("0feb865b99b9e603bfed34fffca312e0dd2fbadb122117e96618cce27226f30a", _FRAME_ONLY),
        "hadith:muslim:1063-2":
            ("dc4c528d05f820af8aede2f7659374072235ec0842082920e12d33624b1ede72", _DEFERRAL),
        "hadith:muslim:1101-4":
            ("833431b28b63a918ba8303abd29fbbafd51d04063d36a46d81bb0a8de7164e4a", _OMISSION_NOTE),
        "hadith:muslim:1106-8":
            ("b9dbd7a085fc7348eff2ebb96a8ada5592395942ac2a7c990c380772244fb070", _DEFERRAL),
        "hadith:muslim:1111-2":
            ("d1671cdd0e6617939cd8df81ecc651250a6ad500c55a5d34d0f0e1a0dc598966", _FRAGMENT_VARIANT),
        "hadith:muslim:1112-2":
            ("485cb7e1bdef56a1bf00792aa9855dbdbf13b73aef4dc1b05e6251564e5fd07c", _OMISSION_NOTE),
        "hadith:muslim:1113-2":
            ("c26ee0f264e06fce4ec1f829e58e9c63d99f8401e0fca8802cad3723f7ad7f0b", _EDITORIAL_DISCUSSION),
        "hadith:muslim:1115-2":
            ("f242afd1e9b14794b683a13754ab881356e893c85b1a6831ee880c8c2946836b", _FRAME_ONLY),
        "hadith:muslim:1116-2":
            ("11e458e569fdc218dfcd08b15b1a7c0cb79c211a8ca636a1df7a20c59f826aa6", _FRAGMENT_VARIANT),
        "hadith:muslim:1123-3":
            ("91586703ddb01da90a70509f969206c96667031abc7cc7c394a9b0776e27ca11", _ISNAD_VARIATION),
        "hadith:muslim:1126-5":
            ("306a59653a453134e8c1e781eadb71e2a17468ec3e911348ba656ebc0bedce9d", _DEFERRAL),
        "hadith:muslim:1130-2":
            ("162c4c82c5cf9a972565a4238e2f954901fa8e76845244ab80917d235562ac0d", _FRAME_ONLY),
        "hadith:muslim:1133-2":
            ("6bf389dad3ea630b2693eecf4b40719d74e75dda752f18665da9039f5a6b6593", _DEFERRAL),
        "hadith:muslim:1141-2":
            ("38c64b1ef5ce320afcd2d3b5fd87fa2b984225fbab678505156f09bc717a739a", _FRAGMENT_VARIANT),
        "hadith:muslim:1142-2":
            ("1021539bfcd8eae8b9bed6f64cd1e87d51f5e1d06b34b5a45e2f2b0e2af5df41", _FRAGMENT_VARIANT),
        "hadith:muslim:1143-2":
            ("6ff3f026e7935866af50b140128362b86eb9f56fa94552c46ee208307495c3a3", _FRAME_ONLY),
        "hadith:muslim:1146-2":
            ("4e29e1e83bd020bb288074c20dcd510af08f2b8b35cbe3a42b9f0cc61113a03f", _POINTER),
        "hadith:muslim:1146-3":
            ("ffa36fbeb6976631206698c11fb8be21ea244410ab94275e22e1d379a4aadac3", _POINTER),
        "hadith:muslim:1149-2":
            ("966da094cf8b5203d18c00dee2c1358e08b814b2189699e9d45f21e313fb5c30", _FRAGMENT_VARIANT),
        "hadith:muslim:1149-3":
            ("aafc01c7a8c59d0f82a52a8bc13e4d6b5b3890e7e966002ae00902729289f2a5", _FRAGMENT_VARIANT),
        "hadith:muslim:1149-5":
            ("38c1b3398bc751bf798484ae000db1814ee8d6dc392239f570d05af5b9822a34", _FRAGMENT_VARIANT),
        "hadith:muslim:1156-4":
            ("63b4d973b2c22003300e055f627c033ed8b69452253155c00d797dd976829541", _ISNAD_COMMENT),
        "hadith:muslim:1157-2":
            ("ea8d1f39d1c52179b89f4b28cde37de30e97fea77769f8d67836f95e6f673975", _FRAGMENT_VARIANT),
        "hadith:muslim:1178-2":
            ("a7466fa9f3c4a975fe43df2104be6500fe29e705eda4fd86e007702a82fa224f", _FRAME_ONLY),
        "hadith:muslim:1206-3":
            ("abdc759429c4a0d2924ad1699d4ad1a05eeee408f21618298da149c31d7d9baf", _FRAME_ONLY),
        "hadith:muslim:1225-3":
            ("114b5b5a638636ccd1eb298241d8c9a4d7483c244f109a4dc0ac840ac422b954", _FRAGMENT_VARIANT),
        "hadith:muslim:1243-2":
            ("49ec2e38840e8f0ae4a717c804965a30de26dd30cae42f46b16200628db1c30a", _DEFERRAL),
        "hadith:muslim:1250-2":
            ("41349fb94d75a3f7afc993be84e600591a6e87c45b1fd3bd49804ce0f4905a30", _FRAGMENT_VARIANT),
        "hadith:muslim:1252-2":
            ("b861e0bd215e4abb16698fe759851314a73d3df7e8a242a9d60cb4226682580b", _POINTER),
        "hadith:muslim:1257-2":
            ("9cdab023e270dda15a5a7cdcade0be51d39879fe7518aeeeb0acdbf141caedcb", _FRAGMENT_VARIANT),
        "hadith:muslim:1262-2":
            ("cb872a9f98d53780321b3befe50c3c5bfd44c4a22faeddb37aafaf79caab03ca", _POINTER),
        "hadith:muslim:1279-2":
            ("a2f574c471a8ca60bd495092c755b444817047b24adacdf14a917af33319bbb7", _FRAGMENT_VARIANT),
        "hadith:muslim:1286-3":
            ("35b63c8bcb8521cdbee49865502125cd0f657a910bc25f6e85d0dee3bc58c821", _FRAGMENT_VARIANT),
        "hadith:muslim:1287-2":
            ("2658cce53187f34c3fadbc8a3cf8829de4817b941c639b742b116744e6a26de5", _ISNAD_COMMENT),
        "hadith:muslim:1288-2":
            ("f5fd03c81dd2bc5c4dd450834d7e40c0dc878a31e743cdf0d18a7c27bad8cf28", _POINTER),
        "hadith:muslim:1289-2":
            ("1d4f61930fc0c4e0377d885525b6815e6c260f746309e0a5d24cc248a17062b0", _FRAGMENT_VARIANT),
        "hadith:muslim:1296-2":
            ("99e4193e78aae065d39b9668b30e7e14cb84b699dbdacd53c4b47e2abba113fa", _SEGMENT),
        "hadith:muslim:1296-5":
            ("4a0b45cd763a6cab2dba7d8c4150651e798d20cf22572500b5f4c2ad8f487009", _FRAGMENT_VARIANT),
        "hadith:muslim:1306-7":
            ("99811d776fdb41813de9a0fb34b7743b7ca0939b237a9ed0cf0e9e7a037c4fc4", _FRAME_ONLY),
        "hadith:muslim:1311-2":
            ("332f42e63e36b3c4b9c75e4dae132a3faeb95854e8ac3e74b295a357e2f6ac2f", _FRAME_ONLY),
        "hadith:muslim:1322-2":
            ("594f34a65807162d1136351dc634107ce183f88bb883bfe521f141f530b8d171", _DEFERRAL),
        "hadith:muslim:1338-2":
            ("5c3a9ea05b372155cda23c2e4b20a74fba48a8cf3e5453b3651e8c8d3fd2205d", _FRAGMENT_VARIANT),
        "hadith:muslim:827-8":
            ("0cb7dfc3fafdff651c23db869e0a0b3e3a16a26152f748a6a7c00f8822acd5bc", _FRAGMENT_VARIANT),
        "hadith:muslim:1344-2":
            ("eb56f2b5b2971b773d72e70bea30859efb46f39d05262ad3c0f89aabf2e48676", _OMISSION_NOTE),
        "hadith:muslim:1350-2":
            ("6078fa3976bbffca6f32e7e42f5acc987426eaf0fb04468624a288de3dd6f4b0", _DEFERRAL),
        "hadith:muslim:1370-3":
            ("12e91f9cbbde125cdda0c658cc4813b1a51c97c0ba797f9308fba4e9f374ef36", _OMISSION_NOTE),
        "hadith:muslim:1378-3":
            ("830c4e941daf6085a61defc228d98ae7eca4c37bde62e96e60f3e913fe22e58e", _DEFERRAL),
        "hadith:muslim:1382-2":
            ("eac1721fe118407aee0e844256ca271ae916ceda31b980a0d6866079de80b9d6", _FRAGMENT_VARIANT),
        "hadith:muslim:1400-5":
            ("c5b3b96c8ee038749bf4fd0db8479ec899a0b2cb7423e15e615332d35cf7eb2c", _OMISSION_NOTE),
        "hadith:muslim:1404-2":
            ("b749f50253449ef231a076bbe3ed36c67566a24d45c8633431387b1478970950", _POINTER),
        "hadith:muslim:1406-5":
            ("e13838c9cbdc1f2a5c9a506df76c2f699ead9c6fb4cd18ff7e5c1da2dac1097a", _FRAME_ONLY),
        "hadith:muslim:1413-5":
            ("2461072ce2ed26bda3b0479d310d333e37b681a8353705e5ffb04e516a7dda36", _FRAGMENT_VARIANT),
        "hadith:muslim:1415-2":
            ("5c1b34013b21147b0bb397ab18427f77f417b06dab8bf26f5d2d535b8104b0d4", _DEFERRAL),
        "hadith:muslim:1427-7":
            ("5449e7e87257c839bc6657184b09ab763314aef4eeca68d9b9f3ebce11c9a2ca", _FRAGMENT_VARIANT),
        "hadith:muslim:1434-2":
            ("8349db8d6a7081c17ff10a42b14573f1375fc4b764362cbbc99617e32dd2979b", _OMISSION_NOTE),
        "hadith:muslim:1438-8":
            ("543db351781195b0962848d3528b715a234073fe47c687247c312b686db5c9eb", _FRAME_ONLY),
        "hadith:muslim:1439-3":
            ("661ed4a8e14f6ac72bddbe86d89c7a530a32c3eec863daf6b96f432db68ce7ef", _FRAME_ONLY),
        "hadith:muslim:1442-3":
            ("dea862f05798c92be58c4bb32146c642dd175a4c31c8458243a8d11936d3b5d9", _FRAGMENT_VARIANT),
        "hadith:muslim:1445-7":
            ("e91f88e7987fcb2d3c92b2c707d89c060ce59b67239ed2d8d2d3995a0347df33", _FRAGMENT_VARIANT),
        "hadith:muslim:1449-4":
            ("f62f51497054dc3565f57bc484200818147e849aae7673845a93652b2243d35a", _ISNAD_VARIATION),
        "hadith:muslim:1451-4":
            ("f17d08455968a56c3ab93869e4a88768ad2c0fb34e7b7715c0623f8be0415088", _FRAGMENT_VARIANT),
        "hadith:muslim:1455-2":
            ("7f865783a24345d6168a8477ee1fd3913a8be854e05f9ba85bcf538d6740c1d5", _FRAGMENT_VARIANT),
        "hadith:muslim:1458-2":
            ("ee4f2571705661e4684a35fba5c69771658a7f549956ac4c0549f6c565915d98", _FRAME_ONLY),
        "hadith:muslim:1471-4":
            ("e1ce729ecddaef68dd5f618b00822689345fe456b8131d9ccb1ce4f6f84c52ed", _FRAGMENT_VARIANT),
        "hadith:muslim:1471-11":
            ("c3d8fa8fc09f46e251ce0d85513b5784a717b52e294e8e700380c1d3a32edcbb", _BARE_RULING),
        "hadith:muslim:1471-21":
            ("1aeedf3191a7081eceeb82ac0c2fa37bcb69317298681596aa95dd5c7e9b4ea2", _ISNAD_COMMENT),
        "hadith:muslim:1485-2":
            ("0fed84a252d3584c16517668b162f5751bf2d5526b43416ce5ab36e37b17f3d8", _OMISSION_NOTE),
        "hadith:muslim:1487-2":
            ("7362dde24a907514833da1059aa846c18d4da89009ca335dac5c4596f3b25327", _FRAME_ONLY),
        "hadith:muslim:1488-3":
            ("2fcc26888a95ce912104bc83c9ccb34fa9a8ea48ba915f88b0ec793452dea215", _ISNAD_COMMENT),
        "hadith:muslim:938-4":
            ("2f0cbdb66c0d3388f3fcd99116851333a7e87679fb5b77f418f17007bffed4f3", _FRAGMENT_VARIANT),
        "hadith:muslim:1497-2":
            ("396512b79110adea0898df3107fb218f01868687e5911331aaafee2f5178380f", _FRAGMENT_VARIANT),
        "hadith:muslim:1499-2":
            ("a7e2dfa98789eac024e2bbc89dd9f68e0db78f7ea79819e743a411c32fd4472d", _FRAGMENT_VARIANT),
        "hadith:muslim:1508-3":
            ("58bb526ad6d73692f824fbad72569054d8a3b99a027b39b9fc524e028310757b", _DEFERRAL),
        "hadith:muslim:1510-2":
            ("73ebdb742d861556a37fa275c59f69187f08393110dccdab4e8583a5a5415e03", _FRAGMENT_VARIANT),
        "hadith:muslim:1539-8":
            ("fd593287f7c168f1c61833668a335d0227bf082005ae28c727375aa9d82b81c4", _FRAGMENT_VARIANT),
        "hadith:muslim:1540-3":
            ("d3446d8f5f5c8e72bd88b692433e34d13f3fc36d27cc65b46801459107b49a47", _FRAGMENT_VARIANT),
        "hadith:muslim:1547-2":
            ("94666cd2776dc4998dda7581584099c63f5cfab6bcb594f410be22ae3e47243b", _POINTER),
        "hadith:muslim:1547-7":
            ("b192f9754118759372f7ed0f0dcaa2cb8b71d1407371bfef4c70b41d936f52ab", _FRAME_ONLY),
        "hadith:muslim:1552-5":
            ("cd362a2f8a554dbbec570b8b84dea833029df2218538470fc91eff0d2435c12f", _ISNAD_COMMENT),
        "hadith:muslim:1559-2":
            ("7aca333a3475ad5d8ab4aee5935d6291ec4eba8c2b0422e3fc8d5a0da8021af8", _FRAGMENT_VARIANT),
        "hadith:muslim:1559-5":
            ("846ae2c25f83aef915c37874641b2c22c994866f090a2c7dfa56c9b4c2e1e16b", _POINTER),
        "hadith:muslim:1581-2":
            ("8bafb9ba5824b7d3fa0cb80b0b4c3a4699622446af1f004fa9c70bfd8a85a895", _ISNAD_COMMENT),
        "hadith:muslim:1604-4":
            ("0367daa570147e9202dbaa85a62597dcd3cefe90b9be9c38cbaa161d4318fbec", _FRAGMENT_VARIANT),
        "hadith:muslim:1616-5":
            ("5615c79617c900e420062c5670547843289dfa0d5b77cc2d3598701975a26494", _FRAGMENT_VARIANT),
        "hadith:muslim:1623-3":
            ("6065c804b6cf7276423ab35f3ab46416a1b519ff14b12277e97453e1fb264dfb", _FRAGMENT_VARIANT),
        "hadith:muslim:1625-8":
            ("237ad5ec47a27587bfe8ee73000f0a44ef2000a1505b8deb004b840ca7443367", _FRAME_ONLY),
        "hadith:muslim:1626-2":
            ("200dee7f4607fbc3e848dac11159ad1e16d41f32bd1f9f5a2bf72762663690c7", _FRAGMENT_VARIANT),
        "hadith:muslim:1627-2":
            ("222d6d0e0773f8af952a10a9917d44468408fb38df1f97000bcfb0f201eef063", _FRAGMENT_VARIANT),
        "hadith:muslim:1627-3":
            ("3ad0fab4d1bc219c224c29f401a1426c36babb759aa3db1b0f85af91da23ff14", _FRAGMENT_VARIANT),
        "hadith:muslim:1004-5":
            ("3c4e89a8deedc94cb3d76f92b9e08920b8c2428b9d398145d9d7264b5b8b67dc", _POINTER),
        "hadith:muslim:1644-2":
            ("4c7669875a23b71fa9a8e18a56fca2cdb31f44eb85dc78b3169b3734d06b5bfb", _DEFERRAL),
        "hadith:muslim:1656-6":
            ("16e53a479f12b1529c7e4b563bdb9992faa53edea86e607c4e6a69a66dcb4d0e", _FRAGMENT_VARIANT),
        "hadith:muslim:1657-3":
            ("38cafa1969e7c30c92453afd56062b879ca6d12b0eee546fd7ad59f35eed0bcc", _FRAGMENT_VARIANT),
        "hadith:muslim:1658-5":
            ("f057600fb7e617bcf756eb4620967bdfd734ece9301cde86e9917b71794f5277", _ISNAD_COMMENT),
        "hadith:muslim:1660-2":
            ("eca9c7e909bddef3a7f4c3af898efaa882131e7c2805144105f554b5e9576208", _FRAME_ONLY),
        "hadith:muslim:1677-2":
            ("b5ff88e5ab39408b74dbd08b611483b5f0c83fa03af8438e3f929e0fba88d5f4", _FRAGMENT_VARIANT),
        "hadith:muslim:1678-2":
            ("0ed78438debef8b738ae8309db3e0073658c3d2ea0bab1dc4fbd3b2834789d04", _FRAGMENT_VARIANT),
        "hadith:muslim:1687-2":
            ("f46b77d6d6653491c4f23211c1ef21bd4dd49c6483185c73c31e4f872b424c5d", _FRAGMENT_VARIANT),
        "hadith:muslim:1691-5":
            ("0f22ec45995aeb33f68f96598a9bc837a286344ad82c84ed5385fe1d55d4ba7f", _ISNAD_COMMENT),
        "hadith:muslim:1692-3":
            ("970b43adf79a7a62b9b042c2295d14a42211472c5e4a26f26c6ebee4721de35d", _POINTER),
        "hadith:muslim:1701-2":
            ("d240a65ac77162b534f1366af5757bbba969bed3c90241db96c83b25c3beac81", _FRAGMENT_VARIANT),
        "hadith:muslim:1704":
            ("3ac4729a4629f39c7bd0e80d290e46629a3a41f15d4fc9f7bb683a20c867259d", _DEFERRAL),
        "hadith:muslim:1706-2":
            ("16c5e2ece70aa560a973d61ace6e1bf0817151f652f234bdea4d60e6c6e97da5", _FRAME_ONLY),
        "hadith:muslim:593-7":
            ("099f0d671c22f1236a34b6c680c1901043ff810690586a7a068d116906fe4089", _BARE_RULING),
        "hadith:muslim:1716-2":
            ("32361bbf81ecef23bba8bb7a12e4efc0b63c1a55786519ac853c915cef725dff", _ISNAD_COMMENT),
        "hadith:muslim:1726-2":
            ("55388d52d7e62174da339736b3844bfcd6a1f552f6e4ce2be998be8070f6a6bf", _FRAGMENT_VARIANT),
        "hadith:muslim:1731":
            ("eacbdcae2887200e5184d1cb7676c95c3a2328ac40bf467674c46ad684c40a6d", _ISNAD_COMMENT),
        "hadith:muslim:1742-3":
            ("d06a273988eb8e26da33d6b68a2fe0855bb7868c77c248971a18f8c6b7840d34", _FRAGMENT_VARIANT),
        "hadith:muslim:1742-4":
            ("c5d60303ee47fa8b9aad3e6909fa3a8b56d4864bc6013e3b025db4555c37ce77", _FRAGMENT_VARIANT),
        "hadith:muslim:1775-3":
            ("82cee034d0a16029ab4d7a048069e4f334772172d2092fff7c6634d0da10f285", _FRAME_ONLY),
        "hadith:muslim:1776-4":
            ("fc6f6250b8e0bad225b0ff70469b877ebbd12c6a2647ee8ff336c36ae6a61eb0", _EDITORIAL_DISCUSSION),
        "hadith:muslim:1785-3":
            ("d99d040e3324dbf345c44cff7f3fa92aadd6e65c1784f37b97246ff8051c9edd", _FRAGMENT_VARIANT),
        "hadith:muslim:1815-2":
            ("ab2e9a16d1fe8e0b1e4ad38376e36cf12fad9744f20a46f075d857e1299223c8", _FRAGMENT_VARIANT),
        "hadith:muslim:1835-7":
            ("8bc6cd26b483c716bf91334c0a64bc6d8ba5397626c7606222d37e4bbed38a8f", _DEFERRAL),
        "hadith:muslim:1837-2":
            ("26622738752d49f966dbb77f9ce3df16936c4e0653e76c8061fe72bf1310fd74", _FRAGMENT_VARIANT),
        "hadith:muslim:1837-3":
            ("e1504414b0ae3687ce900a0f80cecff6987f8ea01c33802cead0d907ad4e7629", _FRAGMENT_VARIANT),
        "hadith:muslim:1838-3":
            ("f30cd25b0d045bb38e5a473712498cbc17f03dcb98f81d667d410046706add0b", _FRAGMENT_VARIANT),
        "hadith:muslim:1838-4":
            ("11abb81782a8e948b802e6673f86ba5da7d87cb963c37474751eac76efaafc85", _FRAME_ONLY),
        "hadith:muslim:1709-7":
            ("f024ac9ea8e0b58b4f6800690ed597119db92ea61be2b502ba599bbb2b596a2a", _FRAME_ONLY),
        "hadith:muslim:1844-3":
            ("3dcafc3ceb25ec3ed371ae883c22e238b0ea4be206d73d977bad5d7e9bb1ae80", _FRAME_ONLY),
        "hadith:muslim:1845-2":
            ("70cdd078277f5e1d581f0a28603789cb2ded21045b9c5bee8b76c4d87bce8fce", _FRAME_ONLY),
        "hadith:muslim:1848-4":
            ("c8c5f87eb8ceb46927f719138e18b485ba2cbe6b2b4c45798f89ebfebf0cc626", _OMISSION_NOTE),
        "hadith:muslim:1863-3":
            ("77359e2b78b1af4390f5c562ed66647c25b20147ba744f46e89c039fd6c8624d", _OMISSION_NOTE),
        "hadith:muslim:1869-4":
            ("05cb70e6ab07cb6827c1dfc3178ec78c3b61a5b29a1233de405ee11797287eaf", _FRAGMENT_VARIANT),
        "hadith:muslim:1879-2":
            ("832ea2e16a2532b47bfd70c06f33a6e7eebd5b83ff0cc8ec714fc76cdc5933ce", _FRAME_ONLY),
        "hadith:muslim:1885-2":
            ("9939788d15cc00cb1e8b58082816335b2dae4342399099d09e02346116ae4f5e", _DEFERRAL),
        "hadith:muslim:1888-3":
            ("5cc3270646c3cab71418240c310bd7d84cf54f306afdee35a3bd50be3a1d7ca9", _FRAGMENT_VARIANT),
        "hadith:muslim:1889-2":
            ("72b663ab8dde807d26924d7239bfa7e062e86402337493c74c38f7bef2c94d58", _FRAGMENT_VARIANT),
        "hadith:muslim:1889-3":
            ("492d19a5c3c5fd820c2cd3a34f187c9e031d6107d95aa433e9826236f3e2fcd2", _FRAGMENT_VARIANT),
        "hadith:muslim:1896-2":
            ("192cbb391091587338a39d76f9486c612b813327f268aaf24fc431dac06b9ace", _FRAME_ONLY),
        "hadith:muslim:1904-3":
            ("50a4b2a7c29d7ccf6a043f4ebe88cfb0f097777571c68ea5ce89413fc56ec800", _DEFERRAL),
        "hadith:muslim:1907-2":
            ("3ad6ecae8ddc9895f96ff06815d4e51ce14a002446b9392d36fe58b462eb3df5", _OMISSION_NOTE),
        "hadith:muslim:1911-2":
            ("b828984c806104b6e908d641fa0cd1c73f2bb4eda5970fc8cfb262ea82aedb70", _FRAGMENT_VARIANT),
        "hadith:muslim:715-27":
            ("16a507585c57f51dff872bb5d0522149d144da6cf2e03bce0899e42650c82248", _FRAGMENT_VARIANT),
        "hadith:muslim:1929-4":
            ("5c564e27d75e5f78e3801ce00cc2e56e7bdcd9a6232364c09524ce9819470489", _DEFERRAL),
        "hadith:muslim:1929-5":
            ("8b5db10b1333ceba5f5c6b0a365d118af094196714a9e5b3b7e8f0f1520a977c", _DEFERRAL),
        "hadith:muslim:1407-7":
            ("12e78875dfe9b4bdd1fdd98087bb560b8cb3a1bac4f414c53f8f236af40145aa", _FRAGMENT_VARIANT),
        "hadith:muslim:1952-2":
            ("05c6c657bd36842dfc8b7ab71b28eed54a608b40e78f6ca7f24ab62949f5a7dd", _FRAGMENT_VARIANT),
        "hadith:muslim:1953-2":
            ("2ac75a1c888b273e4caa0749583bc25011079323f20aa6a098076a24b619d959", _FRAGMENT_VARIANT),
        "hadith:muslim:1960-3":
            ("8b46d8578995ced1eb6a4641a1845ff27243070cc6b264cf874a9162925034bb", _FRAGMENT_VARIANT),
        "hadith:muslim:1961-7":
            ("3872d8cd6cb0901db349bf70e5c0b271a9da3cdfc9520c45a64fda5b57326294", _FRAME_ONLY),
        "hadith:muslim:1966-3":
            ("4afbc3034bc512c31a7822850c7f1695be1e146b1e8527e5bba2432f3a3f8d4b", _BARE_RULING),
        "hadith:muslim:1977-2":
            ("5506f2e86025909345623fd8a8b5929ebb2b13c021ed438931b408bfae11a1d4", _DEFERRAL),
        "hadith:muslim:1988-4":
            ("6ed01b43ce953afcff10027d3c86baa303b2e8963d8e959b1e372914ad7b9157", _FRAGMENT_VARIANT),
        "hadith:muslim:1995-6":
            ("8e50dedf4ccf89b9c05f4397c97344995098315abec0efe3ee86cad2fe7debd5", _FRAGMENT_VARIANT),
        "hadith:muslim:1996-3":
            ("714927b8499dc296ed86d19f9bd59069e19139b64b2311a3df78be88d64f8883", _BARE_RULING),
        "hadith:muslim:1997-11":
            ("4d15c4f12a05e25c512044ea3725b452bac4db22becef547237800191a2eea32", _FRAGMENT_VARIANT),
        "hadith:muslim:2017-3":
            ("8ed176daed4fd50eb5125e965b9516e01f32e5a6afd0014b6f4b1aefcb2fe70a", _EDITORIAL_DISCUSSION),
        "hadith:muslim:2018-2":
            ("05bb20a8174017964e11ff79f16e5dcba6b114d6d610385dc250d8f32edc8297", _FRAGMENT_VARIANT),
        "hadith:muslim:2030-2":
            ("eae07b52d9615ee53a93d49d4f9525f3d2cfe5860381886a2bc2851cd9fae88b", _POINTER),
        "hadith:muslim:2049-3":
            ("83196e246e6e7d8189bc609524fcd57ba48c57e0ed7973f602602390d0813f11", _ISNAD_COMMENT),
        "hadith:muslim:2051-2":
            ("0357fbe8a04712ec79c38248d28c41abbd34c65cced98e283c9d4035edd85522", _FRAGMENT_VARIANT),
        "hadith:muslim:2065-2":
            ("e31712903e51a7cd6ec70c3b9eae459cb951c95f88b52064a909b904f101f272", _DEFERRAL),
        "hadith:muslim:2066-2":
            ("3de86fd49266cadb9b0fd0500682c4117376ce8a985861f1d510133c5356a346", _FRAGMENT_VARIANT),
        "hadith:muslim:2066-5":
            ("ae097cf27dc3437758395bfb1e0b48f88ebd0d7f7a4bb7b00553a2adbde91b7a", _FRAGMENT_VARIANT),
        "hadith:muslim:2067-2":
            ("917dfb7459ffb97cc2b250651e4e4ce3d59c494a70f0eeb548a40af04b978bcc", _OMISSION_NOTE),
        "hadith:muslim:2067-5":
            ("0cb6eda44768cb4e131048eb36cd73c2a2f5c61b309de0d8a5562c120dfc55cd", _ISNAD_COMMENT),
        "hadith:muslim:2080-3":
            ("bf6abc4d306ceee7c7eb98eab6ffa0f20510c59b27b70be278d4cf62588d83e4", _FRAGMENT_VARIANT),
        "hadith:muslim:2082-3":
            ("c0b74c13e840b5bf957b0b1eac1e93238b27679aac38aaf4a666f897ade744e3", _FRAGMENT_VARIANT),
        "hadith:muslim:2085-2":
            ("511e6ad56ba2839dfdf8a9b3aa0fdbfe6cd0ffb5c4d2dfcbf8b09d478d5d64ff", _FRAGMENT_VARIANT),
        "hadith:muslim:2085-8":
            ("6d393523ca0efc8ab8ff3326f229f518c578356f70c8425edd61e8571acd60e9", _DEFERRAL),
        "hadith:muslim:2088-4":
            ("c3ca17b8f0e97c161333581c437a88cb4a0507d0770961d26788d3a705550cdc", _DEFERRAL),
        "hadith:muslim:2107-8":
            ("10727f6bb24ae4a94ae02b6fd96e76a0e2162a22e254c00b7c5d0459ac908af0", _FRAGMENT_VARIANT),
        "hadith:muslim:2125-2":
            ("1d2cba541da4d08609b62a14b1463ce4bba97145e509aa2c1c340b097c24fca0", _FRAGMENT_VARIANT),
        "hadith:muslim:2125-3":
            ("24034ac58c7ddf91caf93a144dfcff225fb63cb2dcfaabc7567a83ba4a456d81", _OMISSION_NOTE),
        "hadith:muslim:2155-3":
            ("f19711055b5221b4e337b82b9c5e18c7a7ba8a0d30b2403829bca06b5b024bf9", _POINTER),
        "hadith:muslim:2167-2":
            ("408b074c51392901e83e1edd38cd56b06606bc6bd0bb488780bf3ecad5d404e5", _FRAGMENT_VARIANT),
        "hadith:muslim:2172-3":
            ("0555d86582969f02fa2012270e8db62365f3bad9fc9436438bd5201357b91d3c", _EDITORIAL_DISCUSSION),
        "hadith:muslim:2215-2":
            ("3b1c336368144b09061072e01e2dfceed48b9e4db68a7dac8b91892ad1ba2c6d", _FRAGMENT_VARIANT),
        "hadith:muslim:2219-3":
            ("7fcc2c1b53b408816463b01ef27c34d9213bcf4ba7d894409b3e920df9bd9d80", _ISNAD_VARIATION),
        "hadith:muslim:2223-2":
            ("09c2a7fe8268f483efa9feb72438c1feace58a634a472749afc90356abdd1e07", _OMISSION_NOTE),
        "hadith:muslim:2225-3":
            ("9b48a5550b3c8a44e2b6a80797922936447a751a30d4aa5dc20432f8f3a524f4", _DEFERRAL),
        "hadith:muslim:2232-2":
            ("7dffe6710cad4f05aacb5ff343299fbee6d2eb7d03dc15a411faf47cad0511e3", _FRAGMENT_VARIANT),
        "hadith:muslim:2234-3":
            ("0429084f0dcba92e846766677a3a2c3e426406cf5679a0a0a54aae5939ce1afa", _FRAME_ONLY),
        "hadith:muslim:2243-2":
            ("a7d1893d17828931a967c9bd45cfc71b5a8715914512b2b863ce262a33a22de8", _FRAGMENT_VARIANT),
        "hadith:muslim:2263-3":
            ("26124e1e6daa71c94a32d258b38ebd6c2313dee46fc45fd7d9ddc251d9f4d4b5", _DEFERRAL),
        "hadith:muslim:843-5":
            ("658c7ce082e314d5541474d32d563770442ba39b8517a0a6ed1e8ce8e65b33bd", _OMISSION_NOTE),
        "hadith:muslim:2301-3":
            ("b91ee02d86aa0f30e221dff53feab04ed0e7bff217de84f94c74d82b4967a9e0", _ISNAD_COMMENT),
        "hadith:muslim:2303-3":
            ("673815e1fcf55662b2fe0a0e903b171b321270d87a5be6a2966678843b4d6ba2", _FRAGMENT_VARIANT),
        "hadith:muslim:2303-5":
            ("d9fe9abe998b88935103412d8b0f19b4c14b04b525f2a79e22bbdef814ed71ee", _FRAGMENT_VARIANT),
        "hadith:muslim:2307-3":
            ("dc3744f318e5d84ae5cd1f1bc2d67ff75c8bbb773e9d71865e310f445b4f0340", _FRAGMENT_VARIANT),
        "hadith:muslim:2354-3":
            ("d941f934c4bc47fe44331f8c7718a0014be145d52a9bedc9d28252daaa0dee58", _ISNAD_COMMENT),
        "hadith:muslim:2358-3":
            ("70e06a865529cd98f7f06a50908bb800d52135ff27c847705b7cbf810ee5d14f", _FRAGMENT_VARIANT),
        "hadith:muslim:2359-4":
            ("48588d8cb47f06b86f71008c584504aac8063fdd9c1b1483b57e06aa8d86351d", _OMISSION_NOTE),
        "hadith:muslim:2382-2":
            ("97215223b55baa7aedab12c25011ea30c2a87e88f8fe885d1ce991e062b35f69", _FRAME_ONLY),
        "hadith:muslim:2386-2":
            ("00082766d79af86094303bb93f3baeba67cfbc6eabb2b700798c198be6d8afa2", _BARE_RULING),
        "hadith:muslim:2393-2":
            ("35d808de5f59c783e3d7e019428656a5b5179c53f8cba024bde0ef5dfbe0f8dc", _DEFERRAL),
        "hadith:muslim:2418-2":
            ("f3973e817d8211b8d78d8dbe75b7452f1f67232bdab0947caf491c053c17ebec", _POINTER),
        "hadith:muslim:2464-3":
            ("88c82268ee54ab828ec4a58c65036e38d1161ce85f0461ed84c4ef3d5e644d65", _EDITORIAL_DISCUSSION),
        "hadith:muslim:2464-4":
            ("18bffd4a0f85d9fb0fed88293a45a5458275916b848ed59ec7a4187407bc65f9", _EDITORIAL_DISCUSSION),
        "hadith:muslim:2464-6":
            ("03f5d01a33706a0c01057fdba6fda94d3a08c5e513b396c85d975078c734b2b4", _ISNAD_COMMENT),
        "hadith:muslim:2480-2":
            ("45d498c1a80ff4b251f36f4a4d43d5c25070333ad79cdab16240afb88f8e71bc", _DEFERRAL),
        "hadith:muslim:2511-6":
            ("9b9c3b6b902cd6d5cc429fb4dc098940a798e2929520a16348ed52d4eda7c370", _DEFERRAL),
        "hadith:muslim:2518-2":
            ("7287886bb224ee409fcb11cd88724320a0ee6cc9ad5cc1a077f6dde1dc13c601", _POINTER),
        "hadith:muslim:2520-2":
            ("f27c29f10b7dca8a18415287d2216ebf24ea38257572b9405329d31bafdfaf01", _ISNAD_COMMENT),
        "hadith:muslim:2522-2":
            ("9dd0c2813f581dfbcd7257bd24c111671012ad2280446009c8b9d81abd9e474f", _FRAGMENT_VARIANT),
        "hadith:muslim:2527-2":
            ("f2056e0f6c7f097d0ce72aae53939c2f66b1c466e3d4f4764326dabe382baff7", _FRAGMENT_VARIANT),
        "hadith:muslim:2534-2":
            ("1de11e19ed1119199f3344f7f8b49d86b4c114267b932b325a86ab1f9e275106", _ISNAD_COMMENT),
        "hadith:muslim:2548-4":
            ("5147b8be33f0d8e10f0af92d8666093bc450a14f59d5f0a67b6021130a63086e", _FRAGMENT_VARIANT),
        "hadith:muslim:2549-2":
            ("8f89c5656e2e85d5a8de17a2c5b34feb67bf3fe261568484f8191254d6cba31e", _FRAME_ONLY),
        "hadith:muslim:2551-3":
            ("c73b438484ed3e8b12aa3bb6c59a42509eddbf32d699d59ac0ceefe58912d682", _FRAME_ONLY),
        "hadith:muslim:2559-6":
            ("c22b6f46240adbd99ddea1084c818458877a972ec57356890b32f8708dedf6f2", _FRAGMENT_VARIANT),
        "hadith:muslim:2560-2":
            ("ff149621060b463ea78ba8fd6bf8508c1dedd8f458797a179ff4cf1fbddc87ae", _FRAGMENT_VARIANT),
        "hadith:muslim:2565-2":
            ("a995704bdc3ce5b0ee1c286682ef1154968fabfdcbfab0e5e4b0978a9cc2d14d", _FRAGMENT_VARIANT),
        "hadith:muslim:2571-2":
            ("e1a0b2e089da77838abde4966271dc57a647f200392d0a528fde5310187bb6d1", _FRAGMENT_VARIANT),
        "hadith:muslim:2602-2":
            ("b75c4ab448faf2159d2170051f54b5712135fb4cd99244155cc567ffbda0029e", _FRAGMENT_VARIANT),
        "hadith:muslim:2601-3":
            ("a10bd5c39944e5af2516c27351eff964c81807242b0c4a8bf622e31bff757709", _ISNAD_COMMENT),
        "hadith:muslim:2607-4":
            ("fc5965b8d836eec4753309aa55e42e3584c7e1e58a0d3a557a28a9d0509fb3f7", _FRAGMENT_VARIANT),
        "hadith:muslim:2612-2":
            ("a243dfcd2242e6a7c429f4e7ec2c6ee4e5a38ecc26d3c2a83e33740c6155444c", _DEFERRAL),
        "hadith:muslim:2632-2":
            ("31df3ccfa2dbe783073eeee428abd543fa1adb56ae11aaf2e542618756d1d8ce", _FRAGMENT_VARIANT),
        "hadith:muslim:2634":
            ("68183fe839010b2b6aa5eb98ea7e9804f50374758e40df9383c7ddc2bd6b9466", _FRAGMENT_VARIANT),
        "hadith:muslim:2641":
            ("bfebba464076f556f1937cc614e66e97d530ea259e2b47952bf98c2a909ee335", _FRAME_ONLY),
        "hadith:muslim:2645-4":
            ("28d9ce46c555a915fa2ad07ed995a12be9587bc4a63e9c6f88b4070876457a21", _DEFERRAL),
        "hadith:muslim:2658-2":
            ("91bb757ce8d5dc39c5be07019de6d41b9cc0b24296938851cc875b5e9b9ace23", _FRAGMENT_VARIANT),
        "hadith:muslim:2659-2":
            ("54390598389de563c897fa53e74e4ac3a7fecc76a745751f3c170753872d053d", _FRAGMENT_VARIANT),
        "hadith:muslim:2663-2":
            ("e784b803c9b7955d49befaafaec6087237e11150104007388ba762ee1467861c", _FRAGMENT_VARIANT),
        "hadith:muslim:2663-4":
            ("82dbd9e99fedfbb679dc54c75a9d5111f7e70904c96d8b0ed2d60d8259f7d2e2", _FRAGMENT_VARIANT),
        "hadith:muslim:2673-2":
            ("cb6966719c466c8c82a6074e967427048e30e2f75fcd973af89b712c8c05c238", _ISNAD_COMMENT),
        "hadith:muslim:1017-7":
            ("24b0a4db4e3d418ed6b2210994b6208685a998c71cdce9a8012bb6aca8ac0390", _DEFERRAL),
        "hadith:muslim:2704-5":
            ("d76242688c38651eac2ccfcdac6ea2bf0f8fc70435bd39d4731f9b7b3d812c93", _FRAME_ONLY),
        "hadith:muslim:2705-2":
            ("a3be0f1f122ac33d312bb4a715cc45180a7c22af77896e87a9644ca753cf6b17", _FRAGMENT_VARIANT),
        "hadith:muslim:2710-5":
            ("361d448ac7a76fb9c37c71475583a31707742d9853b1812dd92fe10bd41787a3", _BARE_RULING),
        "hadith:muslim:2713-2":
            ("bd390a24a2a677e524522bd2b54b2513481ab6ae9ff6cf72e4fd9f35b0ac70bb", _FRAGMENT_VARIANT),
        "hadith:muslim:2716-3":
            ("37f04876b1e7cf5c0247830857cceda001c87af3943d4812cb91347961ae10e8", _FRAGMENT_VARIANT),
        "hadith:muslim:2721-2":
            ("66fae4949f65d30f5603d18cfde3869b730a534aeda051aef959c89ee1476ee2", _FRAGMENT_VARIANT),
        "hadith:muslim:2727-2":
            ("f4b55f28bd3ddc510f08ac3a51ff7242c44635ab2d2d087f807abca0a7133e50", _FRAGMENT_VARIANT),
        "hadith:muslim:2730-3":
            ("ac242ad316641a7fb7ba8a5f8b06d753f9d0bf0374e5a6c5cfa677ff12f6e350", _POINTER),
        "hadith:muslim:2744-2":
            ("ca3531cf81ad1e36f60b41168e9418f1e17b13e7bbbba951fb6fca3424adf84f", _FRAGMENT_VARIANT),
        "hadith:muslim:2756-2":
            ("62b07f507a3addb4416315aa10b6f299ca95c9d59cd1ca52fdbe1e1111ccf797", _DEFERRAL),
        "hadith:muslim:2809-2":
            ("9e4b63b7390d67f0de6d5532eb220fa11e578fddaf22598be28c2dfcba9e470d", _FRAGMENT_VARIANT),
        "hadith:muslim:2816-2":
            ("3004927fcb710a9e0ff28cfc5957ca240827d1cb40960c64eb66dacbb9338f83", _FRAGMENT_VARIANT),
        "hadith:muslim:2834-3":
            ("f429b37f96e60685de791ec69f6a926d24152ca0617bf03757873b9b1017b53d", _SEGMENT),
        "hadith:muslim:2845-3":
            ("eeefb0bb6f0b92c641817308d9f10ea72af518de23791651211eda544bb674c1", _FRAGMENT_VARIANT),
        "hadith:muslim:2853-2":
            ("f29c788a99d3b89af258f9078731e6a0468414f453c93c4388a48e45e6cedb1e", _FRAGMENT_VARIANT),
        "hadith:muslim:2865-3":
            ("b0d8edcd3a02a134d4377eb5db7bd597c12b67c0b2e80f4b25c75eb9e803ab08", _ISNAD_COMMENT),
        "hadith:muslim:2870-3":
            ("89fb585f5ec54a72b36f4800511ab4f528a98c0ac6206854004b4070027dfdcc", _DEFERRAL),
        "hadith:muslim:2890-2":
            ("6bfbb253486bd3e64ab7a523bfbb8db3733f477c72cdef716de317cdf6822be1", _FRAME_ONLY),
        "hadith:muslim:2901-4":
            ("ea7128b0bb329e32a1af02e9b21b4545063ca6e4a618a8d21b6df4337e3e3996", _FRAME_ONLY),
        "hadith:muslim:2915-2":
            ("b3dcd14563d56b6d3d7f0fd11fe7c40cd42cab3e211cdd5ee38e755376ddd5f8", _FRAGMENT_VARIANT),
        "hadith:muslim:2935":
            ("1c042dc0b93dfc269556b33ee812ca535cf57c92ba3b005d87e061df8cd07b00", _FRAME_ONLY),
        "hadith:muslim:2939-3":
            ("e87cb79af646a070b87f0bd9a1be39f0aee594b0523bdcd4da384ecfcc5a7d42", _FRAGMENT_VARIANT),
        "hadith:muslim:1055-4":
            ("9565d9687621ece2afd25c5448a23ea84e92153469db554735d0d414d2993e1d", _FRAGMENT_VARIANT),
        "hadith:muslim:2972-2":
            ("1d4ecd184082016f8172a8ad322497659baf1cb6290daf5fa5864369cb2fee5a", _FRAGMENT_VARIANT),
        "hadith:muslim:2987-2":
            ("8de1b4eeda4ffdbac7ecabc26c9408b71bbc69a76886bbe769d4d577c22f8904", _ISNAD_COMMENT),
        "hadith:muslim:2989-2":
            ("37d55b6426ebe3e36659673f92aa0df66411a23af001a8fb455ca7ca1148877c", _DEFERRAL),
        "hadith:muslim:3018-2":
            ("9d67feb610ff809181ba60cbb5517def478b75632fc9767cb1e2284c3955967c", _FRAGMENT_VARIANT),
        "hadith:muslim:3024-2":
            ("e4c550b49750546d1755ce445d29fee1aacbb44b0463b2a9c0c5e8b915a76dae", _FRAGMENT_VARIANT),
        "hadith:muslim:3032-3":
            ("433d6f11bb3bb9273fc973c98a6d4a7b6eadc0d0dea5620d516c6d8bd37fea2e", _FRAGMENT_VARIANT),
        "hadith:muslim:3033-2":
            ("b74659a22f713c7d252c11c6ba1fee602fc739be6721f69f10b5efb9439d5bf1", _FRAME_ONLY),
    },
    "abudawud": {
        "hadith:abudawud:37":
            ("d5f93c34f1997bab080abef4eb088afc0b779281ff877c70a29678e35c56b77e", _ISNAD_COMMENT),
        "hadith:abudawud:64":
            ("01b898d3505c4262efd4db98b2ee5e744bcbc4f680a68fed572a2d59d13a6c5c", _DEFERRAL),
        "hadith:abudawud:104":
            ("5ef55773bfdc142855e4b70938e66cca13730a7989a25520565402fcfa99ea99", _FRAGMENT_VARIANT),
        "hadith:abudawud:315":
            ("91c254d9b960666275250888b30432248c1d1457f77f2e980e260daafa9b2543", _FRAGMENT_VARIANT),
        "hadith:abudawud:328":
            ("980183638bed59c8e4495ffb8ff28e9a97b9ebeea375134b0b2c01fdafbce56b", _FRAGMENT_VARIANT),
        "hadith:abudawud:339":
            ("558bc0142a6e3c19e468978f95d55c2bedeb3d1965ee985b7d22d9f054986093", _DEFERRAL),
        "hadith:abudawud:346":
            ("3fe527386e3c9aa74d5e34f7b944c55bf776b822411085ebebec578313acef58", _DEFERRAL),
        "hadith:abudawud:491":
            ("c8e672e8a730bbc574396d27ba87bb0bfa0090a55f65dd9c7fb80fae141f2f25", _FRAGMENT_VARIANT),
        "hadith:abudawud:509":
            ("b24cd92daa95742ed5b8dda7c0c41f684c2a6220a52bc9d6088038e1020430e9", _FRAGMENT_VARIANT),
        "hadith:abudawud:690":
            ("bf78ce9db6d9861b6cf1ef6e63df93904a93b89a1c1da64f4521830bd5a002cc", _ISNAD_COMMENT),
        "hadith:abudawud:750":
            ("86556d2e17bc18c1134393c12559820271de07ac746617d99a0d83099975f9da", _OMISSION_NOTE),
        "hadith:abudawud:772":
            ("75bb524258c826a3cf01c25757b07ac18747d4426d198e8a1d0a911d7144bea6", _FRAME_ONLY),
        "hadith:abudawud:1031":
            ("98f12b1c9bee6ff197f1352cced2d8e93b35a2e02a93e827d45d01a5798afc21", _FRAGMENT_VARIANT),
        "hadith:abudawud:1058":
            ("95dd46e49a2530adf145183451f009548ec53952c1097a98c34cc9a1c7f43c82", _POINTER),
        "hadith:abudawud:1075":
            ("0f5726e0cecaa40834ddde35b4eb88bdb46afd2f86722781a240bdab2c44e4fd", _FRAGMENT_VARIANT),
        "hadith:abudawud:1150":
            ("e2a38df11028f1c939589497e468074f28d32484fe89b50231de5ed094088040", _FRAGMENT_VARIANT),
        "hadith:abudawud:1186":
            ("e0ff08ebb503aed0e31a1b07cf79bd6115c1773725c16350fb0d9077e0c1e9ac", _FRAGMENT_VARIANT),
        "hadith:abudawud:1268":
            ("7350186b81897799e01910beef8ae1e23a8aba31f87e50ef00a8ac396e56790a", _FRAME_ONLY),
        "hadith:abudawud:1299":
            ("4aba4991cce5238c3cd9ac9f7780dd37d2c4d4f4e1e0fe21cb8e579f3dd0139b", _DEFERRAL),
        "hadith:abudawud:1426":
            ("77ebdc3ff7ffbefc640c89bf29206ecfd154df8b158bb726e079b31c082cf4da", _POINTER),
        "hadith:abudawud:1661":
            ("62dcd30dda6dfd7bfbabb8d539ba5aaa0b909102d2e43ef5c6cbd697febc5c4d", _FRAGMENT_VARIANT),
        "hadith:abudawud:1700":
            ("51f48478df8cf415294f304d8fece81f9488cdbc645ccd6cb2f6ca5e8b89a77b", _FRAGMENT_VARIANT),
        "hadith:abudawud:1863":
            ("cbef618d1ea9948c6142b850cffa843d2dea7b70ba5a18f119717a698eb50900", _DEFERRAL),
        "hadith:abudawud:1891":
            ("dbdd7e7f88cb1af47778ba17409cc7c020eb95a397a7a0ddc9d31f5f72cdfbdb", _POINTER),
        "hadith:abudawud:1955":
            ("6676697fa9b1d90932aac45128b970a97389869006fae3a4a6c4e38b62c7962b", _FRAME_ONLY),
        "hadith:abudawud:2060":
            ("96721c746907441e7a14857a90ca6556709e4c679ddab027cfe13e9aa360928c", _FRAGMENT_VARIANT),
        "hadith:abudawud:2094":
            ("57be25efc18dd318e5c66e02e67cfbf9aa7940c8aaaf6e1cadee076f709f7562", _FRAGMENT_VARIANT),
        "hadith:abudawud:2113":
            ("fdca638f94dc87a251931e022d21635844b593c672f0cc95825eb38b3f0107c4", _POINTER),
        "hadith:abudawud:2204":
            ("972a274beb0974c3aebc03f97676ff25038dd8d4701120a1d152cae3e1a52ce6", _ISNAD_COMMENT),
        "hadith:abudawud:2411":
            ("6ae1fb1a03c2b2c2a5680512ff4261e56d358cdd396ec98c6deea7fa9103b456", _DEFERRAL),
        "hadith:abudawud:2423":
            ("00ebd52fdbf18e4839b0078e666ab8a486862b32d3cd3937386d5a00b4a7415d", _ISNAD_COMMENT),
        "hadith:abudawud:2424":
            ("38c0d0a4880365a439e9f87d6967771ebecbdd54dc0e056935083fa66400a260", _EDITORIAL_DISCUSSION),
        "hadith:abudawud:2518":
            ("5b3d9fa442c6045c73a61d29d4e294f7041ae71cb82b97ae7dd6add8245defb7", _FRAME_ONLY),
        "hadith:abudawud:2630":
            ("e57c8341b0262b8b36beca60497c3fe6831e790e27fe2031bf653932cfe369b8", _FRAME_ONLY),
        "hadith:abudawud:2674":
            ("4a4c2136a99450b5be4e043b519b5eaba8aa1d8cc1af065fb57fb98858ba2090", _DEFERRAL),
        "hadith:abudawud:2742":
            ("d42c7770899f85ba32e9f60ad2f6d5b8eae087e59bf3a1a840db47941db99609", _ISNAD_COMMENT),
        "hadith:abudawud:2761":
            ("102c313d97a9c0078405f2a0666d8fcd3a1bfdff162f2c5e08b7d84fa7c14174", _SEGMENT),
        "hadith:abudawud:3320":
            ("e8e2cd962302e0d0c64052b316e331a3b5cab3712b8033f480b2cbfe83e15d10", _EDITORIAL_DISCUSSION),
        "hadith:abudawud:3411":
            ("d3dc20664a5383dbf66afd3b1bb0fcdbc7dd3613d08199a9b94f52c7251c8082", _BARE_RULING),
        "hadith:abudawud:3453":
            ("47db5708b5474fa06346c53f076b5b27d69554290f2fa49f626da5ed695a5692", _EDITORIAL_DISCUSSION),
        "hadith:abudawud:3465":
            ("6d6a4fc9a650a0936a9d9718b6c222ed8369ce8f5bbc3dd67e05f919f6c6de81", _FRAGMENT_VARIANT),
        "hadith:abudawud:3491":
            ("7ac75b83100108287ab99d8708264c56e017ea3ce437783150e54b895ab427b7", _FRAGMENT_VARIANT),
        "hadith:abudawud:3587":
            ("0b5fb110c43620ba7545f93d218e312a766b7abba8e75debe891657bcbfbd5e3", _ISNAD_COMMENT),
        "hadith:abudawud:3593":
            ("2df631abf31f74020d5f9c7116fc9ab74ac381aebbc16faaaa2fcf5a7f5bb441", _DEFERRAL),
        "hadith:abudawud:3611":
            ("9b2697082ec9349e4b4635d25f05cce2ddcdf08d53ee3721e22e4b90ce6d4e3f", _ISNAD_COMMENT),
        "hadith:abudawud:3625":
            ("6deada3af87209ffc25e4a3d5539c8382664baaa3aa386faa5b2b28532fc8e5a", _ISNAD_COMMENT),
        "hadith:abudawud:3810":
            ("fa2338f48c0b3014604f5ec90fc049cecc4462e85f8d1b2bad80c3b246552aef", _ISNAD_VARIATION),
        "hadith:abudawud:3814":
            ("a9c379fd528659c96e0cc7bc75f041f208479c2a0c2a941b492d52af30023d65", _DEFERRAL),
        "hadith:abudawud:3941":
            ("ef6edd6e21bf3f341740d485e73c703bb07dc8050e53900be1120ddac04017cc", _DEFERRAL),
        "hadith:abudawud:3989":
            ("db7f9033930bac3a7e9c4e04bae8696aac8ef40e91c4784fa532f7c91113e04b", _FRAGMENT_VARIANT),
        "hadith:abudawud:4030":
            ("3d0968104189f076f683e449cdfd0cfb3df3ab1e84bc0932dbe18a3a97bdf763", _FRAGMENT_VARIANT),
        "hadith:abudawud:4154":
            ("71e2f4973dfefd5f09bd039621405f80d1bec94d69f7b69acda2b6c66624be3d", _ISNAD_COMMENT),
        "hadith:abudawud:4233":
            ("284d544fe954998a34f09e98ebdb02544d9be29c9b191d3703067ae1d9b0cd0b", _DEFERRAL),
        "hadith:abudawud:4266":
            ("9706f524f21efa57ec555befcfce5b91f27f8db61b908ff3a1acb4e399086cca", _EDITORIAL_DISCUSSION),
        "hadith:abudawud:4317":
            ("c9892a6e8764adec2bc54ca91d79af0154ecb81fdc147bb5e27d9e351a22ae20", _FRAME_ONLY),
        "hadith:abudawud:4371":
            ("c180f8ec94de76a726e87995c1554bf5a04ca4fe4c568894c26dd5abaabe05e7", _POINTER),
        "hadith:abudawud:4407":
            ("418471f233b5f27faf893b3e46a37c0cc69a22dcecdd573479b437201ac5b010", _POINTER),
        "hadith:abudawud:4416":
            ("6645751432c113c0201b1cec7cfcc6c44355dba0c4346522c4bd731dad09c117", _FRAGMENT_VARIANT),
        "hadith:abudawud:4544":
            ("5e01a69a01e394569a8ec96657a92e843b51a4c7462813f28996e595993155c9", _FRAGMENT_VARIANT),
        "hadith:abudawud:4704":
            ("c8ba16086a7f3afc0939f1c962ee62095d9f0a1ab6aa3bee16f649d8b25ec801", _EDITORIAL_DISCUSSION),
        "hadith:abudawud:4830":
            ("eab1866a27f680d8b3097a410945c5b65c713476c2610d421c5fb0761ed8b67f", _FRAGMENT_VARIANT),
        "hadith:abudawud:4867":
            ("6019cb78acc88737cd3d8cbe029628e6b5af16a9b7eda16b3c5d3507222c3971", _POINTER),
        "hadith:abudawud:5118":
            ("9c3a3161519cb37218f192d272ed1a602e8cb612752609f56942b68c1c9d79bf", _FRAME_ONLY),
        "hadith:abudawud:5255":
            ("f6449d931ff989a3ede7ee176cae1d0983c508aaf822388691c0c7eab966270c", _POINTER),
    },
    "tirmidhi": {
        "hadith:tirmidhi:263":
            ("ac4a023bb7a9b30b3a5fd6b015aaa05e58e38a3605d3ce7e0294b8ae006d5381", _EDITORIAL_DISCUSSION),
        "hadith:tirmidhi:278":
            ("9980047d713dd8fa499a142aa7c32d97f08f7a50e32b00b0f10363ad847160df", _ISNAD_COMMENT),
        "hadith:tirmidhi:305":
            ("8a88a544ede92e30e0cfbfa9846cf46a021bd97981f7b38e893a4095c573225b", _POINTER),
        "hadith:tirmidhi:382":
            ("50d294dfdea6784de2f2bd65a41c20d01aa3f9244f9e7b4601f950d6a3ea7982", _FRAGMENT_VARIANT),
        "hadith:tirmidhi:495":
            ("0efecab0c11a41339089cb7b47f5b10ce6a8414118632f6ad56ab01bb7f902ad", _FRAME_ONLY),
        "hadith:tirmidhi:567":
            ("9d9d77d9ed387ab6e601b127acda2113cdaea58906eb13d454f375cc8719d761", _FRAME_ONLY),
        "hadith:tirmidhi:596":
            ("33b1fbe65c8c254dc82f70ca57381eb3e06ff87c0b3614c9518966745ffab237", _BARE_RULING),
        "hadith:tirmidhi:624":
            ("1b611bafdad1a67a7e487e2595a77996b747122c1d43f96319caebaf2a467dba", _ISNAD_COMMENT),
        "hadith:tirmidhi:651":
            ("8f55a00226cf518765183e1611c82ff6f21cbe6748ecd55715dcfd47ed238bc3", _EDITORIAL_DISCUSSION),
        "hadith:tirmidhi:737":
            ("09ed9cd91a38ddba3b2915e3dbddf7e7c5e89152a3b64d4e56606fbbe0ea44d5", _EDITORIAL_DISCUSSION),
        "hadith:tirmidhi:805":
            ("a43a2ed8a9ab1d0423599db83f45a6541fa1574cd5a9ec4f67c6ba55863d3591", _EDITORIAL_DISCUSSION),
        "hadith:tirmidhi:887":
            ("f1440e9ce05892b1514e262e86ffb940a5ebbe2671404986919b24844f0102e5", _POINTER),
        "hadith:tirmidhi:979":
            ("52dadfd8bc1057a9bca962df2116a94327c496696768d7f553e63ace72b2ccd3", _ISNAD_COMMENT),
        "hadith:tirmidhi:1333":
            ("02590c82f5414b742b9ee1cd8e51e1926da3167145b7199b10d59b92d8b0d604", _ISNAD_VARIATION),
        "hadith:tirmidhi:2370":
            ("aadd8de1d2731e9f6f9dbe83213f3677828d3e271c8ce31b831f72494608825d", _ISNAD_COMMENT),
        "hadith:tirmidhi:2444":
            ("4c75d3b663f9dd25a98f47de37ba517ed3db32aca039262af30bdf725b8ea00a", _SEGMENT),
        "hadith:tirmidhi:3152":
            ("56579572db237a4fadc54e4053d81499615fadcf9d8e7973623acf43a663aad5", _POINTER),
    },
    "nasai": {
        "hadith:nasai:46":
            ("af5b7f5e267906effb6dcd6fd6cf2e88efedefdbc641dec984b3e5809f7f5518", _POINTER),
        "hadith:nasai:91":
            ("c0a52af7a425dcb605fba57af537c30ec09e7fa543fa0906f64af30fb39209a6", _POINTER),
        "hadith:nasai:226":
            ("ee200c3afe8050892cecbe462ab145d8b6f076c6b210bc81b9fb15618d4b83d5", _POINTER),
        "hadith:nasai:466":
            ("6d0b3aa745a028252ac1ba7077f7a966764c2f9080259035e4c6905d6800cf12", _ISNAD_COMMENT),
        "hadith:nasai:658":
            ("f5fd03c81dd2bc5c4dd450834d7e40c0dc878a31e743cdf0d18a7c27bad8cf28", _POINTER),
        "hadith:nasai:667":
            ("8c11151e7584303fad7e47007b2d2dc89458cba2528d899b43ae032b5ef16bd6", _FRAME_ONLY),
        "hadith:nasai:961":
            ("35437beb0fac6466a24a0d0bd9645856f66045a8a72869c592997f20dc35c270", _POINTER),
        "hadith:nasai:1165":
            ("6c3ed5cb1023b277aae9eb7db4de11e0158cf106616253907c6e570767480ae2", _FRAME_ONLY),
        "hadith:nasai:1406":
            ("652fcfd33f9d49ba65359896250adbbbf2d75924c0268ad7a9850a6ec2c0a5d6", _POINTER),
        "hadith:nasai:1531":
            ("fba52a808464c7bfc663c01ba16592dadea45af62de9177a24bdd8d7c85fd1d3", _DEFERRAL),
        "hadith:nasai:1687":
            ("b047e37b665cdcb6528f3f513fbf75a43ed59c47cc1cd4131a8b79c101368d98", _POINTER),
        "hadith:nasai:1755":
            ("5ea43cce20116d1df6e627339141eecf9caf5be61ac391b44de7743a5da30d00", _DEFERRAL),
        "hadith:nasai:1982":
            ("7c2554e9ca5a8e67980022e8af76fce00618ecd1990ed39db3d4298e6074abcc", _POINTER),
        "hadith:nasai:2208":
            ("dbb4c671ae97a75a9b0a07794342430dcba7e222c64f61fe0620db5ef480d2b2", _SEGMENT),
        "hadith:nasai:2209":
            ("d33511e3cc00b17a95aa6e11aeeeed91047a37f6661f9378a17abae3ee824f01", _DEFERRAL),
        "hadith:nasai:2227":
            ("df2286add61b24d4d6296c081985840bbeb92cf0b22bf44f49e3889b6c8794a7", _ISNAD_VARIATION),
        "hadith:nasai:2266":
            ("9055f3a2d1e15bb949f47eef207796df94bd6c31423ffc5530c21c03007b6b52", _FRAME_ONLY),
        "hadith:nasai:2273":
            ("f2954899a10b1a3158f08fd93d3bfdb0ccd64ee721572626e7d6ae8f8f72282d", _DEFERRAL),
        "hadith:nasai:2465":
            ("dcb785743473224b02f29d9266645c2fb621005eb7810e2e431264365039c2f7", _BARE_RULING),
        "hadith:nasai:2720":
            ("80841e9fbd092505b3c3dabff353f97ba3c13402d132308d9e9e65ccd74c80b5", _DEFERRAL),
        "hadith:nasai:2730":
            ("1397b4c52e5b2d69a9a4cedfa81b4a4e02fbd1424f968dbaff9d5d137b0b9b14", _POINTER),
        "hadith:nasai:2940":
            ("7de40ab5d852bfe2a9a6eda8f855a049818432939906aa1d42cbb86354dd0708", _POINTER),
        "hadith:nasai:3206":
            ("029ca114f3269e9321dc6b405d84010347c94419d49656d8cde89b324ac6fb9c", _SEGMENT),
        "hadith:nasai:3422":
            ("199f2bcd197f9c357570d92f0c6f918ee5dfed316daef002085153dcdae5188e", _SEGMENT),
        "hadith:nasai:3455":
            ("b4c9475f52169dc727bf25940fb6d3f0f531aaaa5ec91e0c457aca800dcc9fc0", _SEGMENT),
        "hadith:nasai:3918":
            ("c33b63b6219a078617b6ec1be5c00efc96456b3db060184ff5df2cff112491de", _SEGMENT),
        "hadith:nasai:3981":
            ("1d4375b46421e0f8f4c1ee7c43f79d1c6709271aa1fdf689d8ecc3bb1255ac1a", _FRAME_ONLY),
        "hadith:nasai:4221":
            ("53bc857ed994ad3c77d48750d60ce663eb7888e38053d47e0759bef8eb58c0e7", _ISNAD_COMMENT),
        "hadith:nasai:4598":
            ("3e7986298ade00543ec3781c8b08d8299839aeb29d9a59cf4f9493ab6bc9b2bf", _FRAGMENT_VARIANT),
        "hadith:nasai:4602":
            ("11c7c2fe80003f89271104b41044738987841c79686de29d4923c31aa78b2138", _FRAME_ONLY),
        "hadith:nasai:4667":
            ("02faf00f1edf9b5e80624ef0eb1b3ca103f579d7a644d5277be329c0c008ba38", _FRAGMENT_VARIANT),
        "hadith:nasai:4792":
            ("5b9e50ed9679cecc1655e6d99839a76128107d5a9f065d51a1917208f00c798b", _FRAME_ONLY),
        "hadith:nasai:5483":
            ("ba710844bbb2189ee519621a08eee05389030fd2989021985a1c0430731f4a9d", _BARE_RULING),
    },
    "ibnmajah": {
        "hadith:ibnmajah:155":
            ("72c1d260184051498d17e1a9f8467cf06c624e6095d02cec001eb140b578f23b", _FRAGMENT_VARIANT),
        "hadith:ibnmajah:511":
            ("1ab690b3a703469f5446612a31cfef67ec1f51a53f34d75634320f235fc3c09f", _POINTER),
        "hadith:ibnmajah:1299":
            ("7de40ab5d852bfe2a9a6eda8f855a049818432939906aa1d42cbb86354dd0708", _POINTER),
        "hadith:ibnmajah:2542":
            ("59161a27ba8f29dc69414f5bce7a69de84ed670525fd36808b1301f8d51f3422", _POINTER),
        "hadith:ibnmajah:2974":
            ("9120906928f3dbb1a2e67ff8d417f424efaf6331fa5dbc40cf15f92cd89a6229", _POINTER),
        "hadith:ibnmajah:3005":
            ("7de40ab5d852bfe2a9a6eda8f855a049818432939906aa1d42cbb86354dd0708", _POINTER),
        "hadith:ibnmajah:3032":
            ("b6e6532775ac6ba221dca184cdf526e90da2de8d0d76c7a71b3eec5a0df8ce25", _POINTER),
    },
}

for _coll, _entries in _A2_READ_SWEEP_POINTERS.items():
    _clash = set(_entries) & set(UNSCORABLE.get(_coll, {}))
    assert not _clash, f"read-sweep pins already on the unscorable list: {_clash}"
    UNSCORABLE.setdefault(_coll, {}).update(_entries)
