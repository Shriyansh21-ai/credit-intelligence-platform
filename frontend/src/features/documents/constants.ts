import type { ConfidenceLevel, DocumentType } from "./types";

export interface DocumentTypeOption {
  value: DocumentType;
  label: string;
}

export const DOCUMENT_TYPE_OPTIONS: DocumentTypeOption[] = [
  { value: "balance_sheet", label: "Balance Sheet" },
  { value: "profit_loss", label: "Profit & Loss" },
  { value: "cash_flow", label: "Cash Flow Statement" },
  { value: "bank_statement", label: "Bank Statement" },
  { value: "gst_return", label: "GST Return" },
  { value: "income_tax_return", label: "Income Tax Return" },
  { value: "business_registration", label: "Business Registration" },
  { value: "other", label: "Other Supporting Document" },
];

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = Object.fromEntries(
  DOCUMENT_TYPE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<DocumentType, string>;

export const ACCEPTED_MIME_TYPES = ["application/pdf", "image/png", "image/jpeg"];
export const ACCEPTED_EXTENSIONS = ".pdf,.png,.jpg,.jpeg";
export const MAX_UPLOAD_MB = 20;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

export const CONFIDENCE_META: Record<ConfidenceLevel, { label: string; tone: "positive" | "warning" | "negative" }> = {
  high: { label: "High", tone: "positive" },
  medium: { label: "Medium", tone: "warning" },
  low: { label: "Low", tone: "negative" },
};

export const STATUS_META: Record<string, { label: string; tone: "neutral" | "positive" | "warning" | "negative" }> = {
  uploaded: { label: "Uploaded", tone: "neutral" },
  extracting: { label: "Extracting", tone: "warning" },
  extracted: { label: "Extracted", tone: "positive" },
  reviewed: { label: "Reviewed", tone: "positive" },
  failed: { label: "Failed", tone: "negative" },
};
