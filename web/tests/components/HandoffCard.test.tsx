import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HandoffCard } from "../../src/components/HandoffCard";

describe("HandoffCard", () => {
  it("says a person should answer, for a personal ruling", () => {
    render(<HandoffCard risk="PERSONAL_RULING" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/qualified/i);
  });

  it("does not render any verdict", () => {
    render(<HandoffCard risk="PERSONAL_RULING" />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("uses different wording for a high-risk topic", () => {
    render(<HandoffCard risk="HIGH_RISK" />);
    expect(screen.getByRole("alert").textContent).toMatch(/sensitive/i);
  });
});
