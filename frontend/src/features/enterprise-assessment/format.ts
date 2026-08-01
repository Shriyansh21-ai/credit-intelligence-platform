/** Presentation helpers for the enterprise assessment result. */

export function formatCurrency(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(0);
}

export function formatPercent(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Colour tone for a 0-100 health / quality score. */
export function scoreTone(score: number): "positive" | "warning" | "negative" {
  if (score >= 70) return "positive";
  if (score >= 45) return "warning";
  return "negative";
}

/** Colour tone for a letter risk grade. */
export function gradeTone(grade: string): "positive" | "warning" | "negative" {
  if (["AAA", "AA", "A"].includes(grade)) return "positive";
  if (["BBB", "BB"].includes(grade)) return "warning";
  return "negative";
}

export function decisionTone(decision: string): "positive" | "warning" | "negative" {
  const normalized = decision.toLowerCase();
  if (normalized === "approve") return "positive";
  if (normalized.includes("condition")) return "warning";
  return "negative";
}
