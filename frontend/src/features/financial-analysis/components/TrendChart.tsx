import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";
import { formatRatioValue } from "../format";
import type { Trends } from "../types";

/**
 * Multi-period trend of a selectable metric. Degrades to an informative empty
 * state when only one period exists (the common case today).
 */
export function TrendChart({ trends }: { trends: Trends }) {
  const metricKeys = Object.keys(trends.metrics);
  const [selected, setSelected] = useState(metricKeys[0] ?? "revenue");
  const metric = trends.metrics[selected];

  if (!trends.sufficient_data) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 shadow-card">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">Financial Trends</h3>
        <div className="mt-6 flex h-40 flex-col items-center justify-center text-center">
          <p className="text-sm text-muted-foreground">{trends.summary}</p>
        </div>
      </div>
    );
  }

  const data = (metric?.series ?? []).map((point) => ({
    period: point.period,
    value: point.value,
  }));

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Financial Trends</h3>
          <p className="mt-1 text-xs text-muted-foreground">{trends.summary}</p>
        </div>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground"
          aria-label="Select trend metric"
        >
          {metricKeys.map((key) => (
            <option key={key} value={key}>
              {trends.metrics[key].label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="period" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
            <YAxis
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickFormatter={(v) => formatRatioValue(v as number, metric?.unit ?? "currency")}
              width={56}
            />
            <Tooltip
              contentStyle={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--foreground)",
              }}
              formatter={(v) => formatRatioValue(v as number, metric?.unit ?? "currency")}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--primary)"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {metric && (
        <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
          {metric.cagr !== null && (
            <span>
              CAGR: <span className="font-medium text-foreground">{(metric.cagr * 100).toFixed(1)}%</span>
            </span>
          )}
          <span className={cn("capitalize", metric.direction === "declining" && "text-destructive")}>
            Direction: <span className="font-medium text-foreground">{metric.direction.replace(/_/g, " ")}</span>
          </span>
        </div>
      )}
    </div>
  );
}
