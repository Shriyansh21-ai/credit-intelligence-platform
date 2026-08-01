import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { TONE_CLASS, sentimentTone } from "../format";
import type { Insight } from "../types";

const ICON = {
  positive: TrendingUp,
  negative: TrendingDown,
  neutral: Minus,
} as const;

/** A deterministic financial observation with its explanation ("why"). */
export function InsightCard({ insight }: { insight: Insight }) {
  const tone = sentimentTone(insight.sentiment);
  const cls = TONE_CLASS[tone];
  const Icon = ICON[insight.sentiment];

  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 shadow-card">
      <div className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", cls.badge)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <h4 className="text-sm font-semibold text-foreground">{insight.title}</h4>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{insight.detail}</p>
      </div>
    </div>
  );
}
