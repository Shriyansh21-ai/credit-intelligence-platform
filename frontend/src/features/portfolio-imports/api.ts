import { authFetch } from "@/lib/http";

export interface PortfolioImportRecord {
  id: number;
  filename: string;
  file_format: string;
  file_size: number;
  status: string;
  worksheet: string | null;
  column_mapping: Record<string, string | null>;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  warning_count: number;
  imported_rows: number;
  skipped_rows: number;
  failed_rows: number;
  error_summary: string | null;
  created_at: string | null;
  completed_at: string | null;
  findings?: ValidationFinding[];
}

export interface ValidationFinding {
  row_number: number;
  field: string | null;
  code: string;
  message: string;
  severity: "error" | "warning" | "info";
}

export interface MappingInspection {
  worksheets: string[];
  worksheet: string;
  headers: string[];
  sample_rows: Record<string, string | number | null>[];
  suggestions: Record<string, string | null>;
  fields: Record<string, { label: string; required: string }>;
}

export interface ImportPreview {
  total: number;
  items: { row_number: number; canonical: Record<string, unknown>; valid: boolean }[];
  findings: ValidationFinding[];
  valid_rows: number;
  invalid_rows: number;
  warning_count: number;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      // Preserve the HTTP status when an error response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function uploadPortfolio(file: File) {
  const form = new FormData();
  form.append("file", file);
  return json<PortfolioImportRecord & MappingInspection>(
    await authFetch("/api/portfolio-imports", { method: "POST", body: form }),
  );
}

export async function getMapping(id: number, worksheet?: string) {
  const query = worksheet ? `?worksheet=${encodeURIComponent(worksheet)}` : "";
  return json<MappingInspection>(await authFetch(`/api/portfolio-imports/${id}/mapping${query}`));
}

export async function validatePortfolioMapping(
  id: number,
  worksheet: string,
  mapping: Record<string, string | null>,
) {
  return json<PortfolioImportRecord>(
    await authFetch(`/api/portfolio-imports/${id}/mapping`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worksheet, mapping }),
    }),
  );
}

export async function getPreview(id: number) {
  return json<ImportPreview>(await authFetch(`/api/portfolio-imports/${id}/preview?limit=200`));
}

export async function confirmPortfolioImport(id: number) {
  return json<PortfolioImportRecord>(
    await authFetch(`/api/portfolio-imports/${id}/confirm`, { method: "POST" }),
  );
}

export async function cancelPortfolioImport(id: number) {
  return json<PortfolioImportRecord>(
    await authFetch(`/api/portfolio-imports/${id}/cancel`, { method: "POST" }),
  );
}

export async function getPortfolioImportHistory() {
  return json<{ total: number; items: PortfolioImportRecord[] }>(
    await authFetch("/api/portfolio-imports?limit=100"),
  );
}

export async function downloadValidationReport(id: number) {
  const response = await authFetch(`/api/portfolio-imports/${id}/validation-report.csv`);
  if (!response.ok) throw new Error(`Report download failed (${response.status})`);
  return response.blob();
}
