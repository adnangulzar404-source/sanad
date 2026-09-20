import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IsnadTrace } from "../../src/components/IsnadTrace";
import type { QuotationOut } from "../../src/api/client";

const base: QuotationOut = {
  quoted_text: "قُلْ هُوَ ٱللَّهُ أَحَدٌ",
  start: 0, end: 20, verdict: "EXACT", tier: "light", score: 1,
  record: {
    id: "quran:112:1", reference_display: "Al-Ikhlas 112:1",
    text_ar: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", text_ar_sha256: "abc123", surah: 112, ayah: 1,
    translation_en: "Say: He is Allah, the One!", translation_disclaimer: "No translation…",
  },
  given_reference: null, diff: null, also_at: [],
} as unknown as QuotationOut;

const q = (over: Partial<QuotationOut>) => ({ ...base, ...over }) as QuotationOut;

describe("IsnadTrace", () => {
  it("renders all five links in order", () => {
    render(<IsnadTrace quotation={base} />);
    const links = screen.getAllByTestId(/^link-/).map((e) => e.getAttribute("data-testid"));
    expect(links).toEqual(["link-quoted", "link-normalized", "link-matched", "link-cited", "link-source"]);
  });

  it("completes the chain on EXACT", () => {
    render(<IsnadTrace quotation={base} />);
    expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "complete");
  });

  it("breaks at the text link on NEAR_MATCH", () => {
    render(<IsnadTrace quotation={q({ verdict: "NEAR_MATCH", tier: "aggressive", score: 0.93 })} />);
    expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "broken");
    expect(screen.getByTestId("link-matched")).toHaveAttribute("data-broken", "true");
  });

  it("breaks at the citation link on WRONG_REFERENCE, leaving the text link intact", () => {
    render(<IsnadTrace quotation={q({ verdict: "WRONG_REFERENCE", given_reference: "2:255" })} />);
    expect(screen.getByTestId("link-matched")).toHaveAttribute("data-broken", "false");
    expect(screen.getByTestId("link-cited")).toHaveAttribute("data-broken", "true");
  });

  it("terminates early on NOT_FOUND and shows no matched record", () => {
    render(<IsnadTrace quotation={q({ verdict: "NOT_FOUND", record: null, tier: null, score: 0 })} />);
    expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "terminated");
    expect(screen.getByTestId("link-matched")).toHaveTextContent(/no match/i);
  });

  it("reports the tier that produced the match", () => {
    render(<IsnadTrace quotation={q({ verdict: "EXACT_ORTHOGRAPHY", tier: "standard" })} />);
    expect(screen.getByTestId("link-normalized")).toHaveTextContent("standard");
  });

  it("discloses other locations when the verse is repeated", () => {
    render(<IsnadTrace quotation={q({ also_at: ["quran:55:16", "quran:55:18"] })} />);
    expect(screen.getByTestId("link-matched")).toHaveTextContent(/also appears at 2 other/i);
  });

  it("says nothing about other locations when the verse is unique", () => {
    render(<IsnadTrace quotation={base} />);
    expect(screen.getByTestId("link-matched")).not.toHaveTextContent(/also appears/i);
  });

  it("shows the citation the user gave when one was found", () => {
    render(<IsnadTrace quotation={q({ verdict: "WRONG_REFERENCE", given_reference: "Al-Baqarah 2:255" })} />);
    expect(screen.getByTestId("link-cited")).toHaveTextContent("Al-Baqarah 2:255");
  });

  it("says no citation was given when none was", () => {
    render(<IsnadTrace quotation={base} />);
    expect(screen.getByTestId("link-cited")).toHaveTextContent(/no citation given/i);
  });

  it("renders the quoted text byte-identical to the input", () => {
    const canonical = "قُلْ هُوَ";
    render(<IsnadTrace quotation={q({ quoted_text: canonical })} />);
    expect(screen.getByTestId("link-quoted").textContent).toContain(canonical);
  });

  it("does not invent a licence when no source metadata was passed", () => {
    render(<IsnadTrace quotation={base} />);
    expect(screen.queryByText(/Tanzil Uthmani/)).toBeNull();
    expect(screen.queryByText(/CC-BY-3\.0/)).toBeNull();
    expect(screen.getByTestId("link-source")).toHaveTextContent("quran:112:1");
    const link = screen.getByTestId("link-source").querySelector("a");
    expect(link).toHaveAttribute("href", "#provenance");
  });

  it("shows the real source metadata instead of a fallback when it is passed", () => {
    render(
      <IsnadTrace
        quotation={base}
        source={{ title: "Tanzil Qur'an Text (Uthmani)", license_id: "CC-BY-3.0" }}
      />
    );
    expect(screen.getByTestId("link-source")).toHaveTextContent("Tanzil Qur'an Text (Uthmani)");
    expect(screen.getByTestId("link-source")).toHaveTextContent("CC-BY-3.0");
    expect(screen.getByTestId("link-source").querySelector("a")).toBeNull();
  });

  it("renders every link when the user prefers reduced motion", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: q.includes("prefers-reduced-motion"),
      media: q, addEventListener: () => {}, removeEventListener: () => {},
      addListener: () => {}, removeListener: () => {}, onchange: null,
      dispatchEvent: () => false,
    }));
    render(<IsnadTrace quotation={base} />);
    expect(screen.getAllByTestId(/^link-/)).toHaveLength(5);
    expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "complete");
  });
});
