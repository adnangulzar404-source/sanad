import type { components } from "./types";

export type VerifyResponse = components["schemas"]["VerifyResponse"];
export type QuotationOut = components["schemas"]["QuotationOut"];
export type RecordOut = components["schemas"]["RecordOut"];
export type ClaimOut = components["schemas"]["ClaimOut"];
export type RecordDetailOut = components["schemas"]["RecordDetailOut"];
export type CorpusResponse = components["schemas"]["CorpusResponse"];
export type CorpusSourceOut = components["schemas"]["CorpusSourceOut"];
export type CorpusStatsOut = components["schemas"]["CorpusStatsOut"];

/** The API could not be reached at all. Distinct from an error it returned. */
export class ApiUnreachable extends Error {
  constructor(cause?: unknown) {
    super("Cannot reach the verifier.");
    this.name = "ApiUnreachable";
    this.cause = cause;
  }
}

/** The API answered, with a status we cannot use. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, body: string) {
    super(`The verifier returned ${status}.`);
    this.name = "ApiError";
    this.status = status;
    this.cause = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (cause) {
    throw new ApiUnreachable(cause);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await response.text().catch(() => ""));
  }
  return (await response.json()) as T;
}

export function verify(text: string): Promise<VerifyResponse> {
  return apiFetch<VerifyResponse>("/api/verify", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function getCorpus(): Promise<CorpusResponse> {
  return apiFetch<CorpusResponse>("/api/corpus");
}
