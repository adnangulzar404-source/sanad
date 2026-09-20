export type DiffOp = [string, string];

/**
 * Renders the character-level difference between what the user wrote and what
 * the corpus holds. Both sides are labelled in words: a reader must be able to
 * tell which is which without relying on colour.
 */
export function CharDiff({ diff }: { diff: DiffOp[] | null }) {
  if (!diff || diff.length === 0) return null;

  let quotedIndex = 0;
  let corpusIndex = 0;

  return (
    <div data-testid="diff" style={{ marginBlockStart: "0.75rem" }}>
      <p className="data" style={{ margin: "0 0 0.25rem" }}>
        <span style={{ color: "var(--rubric)" }}>you wrote</span>
        {" · "}
        <span style={{ color: "var(--verdigris)" }}>corpus has</span>
      </p>
      <p className="arabic" dir="rtl" lang="ar" style={{ margin: 0, fontSize: "var(--step-2)" }}>
        {diff.map(([kind, text], i) => {
          if (kind === "equal") return <span key={i}>{text}</span>;
          if (kind === "quoted-only") {
            return (
              <span
                key={i}
                data-testid={`quoted-only-${quotedIndex++}`}
                style={{
                  color: "var(--rubric)",
                  textDecoration: "underline wavy var(--rubric)",
                  textUnderlineOffset: "0.35em",
                }}
              >
                {text}
              </span>
            );
          }
          return (
            <span
              key={i}
              data-testid={`corpus-only-${corpusIndex++}`}
              style={{
                color: "var(--verdigris)",
                borderBottom: "2px solid var(--verdigris)",
              }}
            >
              {text}
            </span>
          );
        })}
      </p>
    </div>
  );
}
