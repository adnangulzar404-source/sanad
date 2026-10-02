import { useCallback, useState } from "react";
import type { AskFinal, AskTurn } from "./client";

/** The pipeline stages, in the order they stream, with the copy the reveal
 * shows. Not every stage fires on every request (a handoff emits only
 * `router` then `final`; an abstain may stop after `retrieve`), so the reveal
 * marks stages done as their events arrive rather than assuming all six. */
export const ASK_STAGES = [
  { key: "router", label: "Reviewing the question" },
  { key: "expand", label: "Understanding your question" },
  { key: "retrieve", label: "Searching the corpus" },
  { key: "select", label: "Selecting evidence" },
  { key: "check", label: "Checking safety guards" },
  { key: "audit", label: "Auditing" },
] as const;

export type AskPhase = "idle" | "streaming" | "done" | "unreachable" | "error";
export type StageStatus = "pending" | "active" | "done";

/** A prior answer in the running thread, stored client-side for display.
 * `final` is the full server response (records rendered from DB) — kept so
 * each answer in the list renders Arabic from its own `record` objects, not
 * from history prose. The `turn` is the server-safe version (English + IDs
 * only) sent as history on the next request. */
export interface PastAnswer {
  question: string;
  final: AskFinal;
  /** Server-safe turn: English question + summary + record IDs only. */
  turn: AskTurn;
}

/** Same reasoning as useVerify's NOT_UP_YET: a cold start or crashed instance
 * returns these, meaning "not up yet", not "broken". */
const NOT_UP_YET = new Set([502, 503, 504]);

// Match backend HISTORY_MAX_TURNS (api/sanad/api/schemas.py).
const HISTORY_MAX = 6;

function computeStages(seen: Set<string>): Record<string, StageStatus> {
  const out: Record<string, StageStatus> = {};
  let activeAssigned = false;
  for (const s of ASK_STAGES) {
    if (seen.has(s.key)) out[s.key] = "done";
    else if (!activeAssigned) {
      out[s.key] = "active";
      activeAssigned = true;
    } else out[s.key] = "pending";
  }
  return out;
}

export function useAsk() {
  const [phase, setPhase] = useState<AskPhase>("idle");
  const [stages, setStages] = useState<Record<string, StageStatus>>(() =>
    computeStages(new Set()),
  );
  const [final, setFinal] = useState<AskFinal | null>(null);
  // Past answers accumulated client-side. The `turn` field of each is sent as
  // `history` to the server on the next request (English + IDs only, no Arabic).
  const [pastAnswers, setPastAnswers] = useState<PastAnswer[]>([]);

  // `run` accepts the current history to send (derived by Ask.tsx from
  // pastAnswers so the callback needs no closure over state).
  const run = useCallback(async (question: string, history: AskTurn[] = []) => {
    setPhase("streaming");
    setFinal(null);
    const seen = new Set<string>();
    setStages(computeStages(seen));

    let resp: Response;
    try {
      resp = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question, history }),
      });
    } catch {
      setPhase("unreachable");
      return;
    }
    if (!resp.ok) {
      setPhase(NOT_UP_YET.has(resp.status) ? "unreachable" : "error");
      return;
    }
    if (!resp.body) {
      setPhase("error");
      return;
    }

    // We do NOT use EventSource: it is GET-only, and /api/ask is POST. Parse
    // the trivial `data: {json}\n\n` SSE framing by hand off the fetch body.
    // No auto-reconnect — a re-fired pipeline is a second model spend.
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    // `final` is the only terminal frame that carries a result. We track it in
    // a local (not by reading `phase`, which would be stale in this closure) so
    // that:
    //  - an `error` frame does NOT set the phase immediately: production emits
    //    `error` THEN a `final` abstained frame, and the final must win without
    //    a flicker through the error state;
    //  - a lone `error` frame with no following `final` (a hard mid-stream
    //    crash) still surfaces as an error, via the post-loop check;
    //  - a stream that closes cleanly with NO terminal frame at all (a proxy
    //    idle-timeout, a recycled worker, a truncated SSE body) surfaces as an
    //    error instead of hanging on "Thinking…" forever.
    let sawFinal = false;
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const line = frame.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const evt = JSON.parse(line.slice("data: ".length));
          if (evt.stage === "final") {
            const finalPayload = evt.payload as AskFinal;
            setFinal(finalPayload);
            setPhase("done");
            sawFinal = true;
            // Accumulate published turns only. Abstained turns carry no usable
            // summary or IDs, so they add no value as history context.
            if (finalPayload.status === "published") {
              const turn: AskTurn = {
                question,
                summary: finalPayload.summary,
                item_ids: finalPayload.items.map((i) => i.record_id),
              };
              setPastAnswers((prev) =>
                [...prev, { question, final: finalPayload, turn }].slice(-HISTORY_MAX),
              );
            }
          } else if (evt.stage !== "error") {
            seen.add(evt.stage);
            setStages(computeStages(seen));
          }
          // `error` frames are intentionally not acted on here; see above.
        }
        if (sawFinal) break; // stop reading once the terminal result arrived
      }
      if (!sawFinal) setPhase("error");
    } catch {
      // Mid-stream drop (a throw, not a graceful EOF). Keep a result that
      // already arrived; otherwise this is an error.
      if (!sawFinal) setPhase("error");
    }
  }, []);

  const startOver = useCallback(() => {
    setPastAnswers([]);
    setFinal(null);
    setPhase("idle");
    setStages(computeStages(new Set()));
  }, []);

  return { phase, stages, final, run, pastAnswers, startOver };
}
