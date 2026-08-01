import { cn } from "@/lib/utils";
import { normalizeRisk, riskBadge, type RiskLevel } from "@/lib/status";

const LABEL: Record<RiskLevel, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

/**
 * Consistent risk-level pill (low = good/green … critical = bad/red).
 * Accepts any input; it is normalised to one of the four canonical levels.
 */
export function RiskBadge({
  level,
  label,
  className,
}: {
  level: unknown;
  label?: string;
  className?: string;
}) {
  const normalized = normalizeRisk(level);
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        riskBadge(normalized),
        className,
      )}
    >
      {label ?? LABEL[normalized]}
    </span>
  );
}
