const MESSAGES = {
  unreachable: {
    role: "alert" as const,
    text: "Cannot reach the verifier. The service may be starting up — try again in a moment.",
  },
  server: {
    role: "alert" as const,
    text: "The verifier returned an error.",
  },
  "no-arabic": {
    role: "status" as const,
    text: "No quotations found to check. Sanad looks for Arabic text and quoted passages.",
  },
  idle: {
    role: "status" as const,
    text: "Paste text above to check its quotations.",
  },
};

/**
 * "We found nothing to check" and "we checked and it is not in the corpus" are
 * different statements and must never collapse into one another. Silence must
 * never be mistakable for a verdict.
 */
export function ErrorState({
  kind, detail,
}: {
  kind: keyof typeof MESSAGES;
  detail?: string;
}) {
  const m = MESSAGES[kind];
  return (
    <p role={m.role} style={{ color: "var(--ink-60)", maxWidth: "var(--measure)" }}>
      {m.text}
      {detail && <span className="data"> ({detail})</span>}
    </p>
  );
}
