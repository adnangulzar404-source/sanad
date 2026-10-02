import { useState } from "react";
import type { AskFinal, AskTurn } from "../api/client";
import { ASK_STAGES, type PastAnswer, useAsk } from "../api/useAsk";
import { AskEvidenceCard } from "../components/AskEvidenceCard";
import { ErrorState } from "../components/ErrorState";
import { HandoffCard } from "../components/HandoffCard";

const EXAMPLE = "Is there a hadith that actions are judged by intentions?";

const MARK: Record<string, string> = { done: "✓", active: "…", pending: "·" };

/** One published answer brief (reused for both past answers and the current
 * answer). Arabic renders from `final.items[*].record` — never from prose. */
function AnswerBrief({ question, final }: { question: string; final: AskFinal }) {
  const showTranslationNote = final.items.some((i) => i.record?.translation_en);
  const showGradingNote = final.items.some((i) => i.record?.collection);
  const translationDisclaimer = final.items.find(
    (i) => i.record?.translation_disclaimer,
  )?.record?.translation_disclaimer;

  return (
    <section style={{ marginBlockEnd: "2.5rem" }}>
      <p className="data" style={{ margin: "0 0 0.75rem", color: "var(--ink-60)" }}>
        Q: {question}
      </p>
      {final.requires_handoff ? (
        <HandoffCard risk={final.risk} />
      ) : final.status === "abstained" ? (
        <>
          <p role="status" style={{ color: "var(--ink-60)", maxWidth: "var(--measure)" }}>
            {final.abstain_reason ?? "No evidence was found in this corpus."}
          </p>
          <p data-testid="ask-scope" style={{
            marginBlockStart: "1rem", paddingInlineStart: "0.9rem",
            borderInlineStart: "2px solid var(--rubric)", fontFamily: "var(--serif)",
            fontSize: "var(--step-0)", lineHeight: 1.6, color: "var(--ink)", maxWidth: "52ch" }}>
            {final.corpus_scope}
          </p>
        </>
      ) : (
        <>
          {final.summary && (
            <div style={{ marginBlockEnd: "1.5rem" }}>
              <h3 className="data" style={{ margin: "0 0 0.5rem", fontSize: "inherit" }}>
                in brief
              </h3>
              <p data-testid="ask-summary" style={{ margin: 0, maxWidth: "var(--measure)" }}>
                {final.summary}
              </p>
            </div>
          )}
          <div>
            <h3 className="data" style={{ margin: "0 0 0.5rem", fontSize: "inherit" }}>
              evidence
            </h3>
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
              <p data-testid="translation-disclaimer" className="data"
                 style={{ marginBlockStart: "1rem" }}>
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
          </div>
        </>
      )}
    </section>
  );
}

export function Ask() {
  const [question, setQuestion] = useState("");
  const { phase, stages, final, run, pastAnswers, startOver } = useAsk();

  // Server-safe history: English question + summary + IDs only, no Arabic.
  const history: AskTurn[] = pastAnswers.map((pa) => pa.turn);

  const hasThread = pastAnswers.length > 0 || (phase === "done" && final !== null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || phase === "streaming") return;
    run(question, history);
    setQuestion("");
  };

  const handleStartOver = () => {
    startOver();
    setQuestion("");
  };

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

      {/* Running list of past answers */}
      {pastAnswers.map((pa: PastAnswer, i: number) => (
        <AnswerBrief key={i} question={pa.question} final={pa.final} />
      ))}

      {/* Progress while streaming */}
      {phase === "streaming" && (
        <section aria-label="progress" aria-live="polite" style={{ marginBlockEnd: "2rem" }}>
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

      {/* Error states */}
      {phase === "unreachable" && <ErrorState kind="unreachable" />}
      {phase === "error" && <ErrorState kind="server" />}

      {/* Current answer */}
      {phase === "done" && final && (
        <AnswerBrief question={pastAnswers.length > 0
          ? pastAnswers[pastAnswers.length - 1]?.question ?? ""
          : question}
          final={final} />
      )}

      {/* Question input — initial or follow-up */}
      {!hasThread || phase === "done" ? (
        <form onSubmit={handleSubmit} style={{ marginBlockEnd: "1rem" }}>
          <label htmlFor="ask-input" className="data"
                 style={{ display: "block", marginBlockEnd: "0.4rem" }}>
            {hasThread ? "follow-up question" : "your question"}
          </label>
          <textarea
            id="ask-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            style={{
              width: "100%", padding: "0.9rem 1rem",
              background: "color-mix(in srgb, var(--page) 94%, white)",
              border: "var(--rule)", color: "var(--ink)", font: "inherit",
              lineHeight: 1.7, resize: "vertical",
            }}
          />
          <div style={{ display: "flex", gap: "0.75rem", marginBlockStart: "0.75rem",
                        flexWrap: "wrap" }}>
            <button type="submit"
                    disabled={question.trim().length === 0 || phase === "streaming"}
                    style={{ font: "inherit", padding: "0.5rem 1.25rem",
                             border: "1px solid var(--ink)", background: "var(--ink)",
                             color: "var(--page)", cursor: "pointer" }}>
              {phase === "streaming" ? "Thinking…" : "Ask"}
            </button>
            {!hasThread && (
              <button type="button" onClick={() => setQuestion(EXAMPLE)}
                      style={{ font: "inherit", padding: "0.5rem 1.25rem",
                               border: "1px solid var(--ink-30)", background: "transparent",
                               color: "var(--ink)", cursor: "pointer" }}>
                Load example
              </button>
            )}
            {hasThread && (
              <button type="button" onClick={handleStartOver}
                      style={{ font: "inherit", padding: "0.5rem 1.25rem",
                               border: "1px solid var(--ink-30)", background: "transparent",
                               color: "var(--ink)", cursor: "pointer" }}>
                Start over
              </button>
            )}
          </div>
        </form>
      ) : null}

      {/* Idle state: show input (handled above) with a prompt */}
      {phase === "idle" && !hasThread && (
        <p role="status" style={{ color: "var(--ink-60)", maxWidth: "var(--measure)" }}>
          Ask a question above to build an evidence brief.
        </p>
      )}
    </main>
  );
}
