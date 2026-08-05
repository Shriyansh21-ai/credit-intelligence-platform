import { motion } from "framer-motion";
import {
  AlertTriangle,
  BadgeCheck,
  Bot,
  FileText,
  GitBranch,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

import { activityFeed, type ActivityItem, type ActivityKind } from "@/lib/dashboard-data";
import { cn } from "@/lib/utils";

const KIND_ICON: Record<ActivityKind, LucideIcon> = {
  decision: BadgeCheck,
  fraud: ShieldAlert,
  workflow: GitBranch,
  model: Bot,
  alert: AlertTriangle,
  report: FileText,
};

const STATUS_TONE: Record<NonNullable<ActivityItem["status"]>, string> = {
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/25 bg-warning/10 text-warning",
  danger: "border-destructive/25 bg-destructive/10 text-destructive",
  info: "border-info/25 bg-info/10 text-info",
};

/**
 * Recent activity / workflow stream — a modern enterprise feed that makes the
 * dashboard feel live. Decisions, fraud, workflow and model-ops events with
 * relative timestamps and status-toned icons.
 */
export function ActivityFeed() {
  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success/60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
          </span>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Activity Feed</h3>
        </div>
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">Live</span>
      </div>

      <ol className="relative flex-1 space-y-1">
        {/* vertical timeline rail */}
        <span className="absolute bottom-2 left-[15px] top-2 w-px bg-border" aria-hidden />
        {activityFeed.map((item, idx) => {
          const Icon = KIND_ICON[item.kind];
          const tone = item.status ? STATUS_TONE[item.status] : STATUS_TONE.info;
          return (
            <motion.li
              key={item.id}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.04 }}
              className="group relative flex items-start gap-3 rounded-lg px-1 py-2 transition-colors hover:bg-secondary/40"
            >
              <span
                className={cn(
                  "relative z-[1] flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                  tone,
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1 pt-0.5">
                <p className="text-sm leading-snug text-foreground">
                  <span className="font-medium">{item.actor}</span>{" "}
                  <span className="text-muted-foreground">{item.action}</span>{" "}
                  <span className="font-medium">{item.target}</span>
                </p>
                <span className="mt-0.5 block text-[11px] text-muted-foreground">{item.time}</span>
              </div>
            </motion.li>
          );
        })}
      </ol>

      <a
        href="/operations"
        className="mt-3 inline-flex items-center justify-center rounded-lg border border-border bg-secondary/40 px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:border-ring/40 hover:text-foreground"
      >
        View all activity
      </a>
    </div>
  );
}
