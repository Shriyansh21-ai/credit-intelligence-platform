export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2.5">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 shrink-0 animate-pulse rounded-md bg-secondary" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-2/3 animate-pulse rounded bg-secondary" />
              <div className="h-2.5 w-1/3 animate-pulse rounded bg-secondary" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
