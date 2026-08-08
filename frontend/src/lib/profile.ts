/**
 * Authenticated-user profile — the single source of truth for "who is signed
 * in" across the sidebar, top bar, hero greeting and the Settings pages.
 *
 * The profile is fetched from the backend (`GET /api/auth/me`) using the JWT
 * stored at login, so every user sees their OWN name, job title, department,
 * role and organisation. Nothing here is hardcoded to a specific person — the
 * only fallbacks are the generic "User" / "Risk Analyst" / "Unknown
 * Organization", used briefly while the profile loads or when signed out.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPatch } from "@/lib/http";

export const PROFILE_QUERY_KEY = ["auth", "me"] as const;

/** Generic, person-agnostic fallbacks. */
const FALLBACK_NAME = "User";
const FALLBACK_TITLE = "Risk Analyst";
const FALLBACK_ORG = "Unknown Organization";

/** Shape returned by the backend `/api/auth/me` endpoint (snake_case). */
interface ProfileResponse {
  user_id: number;
  email: string | null;
  full_name: string;
  first_name: string;
  job_title: string;
  department: string | null;
  organization: string;
  avatar_url: string | null;
  initials: string;
  role: string | null;
  roles: string[];
}

/** The profile consumed by UI components. */
export interface Profile {
  userId: number | null;
  email: string | null;
  username: string;
  /** Full display name (backend `full_name`). */
  displayName: string;
  firstName: string;
  jobTitle: string;
  department: string | null;
  organization: string;
  avatarUrl: string | null;
  initials: string;
  /** Primary role, humanised (e.g. "Credit Analyst"), or null. */
  role: string | null;
  roles: string[];
  isLoading: boolean;
}

/** Editable fields sent to `PATCH /api/auth/me`. */
export interface ProfileUpdate {
  full_name?: string;
  job_title?: string;
  department?: string;
  organization?: string;
  avatar_url?: string;
}

// ---------------------------------------------------------------------------
// JWT / email helpers (display only — no verification).
// ---------------------------------------------------------------------------

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
  return email.split("@")[0] ?? email;
}

/** Two-letter initials from a display name (falls back to the email). */
export function initialsFrom(name: string, email: string | null): string {
  const source = name.trim() || usernameFromEmail(email);
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
  return (letters || "?").toUpperCase();
}

/** Title-case an email local-part for a plausible placeholder name. */
function titleCaseFromUsername(username: string): string {
  const parts = username.split(/[\s._-]+/).filter(Boolean);
  if (!parts.length) return FALLBACK_NAME;
  return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

// ---------------------------------------------------------------------------
// Mapping + hook.
// ---------------------------------------------------------------------------

function buildProfile(data: ProfileResponse | undefined, email: string | null, loading: boolean): Profile {
  const username = usernameFromEmail(email);

  if (data) {
    return {
      userId: data.user_id ?? null,
      email: data.email ?? email,
      username,
      displayName: data.full_name || FALLBACK_NAME,
      firstName: data.first_name || FALLBACK_NAME,
      jobTitle: data.job_title || FALLBACK_TITLE,
      department: data.department ?? null,
      organization: data.organization || FALLBACK_ORG,
      avatarUrl: data.avatar_url ?? null,
      initials: data.initials || initialsFrom(data.full_name || "", data.email ?? email),
      role: data.role ?? null,
      roles: data.roles ?? [],
      isLoading: false,
    };
  }

  // No backend data yet (loading or signed out): derive a plausible placeholder
  // from the email so the chrome isn't blank, but never a specific person.
  const placeholderName = email ? titleCaseFromUsername(username) : FALLBACK_NAME;
  return {
    userId: null,
    email,
    username,
    displayName: placeholderName,
    firstName: placeholderName.split(" ")[0] || FALLBACK_NAME,
    jobTitle: FALLBACK_TITLE,
    department: null,
    organization: FALLBACK_ORG,
    avatarUrl: null,
    initials: initialsFrom(placeholderName, email),
    role: null,
    roles: [],
    isLoading: loading,
  };
}

export const getMe = () => apiGet<ProfileResponse>("/api/auth/me");

/**
 * Reactive profile hook. Fetches the authenticated user's profile from the
 * backend and re-renders when it arrives. Deterministic on the server / first
 * client render (mounted=false) to avoid SSR hydration mismatches.
 */
export function useProfile(): Profile {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const email = mounted ? getAccountEmail() : null;
  const enabled = mounted && !!email;

  const query = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: getMe,
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return buildProfile(query.data, email, enabled && query.isLoading);
}

/** Mutation for the Profile Settings page — persists to the DB and refreshes. */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: ProfileUpdate) => apiPatch<ProfileResponse>("/api/auth/me", patch),
    onSuccess: (data) => {
      queryClient.setQueryData(PROFILE_QUERY_KEY, data);
    },
  });
}
