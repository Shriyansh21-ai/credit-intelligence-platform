import { FileText, Loader2, ScanLine, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { DOCUMENT_TYPE_LABELS } from "../constants";
import { formatBytes, formatDate } from "../format";
import type { DocumentSummary } from "../types";
import { StatusBadge } from "./Badges";

interface DocumentCardProps {
  document: DocumentSummary;
  active: boolean;
  busy: boolean;
  onSelect: () => void;
  onExtract: () => void;
  onDelete: () => void;
}

export function DocumentCard({ document, active, busy, onSelect, onExtract, onDelete }: DocumentCardProps) {
  return (
    <div
      onClick={onSelect}
      className={cn(
        "cursor-pointer rounded-lg border bg-card p-3 shadow-card transition-colors",
        active ? "border-ring ring-1 ring-ring/30" : "border-border hover:border-ring/40",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-secondary/60 text-muted-foreground">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-foreground">{document.original_filename}</div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            {DOCUMENT_TYPE_LABELS[document.document_type]} · {formatBytes(document.size_bytes)} · {formatDate(document.created_at)}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <StatusBadge status={document.status} />
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onExtract();
                }}
                title="Re-run extraction"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                <ScanLine className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
                title="Delete document"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
