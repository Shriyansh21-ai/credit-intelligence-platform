import { ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { TONE_CLASS, priorityTone, titleCase } from "../format";
import type { Recommendation } from "../types";

/** A structured, deterministic recommendation with priority. */
export function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  const tone = priorityTone(recommendation.priority);
  const cls = TONE_CLASS[tone];

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-card">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-secondary/60 text-foreground">
          <ArrowRight className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-foreground">{recommendation.title}</h4>
            <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", cls.badge)}>
              {recommendation.priority} priority
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{recommendation.detail}</p>
          <span className="mt-2 inline-block text-[11px] uppercase tracking-wide text-muted-foreground">
            {titleCase(recommendation.category)}
          </span>
        </div>
      </div>
    </div>
  );
}
