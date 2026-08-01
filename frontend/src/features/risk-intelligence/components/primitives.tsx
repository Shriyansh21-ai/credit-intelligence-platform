import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { DashboardSkeleton } from "@/components/common/DashboardSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { SEVERITY_TONE, titleCase } from "../format";

/** Loading / error / empty gate around page content. */
export function StateWrap({
  loading,
  error,
  empty,
  emptyTitle = "No data yet",
  emptyMessage = "There's nothing to show here yet. Once data is available it will appear automatically.",
  emptyAction,
  onRetry,
  skeleton,
  children,
}: {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyTitle?: string;
  emptyMessage?: string;
  /** Optional CTA row shown in the empty state. */
  emptyAction?: ReactNode;
  /** Optional retry handler shown in the error state. */
  onRetry?: () => void;
  /** Optional custom loading placeholder; defaults to a dashboard skeleton. */
  skeleton?: ReactNode;
  children: ReactNode;
}) {
  if (loading) {
    return <>{skeleton ?? <DashboardSkeleton />}</>;
  }
  if (error) {
    return <ErrorState error={error} onRetry={onRetry} />;
  }
  if (empty) {
    return <EmptyState title={emptyTitle} description={emptyMessage} action={emptyAction} />;
  }
  return <>{children}</>;
}

export function MetricCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-card transition-colors duration-200 hover:border-border/80 hover:bg-card/80">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-1.5 text-2xl font-semibold tracking-tight", tone ?? "text-foreground")}>
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function SectionCard({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-border bg-card p-5 shadow-card", className)}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A horizontal magnitude bar. ``fraction`` (0..1) sets the width. */
export function Bar({
  label,
  display,
  fraction,
  tone = "bg-primary",
}: {
  label: string;
  display: string;
  fraction: number;
  tone?: string;
}) {
  const width = Math.max(0, Math.min(1, fraction)) * 100;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="truncate text-foreground">{label}</span>
        <span className="shrink-0 font-mono text-muted-foreground">{display}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        SEVERITY_TONE[severity] ?? "border-border bg-muted text-muted-foreground",
      )}
    >
      {titleCase(severity)}
    </span>
  );
}
