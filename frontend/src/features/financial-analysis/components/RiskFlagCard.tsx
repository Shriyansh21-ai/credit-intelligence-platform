import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";
import { TONE_CLASS, severityTone } from "../format";
import type { RiskFlag } from "../types";

/** A single risk flag with severity, why it fired and the recommended action. */
export function RiskFlagCard({ flag }: { flag: RiskFlag }) {
  const tone = severityTone(flag.severity);
  const cls = TONE_CLASS[tone];

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-card">
      <div className="flex items-start gap-3">
        <div className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", cls.badge)}>
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-foreground">{flag.title}</h4>
            <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", cls.badge)}>
              {flag.severity}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{flag.reason}</p>
          <p className="mt-2 text-xs leading-5 text-foreground/80">
            <span className="font-medium text-foreground">Recommendation: </span>
            {flag.recommendation}
          </p>
        </div>
      </div>
    </div>
  );
}
