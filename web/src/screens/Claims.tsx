import { useState } from "react";
import type { ClaimResult } from "../api/client";
import { useClaimCheck } from "../api/useClaimCheck";
import { ErrorState } from "../components/ErrorState";

const EXAMPLES = [
  {
    label: "Actions and intentions",
    text: 'The Prophet ﷺ said that actions are judged by intentions. The Qur\'an teaches that "Allah does not change the condition of a people until they change what is within themselves."',
  },
  {
    label: "Thanking people",
    text: "Whoever does not thank people has not thanked Allah.",
  },
  {
    label: "Charity",
    text: "The Prophet ﷺ said that charity does not decrease wealth and that every Muslim should give in charity every day.",
  },
];

const VERDICT_META: Record<
  ClaimResult["verdict"],
  { label: string; colour: string }
> = {
  supported:           { label: "Supported",           colour: "var(--verdigris)" },
  partially_supported: { label: "Partially supported", colour: "#b07d2a" },
  not_found:           { label: "Not found",           colour: "var(--ink-60)" },
  unverifiable:        { label: "Unverifiable",        colour: "var(--ink-60)" },
};

function ClaimCard({ result }: { result: ClaimResult }) {
  const meta = VERDICT_META[result.verdict] ?? { label: result.verdict, colour: "var(--ink-60)" };
  return (
    <article style={{
      border: "var(--rule)",
      borderInlineStart: "3px solid var(--ink-12)",
      padding: "1rem 1.25rem",
      marginBlockEnd: "1.25rem",
      background: "color-mix(in srgb, var(--page) 94%, white)",
    }}>
      <p style={{ margin: "0 0 0.4rem", maxWidth: "var(--measure)" }}>{result.claim}</p>
      <p className="data" style={{ margin: "0 0 0.25rem", color: meta.colour }}>
        {meta.label}
      </p>
      {result.note && (
        <p className="data" style={{ margin: "0 0 0.75rem", color: "var(--ink-60)" }}>
          {result.note}
        </p>
      )}
      {result.records.map((rec) => (
        <div key={rec.id} style={{
          border: "var(--rule)", padding: "0.75rem 1rem", marginBlockStart: "0.75rem",
          background: "color-mix(in srgb, var(--page) 97%, white)",
        }}>
          <p className="data" style={{ margin: "0 0 0.4rem" }}>{rec.reference_display}</p>
          <p className="arabic" dir="rtl" lang="ar" style={{ margin: 0 }}>
            {rec.addenda_ar ? `${rec.text_ar} ${rec.addenda_ar}` : rec.text_ar}
          </p>
          {rec.translation_en && (
            <p style={{ margin: "0.5rem 0 0" }}>{rec.translation_en}</p>
          )}
        </div>
      ))}
    </article>
  );
}

export function Claims() {
  const [text, setText] = useState("");
  const { phase, claims, results, errorMessage, run, reset } = useClaimCheck();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || phase === "extracting" || phase === "assessing") return;
    run(text);
  };

  const streaming = phase === "extracting" || phase === "assessing";

  return (
    <main style={{ maxWidth: "72rem", margin: "0 auto", padding: "2rem 1.5rem 6rem" }}>
      <header style={{ marginBlockEnd: "2rem" }}>
        <h1 style={{ fontSize: "var(--step-3)", margin: "0 0 0.25rem", fontWeight: 600 }}>Claims</h1>
        <p className="data" style={{ margin: 0 }}>
          paste English text containing Islamic claims — Sanad checks each one against
          the Qur'an and the Kutub al-Sittah and returns a verdict per claim
        </p>
      </header>

      {!streaming && (
        <form onSubmit={handleSubmit} style={{ marginBlockEnd: "2rem" }}>
          <label htmlFor="claims-input" className="data"
                 style={{ display: "block", marginBlockEnd: "0.4rem" }}>
            paste a paragraph containing Islamic claims
          </label>
          <textarea
            id="claims-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            style={{
              width: "100%", padding: "0.9rem 1rem",
              background: "color-mix(in srgb, var(--page) 94%, white)",
              border: "var(--rule)", color: "var(--ink)", font: "inherit",
              lineHeight: 1.7, resize: "vertical",
            }}
          />
          <div style={{ display: "flex", gap: "0.75rem", marginBlockStart: "0.75rem",
                        flexWrap: "wrap" }}>
            <button type="submit" disabled={text.trim().length === 0}
                    style={{ font: "inherit", padding: "0.5rem 1.25rem",
                             border: "1px solid var(--ink)", background: "var(--ink)",
                             color: "var(--page)", cursor: "pointer" }}>
              Check claims
            </button>
            {phase !== "idle" && (
              <button type="button" onClick={() => { reset(); setText(""); }}
                      style={{ font: "inherit", padding: "0.5rem 1.25rem",
                               border: "1px solid var(--ink-30)", background: "transparent",
                               color: "var(--ink)", cursor: "pointer" }}>
                Start over
              </button>
            )}
          </div>
          {phase === "idle" && (
            <div style={{ marginBlockStart: "1rem" }}>
              <span className="data" style={{ color: "var(--ink-60)", marginInlineEnd: "0.5rem" }}>
                try an example:
              </span>
              {EXAMPLES.map((ex) => (
                <button key={ex.label} type="button" onClick={() => setText(ex.text)}
                        style={{ font: "inherit", fontSize: "var(--step--1)",
                                 marginInlineEnd: "0.5rem", marginBlockStart: "0.25rem",
                                 padding: "0.2rem 0.6rem", border: "1px solid var(--ink-30)",
                                 background: "transparent", color: "var(--ink)", cursor: "pointer" }}>
                  {ex.label}
                </button>
              ))}
            </div>
          )}
        </form>
      )}

      {streaming && (
        <section aria-live="polite" style={{ marginBlockEnd: "2rem" }}>
          <p className="data" style={{ color: "var(--ink-60)" }}>
            {phase === "extracting" ? "Extracting claims…" : "Checking claims…"}
          </p>
          {claims.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
              {claims.map((c, i) => (
                <li key={i} className="data" style={{ padding: "0.2rem 0", color: "var(--ink-60)" }}>
                  · {c}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {phase === "error" && results.length === 0 && (
        <ErrorState kind="server" detail={errorMessage ?? undefined} />
      )}

      {results.length > 0 && (
        <section>
          <h2 className="data" style={{ margin: "0 0 1rem", fontSize: "inherit" }}>
            {results.length} claim{results.length !== 1 ? "s" : ""} checked
          </h2>
          {results.map((r, i) => <ClaimCard key={i} result={r} />)}
          <p className="data" style={{
            marginBlockStart: "1rem", paddingInlineStart: "0.9rem",
            borderInlineStart: "2px solid var(--rubric)", fontFamily: "var(--serif)",
            fontSize: "var(--step-0)", lineHeight: 1.6, color: "var(--ink)", maxWidth: "52ch" }}>
            Sanad checks claims against this corpus only. Absence is not a verdict on the
            wider hadith literature.
          </p>
        </section>
      )}

      {phase === "done" && results.length === 0 && (
        <p role="status" style={{ color: "var(--ink-60)", maxWidth: "var(--measure)" }}>
          No Islamic claims were found in the text.
        </p>
      )}
    </main>
  );
}
