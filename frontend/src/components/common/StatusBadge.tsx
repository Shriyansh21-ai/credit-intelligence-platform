import { cn } from "@/lib/utils";
import { statusBadge } from "@/lib/status";

function humanize(s: string): string {
  return s
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Consistent operational-status pill. The colour is derived from the status
 * vocabulary in @/lib/status (healthy/active/pending/failed/…), so the same
 * status always reads the same across every dashboard.
 */
export function StatusBadge({
  status,
  label,
  className,
}: {
  status: string;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        statusBadge(status),
        className,
      )}
    >
      {label ?? humanize(String(status ?? ""))}
    </span>
  );
}
