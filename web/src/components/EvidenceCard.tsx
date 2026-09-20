import type { QuotationOut } from "../api/client";
import { CharDiff, type DiffOp } from "./CharDiff";
import { IsnadTrace } from "./IsnadTrace";
import { VerdictBadge, type Verdict } from "./VerdictBadge";

export function EvidenceCard({
  quotation, corpusScope,
}: {
  quotation: QuotationOut;
  corpusScope: string;
}) {
  const verdict = quotation.verdict as Verdict;
  const rec = quotation.record;

  return (
    <article
      style={{
        border: "var(--rule)",
        borderInlineStart: `3px solid ${verdict === "NOT_FOUND" ? "var(--ink-30)" : "var(--ink-12)"}`,
        padding: "1rem 1.25rem",
        marginBlockEnd: "1rem",
        background: "color-mix(in srgb, var(--page) 94%, white)",
      }}
    >
      <header style={{ marginBlockEnd: "0.75rem" }}>
        <VerdictBadge verdict={verdict} />
      </header>

      <IsnadTrace quotation={quotation} />

      <CharDiff diff={(quotation.diff as DiffOp[] | null) ?? null} />

      {rec?.translation_en && (
        <div style={{ marginBlockStart: "0.9rem", paddingBlockStart: "0.6rem", borderBlockStart: "var(--rule)" }}>
          <p data-testid="translation" style={{ margin: 0 }}>{rec.translation_en}</p>
          <p data-testid="translation-disclaimer" className="data" style={{ margin: "0.3rem 0 0" }}>
            {rec.translation_disclaimer}
          </p>
        </div>
      )}

      {verdict === "NOT_FOUND" && (
        <p
          data-testid="scope-caveat"
          className="data"
          style={{ marginBlockStart: "0.9rem", paddingBlockStart: "0.6rem",
                   borderBlockStart: "var(--rule)", color: "var(--ink)" }}
        >
          {corpusScope}
        </p>
      )}
    </article>
  );
}
