import type { AskItem } from "../api/client";

/** One evidence-brief item: Claude's English framing, then the record rendered
 * from server data. Arabic is shown ONLY from `item.record` (canonical corpus
 * text) — never from `framing`, which is model prose (spec I1). This mirrors
 * EvidenceCard's record rendering but has no verdict/diff, since Ask selects
 * relevant records rather than grading a quotation against them. */
export function AskEvidenceCard({ item }: { item: AskItem }) {
  const rec = item.record;
  return (
    <article
      style={{
        border: "var(--rule)",
        borderInlineStart: "3px solid var(--ink-12)",
        padding: "1rem 1.25rem",
        marginBlockEnd: "1rem",
        background: "color-mix(in srgb, var(--page) 94%, white)",
      }}
    >
      {rec?.reference_display && (
        <header className="data" style={{ marginBlockEnd: "0.5rem" }}>
          {rec.reference_display}
        </header>
      )}

      <p data-testid="ask-framing" style={{ margin: 0 }}>
        {item.framing}
      </p>

      {rec?.text_ar && (
        // matn + addendum joined with the single space the edition uses, never
        // labelled or split -- same rule as EvidenceCard (Task 4 addenda ruling).
        <p
          data-testid="ask-matn"
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
          <p className="data" style={{ margin: "0 0 0.25rem" }}>Pickthall translation</p>
          <p data-testid="ask-translation" style={{ margin: 0 }}>{rec.translation_en}</p>
        </div>
      )}

      {!rec?.translation_en && item.matn_translation && (
        <div style={{ marginBlockStart: "0.9rem", paddingBlockStart: "0.6rem", borderBlockStart: "var(--rule)" }}>
          <p className="data" style={{ margin: "0 0 0.25rem" }} data-testid="ask-rendering-label">
            Sanad&#8217;s plain-English rendering &#8212; not an authoritative translation.
          </p>
          <p data-testid="ask-matn-translation" style={{ margin: 0 }}>{item.matn_translation}</p>
        </div>
      )}

      {rec?.isnad_ar && (
        <p
          data-testid="ask-isnad"
          className="data"
          style={{ margin: "0.5rem 0 0", lineHeight: 1.7 }}
          dir="rtl"
          lang="ar"
        >
          {rec.isnad_ar}
        </p>
      )}
    </article>
  );
}
