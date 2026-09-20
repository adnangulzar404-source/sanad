import { useCallback, useState } from "react";
import { ApiError, ApiUnreachable, verify, type VerifyResponse } from "./client";

export type VerifyState = "idle" | "loading" | "ok" | "unreachable" | "error";

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
      else if (e instanceof ApiError) { setState("error"); setError(String(e.status)); }
      else { setState("error"); setError("unexpected"); }
    }
  }, []);

  const reset = useCallback(() => {
    setState("idle"); setResult(null); setError(undefined);
  }, []);

  return { state, result, error, run, reset };
}
