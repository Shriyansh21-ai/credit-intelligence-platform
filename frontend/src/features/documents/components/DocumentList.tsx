import { FolderOpen } from "lucide-react";
import type { DocumentSummary } from "../types";
import { DocumentCard } from "./DocumentCard";
import { LoadingSkeleton } from "./LoadingSkeleton";

interface DocumentListProps {
  documents: DocumentSummary[];
  activeId: number | null;
  busyId: number | null;
  loading: boolean;
  onSelect: (id: number) => void;
  onExtract: (id: number) => void;
  onDelete: (id: number) => void;
}

export function DocumentList({ documents, activeId, busyId, loading, onSelect, onExtract, onDelete }: DocumentListProps) {
  return (
    <div className="space-y-2.5">
      <h3 className="px-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        Document Library
      </h3>

      {loading ? (
        <LoadingSkeleton rows={3} />
      ) : documents.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-secondary/20 px-4 py-8 text-center">
          <FolderOpen className="h-6 w-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No documents yet. Upload a statement to begin.</p>
        </div>
      ) : (
        documents.map((doc) => (
          <DocumentCard
            key={doc.id}
            document={doc}
            active={doc.id === activeId}
            busy={doc.id === busyId}
            onSelect={() => onSelect(doc.id)}
            onExtract={() => onExtract(doc.id)}
            onDelete={() => onDelete(doc.id)}
          />
        ))
      )}
    </div>
  );
}
