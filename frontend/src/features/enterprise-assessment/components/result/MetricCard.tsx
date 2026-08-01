import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "positive" | "warning" | "negative";

const toneStyles: Record<Tone, { badge: string; value: string }> = {
  neutral: { badge: "bg-secondary/70 text-muted-foreground", value: "text-foreground" },
  positive: { badge: "bg-success/10 text-success", value: "text-foreground" },
  warning: { badge: "bg-warning/10 text-warning", value: "text-foreground" },
  negative: { badge: "bg-destructive/10 text-destructive", value: "text-foreground" },
};

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  badge?: string;
  tone?: Tone;
  icon: LucideIcon;
}

/** Premium KPI card for the enterprise result header. */
export function MetricCard({ label, value, sub, badge, tone = "neutral", icon: Icon }: MetricCardProps) {
  const styles = toneStyles[tone];
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-card">
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-secondary/60 text-foreground">
          <Icon className="h-4.5 w-4.5" />
        </div>
        {badge && (
          <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-semibold", styles.badge)}>{badge}</span>
        )}
      </div>
      <div className="mt-5">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className={cn("mt-1 text-2xl font-semibold tracking-tight", styles.value)}>{value}</div>
        {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
      </div>
    </div>
  );
}
