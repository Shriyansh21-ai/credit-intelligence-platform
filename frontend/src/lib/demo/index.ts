import { isDemoMode } from "./demo-mode";
import { DEMO_FIXTURES } from "./fixtures";

export { isDemoMode, setDemoMode, toggleDemoMode, DEMO_EVENT } from "./demo-mode";

/**
 * If Demo Mode is on and a fixture is registered for this request path, return
 * the sample response; otherwise `undefined` (caller performs the real fetch).
 * Matching is by exact path or path suffix, so it works regardless of API base
 * or `/api` prefixing.
 */
export function getDemoResponse<T>(path: string): T | undefined {
  if (!isDemoMode()) return undefined;
  const clean = path.split("?")[0];
  for (const key of Object.keys(DEMO_FIXTURES)) {
    if (clean === key || clean.endsWith(key)) {
      return DEMO_FIXTURES[key]() as T;
    }
  }
  return undefined;
}
