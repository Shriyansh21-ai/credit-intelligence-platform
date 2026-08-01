import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS, titleCase } from "../format";
import { chartAxisTick, chartCursor, chartGridStroke, chartTooltipStyle } from "@/lib/chart-theme";

interface Datum {
  label: string;
  value: number;
}

/** Horizontal-friendly vertical bar chart for categorical counts. */
export function CountBarChart({ data, color = CHART_COLORS[0] }: { data: Datum[]; color?: string }) {
  if (!data.length) {
    return <p className="text-sm text-muted-foreground">No data.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <XAxis type="number" allowDecimals={false} tick={chartAxisTick} stroke={chartGridStroke} />
        <YAxis
          type="category"
          dataKey="label"
          width={140}
          tick={chartAxisTick}
          stroke={chartGridStroke}
        />
        <Tooltip
          contentStyle={chartTooltipStyle}
          cursor={chartCursor}
          formatter={(v: number) => [v, "Count"]}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} fill={color} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function CategoryPie({ data }: { data: Datum[] }) {
  if (!data.length) {
    return <p className="text-sm text-muted-foreground">No data.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="label" innerRadius={45} outerRadius={80} paddingAngle={2}>
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={chartTooltipStyle} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/** Simple key/value list used where a chart is overkill. */
export function CountList({ data }: { data: Datum[] }) {
  if (!data.length) return <p className="text-sm text-muted-foreground">No data.</p>;
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <ul className="space-y-2">
      {data.map((d) => (
        <li key={d.label} className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-foreground">{titleCase(d.label)}</span>
            <span className="font-mono text-muted-foreground">{d.value}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
