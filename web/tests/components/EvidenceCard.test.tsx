import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceCard } from "../../src/components/EvidenceCard";
import type { QuotationOut } from "../../src/api/client";

const SCOPE = "This corpus contains the Qur'an and Sahih al-Bukhari. It does not contain Sahih Muslim, the four Sunan, or any other collection, so absence from this corpus does not establish that a quotation is fabricated.";

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
    expect(screen.getByTestId("scope-caveat")).toHaveTextContent(/does not establish that a quotation is fabricated/i);
  });

  it("does not attach the caveat to a verified verdict", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.queryByTestId("scope-caveat")).toBeNull();
  });

  it("renders the diff when there is one", () => {
    render(<EvidenceCard quotation={q({ verdict: "NEAR_MATCH", diff: [["quoted-only", "x"], ["corpus-only", "y"]] })} corpusScope={SCOPE} />);
    expect(screen.getByTestId("diff")).toBeInTheDocument();
  });

  it("shows the English translation", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.getByText(/Say: He is Allah, the One!/)).toBeInTheDocument();
  });

  it("does not repeat the translation-accuracy disclaimer per card", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.queryByTestId("translation-disclaimer")).toBeNull();
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

  const hadithRecord = {
    id: "hadith:bukhari:1", reference_display: "Sahih al-Bukhari 1",
    text_ar: "MATN", text_ar_sha256: "abc", isnad_ar: "CHAIN OF NARRATORS",
    collection: "bukhari", hadith_no: "1",
    translation_en: null, translation_disclaimer: null,
  };
  const hadith = q({ record: hadithRecord });

  it("shows the isnad for a hadith, in the apparatus register", () => {
    render(<EvidenceCard quotation={hadith} corpusScope={SCOPE} />);
    const el = screen.getByTestId("isnad");
    expect(el).toHaveTextContent("CHAIN OF NARRATORS");
    expect(el.className).toContain("data");
  });

  it("shows no isnad block for an ayah", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.queryByTestId("isnad")).toBeNull();
  });

  it("renders a hadith's matn and addendum as one continuous text, joined by a space", () => {
    const cut = q({
      record: { ...hadithRecord, text_ar: "PRIMARY MATN", addenda_ar: "SECONDARY MATN" },
    });
    render(<EvidenceCard quotation={cut} corpusScope={SCOPE} />);
    expect(screen.getByTestId("matn").textContent).toBe("PRIMARY MATN SECONDARY MATN");
  });

  it("does not label the addendum separately or split it into its own element", () => {
    const cut = q({
      record: { ...hadithRecord, text_ar: "PRIMARY MATN", addenda_ar: "SECONDARY MATN" },
    });
    render(<EvidenceCard quotation={cut} corpusScope={SCOPE} />);
    expect(screen.queryByTestId("addenda")).toBeNull();
    expect(screen.queryByText(/addend/i)).toBeNull();
  });

  it("renders just the primary matn, with no trailing space, when there is no addendum", () => {
    render(<EvidenceCard quotation={hadith} corpusScope={SCOPE} />);
    expect(screen.getByTestId("matn").textContent).toBe("MATN");
  });

  it("does not render an unscorable hadith as an error", () => {
    const pointer = q({
      record: { ...hadithRecord, text_ar: "بهذا", unscorable_reason: "pointer" },
    });
    render(<EvidenceCard quotation={pointer} corpusScope={SCOPE} />);
    expect(screen.queryByTestId("scope-caveat")).toBeNull();
    expect(screen.getByTestId("matn")).toHaveTextContent("بهذا");
    expect(screen.getByTestId("isnad")).toHaveTextContent("CHAIN OF NARRATORS");
  });
});
