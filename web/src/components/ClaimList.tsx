import type { ClaimOut } from "../api/client";

export function ClaimList({ claims }: { claims: ClaimOut[] }) {
  if (claims.length === 0) return null;
  return (
    <section style={{ marginBlockStart: "1.5rem" }}>
      <h2 className="data" style={{ margin: "0 0 0.5rem" }}>claims that a quotation cannot support</h2>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {claims.map((c) => (
          <li key={c.kind} style={{ borderBlockStart: "var(--rule)", paddingBlock: "0.6rem", maxWidth: "var(--measure)" }}>
            <strong style={{ display: "block" }}>{c.label}</strong>
            <span style={{ color: "var(--ink-60)" }}>{c.note}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
