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


describe("session recovery", () => {
  it("recovers a rejected activation without losing its body or idempotency key", async () => {
    const calls: any[] = [];
    vi.stubGlobal("fetch", vi.fn(async (path, options) => {
      calls.push([path, options]);
      if (calls.length === 1) return new Response(JSON.stringify({error: {code: "SESSION_REQUIRED"}}), {status: 401});
      if (calls.length === 2) return new Response("<html></html>");
      if (calls.length === 3) return new Response(JSON.stringify({csrf_token: "renewed"}));
      return new Response(JSON.stringify({status: "valid"}));
    }));
    const payload = jsonOptions("POST", {token: "test-license"});
    await expect(api("/api/v2/license/activate", payload)).resolves.toMatchObject({status: "valid"});
    expect(calls).toHaveLength(4);
    expect(calls[3][1].body).toBe(payload.body);
    expect(calls[3][1].headers.get("X-CSRF-Token")).toBe("renewed");
    expect(calls[3][1].headers.get("Idempotency-Key")).toBe(calls[0][1].headers.get("Idempotency-Key"));
  });
  it("does not retry ambiguous network failures", async () => {
    const fetcher = vi.fn(async () => { throw Error("connection lost"); });
    vi.stubGlobal("fetch", fetcher);
    await expect(api("/api/v2/license/activate", jsonOptions("POST", {token: "test"}))).rejects.toBeInstanceOf(ApiError);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

 it("recovers legacy GET session failures with a flat code", async () => {
 const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({error:"本地会话已失效",code:"SESSION_REQUIRED"}),{status:401})).mockResolvedValueOnce(new Response("ok")).mockResolvedValueOnce(new Response(JSON.stringify({csrf_token:"new"}))).mockResolvedValueOnce(new Response(JSON.stringify({ready:true})));
 vi.stubGlobal("fetch",fetcher);await expect(api("/api/bootstrap")).resolves.toMatchObject({ready:true});expect(fetcher).toHaveBeenCalledTimes(4);
 });
