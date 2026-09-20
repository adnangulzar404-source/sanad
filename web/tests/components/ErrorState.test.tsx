import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorState } from "../../src/components/ErrorState";

describe("ErrorState", () => {
  it("says the verifier cannot be reached, rather than showing nothing", () => {
    render(<ErrorState kind="unreachable" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the verifier/i);
  });

  it("distinguishes 'nothing to check' from 'checked and not found'", () => {
    render(<ErrorState kind="no-arabic" />);
    const text = screen.getByRole("status").textContent ?? "";
    expect(text).toMatch(/no quotations found to check/i);
    expect(text).not.toMatch(/not in this corpus/i);
  });

  it("reports a server error with its status", () => {
    render(<ErrorState kind="server" detail="503" />);
    expect(screen.getByRole("alert")).toHaveTextContent("503");
  });

  it("invites action when idle", () => {
    render(<ErrorState kind="idle" />);
    expect(screen.getByRole("status")).toHaveTextContent(/paste/i);
  });
});
