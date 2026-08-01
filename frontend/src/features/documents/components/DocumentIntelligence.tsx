import { AlertCircle, FileStack, Info, X } from "lucide-react";
import { useDocuments } from "../hooks/useDocuments";
import { UploadZone } from "./UploadZone";
import { DocumentList } from "./DocumentList";
import { DocumentViewer } from "./DocumentViewer";

/**
 * Enterprise Document Intelligence workspace: upload → extract → review.
 * All state lives in `useDocuments`; this component is presentational.
 */
export function DocumentIntelligence() {
  const docs = useDocuments();

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Document Intelligence</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Upload financial statements and supporting documents. The system extracts key financial fields with
          confidence scores for review before they feed downstream analysis.
        </p>
      </div>

      {docs.error && (
        <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{docs.error}</span>
        </div>
      )}
      {docs.notice && (
        <div className="flex items-start justify-between gap-3 rounded-lg border border-border bg-secondary/40 px-4 py-3 text-sm text-muted-foreground">
          <span className="flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            {docs.notice}
          </span>
          <button type="button" onClick={docs.dismissNotice} aria-label="Dismiss" className="rounded p-0.5 hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <UploadZone onUpload={docs.upload} uploading={docs.uploading} />

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <DocumentList
          documents={docs.history}
          activeId={docs.active?.id ?? null}
          busyId={docs.busyId}
          loading={docs.loadingHistory}
          onSelect={docs.select}
          onExtract={docs.extract}
          onDelete={docs.remove}
        />

        {docs.active ? (
          <DocumentViewer
            document={docs.active}
            saving={docs.busyId === docs.active.id}
            onSave={(fields) => docs.review(docs.active!.id, fields)}
            onExtract={() => docs.extract(docs.active!.id)}
          />
        ) : (
          <div className="flex min-h-[24rem] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-secondary/20 p-8 text-center">
            <FileStack className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Select a document from the library to view and review its extracted fields.</p>
          </div>
        )}
      </div>
    </div>
  );
}
