let csrfToken: string | null = null;

export class ApiError extends Error {
  code?: string;
  field?: string;
  action?: string;
  status: number;
  item?: string;
  constructor(message: string, status = 500, details: Record<string, any> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = details.code;
    this.field = details.field;
    this.action = details.action;
    this.item = details.item;
  }
}

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (method !== "GET") {
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
    if (!headers.has("Idempotency-Key")) headers.set("Idempotency-Key", crypto.randomUUID());
  }
  let response: Response;
  try {
    response = await fetch(path, { ...options, method, headers, credentials: "same-origin" });
  } catch {
    throw new ApiError("无法连接本地服务，请确认 127.0.0.1:8765 正在运行", 0, { action: "检查本地服务后重试" });
  }
  let result: any = {};
  try { result = await response.json(); } catch { /* media responses are handled by download URLs */ }
  if (result?.csrf_token) csrfToken = result.csrf_token;
  if (!response.ok) {
    const details = typeof result.error === "object" && result.error ? result.error : result;
    throw new ApiError(details.message || `请求失败（HTTP ${response.status}）`, response.status, details);
  }
  return result as T;
}

export function jsonOptions(method: string, payload?: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload ?? {}) };
}

export function uploadOptions(file: File | Blob, method = "POST"): RequestInit {
  return { method, headers: { "Content-Type": "application/octet-stream" }, body: file };
}

export function formatNumber(value: unknown) {
  if (value === null || value === undefined || value === "") return "未读取";
  return typeof value === "number" ? new Intl.NumberFormat("zh-CN").format(value) : String(value);
}

export function errorText(error: unknown) {
  if (error instanceof ApiError) return `${error.message}${error.action ? `\n怎么改：${error.action}` : ""}`;
  return error instanceof Error ? error.message : "操作未完成，请检查当前输入后重试";
}
