/** Formatting helpers for the ML platform dashboards. */

export function pct(value: number | null | undefined, digits = 1): string {
  if (value == null) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 3): string {
  if (value == null) return "-";
  return value.toFixed(digits);
}

export function ms(value: number | null | undefined): string {
  if (value == null) return "-";
  return `${value.toFixed(1)} ms`;
}

/** Tailwind tone class for a governance status. */
export function statusTone(status: string): string {
  switch (status) {
    case "production":
    case "approved":
      return "text-emerald-500";
    case "pending":
    case "staging":
      return "text-amber-500";
    case "rejected":
    case "rolled_back":
      return "text-red-500";
    case "archived":
      return "text-muted-foreground";
    default:
      return "text-foreground";
  }
}
