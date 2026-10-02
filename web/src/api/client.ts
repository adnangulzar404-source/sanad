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

// One prior turn in a threaded Ask conversation. Mirrors backend `AskTurn`
// (api/sanad/api/schemas.py). Only English framing text and record IDs —
// never raw Arabic. The server re-fetches every ID from the corpus.
export interface AskTurn {
  question: string;
  summary: string | null;
  item_ids: string[];
}

// The `/api/ask` SSE `final` payload. Declared by hand rather than generated:
// the endpoint streams `text/event-stream`, so it has no typed JSON body in the
// OpenAPI schema. Mirrors the backend `AskFinalOut` (api/sanad/api/schemas.py).
export interface AskItem {
  record_id: string;
  framing: string;
  matn_translation: string | null;
  record: RecordOut | null;
}
export interface AskReached {
  quran: boolean;
  hadith: boolean;
}
// The `/api/claim-check` SSE `assess` event's per-claim shape.
export interface ClaimResult {
  claim: string;
  verdict: "supported" | "partially_supported" | "not_found" | "unverifiable";
  note: string;
  records: RecordOut[];
}

export interface AskFinal {
  status: "published" | "abstained";
  question_language: string | null;
  summary: string | null;
  items: AskItem[];
  reached: AskReached;
  unreached_reason: string | null;
  risk: string;
  requires_handoff: boolean;
  abstain_reason: string | null;
  corpus_scope: string;
}
