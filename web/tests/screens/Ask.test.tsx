import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Ask } from "../../src/screens/Ask";

// Stage A3 ruling R-A3-17: the backend now DERIVES this caveat from what the
// corpus actually contains (sanad.corpus.scope.corpus_scope), so it no
// longer names specific absent collections -- the absent half is generic and
// stays true regardless of how many more collections Stage A3 ingests.
const SCOPE = "This corpus contains the Qur'an and Sahih al-Bukhari. It does not contain any other hadith collection. Absence from this corpus does not establish that a quotation is fabricated.";

// Any Arabic-script codepoint (blocks + presentation forms).
const ARABIC = /[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]/;

function sse(frames: object[]) {
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    start(c) {
      for (const f of frames) c.enqueue(enc.encode(`data: ${JSON.stringify(f)}\n\n`));
      c.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
}

const publishedFinal = {
  stage: "final",
  payload: {
    status: "published", question_language: "en",
    summary: "The sources address intentions in worship.",
    items: [{
      record_id: "hadith:bukhari:1", framing: "Deeds are judged by their intentions.",
      record: {
        id: "hadith:bukhari:1", reference_display: "Sahih al-Bukhari 1",
        text_ar: "إنما الأعمال بالنيات", text_ar_sha256: "x",
        isnad_ar: "حدثنا الحميدي", collection: "bukhari", hadith_no: "1",
        translation_en: null, translation_disclaimer: null,
      },
    }],
    reached: { quran: false, hadith: true }, unreached_reason: null,
    risk: "GENERAL", requires_handoff: false, abstain_reason: null, corpus_scope: SCOPE,
  },
};

async function ask(question = "intentions?") {
  const user = userEvent.setup();
  render(<Ask />);
  await user.type(screen.getByRole("textbox"), question);
  await user.click(screen.getByRole("button", { name: "Ask" }));
}

afterEach(() => vi.unstubAllGlobals());

describe("Ask screen", () => {
  it("renders the evidence brief, with Arabic only from the record", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sse([
      { stage: "router", payload: { risk: "GENERAL", requires_handoff: false } },
      publishedFinal,
    ])));
    await ask();
    await waitFor(() => expect(screen.getByTestId("ask-summary")).toBeInTheDocument());

    // English prose fields carry no Arabic; the scripture is in the record matn.
    expect(ARABIC.test(screen.getByTestId("ask-summary").textContent ?? "")).toBe(false);
    expect(ARABIC.test(screen.getByTestId("ask-framing").textContent ?? "")).toBe(false);
    expect(ARABIC.test(screen.getByTestId("ask-matn").textContent ?? "")).toBe(true);
    expect(screen.getByTestId("ask-isnad")).toBeInTheDocument();
    // hadith shown -> the does-not-grade note appears once
    expect(screen.getAllByTestId("no-grading")).toHaveLength(1);
    expect(screen.getByTestId("ask-scope")).toHaveTextContent(/does not contain any other hadith collection/i);
  });

  it("shows the abstain reason honestly, not a fabricated answer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sse([
      { stage: "final", payload: {
        status: "abstained", question_language: "en", summary: null, items: [],
        reached: { quran: false, hadith: false }, unreached_reason: null,
        risk: "GENERAL", requires_handoff: false,
        abstain_reason: "No evidence was found in this corpus.", corpus_scope: SCOPE } },
    ])));
    await ask();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no evidence was found/i));
    expect(screen.queryByTestId("ask-summary")).toBeNull();
    expect(screen.getByTestId("ask-scope")).toBeInTheDocument();
  });

  it("routes a personal-ruling question to a handoff, with no evidence stack", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sse([
      { stage: "router", payload: { risk: "PERSONAL_RULING", requires_handoff: true } },
      { stage: "final", payload: {
        status: "abstained", question_language: "en", summary: null, items: [],
        reached: { quran: false, hadith: false }, unreached_reason: null,
        risk: "PERSONAL_RULING", requires_handoff: true,
        abstain_reason: null, corpus_scope: SCOPE } },
    ])));
    await ask("should I divorce my wife?");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/qualified|person/i));
    expect(screen.queryByTestId("ask-summary")).toBeNull();
    expect(screen.queryByTestId("ask-matn")).toBeNull();
  });

  it("shows a server error on an error frame", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sse([
      { stage: "error", payload: { code: "EXPAND_FAILED", message: "internal error" } },
    ])));
    await ask();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/returned an error/i));
  });

  it("shows the abstain, not an error, when a stage fails then the pipeline abstains", async () => {
    // Production sequence for a recoverable stage failure: an `error` frame
    // followed by a `final` abstained frame. The final must win.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sse([
      { stage: "error", payload: { code: "select_failed", message: "internal error" } },
      { stage: "final", payload: {
        status: "abstained", question_language: "en", summary: null, items: [],
        reached: { quran: true, hadith: false }, unreached_reason: null,
        risk: "GENERAL", requires_handoff: false,
        abstain_reason: "The brief could not be generated.", corpus_scope: SCOPE } },
    ])));
    await ask();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/could not be generated/i));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("surfaces an error (not a permanent spinner) when the stream closes with no terminal frame", async () => {
    // A truncated SSE body / recycled worker: some stage frames, then a clean
    // EOF with no `final` or `error`. Must not hang on "Thinking…".
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sse([
      { stage: "router", payload: { risk: "GENERAL", requires_handoff: false } },
      { stage: "retrieve", payload: { candidate_count: 2 } },
    ])));
    await ask();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/returned an error/i));
    expect(screen.getByRole("button", { name: "Ask" })).not.toBeDisabled();
  });

  it("says unreachable when the endpoint cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    await ask();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach/i));
  });

  it("reveals pipeline stages while streaming, then the result", async () => {
    let ctrl!: ReadableStreamDefaultController;
    const enc = new TextEncoder();
    const stream = new ReadableStream({ start(c) { ctrl = c; } });
    const push = (o: object) => ctrl.enqueue(enc.encode(`data: ${JSON.stringify(o)}\n\n`));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } })));

    await ask();
    push({ stage: "router", payload: { risk: "GENERAL", requires_handoff: false } });
    push({ stage: "retrieve", payload: { candidate_count: 2 } });
    await waitFor(() => expect(screen.getByTestId("stage-retrieve")).toHaveAttribute("data-status", "done"));
    expect(screen.getByTestId("stage-audit")).toHaveAttribute("data-status", "pending");

    push(publishedFinal);
    ctrl.close();
    await waitFor(() => expect(screen.getByTestId("ask-summary")).toBeInTheDocument());
  });

  it("disables Ask while the input is empty", () => {
    render(<Ask />);
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });
});
