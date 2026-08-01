import { FileText, Loader2, X } from "lucide-react";
import { formatBytes } from "../format";

interface ProgressCardProps {
  name: string;
  size: number;
  uploading?: boolean;
  onRemove?: () => void;
}

/** A selected/uploading file row with an indeterminate progress bar. */
export function ProgressCard({ name, size, uploading, onRemove }: ProgressCardProps) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-secondary/60 text-muted-foreground">
        <FileText className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">{name}</div>
        <div className="text-[11px] text-muted-foreground">{formatBytes(size)}</div>
        {uploading && (
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-secondary">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-primary" />
          </div>
        )}
      </div>
      {uploading ? (
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
      ) : onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${name}`}
          className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}
