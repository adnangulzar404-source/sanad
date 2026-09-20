import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CharDiff } from "../../src/components/CharDiff";

describe("CharDiff", () => {
  it("renders nothing when there is no diff", () => {
    const { container } = render(<CharDiff diff={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("marks what you wrote and what the corpus has, distinctly", () => {
    render(<CharDiff diff={[["equal", "قل هو الله "], ["quoted-only", "احدق"], ["corpus-only", "احد"]]} />);
    expect(screen.getByTestId("quoted-only-0")).toHaveTextContent("احدق");
    expect(screen.getByTestId("corpus-only-0")).toHaveTextContent("احد");
  });

  it("labels each side in words, not by colour", () => {
    render(<CharDiff diff={[["quoted-only", "x"], ["corpus-only", "y"]]} />);
    expect(screen.getByText(/you wrote/i)).toBeInTheDocument();
    expect(screen.getByText(/corpus has/i)).toBeInTheDocument();
  });

  it("renders equal runs without marking them", () => {
    render(<CharDiff diff={[["equal", "قل هو"]]} />);
    expect(screen.queryByTestId("quoted-only-0")).toBeNull();
    expect(screen.queryByTestId("corpus-only-0")).toBeNull();
  });

  it("preserves the diff text byte-for-byte", () => {
    const seg = "ٱللَّهُ";
    render(<CharDiff diff={[["equal", seg]]} />);
    expect(screen.getByTestId("diff").textContent).toContain(seg);
  });
});
