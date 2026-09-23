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

      {rec?.text_ar && (
        // A record's matn and its addendum are one printed text -- the split
        // is an indexing artefact (see Task 4's addenda_ar ruling), and in at
        // least two records the boundary falls mid-narration. Never label the
        // addendum, never head it, never drop it: join with the single space
        // the edition's own text uses (verified in test_build.py).
        <p
          data-testid="matn"
          className="arabic"
          dir="rtl"
          lang="ar"
          style={{ margin: "0.9rem 0 0" }}
        >
          {rec.addenda_ar ? `${rec.text_ar} ${rec.addenda_ar}` : rec.text_ar}
        </p>
      )}

      {rec?.translation_en && (
        <div style={{ marginBlockStart: "0.9rem", paddingBlockStart: "0.6rem", borderBlockStart: "var(--rule)" }}>
          <p data-testid="translation" style={{ margin: 0 }}>{rec.translation_en}</p>
        </div>
      )}

      {rec?.isnad_ar && (
        <p
          data-testid="isnad"
          className="data"
          style={{ margin: "0.5rem 0 0", lineHeight: 1.7 }}
          dir="rtl"
          lang="ar"
        >
          {rec.isnad_ar}
        </p>
      )}

      {verdict === "NOT_FOUND" && (
        <p
          data-testid="scope-caveat"
          style={{
            marginBlockStart: "1rem",
            paddingInlineStart: "0.9rem",
            borderInlineStart: "2px solid var(--rubric)",
            fontFamily: "var(--serif)",
            fontSize: "var(--step-0)",
            lineHeight: 1.6,
            color: "var(--ink)",
            maxWidth: "52ch",
          }}
        >
          {corpusScope}
        </p>
      )}
    </article>
  );
}
