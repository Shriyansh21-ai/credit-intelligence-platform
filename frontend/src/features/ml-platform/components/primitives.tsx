import { cn } from "@/lib/utils";
import { statusTone } from "../format";

/** A pill badge for a model's approval / production status. */
export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-border px-2 py-0.5 text-[11px] font-medium",
        statusTone(status),
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
