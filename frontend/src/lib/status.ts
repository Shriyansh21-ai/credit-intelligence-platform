/**
 * Canonical status / risk / severity tone system.
 *
 * Single source of truth for how the platform colours risk levels, alert
 * severities, credit scores, rating grades and operational statuses. Every
 * feature should map through these helpers instead of hand-writing ternaries
 * with raw Tailwind palette classes — that keeps colour semantics consistent
 * across all pages and themes.
 *
 * See docs/frontend/DESIGN_SYSTEM.md for the design language and token map.
 */

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type Severity = "low" | "medium" | "high" | "critical";
export type ToneKind =
  | "neutral"
  | "success"
  | "info"
  | "warning"
  | "danger"
  | "risk-low"
  | "risk-medium"
  | "risk-high"
  | "risk-critical";

const FALLBACK_BADGE = "border-border bg-muted text-muted-foreground";

/** Badge tone (border + translucent bg + text) for each semantic kind. */
export const TONE_BADGE: Record<ToneKind, string> = {
  neutral: FALLBACK_BADGE,
  success: "border-success/30 bg-success/15 text-success",
  info: "border-info/30 bg-info/15 text-info",
  warning: "border-warning/30 bg-warning/15 text-warning",
  danger: "border-destructive/30 bg-destructive/15 text-destructive",
  "risk-low": "border-risk-low/30 bg-risk-low/15 text-risk-low",
  "risk-medium": "border-risk-medium/30 bg-risk-medium/15 text-risk-medium",
  "risk-high": "border-risk-high/30 bg-risk-high/15 text-risk-high",
  "risk-critical": "border-risk-critical/30 bg-risk-critical/15 text-risk-critical",
};

/** Text-only tone for each semantic kind (e.g. KPI values, inline figures). */
export const TONE_TEXT: Record<ToneKind, string> = {
  neutral: "text-foreground",
  success: "text-success",
  info: "text-info",
  warning: "text-warning",
  danger: "text-destructive",
  "risk-low": "text-risk-low",
  "risk-medium": "text-risk-medium",
  "risk-high": "text-risk-high",
  "risk-critical": "text-risk-critical",
};

/** Solid fill tone (e.g. progress/magnitude bars). */
export const TONE_FILL: Record<ToneKind, string> = {
  neutral: "bg-muted-foreground",
  success: "bg-success",
  info: "bg-info",
  warning: "bg-warning",
  danger: "bg-destructive",
  "risk-low": "bg-risk-low",
  "risk-medium": "bg-risk-medium",
  "risk-high": "bg-risk-high",
  "risk-critical": "bg-risk-critical",
};

const norm = (s: unknown): string =>
  String(s ?? "")
    .trim()
    .toLowerCase();

/** Coerce arbitrary input into one of the four canonical risk levels. */
export function normalizeRisk(input: unknown): RiskLevel {
  const s = norm(input);
  if (["critical", "severe", "very high", "very_high"].includes(s)) return "critical";
  if (["high", "elevated"].includes(s)) return "high";
  if (["medium", "moderate", "mid"].includes(s)) return "medium";
  return "low";
}

const RISK_TONE_KIND: Record<RiskLevel, ToneKind> = {
  low: "risk-low",
  medium: "risk-medium",
  high: "risk-high",
  critical: "risk-critical",
};

/** Risk-level → tone kind (low = good/green, critical = bad/red). */
export const riskToneKind = (input: unknown): ToneKind => RISK_TONE_KIND[normalizeRisk(input)];
export const riskBadge = (input: unknown): string => TONE_BADGE[riskToneKind(input)];
export const riskText = (input: unknown): string => TONE_TEXT[riskToneKind(input)];
export const riskFill = (input: unknown): string => TONE_FILL[riskToneKind(input)];

/**
 * Alert / issue **severity**. Distinct from risk: a *low* severity alert is
 * informational (blue), not "good". Preserves the historical palette.
 */
export const SEVERITY_TONE: Record<string, string> = {
  critical: "bg-red-500/15 text-red-500 border-red-500/30",
  high: "bg-orange-500/15 text-orange-500 border-orange-500/30",
  medium: "bg-amber-500/15 text-amber-600 border-amber-500/30",
  low: "bg-sky-500/15 text-sky-500 border-sky-500/30",
};

export function severityTone(sev: unknown): string {
  return SEVERITY_TONE[norm(sev)] ?? FALLBACK_BADGE;
}

/** Credit score → text tone. */
export function scoreTone(score: number): string {
  if (score >= 700) return TONE_TEXT.success;
  if (score >= 580) return TONE_TEXT.warning;
  return TONE_TEXT.danger;
}

/** Rating grade → text tone. */
export function gradeTone(grade: string): string {
  const g = String(grade ?? "").toUpperCase();
  if (["AAA", "AA", "A"].includes(g)) return TONE_TEXT.success;
  if (["BBB", "BB"].includes(g)) return TONE_TEXT.warning;
  return TONE_TEXT.danger;
}

/**
 * Operational status → tone kind. Covers the recurring lifecycle vocabularies
 * used across dashboards (health, task, connector, approval, session states).
 */
const STATUS_TONE_KIND: Record<string, ToneKind> = {
  // health / system
  healthy: "success",
  ok: "success",
  up: "success",
  operational: "success",
  degraded: "warning",
  warning: "warning",
  unhealthy: "danger",
  critical: "danger",
  down: "danger",
  error: "danger",
  failed: "danger",
  // lifecycle / workflow
  active: "success",
  enabled: "success",
  live: "success",
  running: "success",
  in_session: "success",
  approved: "success",
  passed: "success",
  completed: "success",
  resolved: "success",
  connected: "success",
  synced: "success",
  pending: "warning",
  in_progress: "info",
  in_review: "info",
  processing: "info",
  queued: "info",
  scheduled: "info",
  draft: "neutral",
  open: "warning",
  rejected: "danger",
  denied: "danger",
  blocked: "danger",
  overdue: "danger",
  breached: "danger",
  expired: "danger",
  disabled: "neutral",
  inactive: "neutral",
  closed: "neutral",
  archived: "neutral",
  cancelled: "neutral",
  canceled: "neutral",
};

export function statusToneKind(status: unknown): ToneKind {
  return STATUS_TONE_KIND[norm(status)] ?? "neutral";
}
export const statusBadge = (status: unknown): string => TONE_BADGE[statusToneKind(status)];
export const statusText = (status: unknown): string => TONE_TEXT[statusToneKind(status)];
