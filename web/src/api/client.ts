import type { components } from "./types";

export type VerifyResponse = components["schemas"]["VerifyResponse"];
export type QuotationOut = components["schemas"]["QuotationOut"];
export type RecordOut = components["schemas"]["RecordOut"];
export type ClaimOut = components["schemas"]["ClaimOut"];

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

export interface CorpusSource {
  id: string;
  kind: string;
  title: string;
  publisher: string | null;
  edition: string | null;
  url: string;
  license_id: string;
  license_url: string | null;
  attribution: string;
  retrieved_at: string;
  upstream_sha256: string;
  modifications: string;
}

export interface CorpusResponse {
  db_sha256: string;
  db_path: string;
  stats: { records: number; sources: number; translations: number };
  scope: string;
  sources: CorpusSource[];
}

export function getCorpus(): Promise<CorpusResponse> {
  return apiFetch<CorpusResponse>("/api/corpus");
}
