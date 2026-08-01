import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import { HEALTH_DIMENSIONS, type HealthScore } from "../types";

/**
 * Radar of the seven health dimensions. Unavailable dimensions plot at 0 and
 * are annotated below so a thin dataset doesn't read as a failing business.
 */
export function FinancialRadar({ health }: { health: Record<string, HealthScore> }) {
  const data = HEALTH_DIMENSIONS.map((key) => {
    const hs = health[key];
    return {
      dimension: hs?.label.replace(/ Health$/, "") ?? key,
      score: hs?.score ?? 0,
      available: hs?.score !== null && hs?.score !== undefined,
    };
  });

  const unavailable = data.filter((d) => !d.available).map((d) => d.dimension);

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <h3 className="text-sm font-semibold tracking-tight text-foreground">Health Profile</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Seven dimensions on a 0–100 scale.
      </p>
      <div className="mt-3 h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="72%">
            <PolarGrid stroke="var(--border)" />
            <PolarAngleAxis
              dataKey="dimension"
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
            />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Radar
              name="Health"
              dataKey="score"
              stroke="var(--primary)"
              fill="var(--primary)"
              fillOpacity={0.35}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      {unavailable.length > 0 && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Not yet assessable: {unavailable.join(", ")}.
        </p>
      )}
    </div>
  );
}
