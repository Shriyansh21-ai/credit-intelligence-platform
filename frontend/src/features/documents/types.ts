/** Types mirroring the backend Document Intelligence API (schemas/document.py). */

export type DocumentType =
  | "balance_sheet"
  | "profit_loss"
  | "cash_flow"
  | "bank_statement"
  | "gst_return"
  | "income_tax_return"
  | "business_registration"
  | "other";

export type DocumentStatus = "uploaded" | "extracting" | "extracted" | "reviewed" | "failed";

export type ConfidenceLevel = "high" | "medium" | "low";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  page: number;
}

export interface ExtractedField {
  key: string;
  label: string;
  type: "currency" | "text" | "year" | "gst" | "identifier";
  value: string | number | null;
  raw_text: string | null;
  confidence: number;
  confidence_level: ConfidenceLevel;
  bbox: BoundingBox | null;
  edited: boolean;
}

export interface ValidationIssue {
  field: string | null;
  severity: "error" | "warning";
  message: string;
}

export interface DocumentSummary {
  id: number;
  document_type: DocumentType;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  ocr_source: string | null;
  page_count: number | null;
  content_hash: string;
  created_at: string;
  updated_at: string | null;
}

export interface DocumentExtraction {
  version: number;
  is_current: boolean;
  source: string | null;
  overall_confidence: number | null;
  fields: ExtractedField[];
  validation: ValidationIssue[];
  created_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  current_extraction: DocumentExtraction | null;
}

export interface UploadResponse {
  documents: DocumentSummary[];
  duplicates: string[];
}

export interface ExtractResponse {
  document: DocumentDetail;
}

export interface HistoryResponse {
  documents: DocumentSummary[];
}
