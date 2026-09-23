import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, afterEach } from "vitest";
import { Verify } from "../../src/screens/Verify";

const SCOPE = "This corpus contains the Qur'an and Sahih al-Bukhari. It does not contain Sahih Muslim, the four Sunan, or any other collection, so absence from this corpus does not establish that a quotation is fabricated.";

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

  it("shows no verdict vocabulary at all on a handoff, including marks", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...verified,
      quotations: [
        ...verified.quotations,
        { quoted_text: "إنما الأعمال بالنيات", start: 20, end: 41, verdict: "NOT_FOUND",
          tier: null, score: 0, record: null, given_reference: null, diff: null, also_at: [] },
      ],
      risk: "PERSONAL_RULING", requires_handoff: true, overall: "handoff",
    })));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "Can I marry my cousin? قُلْ هُوَ ٱللَّهُ أَحَدٌ");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await screen.findByRole("alert");
    expect(screen.queryByRole("status")).toBeNull();
    expect(document.querySelectorAll("mark")).toHaveLength(0);
    expect(screen.queryByTitle(/wrong reference|not in this corpus|verified/i)).toBeNull();
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

  it("shows the translation-accuracy disclaimer exactly once, even with several translated citations", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...verified,
      quotations: [
        ...verified.quotations,
        { quoted_text: "قُلْ أَعُوذُ بِرَبِّ ٱلْفَلَقِ", start: 22, end: 45, verdict: "EXACT",
          tier: "light", score: 1,
          record: { id: "quran:113:1", reference_display: "Al-Falaq 113:1",
                    text_ar: "قُلْ أَعُوذُ بِرَبِّ ٱلْفَلَقِ", text_ar_sha256: "def67890", surah: 113, ayah: 1,
                    translation_en: "Say: I seek refuge in the Lord of the Daybreak.",
                    translation_disclaimer: "Not a replacement." },
          given_reference: null, diff: null, also_at: [] },
      ],
    })));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "two verses");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getAllByText(/^Verified$/).length).toBeGreaterThan(0));
    expect(screen.getAllByTestId("translation-disclaimer")).toHaveLength(1);
    expect(screen.getByTestId("translation-disclaimer")).toHaveTextContent(/not a replacement/i);
  });

  it("shows no translation disclaimer when nothing on screen carries a translation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...verified,
      quotations: [{
        ...verified.quotations[0],
        record: { ...verified.quotations[0].record, translation_en: null, translation_disclaimer: null },
      }],
    })));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "one verse");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByText(/^Verified$/)).toBeInTheDocument());
    expect(screen.queryByTestId("translation-disclaimer")).toBeNull();
  });

  it("loads an example that exercises several verdicts", async () => {
    const user = userEvent.setup();
    render(<Verify />);
    await user.click(screen.getByRole("button", { name: /example/i }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value.length).toBeGreaterThan(40);
  });
});
