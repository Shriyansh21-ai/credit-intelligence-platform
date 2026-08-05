/**
 * User profile helpers — a single, client-side source of truth for "who is
 * signed in" so the sidebar, top bar and the Profile Settings page all agree.
 *
 * Account identity (email) is derived from the JWT stored at login; the token's
 * `sub` claim holds the user's email. A couple of presentation-only fields
 * (display name, job title) are editable on the settings page and persisted to
 * localStorage. Everything here is client-side and resilient — it never throws
 * and works even when the backend is unreachable (e.g. demo mode).
 */

import { useEffect, useState } from "react";

const PROFILE_KEY = "profile:prefs:v1";
export const PROFILE_EVENT = "profile:changed";

/** Sensible defaults so the chrome looks populated before anything is set. */
const DEFAULT_DISPLAY_NAME = "Shriyansh Dev";
const DEFAULT_JOB_TITLE = "Head of Risk";

export interface ProfilePrefs {
  /** User-chosen display name shown in the sidebar / top bar. */
  displayName: string;
  /** User-chosen job title / role label. */
  jobTitle: string;
}

/** Decode a JWT payload without verifying it (client display only). */
function decodeJwt(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join(""),
    );
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** The signed-in user's email, read from the JWT. `null` when logged out. */
export function getAccountEmail(): string | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("token");
  if (!token) return null;
  const claims = decodeJwt(token);
  const sub = claims?.sub;
  return typeof sub === "string" ? sub : null;
}

/** Derive a username (the email local-part) from an email address. */
export function usernameFromEmail(email: string | null): string {
  if (!email) return "guest";
  const local = email.split("@")[0] ?? email;
  return local;
}

/** Two-letter initials from a display name (falls back to the email). */
export function initialsFrom(name: string, email: string | null): string {
  const source = name.trim() || usernameFromEmail(email);
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
  return letters.toUpperCase();
}

export function getProfilePrefs(): ProfilePrefs {
  if (typeof window === "undefined") {
    return { displayName: DEFAULT_DISPLAY_NAME, jobTitle: DEFAULT_JOB_TITLE };
  }
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ProfilePrefs>;
      return {
        displayName: parsed.displayName || DEFAULT_DISPLAY_NAME,
        jobTitle: parsed.jobTitle || DEFAULT_JOB_TITLE,
      };
    }
  } catch {
    /* ignore corrupt storage */
  }
  return { displayName: DEFAULT_DISPLAY_NAME, jobTitle: DEFAULT_JOB_TITLE };
}

export function setProfilePrefs(next: Partial<ProfilePrefs>): ProfilePrefs {
  const merged = { ...getProfilePrefs(), ...next };
  try {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(merged));
    // Notify same-tab listeners (the `storage` event only fires cross-tab).
    window.dispatchEvent(new CustomEvent(PROFILE_EVENT));
  } catch {
    /* ignore quota / private-mode errors */
  }
  return merged;
}

export interface Profile extends ProfilePrefs {
  email: string | null;
  username: string;
  initials: string;
}

function buildProfile(): Profile {
  const prefs = getProfilePrefs();
  const email = getAccountEmail();
  return {
    ...prefs,
    email,
    username: usernameFromEmail(email),
    initials: initialsFrom(prefs.displayName, email),
  };
}

/**
 * Reactive profile hook. Re-renders when the profile is edited (same tab) or
 * changed in another tab.
 */
export function useProfile(): Profile {
  // Start from deterministic defaults so the server render and the first client
  // (hydration) render agree; real values are read from storage in the effect
  // below. Reading localStorage in the initializer would risk a hydration
  // mismatch (server has no storage, client does).
  const [profile, setProfile] = useState<Profile>(() => ({
    displayName: DEFAULT_DISPLAY_NAME,
    jobTitle: DEFAULT_JOB_TITLE,
    email: null,
    username: usernameFromEmail(null),
    initials: initialsFrom(DEFAULT_DISPLAY_NAME, null),
  }));

  useEffect(() => {
    const refresh = () => setProfile(buildProfile());
    // Read prefs on mount (SSR/first render used deterministic defaults).
    refresh();
    window.addEventListener(PROFILE_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(PROFILE_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  return profile;
}
