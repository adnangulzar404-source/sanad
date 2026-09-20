# Draft enquiry to OpenITI — licence scope for the GitHub corpus

**Purpose:** resolve the one open question blocking a Hadith layer, recorded in
`docs/superpowers/specs/2026-09-19-sanad-design.md` §14.1 and assessed in
`2026-09-20-hadith-source-assessment.md`.

**Send it as a GitHub issue, not an email.** Open it on
`github.com/OpenITI/RELEASE` (or the specific corpus repo). Three reasons:

- The answer becomes **publicly citable**, which matters for a project whose
  whole claim is documented provenance. A private email reply cannot be linked
  from a lockfile comment; an issue can.
- Others have the same question, so the answer has value beyond this project.
- Academic projects answer issues. Email to a multi-institution collaboration
  often reaches nobody in particular.

If the issue goes unanswered for a few weeks, fall back to the KITAB project's
contact address.

---

## The draft

**Title:** Licence scope: does the CC BY-SA statement cover the corpus files in this repository?

> Hello,
>
> I maintain [Sanad](https://github.com/adnangulzar404-source/sanad), an
> open-source tool that verifies whether a quotation attributed to the Qur'an
> or Hadith is genuinely present in a documented corpus, and shows the user the
> source, edition and checksum behind every match. It currently ships the
> Tanzil Qur'an text under CC BY 3.0. I would like to add Hadith, and after
> surveying the available sources OpenITI is the only one I found whose
> per-text metadata is good enough to build on — the `JK`-prefixed Ṣaḥīḥ
> al-Bukhārī in `0275AH` names its printed edition, links a WorldCat record and
> a scan, names its annotator, and lists exactly what editorial material was
> removed. Thank you for that; it is rare and it is the reason I am asking
> rather than looking elsewhere.
>
> My question is narrow. The Terms of Use on the OpenITI website state CC BY-SA,
> but scope themselves to "the OpenITI website and portal", and the corpus
> repositories here carry no `LICENSE` file. Could you confirm whether the
> CC BY-SA statement is intended to cover the text files in the GitHub
> repositories as well?
>
> Two smaller things, if you have a moment:
>
> 1. Is there an attribution form you would prefer? I intend to record the
>    OpenITI version URI, the annotator and the edition in a machine-readable
>    provenance record shown to end users, and I would rather match your
>    conventions than invent my own.
> 2. Am I right that the OpenITI-specific markup and metadata are your
>    contribution, while the underlying matn is a transcription of a
>    public-domain text? I ask because I plan to strip the markup and store the
>    matn with its provenance recorded, and I want to describe that accurately
>    rather than overclaim in either direction.
>
> Happy to add a `LICENSE` file or a metadata patch by pull request if that
> would be useful.
>
> Thank you,
> Adnan Gulzar

---

## Why it is worded this way

**It leads with what they did well, specifically.** Naming the JK file's actual
metadata shows the question comes from someone who read the corpus rather than
skimmed the homepage, which is the difference between a reply and a ignored
notification.

**It asks one question, answerable in one line.** "Does the ToU cover the
GitHub files?" can be answered yes or no. The two follow-ups are explicitly
optional.

**It does not ask for permission we may not need.** The classical matn is
public domain; al-Bukhārī died in 870. Question 2 invites them to confirm that
framing rather than asserting it at them, which is both more honest and more
likely to get a considered answer.

**It offers to contribute.** A `LICENSE` file is exactly the sort of thing an
academic corpus project knows it should have and has not got to.

## What each possible answer means

| Reply | What we do |
|---|---|
| "Yes, CC BY-SA covers the repos" | Usable, but BY-SA is share-alike — our corpus would carry it forward. Record that in the lockfile and check it against the MIT code before shipping. |
| "No, the repos are unlicensed" | Fall back to the public-domain basis for the matn alone, strip all OpenITI markup, and record the basis as the work's PD status — exactly the Pickthall pattern. |
| "The matn is PD; our markup is ours" | The cleanest outcome. Strip markup, ship matn, attribute generously. |
| No reply | Proceed on the PD basis with generous attribution, and record in the lockfile that the enquiry was made and went unanswered, with a link to the issue. |

Note the last row: an unanswered enquiry is not a blocker. It is a documented
attempt, which is materially better than not having asked, and the public issue
link is itself the evidence.
