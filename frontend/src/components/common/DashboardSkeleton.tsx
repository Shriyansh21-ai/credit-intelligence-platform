import { Skeleton } from "@/components/ui/skeleton";

/**
 * Generic dashboard loading skeleton — a KPI row plus a content panel that
 * mirrors the typical page structure (metrics + section card). Used as the
 * default loading state for `StateWrap`, so async pages fade in structured
 * placeholders instead of a bare spinner.
 */
export function DashboardSkeleton({
  metrics = 4,
  rows = 4,
  className,
}: {
  metrics?: number;
  rows?: number;
  className?: string;
}) {
  return (
    <div className={className} aria-busy="true" aria-live="polite">
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: metrics }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 shadow-card">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-7 w-16" />
            </div>
          ))}
        </div>
        <div className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-card">
          <Skeleton className="h-4 w-40" />
          {Array.from({ length: rows }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  );
}
