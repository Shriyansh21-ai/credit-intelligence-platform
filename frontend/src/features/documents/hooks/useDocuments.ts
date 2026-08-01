import { useCallback, useEffect, useState } from "react";
import {
  deleteDocument,
  extractDocument,
  getDocument,
  getHistory,
  reviewDocument,
  uploadDocuments,
} from "../api";
import type { DocumentDetail, DocumentSummary, DocumentType } from "../types";

/**
 * Orchestrates the document workspace: history, the active document + its
 * extraction, and the upload → extract → review → delete actions.
 */
export function useDocuments() {
  const [history, setHistory] = useState<DocumentSummary[]>([]);
  const [active, setActive] = useState<DocumentDetail | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    try {
      const response = await getHistory();
      setHistory(response.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  const select = useCallback(async (id: number) => {
    setError(null);
    try {
      setActive(await getDocument(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open document");
    }
  }, []);

  const upload = useCallback(
    async (files: File[], documentType: DocumentType) => {
      setUploading(true);
      setError(null);
      setNotice(null);
      try {
        const result = await uploadDocuments(files, documentType);
        await refreshHistory();
        if (result.duplicates.length) {
          setNotice(`Skipped ${result.duplicates.length} duplicate file(s): ${result.duplicates.join(", ")}`);
        }
        // Auto-select and extract the first newly uploaded document.
        const first = result.documents[0];
        if (first) {
          await extract(first.id);
        }
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        throw err;
      } finally {
        setUploading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [refreshHistory],
  );

  const extract = useCallback(
    async (id: number) => {
      setBusyId(id);
      setError(null);
      try {
        const response = await extractDocument(id);
        setActive(response.document);
        await refreshHistory();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Extraction failed");
      } finally {
        setBusyId(null);
      }
    },
    [refreshHistory],
  );

  const review = useCallback(
    async (id: number, fields: Record<string, string | number | null>, documentType?: DocumentType) => {
      setBusyId(id);
      setError(null);
      try {
        const response = await reviewDocument(id, fields, { documentType });
        setActive(response.document);
        await refreshHistory();
        setNotice("Changes saved.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save review");
      } finally {
        setBusyId(null);
      }
    },
    [refreshHistory],
  );

  const remove = useCallback(
    async (id: number) => {
      setBusyId(id);
      try {
        await deleteDocument(id);
        setActive((current) => (current?.id === id ? null : current));
        await refreshHistory();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete document");
      } finally {
        setBusyId(null);
      }
    },
    [refreshHistory],
  );

  return {
    history,
    active,
    loadingHistory,
    uploading,
    busyId,
    error,
    notice,
    setActive,
    select,
    upload,
    extract,
    review,
    remove,
    dismissNotice: () => setNotice(null),
  };
}
