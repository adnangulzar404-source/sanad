import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkedText } from "../../src/components/MarkedText";
import type { QuotationOut } from "../../src/api/client";

const span = (start: number, end: number, verdict: string) =>
  ({ start, end, verdict, quoted_text: "", tier: null, score: 0,
     record: null, given_reference: null, diff: null, also_at: [] }) as unknown as QuotationOut;

describe("MarkedText", () => {
  it("reproduces the user's text exactly", () => {
    const text = "He said «قل هو الله احد» yesterday.";
    render(<MarkedText text={text} quotations={[span(8, 24, "EXACT")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(text);
  });

  it("never substitutes the corpus reading for what the user typed", () => {
    const typo = "قل هو الله احدق";
    render(<MarkedText text={typo} quotations={[span(0, typo.length, "NEAR_MATCH")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(typo);
    expect(screen.getByTestId("marked").textContent).not.toContain("احد ");
  });

  it("marks each span with its verdict", () => {
    render(<MarkedText text="aaaabbbb" quotations={[span(0, 4, "EXACT"), span(4, 8, "NOT_FOUND")]} />);
    expect(screen.getByTestId("span-0")).toHaveAttribute("data-verdict", "EXACT");
    expect(screen.getByTestId("span-1")).toHaveAttribute("data-verdict", "NOT_FOUND");
  });

  it("renders plain text unchanged when there are no spans", () => {
    render(<MarkedText text="nothing to mark here" quotations={[]} />);
    expect(screen.getByTestId("marked").textContent).toBe("nothing to mark here");
  });

  it("handles spans given out of order without corrupting the text", () => {
    const text = "aaaabbbbcccc";
    render(<MarkedText text={text} quotations={[span(8, 12, "EXACT"), span(0, 4, "NOT_FOUND")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(text);
  });

  it("gives each mark an accessible description of its verdict", () => {
    render(<MarkedText text="aaaa" quotations={[span(0, 4, "WRONG_REFERENCE")]} />);
    expect(screen.getByTestId("span-0")).toHaveAttribute("title", expect.stringMatching(/wrong reference/i));
  });

  it("emits no character twice when spans overlap", () => {
    const text = "abcdefghij";
    render(<MarkedText text={text} quotations={[span(0, 6, "EXACT"), span(4, 10, "NOT_FOUND")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(text);
  });

  it("drops a span entirely consumed by an earlier one", () => {
    const text = "abcdefghij";
    render(<MarkedText text={text} quotations={[span(0, 8, "EXACT"), span(2, 5, "NOT_FOUND")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(text);
  });

  it("still renders exactly the input for a span pathologically past the end", () => {
    const text = "abc";
    render(<MarkedText text={text} quotations={[span(0, 99, "EXACT")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(text);
  });
});
