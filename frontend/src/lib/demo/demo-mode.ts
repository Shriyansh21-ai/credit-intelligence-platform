/**
 * Client-side Demo Mode (Stage 2 · M8).
 *
 * Additive and OFF by default. When enabled, the API client short-circuits a
 * curated set of read endpoints with representative sample data so dashboards
 * are populated for demos/evaluation — WITHOUT any backend, DB or migration
 * change. When off, behaviour is byte-for-byte unchanged.
 */

const KEY = "aicredit.demo";
export const DEMO_EVENT = "aicredit:demo-changed";

export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function setDemoMode(on: boolean): void {
  try {
    if (on) localStorage.setItem(KEY, "1");
    else localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event(DEMO_EVENT));
}

export function toggleDemoMode(): boolean {
  const next = !isDemoMode();
  setDemoMode(next);
  return next;
}
