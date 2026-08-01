/**
 * Shared HTTP client.
 *
 * Centralises the API base URL, auth headers and error/401 handling so feature
 * API modules don't each re-implement fetch plumbing.
 */

// Configurable API origin (Phase 11). Defaults to the historical local dev
// backend so existing setups keep working; set VITE_API_URL at build time to
// point the browser at the production API edge (e.g. https://api.yourbank.com).
import { getDemoResponse } from "@/lib/demo";

export const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://127.0.0.1:8000";

export function getAuthHeaders(): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function requireAuth() {
  if (typeof window !== "undefined" && !localStorage.getItem("token")) {
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
}

async function handle<T>(response: Response): Promise<T> {
  if (response.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  requireAuth();
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}

export async function apiGet<T>(path: string): Promise<T> {
  const demo = getDemoResponse<T>(path);
  if (demo !== undefined) return demo;
  requireAuth();
  const response = await fetch(`${API_BASE}${path}`, { headers: getAuthHeaders() });
  return handle<T>(response);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  requireAuth();
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  requireAuth();
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}

export async function apiDelete(path: string): Promise<void> {
  requireAuth();
  const response = await fetch(`${API_BASE}${path}`, { method: "DELETE", headers: getAuthHeaders() });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Delete failed (${response.status})`);
  }
}

/** Authorized fetch returning the raw Response (for blobs / multipart). */
export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  requireAuth();
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}
