import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Briefcase,
  CheckCircle2,
  Gauge,
  ShieldAlert,
  Users,
  ArrowUpRight,
  ArrowDownRight,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  Gauge,
  CheckCircle2,
  Activity,
  ShieldAlert,
  Users,
  AlertTriangle,
  Briefcase,
};

interface KpiCardProps {
  label: string;
  value: string;
  delta: number;
  trend: "up" | "down";
  icon: string;
  index?: number;
  /** Optional micro-trend series rendered as a sparkline. */
  spark?: number[];
  /** Small caption under the value, e.g. "vs prior 30 days". */
  compareLabel?: string;
}

/** Tiny inline SVG sparkline — no chart library, no layout cost. */
function Sparkline({ points, positive }: { points: number[]; positive: boolean }) {
  if (!points || points.length < 2) return null;
  const w = 96;
  const h = 28;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const step = w / (points.length - 1);
  const coords = points.map((p, i) => [i * step, h - ((p - min) / range) * h]);
  const line = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${w},${h} L0,${h} Z`;
  const stroke = positive ? "var(--color-success)" : "var(--color-destructive)";
  const gid = `spark-${positive ? "up" : "dn"}`;
  const [lx, ly] = coords[coords.length - 1];
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      preserveAspectRatio="none"
      className="h-7 w-full overflow-visible opacity-90"
      aria-hidden
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.22} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lx} cy={ly} r={2} fill={stroke} />
    </svg>
  );
}

export function KpiCard({ label, value, delta, trend, icon, index = 0, spark, compareLabel }: KpiCardProps) {
  const Icon = ICONS[icon] ?? Activity;
  const positive = (trend === "up" && delta >= 0) || (trend === "down" && delta <= 0);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35 }}
      whileHover={{ y: -2 }}
      className="group relative flex flex-col overflow-hidden rounded-xl border border-border bg-card p-4 shadow-card transition-colors hover:border-ring/40"
    >
      <div className="absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="flex items-start justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-secondary/60 text-foreground transition-colors group-hover:text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold tabular-nums",
            positive ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
          )}
          title={compareLabel}
        >
          {trend === "up" ? (
            <ArrowUpRight className="h-3 w-3" />
          ) : (
            <ArrowDownRight className="h-3 w-3" />
          )}
          {Math.abs(delta)}%
        </span>
      </div>

      <div className="mt-3">
        <div className="truncate text-[11px] font-medium uppercase tracking-wider text-muted-foreground" title={label}>
          {label}
        </div>
        <div className="mt-0.5 text-2xl font-semibold tracking-tight text-foreground tabular-nums">
          {value}
        </div>
      </div>

      {spark && spark.length > 1 ? (
        <div className="mt-3 flex items-end justify-between gap-2">
          <span className="text-[10px] text-muted-foreground">{compareLabel}</span>
          <div className="h-7 w-24 shrink-0">
            <Sparkline points={spark} positive={positive} />
          </div>
        </div>
      ) : (
        compareLabel && <div className="mt-2 text-[10px] text-muted-foreground">{compareLabel}</div>
      )}
    </motion.div>
  );
}
