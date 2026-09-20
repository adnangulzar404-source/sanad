import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";

const corpusFixture = {
  db_sha256: "2816ad6e161e621c21b410290f373aebec2983bb88e4cfb7acb8f4e555f640",
  db_path: "data/sanad-quran.db",
  stats: { records: 6236, sources: 2, translations: 6236 },
  scope: "This corpus contains the Qur'an only.",
  sources: [],
};

function stubCorpusFetch() {
  // A fresh Response per call: the "reopens after being closed" test causes
  // ProvenancePanel to mount twice, and a Response body can only be read
  // once -- reusing one instance would fail the second fetch with an
  // unrelated "body already consumed" error.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(corpusFixture), { status: 200 })))
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  // Every test that touches the hash must leave it clean for the next one:
  // App's initial state reads window.location.hash directly.
  window.history.replaceState(null, "", window.location.pathname);
});

describe("App / #provenance", () => {
  it("opens the provenance panel when the page loads at #provenance", async () => {
    window.location.hash = "#provenance";
    stubCorpusFetch();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /what this corpus is/i })
    ).toBeInTheDocument();
  });

  it("does not open the panel on a plain load, and opens it once the hash changes after mount", async () => {
    stubCorpusFetch();
    render(<App />);

    // Closed state: only the toggle button exists, no panel heading.
    expect(screen.queryByRole("heading", { name: /what this corpus is/i })).toBeNull();

    act(() => {
      window.location.hash = "#provenance";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });

    expect(
      await screen.findByRole("heading", { name: /what this corpus is/i })
    ).toBeInTheDocument();
  });

  it("reopens after being closed, so the link is not dead on a second click", async () => {
    window.location.hash = "#provenance";
    stubCorpusFetch();
    const user = userEvent.setup();

    render(<App />);
    await screen.findByRole("heading", { name: /what this corpus is/i });

    await user.click(screen.getByRole("button", { name: /close/i }));
    expect(screen.queryByRole("heading", { name: /what this corpus is/i })).toBeNull();
    // The hash must be cleared on close: if it were still "#provenance",
    // navigating to "#provenance" again below would not change the hash, no
    // "hashchange" would fire, and the link would be dead a second time.
    expect(window.location.hash).toBe("");

    // Simulate clicking a "#provenance" link a second time.
    act(() => {
      window.location.hash = "#provenance";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });

    expect(
      await screen.findByRole("heading", { name: /what this corpus is/i })
    ).toBeInTheDocument();
  });
});
