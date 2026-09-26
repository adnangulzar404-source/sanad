import { useCallback, useState } from "react";
import type { AskFinal } from "./client";

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

/** Same reasoning as useVerify's NOT_UP_YET: a cold start or crashed instance
 * returns these, meaning "not up yet", not "broken". */
const NOT_UP_YET = new Set([502, 503, 504]);

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

  const run = useCallback(async (question: string) => {
    setPhase("streaming");
    setFinal(null);
    const seen = new Set<string>();
    setStages(computeStages(seen));

    let resp: Response;
    try {
      resp = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question }),
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
            setFinal(evt.payload as AskFinal);
            setPhase("done");
          } else if (evt.stage === "error") {
            setPhase("error");
          } else {
            seen.add(evt.stage);
            setStages(computeStages(seen));
          }
        }
      }
    } catch {
      // Mid-stream drop. If `final` already arrived, keep the result.
      setPhase((p) => (p === "done" ? p : "error"));
    }
  }, []);

  return { phase, stages, final, run };
}
