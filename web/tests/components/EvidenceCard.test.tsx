import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceCard } from "../../src/components/EvidenceCard";
import type { QuotationOut } from "../../src/api/client";

const SCOPE = "This corpus contains the Qur'an only. Absence of a quotation from this corpus does not establish that it is fabricated.";

const base = {
  quoted_text: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", start: 0, end: 20,
  verdict: "EXACT", tier: "light", score: 1,
  record: { id: "quran:112:1", reference_display: "Al-Ikhlas 112:1",
            text_ar: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", text_ar_sha256: "abc12345",
            surah: 112, ayah: 1, translation_en: "Say: He is Allah, the One!",
            translation_disclaimer: "No translation of Quran can be a hundred percent accurate." },
  given_reference: null, diff: null, also_at: [],
} as unknown as QuotationOut;

const q = (over: Partial<QuotationOut>) => ({ ...base, ...over }) as QuotationOut;

describe("EvidenceCard", () => {
  it("attaches the corpus-scope caveat to a NOT_FOUND verdict", () => {
    render(<EvidenceCard quotation={q({ verdict: "NOT_FOUND", record: null })} corpusScope={SCOPE} />);
    expect(screen.getByTestId("scope-caveat")).toHaveTextContent(/does not establish that it is fabricated/i);
  });

  it("does not attach the caveat to a verified verdict", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.queryByTestId("scope-caveat")).toBeNull();
  });

  it("renders the diff when there is one", () => {
    render(<EvidenceCard quotation={q({ verdict: "NEAR_MATCH", diff: [["quoted-only", "x"], ["corpus-only", "y"]] })} corpusScope={SCOPE} />);
    expect(screen.getByTestId("diff")).toBeInTheDocument();
  });

  it("shows the English translation with its accuracy disclaimer", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.getByText(/Say: He is Allah, the One!/)).toBeInTheDocument();
    expect(screen.getByText(/hundred percent accurate/i)).toBeInTheDocument();
  });

  it("never shows a translation without its disclaimer", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    const translation = screen.queryByTestId("translation");
    const disclaimer = screen.queryByTestId("translation-disclaimer");
    expect(Boolean(translation)).toBe(Boolean(disclaimer));
  });

  it("renders the verdict label", () => {
    render(<EvidenceCard quotation={q({ verdict: "WRONG_REFERENCE", given_reference: "2:255" })} corpusScope={SCOPE} />);
    expect(screen.getByText(/wrong reference/i)).toBeInTheDocument();
  });

  it("sets the corpus-scope caveat as prose, not as metadata", () => {
    render(<EvidenceCard quotation={q({ verdict: "NOT_FOUND", record: null })} corpusScope={SCOPE} />);
    const caveat = screen.getByTestId("scope-caveat");
    expect(caveat.className).not.toContain("data");
    expect(caveat).toHaveStyle({ fontFamily: "var(--serif)" });
  });
});
