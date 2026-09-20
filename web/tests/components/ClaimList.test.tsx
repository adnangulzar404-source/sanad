import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClaimList } from "../../src/components/ClaimList";

describe("ClaimList", () => {
  it("renders nothing when there are no claims", () => {
    const { container } = render(<ClaimList claims={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows each claim's label and note", () => {
    render(<ClaimList claims={[{ kind: "unanimity", label: "Unanimity claimed", note: "Requires named evidence." }]} />);
    expect(screen.getByText("Unanimity claimed")).toBeInTheDocument();
    expect(screen.getByText(/requires named evidence/i)).toBeInTheDocument();
  });
});
