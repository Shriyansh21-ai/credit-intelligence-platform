import { cn } from "@/lib/utils";
import { TONE_CLASS, formatRatioValue, statusTone, titleCase } from "../format";
import type { Ratio } from "../types";

/** A single financial ratio with its value, status, ideal range and meaning. */
export function RatioCard({ ratio }: { ratio: Ratio }) {
  const tone = statusTone(ratio.status);
  const cls = TONE_CLASS[tone];
  const unavailable = ratio.value === null;

  return (
    <div className="flex flex-col rounded-xl border border-border bg-card p-4 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-foreground">{ratio.label}</span>
        <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", cls.badge)}>
          {ratio.status === "unavailable" ? "N/A" : titleCase(ratio.status)}
        </span>
      </div>

      <div className={cn("mt-2 text-2xl font-semibold tracking-tight", unavailable ? "text-muted-foreground" : "text-foreground")}>
        {formatRatioValue(ratio.value, ratio.unit)}
      </div>

      <dl className="mt-3 space-y-1 text-[11px] text-muted-foreground">
        <div className="flex justify-between gap-2">
          <dt>Formula</dt>
          <dd className="text-right font-mono text-foreground/80">{ratio.formula}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Ideal</dt>
          <dd className="text-right text-foreground/80">{ratio.ideal_range}</dd>
        </div>
      </dl>

      <p className="mt-3 border-t border-border pt-3 text-xs leading-5 text-muted-foreground">
        {ratio.interpretation}
      </p>
    </div>
  );
}
