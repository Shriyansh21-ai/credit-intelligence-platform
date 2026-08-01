import { Activity, CalendarDays, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import { TONE_CLASS, statusTone, titleCase } from "../format";
import type { AnalysisResult } from "../types";

/** Headline banner: overall health, reporting period and flag count. */
export function AnalysisSummary({ analysis }: { analysis: AnalysisResult }) {
  const overall = analysis.overall_health;
  const tone = statusTone(overall.status);
  const cls = TONE_CLASS[tone];
  const period = analysis.period.label ?? "Latest period";
  const flags = analysis.risk_flag_count;

  return (
    <div className="rounded-2xl border border-border bg-card p-6 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-5">
          <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-primary/10">
            <div className="flex flex-col items-center">
              <span className={cn("text-3xl font-bold leading-none", cls.text)}>
                {overall.score ?? "—"}
              </span>
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">/ 100</span>
            </div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Overall Financial Health
            </div>
            <div className={cn("mt-1 text-2xl font-semibold tracking-tight", cls.text)}>
              {overall.status === "unavailable" ? "Not assessable" : titleCase(overall.status)}
            </div>
            <p className="mt-1 max-w-md text-xs text-muted-foreground">
              Deterministic financial intelligence derived from the analysed statement — not an ML score.
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <SummaryStat icon={CalendarDays} label="Period" value={period} tone="neutral" />
          <SummaryStat
            icon={ShieldAlert}
            label="Risk Flags"
            value={String(flags)}
            tone={flags === 0 ? "positive" : flags > 2 ? "negative" : "warning"}
          />
          <SummaryStat icon={Activity} label="Version" value={`v${analysis.version}`} tone="neutral" />
        </div>
      </div>
    </div>
  );
}

function SummaryStat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  tone: keyof typeof TONE_CLASS;
}) {
  return (
    <div className="min-w-[104px] rounded-xl border border-border bg-background p-3">
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className={cn("mt-1 truncate text-sm font-semibold", TONE_CLASS[tone].text)}>{value}</div>
    </div>
  );
}
