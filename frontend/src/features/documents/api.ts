import { apiDelete, apiGet, apiPost, apiPut, authFetch } from "@/lib/http";
import type {
  DocumentDetail,
  DocumentType,
  ExtractResponse,
  HistoryResponse,
  UploadResponse,
} from "./types";

export async function uploadDocuments(files: File[], documentType: DocumentType): Promise<UploadResponse> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  form.append("document_type", documentType);

  // Multipart: let the browser set the Content-Type boundary.
  const response = await authFetch("/documents/upload", { method: "POST", body: form });
  if (!response.ok) {
    let detail = `Upload failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return response.json();
}

export function extractDocument(id: number): Promise<ExtractResponse> {
  return apiPost<ExtractResponse>(`/documents/${id}/extract`, {});
}

export function getDocument(id: number): Promise<DocumentDetail> {
  return apiGet<DocumentDetail>(`/documents/${id}`);
}

export function reviewDocument(
  id: number,
  fields: Record<string, string | number | null>,
  options?: { documentType?: DocumentType; markReviewed?: boolean },
): Promise<ExtractResponse> {
  return apiPut<ExtractResponse>(`/documents/${id}/review`, {
    fields,
    document_type: options?.documentType,
    mark_reviewed: options?.markReviewed ?? true,
  });
}

export function deleteDocument(id: number): Promise<void> {
  return apiDelete(`/documents/${id}`);
}

export function getHistory(): Promise<HistoryResponse> {
  return apiGet<HistoryResponse>("/documents/history");
}

/** Fetch the original file as an object URL (authorized) for the viewer. */
export async function fetchDocumentObjectUrl(id: number): Promise<string> {
  const response = await authFetch(`/documents/${id}/file`);
  if (!response.ok) throw new Error(`Failed to load document file (${response.status})`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
