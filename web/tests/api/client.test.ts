import { describe, expect, it, vi, afterEach } from "vitest";
import { apiFetch, ApiUnreachable, ApiError } from "../../src/api/client";

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("returns parsed json on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    ));
    await expect(apiFetch<{ ok: boolean }>("/api/health")).resolves.toEqual({ ok: true });
  });

  it("throws ApiUnreachable when the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    await expect(apiFetch("/api/health")).rejects.toBeInstanceOf(ApiUnreachable);
  });

  it("throws ApiError carrying the status on a 5xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 503 })));
    await expect(apiFetch("/api/health")).rejects.toMatchObject({ status: 503 });
  });

  it("throws ApiError on a 422 so validation is distinguishable from unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: [] }), { status: 422 })
    ));
    await expect(apiFetch("/api/verify")).rejects.toBeInstanceOf(ApiError);
  });
});
