import { useState } from "react";
import { useVerify } from "../api/useVerify";
import { ClaimList } from "../components/ClaimList";
import { ErrorState } from "../components/ErrorState";
import { EvidenceCard } from "../components/EvidenceCard";
import { HandoffCard } from "../components/HandoffCard";
import { MarkedText } from "../components/MarkedText";

const EXAMPLE =
  "Islam teaches tawhid. The Qur'an says «قُلْ هُوَ " +
  "ٱللَّهُ أَحَدٌ» " +
  "(Al-Baqarah 2:255). All scholars agree that this settles the matter.";

export function Verify() {
  const [text, setText] = useState("");
  const { state, result, error, run } = useVerify();

  return (
    <main style={{ maxWidth: "72rem", margin: "0 auto", padding: "2rem 1.5rem 6rem" }}>
      <header style={{ marginBlockEnd: "2rem" }}>
        <h1 style={{ fontSize: "var(--step-3)", margin: "0 0 0.25rem", fontWeight: 600 }}>Sanad</h1>
        <p className="data" style={{ margin: 0 }}>
          check whether a quotation is genuinely in the Qur'an, and see the chain back to its source
        </p>
      </header>

      <form
        onSubmit={(e) => { e.preventDefault(); run(text); }}
        style={{ marginBlockEnd: "2rem" }}
      >
        <label htmlFor="input" className="data" style={{ display: "block", marginBlockEnd: "0.4rem" }}>
          paste anything — a chatbot answer, a sermon, a forum post
        </label>
        <textarea
          id="input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          style={{
            width: "100%", padding: "0.9rem 1rem", background: "color-mix(in srgb, var(--page) 94%, white)",
            border: "var(--rule)", color: "var(--ink)", font: "inherit", lineHeight: 1.7, resize: "vertical",
          }}
        />
        <div style={{ display: "flex", gap: "0.75rem", marginBlockStart: "0.75rem" }}>
          <button type="submit" disabled={text.trim().length === 0 || state === "loading"}
                  style={{ font: "inherit", padding: "0.5rem 1.25rem", border: "1px solid var(--ink)",
                           background: "var(--ink)", color: "var(--page)", cursor: "pointer" }}>
            {state === "loading" ? "Checking…" : "Verify"}
          </button>
          <button type="button" onClick={() => setText(EXAMPLE)}
                  style={{ font: "inherit", padding: "0.5rem 1.25rem", border: "1px solid var(--ink-30)",
                           background: "transparent", color: "var(--ink)", cursor: "pointer" }}>
            Load example
          </button>
        </div>
      </form>

      {state === "idle" && <ErrorState kind="idle" />}
      {state === "unreachable" && <ErrorState kind="unreachable" />}
      {state === "error" && <ErrorState kind="server" detail={error} />}

      {state === "ok" && result && (
        <>
          <section style={{ marginBlockEnd: "2rem" }}>
            <h2 className="data" style={{ margin: "0 0 0.6rem" }}>your text</h2>
            <MarkedText text={text} quotations={result.quotations} />
          </section>

          {result.requires_handoff ? (
            <HandoffCard risk={result.risk} />
          ) : result.quotations.length === 0 ? (
            <ErrorState kind="no-arabic" />
          ) : (
            <section>
              <h2 className="data" style={{ margin: "0 0 0.6rem" }}>evidence</h2>
              {result.quotations.map((q, i) => (
                <EvidenceCard key={i} quotation={q} corpusScope={result.corpus_scope} />
              ))}
            </section>
          )}

          {!result.requires_handoff && <ClaimList claims={result.claims} />}
        </>
      )}
    </main>
  );
}
