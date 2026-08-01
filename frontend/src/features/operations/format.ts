/** Formatting helpers shared across the operations dashboards. */

export function fmtCurrency(value: number | null | undefined): string {
  if (value == null) return "-";
  if (Math.abs(value) >= 1_000_000_0)
    return `₹${(value / 1_000_000_0).toFixed(2)} Cr`;
  if (Math.abs(value) >= 100_000) return `₹${(value / 100_000).toFixed(2)} L`;
  return `₹${value.toLocaleString("en-IN")}`;
}

export function fmtNumber(value: number | null | undefined): string {
  if (value == null) return "-";
  return value.toLocaleString("en-IN");
}

export function titleCase(text: string | null | undefined): string {
  if (!text) return "-";
  return text
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** A small, stable categorical palette (aligned with the app's chart usage). */
// Consistent, theme-driven categorical palette (single source of truth).
export { CHART_COLORS } from "@/lib/chart-theme";

export const SEVERITY_TONE: Record<string, string> = {
  critical: "border-red-500/40 bg-red-500/10 text-red-500",
  high: "border-red-500/40 bg-red-500/10 text-red-500",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-500",
  medium: "border-amber-500/40 bg-amber-500/10 text-amber-500",
  info: "border-sky-500/40 bg-sky-500/10 text-sky-500",
  low: "border-border bg-muted text-muted-foreground",
};
