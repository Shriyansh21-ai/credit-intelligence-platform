import { apiDelete, apiGet, apiPost, apiPut, authFetch } from "@/lib/http";
import type {
  DocumentDetail,
  DocumentCompany,
  DocumentType,
  ExtractResponse,
  HistoryResponse,
  UploadResponse,
} from "./types";

export async function uploadDocuments(
  files: File[],
  documentType: DocumentType,
  options?: {
    companyId?: number | null;
    fiscalYear?: number | null;
    currency?: string;
    unit?: string;
  },
): Promise<UploadResponse> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  form.append("document_type", documentType);
  if (options?.companyId != null) form.append("company_id", String(options.companyId));
  if (options?.fiscalYear != null) form.append("fiscal_year", String(options.fiscalYear));
  if (options?.currency) form.append("currency", options.currency);
  if (options?.unit) form.append("unit", options.unit);

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
  options?: {
    documentType?: DocumentType;
    companyId?: number | null;
    fiscalYear?: number | null;
    currency?: string | null;
    unit?: string | null;
  },
): Promise<ExtractResponse> {
  return apiPut<ExtractResponse>(`/documents/${id}/review`, {
    fields,
    document_type: options?.documentType,
    company_id: options?.companyId ?? null,
    fiscal_year: options?.fiscalYear ?? null,
    currency: options?.currency ?? null,
    unit: options?.unit ?? null,
  });
}

export function deleteDocument(id: number): Promise<void> {
  return apiDelete(`/documents/${id}`);
}

export function getHistory(): Promise<HistoryResponse> {
  return apiGet<HistoryResponse>("/documents/history");
}

export function getDocumentCompanies(): Promise<{ items: DocumentCompany[] }> {
  return apiGet<{ items: DocumentCompany[] }>("/documents/companies");
}

export function approveDocument(
  id: number,
  acknowledgedWarnings: string[],
  replaceExistingFinancials: boolean,
): Promise<{ document: DocumentDetail; persistence_status: string }> {
  return apiPost<{ document: DocumentDetail; persistence_status: string }>(
    `/documents/${id}/approve`,
    {
      acknowledged_warnings: acknowledgedWarnings,
      replace_existing_financials: replaceExistingFinancials,
    },
  );
}

export function rejectDocument(id: number, reason: string): Promise<DocumentDetail> {
  return apiPost<DocumentDetail>(`/documents/${id}/reject`, { reason });
}

/** Fetch the original file as an object URL (authorized) for the viewer. */
export async function fetchDocumentObjectUrl(id: number): Promise<string> {
  const response = await authFetch(`/documents/${id}/file`);
  if (!response.ok) throw new Error(`Failed to load document file (${response.status})`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
