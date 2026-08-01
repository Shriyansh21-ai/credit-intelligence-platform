import { HEALTH_DIMENSIONS, type HealthScore } from "../types";
import { FinancialRadar } from "./FinancialRadar";
import { HealthGauge } from "./HealthGauge";

/** Health overview: radar profile alongside the seven dimension gauges. */
export function FinancialOverview({ health }: { health: Record<string, HealthScore> }) {
  const dimensions = HEALTH_DIMENSIONS.map((key) => health[key]).filter(Boolean) as HealthScore[];

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <FinancialRadar health={health} />
      <div className="rounded-xl border border-border bg-card p-5 shadow-card">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">Health Dimensions</h3>
        <p className="mt-1 text-xs text-muted-foreground">Independent 0–100 scores per dimension.</p>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {dimensions.map((hs) => (
            <HealthGauge key={hs.key} health={hs} size={96} />
          ))}
        </div>
      </div>
    </div>
  );
}
