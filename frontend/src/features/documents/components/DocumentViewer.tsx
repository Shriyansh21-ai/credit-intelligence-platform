import { useState } from "react";
import { FileWarning, Loader2, ScanLine } from "lucide-react";
import { useDocumentFile } from "../hooks/useDocumentFile";
import { isImageMime, isPdfMime } from "../format";
import type { BoundingBox, DocumentDetail } from "../types";
import { ReviewPanel } from "./ReviewPanel";

interface DocumentViewerProps {
  document: DocumentDetail;
  saving: boolean;
  onSave: (fields: Record<string, string | number | null>) => void;
  onExtract: () => void;
}

/** Split layout: original document (left) + editable extraction (right). */
export function DocumentViewer({ document, saving, onSave, onExtract }: DocumentViewerProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const extraction = document.current_extraction;
  const selectedField = extraction?.fields.find((f) => f.key === selectedKey) ?? null;

  return (
    <div className="grid gap-4 overflow-hidden rounded-xl border border-border bg-card shadow-card lg:grid-cols-2">
      <div className="border-b border-border lg:border-b-0 lg:border-r">
        <DocumentCanvas
          documentId={document.id}
          mime={document.mime_type}
          highlight={selectedField?.bbox ?? null}
        />
      </div>

      <div className="min-h-[24rem]">
        {extraction ? (
          <ReviewPanel
            extraction={extraction}
            saving={saving}
            selectedKey={selectedKey}
            onSelectField={setSelectedKey}
            onSave={onSave}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <ScanLine className="h-7 w-7 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">This document hasn't been processed yet.</p>
            <button
              type="button"
              onClick={onExtract}
              className="inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-glow hover:opacity-90"
            >
              <ScanLine className="h-4 w-4" /> Run extraction
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function DocumentCanvas({
  documentId,
  mime,
  highlight,
}: {
  documentId: number;
  mime: string;
  highlight: BoundingBox | null;
}) {
  const { url, loading, error } = useDocumentFile(documentId);

  if (loading) {
    return (
      <div className="flex h-full min-h-[24rem] items-center justify-center bg-secondary/20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !url) {
    return (
      <div className="flex h-full min-h-[24rem] flex-col items-center justify-center gap-2 bg-secondary/20 text-center">
        <FileWarning className="h-6 w-6 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">{error ?? "Preview unavailable"}</p>
      </div>
    );
  }

  if (isImageMime(mime)) {
    return (
      <div className="relative max-h-[40rem] overflow-auto bg-secondary/20 p-3">
        <div className="relative inline-block">
          <img src={url} alt="Document preview" className="max-w-full" />
          {highlight && (
            <div
              className="pointer-events-none absolute rounded-sm border-2 border-primary bg-primary/15 transition-all"
              style={{
                left: `${highlight.x * 100}%`,
                top: `${highlight.y * 100}%`,
                width: `${highlight.width * 100}%`,
                height: `${highlight.height * 100}%`,
              }}
            />
          )}
        </div>
      </div>
    );
  }

  if (isPdfMime(mime)) {
    return (
      <div className="flex h-full flex-col">
        <iframe src={url} title="Document preview" className="h-[40rem] w-full bg-secondary/20" />
        {highlight && (
          <p className="border-t border-border px-3 py-1.5 text-[11px] text-muted-foreground">
            Selected field is on page {highlight.page + 1}. Region highlighting is available for image documents.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[24rem] items-center justify-center bg-secondary/20 text-sm text-muted-foreground">
      Preview not supported for this file type.
    </div>
  );
}
