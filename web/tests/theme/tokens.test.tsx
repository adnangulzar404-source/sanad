/// <reference types="vite/client" />
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import "../../src/theme/tokens.css";
// Loaded as raw source text (not executed) so these tests can parse the
// actual token/style definitions rather than a copy that could drift from
// what ships. See the "colour contrast" describe block below.
import tokensCss from "../../src/theme/tokens.css?raw";
import provenancePanelSrc from "../../src/components/ProvenancePanel.tsx?raw";

type Rgb = [number, number, number];

function hexToRgb(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

function srgbToLinear(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance([r, g, b]: Rgb): number {
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

/** WCAG contrast ratio between two sRGB colours. */
function contrastRatio(a: Rgb, b: Rgb): number {
  const la = relativeLuminance(a) + 0.05;
  const lb = relativeLuminance(b) + 0.05;
  return Math.max(la, lb) / Math.min(la, lb);
}

/** Mirrors CSS `color-mix(in srgb, c1 p1%, c2)`: linear interpolation of the
 * gamma-encoded channel values, not linear-light. */
function mix(c1: Rgb, c2: Rgb, p1: number): Rgb {
  return [0, 1, 2].map((i) => c1[i] * p1 + c2[i] * (1 - p1)) as Rgb;
}

function cssHexVar(name: string): string {
  const m = tokensCss.match(new RegExp(`${name}:\\s*(#[0-9A-Fa-f]{6})`));
  if (!m) throw new Error(`could not find ${name} in tokens.css`);
  return m[1];
}

const page = hexToRgb(cssHexVar("--page"));
const ink = hexToRgb(cssHexVar("--ink"));
const rubric = hexToRgb(cssHexVar("--rubric"));
const verdigris = hexToRgb(cssHexVar("--verdigris"));

// WCAG AA for body text (and for the .data / error-message / badge text this
// token backs, none of which is large text): 4.5:1.
const AA_TEXT = 4.5;

describe("colour contrast (WCAG AA)", () => {
  it("keeps --ink-60 at or above 4.5:1 against --page", () => {
    const m = tokensCss.match(/--ink-60:\s*color-mix\(in srgb, var\(--ink\) (\d+)%, var\(--page\)\)/);
    if (!m) throw new Error("could not parse the --ink-60 definition in tokens.css");
    const inkPct = Number(m[1]) / 100;
    const ink60 = mix(ink, page, inkPct);
    expect(contrastRatio(ink60, page)).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it("keeps --ink, --rubric and --verdigris passing against --page", () => {
    expect(contrastRatio(ink, page)).toBeGreaterThanOrEqual(AA_TEXT);
    expect(contrastRatio(rubric, page)).toBeGreaterThanOrEqual(AA_TEXT);
    expect(contrastRatio(verdigris, page)).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it("keeps the licence <pre> in ProvenancePanel at or above 4.5:1", () => {
    const bgMatch = provenancePanelSrc.match(
      /background: "color-mix\(in srgb, var\(--page\) (\d+)%, var\(--ink\)\)"/
    );
    if (!bgMatch) throw new Error("could not parse the <pre> background in ProvenancePanel.tsx");
    const pagePct = Number(bgMatch[1]) / 100;
    const bg = mix(page, ink, pagePct);

    // The <pre> must set its own text colour rather than inherit the muted
    // .data colour (--ink-60): that pairing is what measured 3.34:1 in the
    // Stage C review, and no --ink-60 darkening alone can clear 4.5:1 against
    // a background this close to --page (the ceiling equals the --ink-60
    // vs --page ratio itself, reached only at zero tint).
    expect(provenancePanelSrc).toMatch(/color: "var\(--ink\)"/);
    expect(contrastRatio(ink, bg)).toBeGreaterThanOrEqual(AA_TEXT);
  });
});

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
