import { useState } from "react";
import { ASK_STAGES, useAsk } from "../api/useAsk";
import { AskEvidenceCard } from "../components/AskEvidenceCard";
import { ErrorState } from "../components/ErrorState";
import { HandoffCard } from "../components/HandoffCard";

const EXAMPLE = "Is there a hadith that actions are judged by intentions?";

const MARK: Record<string, string> = { done: "✓", active: "…", pending: "·" };

export function Ask() {
  const [question, setQuestion] = useState("");
  const { phase, stages, final, run } = useAsk();

  const showTranslationNote = final?.items.some((i) => i.record?.translation_en);
  const showGradingNote = final?.items.some((i) => i.record?.collection);
  const translationDisclaimer = final?.items.find(
    (i) => i.record?.translation_disclaimer,
  )?.record?.translation_disclaimer;

  return (
    <main style={{ maxWidth: "72rem", margin: "0 auto", padding: "2rem 1.5rem 6rem" }}>
      <header style={{ marginBlockEnd: "2rem" }}>
        <h1 style={{ fontSize: "var(--step-3)", margin: "0 0 0.25rem", fontWeight: 600 }}>Ask</h1>
        <p className="data" style={{ margin: 0 }}>
          ask a question and read an evidence brief drawn from the Qur'an and Sahih al-Bukhari —
          Sanad selects passages and frames them in English; every Arabic quotation is rendered
          from the source, never written by the model
        </p>
      </header>

      <form
        onSubmit={(e) => { e.preventDefault(); run(question); }}
        style={{ marginBlockEnd: "2rem" }}
      >
        <label htmlFor="ask-input" className="data" style={{ display: "block", marginBlockEnd: "0.4rem" }}>
          your question
        </label>
        <textarea
          id="ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          style={{
            width: "100%", padding: "0.9rem 1rem", background: "color-mix(in srgb, var(--page) 94%, white)",
            border: "var(--rule)", color: "var(--ink)", font: "inherit", lineHeight: 1.7, resize: "vertical",
          }}
        />
        <div style={{ display: "flex", gap: "0.75rem", marginBlockStart: "0.75rem" }}>
          <button type="submit" disabled={question.trim().length === 0 || phase === "streaming"}
                  style={{ font: "inherit", padding: "0.5rem 1.25rem", border: "1px solid var(--ink)",
                           background: "var(--ink)", color: "var(--page)", cursor: "pointer" }}>
            {phase === "streaming" ? "Thinking…" : "Ask"}
          </button>
          <button type="button" onClick={() => setQuestion(EXAMPLE)}
                  style={{ font: "inherit", padding: "0.5rem 1.25rem", border: "1px solid var(--ink-30)",
                           background: "transparent", color: "var(--ink)", cursor: "pointer" }}>
            Load example
          </button>
        </div>
      </form>

      {phase === "idle" && (
        <p role="status" style={{ color: "var(--ink-60)", maxWidth: "var(--measure)" }}>
          Ask a question above to build an evidence brief.
        </p>
      )}

      {phase === "streaming" && (
        <section aria-label="progress" aria-live="polite">
          <ol style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {ASK_STAGES.map((s) => {
              const status = stages[s.key] ?? "pending";
              return (
                <li key={s.key} data-testid={`stage-${s.key}`} data-status={status}
                    className="data"
                    style={{ display: "flex", gap: "0.6rem", padding: "0.25rem 0",
                             color: status === "pending" ? "var(--ink-30)" : "var(--ink)" }}>
                  <span aria-hidden style={{ width: "1rem" }}>{MARK[status]}</span>
                  <span>{s.label}</span>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {phase === "unreachable" && <ErrorState kind="unreachable" />}
      {phase === "error" && <ErrorState kind="server" />}

      {phase === "done" && final && (
        <>
          {final.requires_handoff ? (
            <HandoffCard risk={final.risk} />
          ) : final.status === "abstained" ? (
            <section>
              <p role="status" style={{ color: "var(--ink-60)", maxWidth: "var(--measure)" }}>
                {final.abstain_reason ?? "No evidence was found in this corpus."}
              </p>
              <p data-testid="ask-scope" style={{
                marginBlockStart: "1rem", paddingInlineStart: "0.9rem",
                borderInlineStart: "2px solid var(--rubric)", fontFamily: "var(--serif)",
                fontSize: "var(--step-0)", lineHeight: 1.6, color: "var(--ink)", maxWidth: "52ch" }}>
                {final.corpus_scope}
              </p>
            </section>
          ) : (
            <>
              {final.summary && (
                <section style={{ marginBlockEnd: "2rem" }}>
                  <h2 className="data" style={{ margin: "0 0 0.6rem" }}>in brief</h2>
                  <p data-testid="ask-summary" style={{ margin: 0, maxWidth: "var(--measure)" }}>
                    {final.summary}
                  </p>
                </section>
              )}

              <section>
                <h2 className="data" style={{ margin: "0 0 0.6rem" }}>evidence</h2>
                {(final.reached.quran || final.reached.hadith) && (
                  <p data-testid="ask-reached" className="data" style={{ margin: "0 0 0.75rem" }}>
                    Drawn from: {[
                      final.reached.quran && "the Qur'an",
                      final.reached.hadith && "Sahih al-Bukhari",
                    ].filter(Boolean).join(" and ")}
                  </p>
                )}
                {final.items.map((item) => (
                  <AskEvidenceCard key={item.record_id} item={item} />
                ))}

                {showTranslationNote && translationDisclaimer && (
                  <p data-testid="translation-disclaimer" className="data" style={{ marginBlockStart: "1rem" }}>
                    {translationDisclaimer}
                  </p>
                )}
                {showGradingNote && (
                  <p data-testid="no-grading" className="data" style={{ marginBlockStart: "0.5rem" }}>
                    Sanad confirms wording against this printed edition. It does not grade
                    authenticity (ṣaḥīḥ/ḍaʿīf); that requires a scholarly source.
                  </p>
                )}
                <p data-testid="ask-scope" style={{
                  marginBlockStart: "1rem", paddingInlineStart: "0.9rem",
                  borderInlineStart: "2px solid var(--rubric)", fontFamily: "var(--serif)",
                  fontSize: "var(--step-0)", lineHeight: 1.6, color: "var(--ink)", maxWidth: "52ch" }}>
                  {final.corpus_scope}
                </p>
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}
