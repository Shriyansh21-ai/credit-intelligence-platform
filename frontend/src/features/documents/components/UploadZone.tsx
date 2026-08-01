import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { AlertCircle, UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";
import { ACCEPTED_EXTENSIONS, DOCUMENT_TYPE_OPTIONS } from "../constants";
import { validateFiles, type RejectedFile } from "../validation";
import type { DocumentType } from "../types";
import { ProgressCard } from "./ProgressCard";

interface UploadZoneProps {
  onUpload: (files: File[], documentType: DocumentType) => Promise<unknown>;
  uploading: boolean;
}

export function UploadZone({ onUpload, uploading }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selected, setSelected] = useState<File[]>([]);
  const [rejected, setRejected] = useState<RejectedFile[]>([]);
  const [documentType, setDocumentType] = useState<DocumentType>("balance_sheet");

  function addFiles(fileList: FileList | null) {
    if (!fileList) return;
    const { accepted, rejected: bad } = validateFiles(Array.from(fileList));
    setRejected(bad);
    setSelected((prev) => {
      const names = new Set(prev.map((f) => f.name + f.size));
      return [...prev, ...accepted.filter((f) => !names.has(f.name + f.size))];
    });
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragActive(false);
    addFiles(event.dataTransfer.files);
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    addFiles(event.target.files);
    event.target.value = "";
  }

  function removeFile(index: number) {
    setSelected((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleUpload() {
    if (!selected.length) return;
    await onUpload(selected, documentType);
    setSelected([]);
    setRejected([]);
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-foreground">Upload Documents</h2>
          <p className="text-xs text-muted-foreground">Balance sheets, P&L, cash-flow, bank statements, GST/ITR — PDF, PNG or JPG.</p>
        </div>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          Document type
          <select
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value as DocumentType)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
          >
            {DOCUMENT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragActive ? "border-primary bg-primary/5" : "border-border bg-secondary/30 hover:border-ring/50",
        )}
      >
        <div className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-background text-primary">
          <UploadCloud className="h-5 w-5" />
        </div>
        <p className="text-sm font-medium text-foreground">Drag &amp; drop files here</p>
        <p className="text-xs text-muted-foreground">or click to browse</p>
        <input ref={inputRef} type="file" accept={ACCEPTED_EXTENSIONS} multiple hidden onChange={onInputChange} />
      </div>

      {rejected.length > 0 && (
        <div className="mt-3 space-y-1">
          {rejected.map((r) => (
            <p key={r.name} className="flex items-center gap-2 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5" /> {r.name} — {r.reason}
            </p>
          ))}
        </div>
      )}

      {selected.length > 0 && (
        <div className="mt-4 space-y-2">
          {selected.map((file, index) => (
            <ProgressCard
              key={file.name + file.size}
              name={file.name}
              size={file.size}
              uploading={uploading}
              onRemove={uploading ? undefined : () => removeFile(index)}
            />
          ))}
          <div className="flex justify-end pt-1">
            <button
              type="button"
              disabled={uploading}
              onClick={handleUpload}
              className="inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {uploading ? "Uploading…" : `Upload & Extract (${selected.length})`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
