import { useCallback, useState } from "react";
import type { ClaimResult } from "./client";

export type ClaimPhase = "idle" | "extracting" | "assessing" | "done" | "error";

const NOT_UP_YET = new Set([502, 503, 504]);

export function useClaimCheck() {
  const [phase, setPhase] = useState<ClaimPhase>("idle");
  const [claims, setClaims] = useState<string[]>([]);
  const [results, setResults] = useState<ClaimResult[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const run = useCallback(async (text: string) => {
    setPhase("extracting");
    setClaims([]);
    setResults([]);
    setErrorMessage(null);

    let resp: Response;
    try {
      resp = await fetch("/api/claim-check", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
    } catch {
      setPhase("error");
      return;
    }
    if (!resp.ok) {
      setPhase(NOT_UP_YET.has(resp.status) ? "error" : "error");
      return;
    }
    if (!resp.body) { setPhase("error"); return; }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
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
          if (evt.stage === "extract") {
            setClaims(evt.payload.claims as string[]);
            setPhase("assessing");
          } else if (evt.stage === "assess") {
            setResults(evt.payload.results as ClaimResult[]);
          } else if (evt.stage === "final") {
            setPhase("done");
            sawFinal = true;
          } else if (evt.stage === "error") {
            setErrorMessage((evt.payload as { message?: string }).message ?? null);
            setPhase("error");
            sawFinal = true;
          }
        }
        if (sawFinal) break;
      }
      if (!sawFinal) setPhase("error");
    } catch {
      if (!sawFinal) setPhase("error");
    }
  }, []);

  const reset = useCallback(() => {
    setPhase("idle");
    setClaims([]);
    setResults([]);
    setErrorMessage(null);
  }, []);

  return { phase, claims, results, errorMessage, run, reset };
}
