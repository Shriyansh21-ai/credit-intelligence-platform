import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import { riskDistribution, volumeTrend, approvalTrend } from "@/lib/dashboard-data";

function Panel({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-border bg-card p-5 shadow-card ${className}`}>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">{title}</h3>
          {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

const tooltipStyle = {
  backgroundColor: "var(--color-popover)",
  border: "1px solid var(--color-border)",
  borderRadius: 10,
  fontSize: 12,
  color: "var(--color-popover-foreground)",
};

export function RiskDonut() {
  const total = riskDistribution.reduce((s, x) => s + x.value, 0);
  return (
    <Panel title="Credit Risk Distribution" subtitle="Across active portfolio">
      <div className="relative h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={riskDistribution}
              dataKey="value"
              innerRadius={70}
              outerRadius={95}
              paddingAngle={3}
              stroke="var(--color-card)"
              strokeWidth={2}
            >
              {riskDistribution.map((d) => (
                <Cell key={d.name} fill={d.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Total</div>
          <div className="text-2xl font-semibold text-foreground">{total.toLocaleString()}</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        {riskDistribution.map((d) => (
          <div
            key={d.name}
            className="flex items-center justify-between rounded-md border border-border bg-secondary/40 px-2.5 py-1.5"
          >
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
              <span className="text-foreground">{d.name}</span>
            </div>
            <span className="text-muted-foreground">{((d.value / total) * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function VolumeArea() {
  return (
    <Panel title="Prediction Volume Trend" subtitle="Last 12 months">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={volumeTrend} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-chart-1)" stopOpacity={0.6} />
                <stop offset="95%" stopColor="var(--color-chart-1)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Area
              type="monotone"
              dataKey="predictions"
              stroke="var(--color-chart-1)"
              strokeWidth={2}
              fill="url(#g1)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

export function ApprovalBar() {
  return (
    <Panel title="Approval vs Rejection Trend" subtitle="Weekly decisions">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={approvalTrend} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="week"
              tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              cursor={{ fill: "var(--color-secondary)", opacity: 0.4 }}
            />
            <Legend
              wrapperStyle={{ fontSize: 12, color: "var(--color-muted-foreground)" }}
              iconType="circle"
            />
            <Bar dataKey="approved" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
            <Bar dataKey="rejected" fill="var(--color-chart-5)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
