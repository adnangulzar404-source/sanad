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
 */
export function MarkedText({
  text, quotations,
}: {
  text: string;
  quotations: QuotationOut[];
}) {
  const spans = [...quotations].sort((a, b) => a.start - b.start);
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
        style={{
          background: "transparent",
          color: "inherit",
          textDecoration: `underline ${UNDERLINE[verdict]}`,
          textUnderlineOffset: "0.3em",
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
