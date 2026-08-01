import { cn } from "@/lib/utils";
import { scoreTone } from "../../format";
import type { HealthMetrics as HealthMetricsType, HealthScore } from "../../types";

const barColor: Record<ReturnType<typeof scoreTone>, string> = {
  positive: "bg-success",
  warning: "bg-warning",
  negative: "bg-destructive",
};

const labelColor: Record<ReturnType<typeof scoreTone>, string> = {
  positive: "text-success",
  warning: "text-warning",
  negative: "text-destructive",
};

function HealthRow({ title, dimension }: { title: string; dimension: HealthScore }) {
  const tone = scoreTone(dimension.score);
  return (
    <div className="space-y-2 rounded-lg border border-border bg-background p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-foreground">{title}</span>
        <span className={cn("text-sm font-semibold", labelColor[tone])}>
          {dimension.label} · {dimension.score}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div className={cn("h-full rounded-full transition-all", barColor[tone])} style={{ width: `${dimension.score}%` }} />
      </div>
      <p className="text-xs leading-5 text-muted-foreground">{dimension.rationale}</p>
    </div>
  );
}

export function HealthMetrics({ health }: { health: HealthMetricsType }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <h3 className="text-sm font-semibold tracking-tight text-foreground">Financial Health</h3>
      <p className="mt-1 text-xs text-muted-foreground">Deterministic 0–100 scores across the core credit dimensions.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <HealthRow title="Liquidity Health" dimension={health.liquidity_health} />
        <HealthRow title="Debt Health" dimension={health.debt_health} />
        <HealthRow title="Working Capital Health" dimension={health.working_capital_health} />
        <HealthRow title="Business Stability" dimension={health.business_stability} />
      </div>
    </div>
  );
}
