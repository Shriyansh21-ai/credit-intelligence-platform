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
}

export function KpiCard({ label, value, delta, trend, icon, index = 0 }: KpiCardProps) {
  const Icon = ICONS[icon] ?? Activity;
  const positive = (trend === "up" && delta >= 0) || (trend === "down" && delta <= 0);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
      whileHover={{ y: -2 }}
      className="group relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-card transition-colors hover:border-ring/40"
    >
      <div className="absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-secondary/60 text-foreground">
          <Icon className="h-4.5 w-4.5" />
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
            positive ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
          )}
        >
          {trend === "up" ? (
            <ArrowUpRight className="h-3 w-3" />
          ) : (
            <ArrowDownRight className="h-3 w-3" />
          )}
          {Math.abs(delta)}%
        </span>
      </div>

      <div className="mt-5">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className="mt-1 text-2xl font-semibold tracking-tight text-foreground">{value}</div>
      </div>
    </motion.div>
  );
}
