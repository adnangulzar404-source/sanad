import { useCallback, useState } from "react";
import { ApiError, ApiUnreachable, verify, type VerifyResponse } from "./client";

export type VerifyState = "idle" | "loading" | "ok" | "unreachable" | "error";

/**
 * In production this deploys as a same-origin serverless function: there is
 * no proxy to fail the fetch outright, so `ApiUnreachable` almost never
 * fires. What a cold start or a crashed instance actually produces is one of
 * these statuses -- and they mean "not up yet", not "broken". They get the
 * same reassuring copy as a genuine network failure rather than a bare
 * status code that tells a judge something broke without saying that
 * waiting will fix it.
 */
const NOT_UP_YET = new Set([502, 503, 504]);

export function useVerify() {
  const [state, setState] = useState<VerifyState>("idle");
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | undefined>();

  const run = useCallback(async (text: string) => {
    setState("loading");
    setError(undefined);
    try {
      setResult(await verify(text));
      setState("ok");
    } catch (e) {
      setResult(null);
      if (e instanceof ApiUnreachable) setState("unreachable");
      else if (e instanceof ApiError && NOT_UP_YET.has(e.status)) setState("unreachable");
      else if (e instanceof ApiError) { setState("error"); setError(String(e.status)); }
      else { setState("error"); setError("unexpected"); }
    }
  }, []);

  const reset = useCallback(() => {
    setState("idle"); setResult(null); setError(undefined);
  }, []);

  return { state, result, error, run, reset };
}
