import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, jsonOptions } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("API session and errors", () => {
  it("reuses the CSRF token and creates idempotency keys", async () => {
    const calls: any[] = [];
    vi.stubGlobal("fetch", vi.fn(async (path, options) => {
      calls.push([path, options]);
      return new Response(JSON.stringify({ csrf_token: "session-token", ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    await api("/api/topics/bootstrap");
    await api("/api/topics/settings", jsonOptions("POST", { daily_enabled: false }));
    const [, options] = calls[1];
    expect(options.headers.get("X-CSRF-Token")).toBe("session-token");
    expect(options.headers.get("Idempotency-Key")).toBeTruthy();
  });

  it("keeps the exact field and recovery action", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "LOGIN_REQUIRED", message: "需要登录", field: "browser", action: "打开专用窗口" } }), { status: 409 })));
    const request = api("/api/publishing/batches", jsonOptions("POST"));
    await expect(request).rejects.toMatchObject({ code: "LOGIN_REQUIRED", field: "browser", action: "打开专用窗口", status: 409 });
    await expect(request).rejects.toBeInstanceOf(ApiError);
  });
});
