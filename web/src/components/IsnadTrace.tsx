import { motion, useReducedMotion } from "motion/react";
import type { QuotationOut } from "../api/client";
import { VERDICT_META, type Verdict } from "./VerdictBadge";

type ChainState = "complete" | "broken" | "terminated";

function chainState(verdict: Verdict): ChainState {
  if (verdict === "NOT_FOUND") return "terminated";
  return VERDICT_META[verdict].tone === "verified" ? "complete" : "broken";
}

function Link({
  id, label, children, broken = false, last = false, index = 0,
}: {
  id: string; label: string; children: React.ReactNode;
  broken?: boolean; last?: boolean; index?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.li
      data-testid={`link-${id}`}
      data-broken={String(broken)}
      initial={reduce ? false : { opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduce ? { duration: 0 } : { duration: 0.18, delay: index * 0.04 }}
      style={{ display: "grid", gridTemplateColumns: "1.5rem 8rem 1fr", gap: "0.75rem",
               alignItems: "start", paddingBlock: "0.4rem", position: "relative" }}
    >
      {/* the ruled line and its ring — the mistara and the rosette */}
      <span aria-hidden="true" style={{ display: "block", position: "relative", height: "100%" }}>
        <span style={{
          position: "absolute", insetInlineStart: "0.5rem", insetBlockStart: "0.55rem",
          width: "0.5rem", height: "0.5rem", borderRadius: "50%",
          border: `1.5px solid ${broken ? "var(--rubric)" : "var(--ink-60)"}`,
          background: broken ? "var(--rubric)" : "transparent",
        }} />
        {!last && (
          <span style={{
            position: "absolute", insetInlineStart: "0.73rem", insetBlockStart: "1.1rem",
            bottom: "-0.4rem", width: 0,
            borderInlineStart: broken ? "1.5px dotted var(--rubric)" : "1.5px solid var(--ink-30)",
          }} />
        )}
      </span>
      <span className="data" style={{ paddingBlockStart: "0.15rem" }}>{label}</span>
      <span>{children}</span>
    </motion.li>
  );
}

export function IsnadTrace({
  quotation, source,
}: {
  quotation: QuotationOut;
  source?: { license_id: string; title: string } | null;
}) {
  const verdict = quotation.verdict as Verdict;
  const state = chainState(verdict);
  const rec = quotation.record;
  const alsoCount = quotation.also_at?.length ?? 0;

  const textLinkBroken = verdict === "NEAR_MATCH" || verdict === "NOT_FOUND";
  const citationBroken = verdict === "WRONG_REFERENCE";

  return (
    <ol
      data-testid="chain"
      data-state={state}
      style={{ listStyle: "none", margin: 0, padding: 0, borderInlineStart: "none" }}
    >
      <Link id="quoted" label="you quoted" index={0}>
        <span className="arabic" dir="rtl" lang="ar" style={{ fontSize: "var(--step-2)" }}>
          {quotation.quoted_text}
        </span>
      </Link>

      <Link id="normalized" label="normalized" index={1}>
        <span className="data">
          {quotation.tier ? `tier: ${quotation.tier}` : "not normalized"}
          {quotation.score != null && ` · score ${quotation.score.toFixed(3)}`}
        </span>
      </Link>

      <Link id="matched" label="matched" broken={textLinkBroken} index={2}>
        {rec ? (
          <>
            <span>{rec.reference_display}</span>
            {alsoCount > 0 && (
              <span className="data" style={{ display: "block" }}>
                also appears at {alsoCount} other {alsoCount === 1 ? "place" : "places"}
              </span>
            )}
          </>
        ) : (
          <span style={{ color: "var(--ink-60)" }}>no match in this corpus</span>
        )}
      </Link>

      <Link id="cited" label="you cited" broken={citationBroken} index={3}>
        {quotation.given_reference ? (
          <span style={{ textDecoration: citationBroken ? "line-through" : "none" }}>
            {quotation.given_reference}
          </span>
        ) : (
          <span style={{ color: "var(--ink-60)" }}>no citation given</span>
        )}
      </Link>

      <Link id="source" label="source" last index={4}>
        {rec ? (
          <span className="data">
            {source ? (
              <>{source.title} · {source.license_id} · </>
            ) : (
              <>{rec.id} · </>
            )}
            ⌗{rec.text_ar_sha256.slice(0, 8)}
            {!source && (
              <>
                {" · "}
                <a href="#provenance" style={{ color: "inherit" }}>see corpus provenance</a>
              </>
            )}
          </span>
        ) : (
          <span className="data">—</span>
        )}
      </Link>
    </ol>
  );
}
