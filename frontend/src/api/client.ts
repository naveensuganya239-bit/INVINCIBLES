// INVINCIBLES - API client
// Single source of truth for talking to the FastAPI backend. Base URL is
// configurable via VITE_API_BASE_URL so the frontend can be deployed
// separately from the backend (Section 47/48).

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch {
    throw new ApiError(
      `Could not reach the INVINCIBLES backend at ${BASE_URL}. Is it running?`,
      0,
      null
    );
  }

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      /* body wasn't JSON */
    }
    let message = `Request to ${path} failed with status ${res.status}`;
    if (detail && typeof detail === "object" && "detail" in detail) {
      message = String((detail as Record<string, unknown>).detail);
    }
    throw new ApiError(message, res.status, detail);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
};

/** Resolves a backend-relative URL (e.g. "/static/output/...") into a full URL. */
export function resolveAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BASE_URL}${path}`;
}

export { BASE_URL as API_BASE_URL };
