const COPY: Record<string, { heading: string; body: string }> = {
  PERSONAL_RULING: {
    heading: "This needs a qualified person, not software",
    body: "You are asking about your own situation. Sanad checks whether a quotation is genuine; it cannot weigh your circumstances, and it will not try. Take this to a qualified scholar who can ask you the questions that matter.",
  },
  HIGH_RISK: {
    heading: "This topic is too sensitive for an automated answer",
    body: "Sanad verifies quotations. It does not rule on sensitive questions, and an answer assembled from matched text would carry an authority it has not earned.",
  },
};

export function HandoffCard({ risk }: { risk: string }) {
  const copy = COPY[risk] ?? COPY.PERSONAL_RULING;
  return (
    <div
      role="alert"
      style={{ border: `1px solid var(--rubric)`, borderInlineStart: "3px solid var(--rubric)",
               padding: "1.25rem 1.5rem", maxWidth: "var(--measure)" }}
    >
      <h2 style={{ margin: "0 0 0.5rem", fontSize: "var(--step-1)", color: "var(--rubric)" }}>
        {copy.heading}
      </h2>
      <p style={{ margin: 0 }}>{copy.body}</p>
    </div>
  );
}
