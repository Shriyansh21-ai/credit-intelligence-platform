import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Download, FileSpreadsheet, Upload } from "lucide-react";

import { OpsLayout } from "@/features/operations";
import { authFetch } from "@/lib/http";
import {
  cancelPortfolioImport,
  confirmPortfolioImport,
  downloadValidationReport,
  getMapping,
  getPortfolioImportHistory,
  getPreview,
  uploadPortfolio,
  validatePortfolioMapping,
  type ImportPreview,
  type MappingInspection,
  type PortfolioImportRecord,
} from "@/features/portfolio-imports/api";

export const Route = createFileRoute("/portfolio-imports")({ component: PortfolioImportsPage });

type Stage = "upload" | "mapping" | "preview" | "complete";

function PortfolioImportsPage() {
  const [stage, setStage] = useState<Stage>("upload");
  const [record, setRecord] = useState<PortfolioImportRecord | null>(null);
  const [inspection, setInspection] = useState<MappingInspection | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [history, setHistory] = useState<PortfolioImportRecord[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshHistory() {
    try {
      const result = await getPortfolioImportHistory();
      setHistory(result.items);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  useEffect(() => {
    void refreshHistory();
  }, []);

  async function inspectFile() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadPortfolio(file);
      setRecord(result);
      setInspection(result);
      setMapping(result.suggestions);
      setPreview(null);
      setStage("mapping");
      await refreshHistory();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function selectWorksheet(worksheet: string) {
    if (!record) return;
    setBusy(true);
    setError(null);
    try {
      const result = await getMapping(record.id, worksheet);
      setInspection(result);
      setMapping(result.suggestions);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function validateFile() {
    if (!record || !inspection) return;
    setBusy(true);
    setError(null);
    try {
      const result = await validatePortfolioMapping(record.id, inspection.worksheet, mapping);
      const previewResult = await getPreview(record.id);
      setRecord(result);
      setPreview(previewResult);
      setConfirmed(false);
      setStage("preview");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport() {
    if (!record || !confirmed) return;
    setBusy(true);
    setError(null);
    try {
      setRecord(await confirmPortfolioImport(record.id));
      setStage("complete");
      await refreshHistory();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelImport() {
    if (!record) return;
    setBusy(true);
    setError(null);
    try {
      await cancelPortfolioImport(record.id);
      setRecord(null);
      setInspection(null);
      setPreview(null);
      setStage("upload");
      await refreshHistory();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function downloadReport(id: number) {
    try {
      const blob = await downloadValidationReport(id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `portfolio-import-${id}-validation.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  return (
    <OpsLayout
      title="Import Portfolio"
      description="Bring in borrower and financial data from a customer-owned CSV or XLSX file. Review validation results before importing."
      icon={FileSpreadsheet}
    >
      <section className="space-y-5">
        <div className="flex flex-wrap items-center gap-3 border-b border-border pb-4 text-sm">
          {["Select file", "Map columns", "Review & confirm", "Results"].map((label, index) => {
            const active = index === ["upload", "mapping", "preview", "complete"].indexOf(stage);
            return (
              <div
                key={label}
                className={`flex items-center gap-2 ${active ? "font-semibold text-foreground" : "text-muted-foreground"}`}
              >
                <span
                  className={`grid size-6 place-items-center rounded-full border text-xs ${active ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}
                >
                  {index + 1}
                </span>
                {label}
              </div>
            );
          })}
        </div>

        {error && (
          <div
            role="alert"
            className="border-l-4 border-destructive bg-destructive/10 px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}

        {stage === "upload" && (
          <div className="max-w-3xl space-y-4">
            <label className="block text-sm font-medium" htmlFor="portfolio-file">
              Portfolio file
            </label>
            <input
              id="portfolio-file"
              type="file"
              accept=".csv,.xlsx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-md border border-border bg-background p-3 text-sm file:mr-4 file:rounded file:border-0 file:bg-muted file:px-3 file:py-2"
            />
            <p className="text-sm text-muted-foreground">
              CSV and XLSX are supported. The file is staged only for review and removed after
              import or cancellation.
            </p>
            <button
              type="button"
              onClick={() => void inspectFile()}
              disabled={!file || busy}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              <Upload size={16} aria-hidden="true" />
              {busy ? "Inspecting…" : "Upload and inspect"}
            </button>
          </div>
        )}

        {stage === "mapping" && record && inspection && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold">{record.filename}</h2>
                <p className="text-sm text-muted-foreground">
                  {record.total_rows} rows detected in {inspection.worksheets.length} worksheet(s)
                </p>
              </div>
              {inspection.worksheets.length > 1 && (
                <label className="text-sm">
                  Worksheet
                  <select
                    className="ml-2 rounded-md border border-border bg-background px-3 py-2"
                    value={inspection.worksheet}
                    onChange={(event) => void selectWorksheet(event.target.value)}
                    disabled={busy}
                  >
                    {inspection.worksheets.map((sheet) => (
                      <option key={sheet}>{sheet}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            <div className="overflow-x-auto border-y border-border">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-3">Source column</th>
                    <th className="px-3 py-3">Sample value</th>
                    <th className="px-3 py-3">Destination field</th>
                    <th className="px-3 py-3">Suggestion</th>
                  </tr>
                </thead>
                <tbody>
                  {inspection.headers.map((header) => (
                    <tr key={header} className="border-t border-border">
                      <td className="px-3 py-3 font-medium">{header}</td>
                      <td className="max-w-64 truncate px-3 py-3 text-muted-foreground">
                        {String(inspection.sample_rows[0]?.[header] ?? "")}
                      </td>
                      <td className="px-3 py-3">
                        <select
                          aria-label={`Map ${header}`}
                          className="w-full rounded-md border border-border bg-background px-2 py-2"
                          value={mapping[header] ?? ""}
                          onChange={(event) =>
                            setMapping((current) => ({
                              ...current,
                              [header]: event.target.value || null,
                            }))
                          }
                        >
                          <option value="">Ignore column</option>
                          {Object.entries(inspection.fields).map(([field, details]) => (
                            <option key={field} value={field}>
                              {details.label}
                              {details.required === "true" ? " *" : ""}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-3 text-muted-foreground">
                        {inspection.suggestions[header] ? "Header alias" : "No automatic match"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void validateFile()}
                disabled={busy || !Object.values(mapping).includes("company_name")}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
              >
                {busy ? "Validating…" : "Validate and preview"}
              </button>
              <button
                type="button"
                onClick={() => void cancelImport()}
                disabled={busy}
                className="rounded-md border border-border px-4 py-2 text-sm"
              >
                Cancel import
              </button>
            </div>
          </div>
        )}

        {stage === "preview" && record && preview && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4 border-y border-border py-4 md:grid-cols-4">
              <Summary label="Total rows" value={preview.total} />
              <Summary label="Valid rows" value={preview.valid_rows} />
              <Summary label="Invalid rows" value={preview.invalid_rows} />
              <Summary label="Warnings" value={preview.warning_count} />
            </div>
            <div className="overflow-x-auto border-y border-border">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-3">Row</th>
                    <th className="px-3 py-3">Company</th>
                    <th className="px-3 py-3">Industry</th>
                    <th className="px-3 py-3">Year</th>
                    <th className="px-3 py-3">Revenue</th>
                    <th className="px-3 py-3">Validation</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.items.map((row) => (
                    <tr key={row.row_number} className="border-t border-border">
                      <td className="px-3 py-3">{row.row_number}</td>
                      <td className="px-3 py-3">{String(row.canonical.company_name ?? "")}</td>
                      <td className="px-3 py-3">{String(row.canonical.industry ?? "")}</td>
                      <td className="px-3 py-3">{String(row.canonical.fiscal_year ?? "")}</td>
                      <td className="px-3 py-3">
                        {String(row.canonical.revenue ?? row.canonical.annual_revenue ?? "")}
                      </td>
                      <td
                        className={`px-3 py-3 ${row.valid ? "text-emerald-700" : "text-destructive"}`}
                      >
                        {row.valid ? "Ready" : "Rejected"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview.findings.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Validation findings</h3>
                {preview.findings.slice(0, 100).map((finding, index) => (
                  <p
                    key={`${finding.row_number}-${finding.code}-${index}`}
                    className={`text-sm ${finding.severity === "error" ? "text-destructive" : "text-muted-foreground"}`}
                  >
                    Row {finding.row_number}: {finding.message}
                  </p>
                ))}
              </div>
            )}
            <label className="flex max-w-3xl items-start gap-3 text-sm">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
                className="mt-1"
              />
              I reviewed the preview and authorize importing {preview.valid_rows} valid rows.
              Existing company identities will be skipped; no credit decision is made by this
              import.
            </label>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void confirmImport()}
                disabled={busy || !confirmed}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
              >
                {busy ? "Importing…" : "Confirm import"}
              </button>
              <button
                type="button"
                onClick={() => void cancelImport()}
                disabled={busy}
                className="rounded-md border border-border px-4 py-2 text-sm"
              >
                Cancel import
              </button>
              <button
                type="button"
                onClick={() => void downloadReport(record.id)}
                className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm"
              >
                <Download size={15} aria-hidden="true" />
                Validation report
              </button>
            </div>
          </div>
        )}

        {stage === "complete" && record && (
          <div
            role="status"
            className="max-w-3xl border-l-4 border-emerald-600 bg-emerald-50 px-4 py-4 text-sm text-emerald-950"
          >
            <h2 className="font-semibold">
              Import {record.status === "completed" ? "completed" : "completed with rejected rows"}
            </h2>
            <p className="mt-1">
              {record.imported_rows} companies imported; {record.skipped_rows} duplicate identities
              skipped; {record.failed_rows} rows rejected. No credit scores were generated.
            </p>
            <button
              type="button"
              className="mt-3 underline"
              onClick={() => {
                setRecord(null);
                setInspection(null);
                setPreview(null);
                setFile(null);
                setStage("upload");
              }}
            >
              Start another import
            </button>
          </div>
        )}
      </section>

      <section className="space-y-3 border-t border-border pt-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Import history</h2>
          <span className="text-sm text-muted-foreground">{history.length} recent imports</span>
        </div>
        {history.length === 0 ? (
          <p className="py-5 text-sm text-muted-foreground">No portfolio imports yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="border-y border-border bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-3">File</th>
                  <th className="px-3 py-3">Uploaded</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Rows</th>
                  <th className="px-3 py-3">Results</th>
                  <th className="px-3 py-3">Report</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id} className="border-b border-border">
                    <td className="px-3 py-3 font-medium">{item.filename}</td>
                    <td className="px-3 py-3">
                      {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-3 py-3">{item.status}</td>
                    <td className="px-3 py-3">{item.total_rows}</td>
                    <td className="px-3 py-3">
                      {item.imported_rows} imported · {item.failed_rows} rejected ·{" "}
                      {item.skipped_rows} skipped
                    </td>
                    <td className="px-3 py-3">
                      {item.findings || item.invalid_rows > 0 ? (
                        <button
                          type="button"
                          className="underline"
                          onClick={() => void downloadReport(item.id)}
                        >
                          Download CSV
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </OpsLayout>
  );
}

function Summary({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value.toLocaleString()}</p>
    </div>
  );
}
