import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, afterEach } from "vitest";
import { Verify } from "../../src/screens/Verify";

const SCOPE = "This corpus contains the Qur'an only. Absence of a quotation from this corpus does not establish that it is fabricated.";

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

const verified = {
  quotations: [{
    quoted_text: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", start: 0, end: 20, verdict: "EXACT",
    tier: "light", score: 1,
    record: { id: "quran:112:1", reference_display: "Al-Ikhlas 112:1",
              text_ar: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", text_ar_sha256: "abc12345", surah: 112, ayah: 1,
              translation_en: "Say: He is Allah, the One!", translation_disclaimer: "Not a replacement." },
    given_reference: null, diff: null, also_at: [] }],
  claims: [], risk: "GENERAL", requires_handoff: false, overall: "grounded", corpus_scope: SCOPE,
};

afterEach(() => vi.unstubAllGlobals());

describe("Verify screen", () => {
  it("shows a verdict after verifying", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(verified)));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "قُلْ هُوَ ٱللَّهُ أَحَدٌ");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByText(/^Verified$/)).toBeInTheDocument());
  });

  it("replaces the evidence stack with a handoff card on a personal ruling", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...verified, risk: "PERSONAL_RULING", requires_handoff: true, overall: "handoff",
    })));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "Can I marry my cousin?");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/qualified/i));
    // the critical assertion: no verdict is shown at all
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("says the verifier is unreachable rather than rendering an empty result", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "anything");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the verifier/i));
  });

  it("treats a 503 as not-up-yet rather than a bare error, since that is what a cold start returns", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ detail: "cold start" }, 503)));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "anything");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the verifier/i));
  });

  it("distinguishes no-quotations-found from not-in-corpus", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...verified, quotations: [], overall: "insufficient_span",
    })));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "plain english");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no quotations found to check/i));
    expect(screen.queryByText(/not in this corpus/i)).toBeNull();
  });

  it("disables verify while the input is empty", () => {
    render(<Verify />);
    expect(screen.getByRole("button", { name: /verify/i })).toBeDisabled();
  });

  it("loads an example that exercises several verdicts", async () => {
    const user = userEvent.setup();
    render(<Verify />);
    await user.click(screen.getByRole("button", { name: /example/i }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value.length).toBeGreaterThan(40);
  });
});
