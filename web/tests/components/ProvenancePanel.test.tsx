import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { ProvenancePanel } from "../../src/components/ProvenancePanel";

const NOTICE = "# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK\n#  Tanzil Quran Text (Uthmani, Version 1.1)\n#  License: Creative Commons Attribution 3.0";

const corpus = {
  db_sha256: "2816ad6e161e621c21b410290f373aebec2983bb88e4cfb7acb8f4e555f64021",
  db_path: "data/sanad-quran.db",
  stats: { records: 6236, sources: 2, translations: 6236 },
  scope: "This corpus contains the Qur'an only.",
  sources: [
    { id: "tanzil-uthmani-1.1", kind: "quran-arabic", title: "Tanzil Qur'an Text (Uthmani)",
      publisher: "Tanzil Project", edition: "1.1", url: "https://tanzil.net/",
      license_id: "CC-BY-3.0", license_url: "https://tanzil.net/docs/text_license",
      attribution: NOTICE, retrieved_at: "2026-09-20", upstream_sha256: "36da55e2", modifications: "none" },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("ProvenancePanel", () => {
  it("shows the corpus checksum", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpus), { status: 200 })));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/2816ad6e/)).toBeInTheDocument());
  });

  it("reproduces the licence notice verbatim, not summarised", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpus), { status: 200 })));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByTestId("attribution-tanzil-uthmani-1.1").textContent).toBe(NOTICE);
    });
  });

  it("shows the record count", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpus), { status: 200 })));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByTestId("stat-records")).toHaveTextContent("6,236");
    });
  });

  it("lets a sceptic get back to the upstream source and its content checksum", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpus), { status: 200 })));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByTestId("source-url-tanzil-uthmani-1.1")).toHaveTextContent("https://tanzil.net/");
      expect(screen.getByTestId("upstream-sha256-tanzil-uthmani-1.1")).toHaveTextContent("36da55e2");
    });
  });

  it("says the verifier is unreachable when the corpus cannot be fetched", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the verifier/i));
  });
});
