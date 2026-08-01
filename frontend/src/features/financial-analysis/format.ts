/** Presentation helpers for the financial analysis dashboard. */

import type {
  HealthStatus,
  Priority,
  RatioUnit,
  Sentiment,
  Severity,
} from "./types";

export type Tone = "positive" | "warning" | "negative" | "neutral";

/** Map the five-tier engine status onto a UI tone. */
export function statusTone(status: HealthStatus): Tone {
  switch (status) {
    case "excellent":
    case "good":
      return "positive";
    case "moderate":
      return "warning";
    case "weak":
    case "critical":
      return "negative";
    default:
      return "neutral";
  }
}

export function severityTone(severity: Severity): Tone {
  switch (severity) {
    case "critical":
    case "high":
      return "negative";
    case "medium":
      return "warning";
    default:
      return "neutral";
  }
}

export function sentimentTone(sentiment: Sentiment): Tone {
  if (sentiment === "positive") return "positive";
  if (sentiment === "negative") return "negative";
  return "neutral";
}

export function priorityTone(priority: Priority): Tone {
  if (priority === "high") return "negative";
  if (priority === "medium") return "warning";
  return "neutral";
}

/** CSS colour token for a tone (used by charts + accents). */
export const TONE_COLOR: Record<Tone, string> = {
  positive: "var(--success)",
  warning: "var(--warning)",
  negative: "var(--destructive)",
  neutral: "var(--muted-foreground)",
};

/** Tailwind classes per tone for badges/text/bars. */
export const TONE_CLASS: Record<Tone, { text: string; bg: string; badge: string }> = {
  positive: { text: "text-success", bg: "bg-success", badge: "bg-success/10 text-success" },
  warning: { text: "text-warning", bg: "bg-warning", badge: "bg-warning/10 text-warning" },
  negative: {
    text: "text-destructive",
    bg: "bg-destructive",
    badge: "bg-destructive/10 text-destructive",
  },
  neutral: {
    text: "text-muted-foreground",
    bg: "bg-muted-foreground",
    badge: "bg-secondary/70 text-muted-foreground",
  },
};

export function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatCurrency(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

/** Format a ratio value according to its unit. Missing values render as "—". */
export function formatRatioValue(value: number | null, unit: RatioUnit): string {
  if (value === null || !Number.isFinite(value)) return "—";
  switch (unit) {
    case "ratio":
      return `${value.toFixed(2)}x`;
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "days":
      return `${value.toFixed(0)} days`;
    default:
      return formatCurrency(value);
  }
}

export function formatSignedPercent(value: number | null, digits = 1): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}
