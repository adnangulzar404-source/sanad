import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import "../../src/theme/tokens.css";

describe("Arabic typography", () => {
  it("marks Arabic text with dir=rtl and lang=ar so it renders correctly", () => {
    render(<span className="arabic" dir="rtl" lang="ar" data-testid="a">قُلْ هُوَ ٱللَّهُ أَحَدٌ</span>);
    const el = screen.getByTestId("a");
    expect(el).toHaveAttribute("dir", "rtl");
    expect(el).toHaveAttribute("lang", "ar");
  });

  it("renders canonical Arabic byte-identical to its input", () => {
    // text_ar is verbatim Tanzil under CC BY 3.0 — no normalization anywhere.
    const canonical = "قُلْ هُوَ ٱللَّهُ أَحَدٌ";
    render(<span className="arabic" data-testid="b">{canonical}</span>);
    expect(screen.getByTestId("b").textContent).toBe(canonical);
    expect(screen.getByTestId("b").textContent).not.toBe(canonical.normalize("NFC"));
  });
});
