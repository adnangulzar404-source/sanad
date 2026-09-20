export type Verdict =
  | "EXACT"
  | "EXACT_ORTHOGRAPHY"
  | "NEAR_MATCH"
  | "WRONG_REFERENCE"
  | "NOT_FOUND";

/**
 * Every verdict carries a glyph AND a label AND a tone. Colour is never the
 * only signal — the gap between "verified" and "near match" is too
 * consequential to encode as a hue a reader may not distinguish.
 */
export const VERDICT_META: Record<
  Verdict,
  { glyph: string; label: string; tone: "verified" | "broken" | "absent" }
> = {
  EXACT:             { glyph: "۝", label: "Verified",                tone: "verified" },
  EXACT_ORTHOGRAPHY: { glyph: "۞", label: "Verified, spelling differs", tone: "verified" },
  NEAR_MATCH:        { glyph: "†", label: "Near match",              tone: "broken" },
  WRONG_REFERENCE:   { glyph: "‡", label: "Wrong reference",         tone: "broken" },
  NOT_FOUND:         { glyph: "○", label: "Not in this corpus",      tone: "absent" },
};

const TONE_COLOUR = {
  verified: "var(--verdigris)",
  broken: "var(--rubric)",
  absent: "var(--ink-60)",
} as const;

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const meta = VERDICT_META[verdict];
  return (
    <span
      role="status"
      data-verdict={verdict}
      data-tone={meta.tone}
      style={{
        display: "inline-flex",
        alignItems: "baseline",
        gap: "0.5ch",
        color: TONE_COLOUR[meta.tone],
        fontFamily: "var(--mono)",
        fontSize: "var(--step--1)",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
      }}
    >
      <span aria-hidden="true" style={{ fontSize: "var(--step-1)" }}>{meta.glyph}</span>
      {meta.label}
    </span>
  );
}
