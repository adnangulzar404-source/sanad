import type { QuotationOut } from "../api/client";
import { VERDICT_META, type Verdict } from "./VerdictBadge";

const UNDERLINE: Record<Verdict, string> = {
  EXACT:             "2px solid var(--verdigris)",
  EXACT_ORTHOGRAPHY: "2px dashed var(--verdigris)",
  NEAR_MATCH:        "2px wavy var(--rubric)",
  WRONG_REFERENCE:   "2px dotted var(--rubric)",
  NOT_FOUND:         "2px solid var(--ink-30)",
};

/**
 * The user's text with each span marked in place.
 *
 * The text is never rewritten. Sanad's non-goals forbid silently correcting a
 * quotation, and this component is where that promise is kept: it renders the
 * exact input string, adding marks around ranges and nothing else.
 *
 * `marksWithheld` is distinct from passing an empty `quotations` array. An
 * empty array is itself a claim — "no spans were found here" — which is not
 * true on a handoff: quotations may well exist, but the verdict vocabulary
 * built to explain them (WRONG_REFERENCE, NOT_FOUND, …) must not appear on a
 * screen the product promises will carry no verdict. `marksWithheld` says
 * that explicitly, so a caller can never confuse "nothing found" with
 * "found, but suppressed."
 */
export function MarkedText({
  text, quotations, marksWithheld = false,
}: {
  text: string;
  quotations: QuotationOut[];
  marksWithheld?: boolean;
}) {
  const spans = marksWithheld ? [] : [...quotations].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  spans.forEach((s, i) => {
    if (s.start > cursor) parts.push(<span key={`t${i}`}>{text.slice(cursor, s.start)}</span>);

    // A span may overlap one already rendered. Clamp to the cursor so no
    // character is emitted twice: this component's contract is that its
    // output equals its input, and that must not depend on an upstream
    // deduplication.
    const from = Math.max(s.start, cursor);
    if (from >= s.end) return; // fully consumed by an earlier span

    const verdict = s.verdict as Verdict;
    parts.push(
      <mark
        key={`s${i}`}
        data-testid={`span-${i}`}
        data-verdict={verdict}
        title={VERDICT_META[verdict].label}
        // The title attribute alone is invisible to most screen readers on a
        // non-interactive element -- an aria-label carries the same verdict
        // label without adding a single character to this component's
        // exact-text contract (aria-label is not part of textContent).
        aria-label={VERDICT_META[verdict].label}
        style={{
          background: "transparent",
          color: "inherit",
          textDecoration: `underline ${UNDERLINE[verdict]}`,
          textUnderlineOffset: "0.5em",
          textDecorationThickness: "2px",
          textDecorationSkipInk: "none",
        }}
      >
        {text.slice(from, s.end)}
      </mark>
    );
    cursor = s.end;
  });

  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);

  return (
    <p
      data-testid="marked"
      style={{ maxWidth: "var(--measure)", whiteSpace: "pre-wrap", margin: 0, lineHeight: 1.9 }}
    >
      {parts}
    </p>
  );
}
