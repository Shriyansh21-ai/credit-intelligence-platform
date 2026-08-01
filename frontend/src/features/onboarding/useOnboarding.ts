import { useEffect, useState } from "react";

const STORAGE_KEY = "aicredit.onboarding.v1";
const OPEN_EVENT = "aicredit:open-onboarding";

/** Programmatically (re)open the onboarding flow from anywhere (e.g. a Help menu). */
export function openOnboarding() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(OPEN_EVENT));
}

/**
 * First-run onboarding state. Auto-opens once per browser (localStorage-gated),
 * and can be re-opened on demand via {@link openOnboarding}. SSR-safe: all
 * browser access happens inside effects, so the server render shows nothing.
 */
export function useOnboarding() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      const seen = localStorage.getItem(STORAGE_KEY);
      const path = window.location.pathname;
      const isAuthPage = path === "/login" || path === "/signup";
      if (!seen && !isAuthPage) setOpen(true);
    } catch {
      /* localStorage unavailable — skip auto-open */
    }
    const onOpen = () => setOpen(true);
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOpen);
  }, []);

  function markSeen() {
    try {
      localStorage.setItem(STORAGE_KEY, new Date().toISOString());
    } catch {
      /* ignore */
    }
  }

  /** Close and remember (used by Skip / Finish). */
  function dismiss() {
    markSeen();
    setOpen(false);
  }

  return { open, setOpen, dismiss };
}
