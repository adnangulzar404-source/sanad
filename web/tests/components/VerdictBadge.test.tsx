import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VerdictBadge, VERDICT_META, type Verdict } from "../../src/components/VerdictBadge";

const ALL: Verdict[] = ["EXACT", "EXACT_ORTHOGRAPHY", "NEAR_MATCH", "WRONG_REFERENCE", "NOT_FOUND"];

describe("VerdictBadge", () => {
  it.each(ALL)("renders a text label for %s", (v) => {
    render(<VerdictBadge verdict={v} />);
    expect(screen.getByText(VERDICT_META[v].label)).toBeInTheDocument();
  });

  it("gives every verdict a distinct glyph, so colour is never the only signal", () => {
    const glyphs = ALL.map((v) => VERDICT_META[v].glyph);
    expect(new Set(glyphs).size).toBe(ALL.length);
  });

  it("gives every verdict a distinct label", () => {
    const labels = ALL.map((v) => VERDICT_META[v].label);
    expect(new Set(labels).size).toBe(ALL.length);
  });

  it("exposes the verdict to assistive technology, not just visually", () => {
    render(<VerdictBadge verdict="NEAR_MATCH" />);
    expect(screen.getByRole("status")).toHaveTextContent(/near match/i);
  });

  it("never labels a NEAR_MATCH as verified", () => {
    expect(VERDICT_META.NEAR_MATCH.tone).not.toBe("verified");
    expect(VERDICT_META.NEAR_MATCH.label.toLowerCase()).not.toContain("verified");
  });

  it("marks only the two exact verdicts as verified", () => {
    const verified = ALL.filter((v) => VERDICT_META[v].tone === "verified");
    expect(verified.sort()).toEqual(["EXACT", "EXACT_ORTHOGRAPHY"]);
  });
});
