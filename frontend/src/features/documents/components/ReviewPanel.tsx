import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Save, XCircle } from "lucide-react";
import type { DocumentDetail, DocumentExtraction, ExtractedField } from "../types";
import type { DocumentCompany } from "../types";
import { getDocumentCompanies } from "../api";
import { EditableFinancialForm } from "./EditableFinancialForm";
import { ValidationPanel } from "./ValidationPanel";

interface ReviewPanelProps {
  document: DocumentDetail;
  extraction: DocumentExtraction;
  saving: boolean;
  selectedKey: string | null;
  onSelectField: (key: string) => void;
  onSave: (
    fields: Record<string, string | number | null>,
    metadata: { companyId?: number; fiscalYear?: number; currency?: string; unit: string },
  ) => void;
  onApprove: (acknowledgedWarnings: string[], replaceExisting: boolean) => void;
  onReject: (reason: string) => void;
}

function toInputValue(field: ExtractedField): string {
  return field.value === null || field.value === undefined ? "" : String(field.value);
}

/** Editable review of the extracted fields with confidence cues + validation. */
export function ReviewPanel({
  document,
  extraction,
  saving,
  selectedKey,
  onSelectField,
  onSave,
  onApprove,
  onReject,
}: ReviewPanelProps) {
  const initial = useMemo(() => {
    const values: Record<string, string> = {};
    extraction.fields.forEach((f) => (values[f.key] = toInputValue(f)));
    return values;
  }, [extraction]);

  const [values, setValues] = useState<Record<string, string>>(initial);
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<string[]>([]);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [companies, setCompanies] = useState<DocumentCompany[]>([]);
  const [companyId, setCompanyId] = useState(document.company_id?.toString() ?? "");
  const [fiscalYear, setFiscalYear] = useState(document.fiscal_year?.toString() ?? "");
  const [currency, setCurrency] = useState(document.currency ?? "");
  const [unit, setUnit] = useState(document.unit);
  const [companyError, setCompanyError] = useState<string | null>(null);

  // Re-sync when a new extraction version arrives (after save/extract).
  useEffect(() => {
    setValues(initial);
    setDirty({});
  }, [initial]);

  useEffect(() => {
    setCompanyId(document.company_id?.toString() ?? "");
    setFiscalYear(document.fiscal_year?.toString() ?? "");
    setCurrency(document.currency ?? "");
    setUnit(document.unit);
  }, [document.company_id, document.fiscal_year, document.currency, document.unit]);

  useEffect(() => {
    let cancelled = false;
    void getDocumentCompanies()
      .then((response) => {
        if (!cancelled) setCompanies(response.items);
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setCompanyError(error instanceof Error ? error.message : "Could not load companies");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleChange(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
    setDirty((prev) => ({ ...prev, [key]: true }));
  }

  const hasChanges = Object.values(dirty).some(Boolean);
  const warnings = extraction.validation.filter((issue) => issue.severity === "warning");

  function handleSave() {
    const typeByKey = new Map(extraction.fields.map((f) => [f.key, f.type]));
    const payload: Record<string, string | number | null> = {};
    for (const [key, isDirty] of Object.entries(dirty)) {
      if (!isDirty) continue;
      const raw = values[key];
      if (typeByKey.get(key) === "currency") {
        payload[key] = raw === "" ? null : Number(raw);
      } else {
        payload[key] = raw === "" ? null : raw;
      }
    }
    onSave(payload, {
      companyId: companyId ? Number(companyId) : undefined,
      fiscalYear: fiscalYear ? Number(fiscalYear) : undefined,
      currency: currency || undefined,
      unit,
    });
  }

  const canReview = ["needs_review", "extracted", "reviewed", "rejected"].includes(document.status);
  const canApprove = document.status === "reviewed";
  const canReject = ["needs_review", "extracted", "reviewed"].includes(document.status);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Extracted Fields</h3>
          <p className="text-[11px] text-muted-foreground">
            Version {extraction.version} · {extraction.source ?? "—"} ·{" "}
            {extraction.overall_confidence != null
              ? `${Math.round(extraction.overall_confidence * 100)}% avg confidence`
              : "—"}
          </p>
        </div>
        {canReview && (
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? "Saving…" : hasChanges ? "Save corrections" : "Mark reviewed"}
          </button>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {canReview && (
          <div className="grid gap-2 rounded-md bg-secondary/40 p-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Company
              <select
                value={companyId}
                onChange={(event) => setCompanyId(event.target.value)}
                className="rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              >
                <option value="">Select company</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Fiscal year
              <input
                type="number"
                min={1900}
                max={2200}
                value={fiscalYear}
                onChange={(event) => setFiscalYear(event.target.value)}
                className="rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Currency (ISO 4217)
              <input
                value={currency}
                maxLength={3}
                onChange={(event) => setCurrency(event.target.value.toUpperCase().slice(0, 3))}
                className="rounded-md border border-border bg-background px-2 py-1.5 text-sm uppercase text-foreground"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Statement unit
              <select
                value={unit}
                onChange={(event) => setUnit(event.target.value)}
                className="rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              >
                {["units", "thousands", "millions", "lakhs", "crores"].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            {companyError && (
              <p className="text-xs text-destructive sm:col-span-2">{companyError}</p>
            )}
          </div>
        )}
        {!canReview && (
          <p className="rounded-md bg-secondary/40 px-3 py-2 text-xs text-muted-foreground">
            Company: {document.company_id ?? "not selected"} · FY{document.fiscal_year ?? "—"} ·{" "}
            {document.currency ?? "currency not confirmed"} · {document.unit}
          </p>
        )}
        <ValidationPanel issues={extraction.validation} />
        <EditableFinancialForm
          fields={extraction.fields}
          values={values}
          edited={dirty}
          selectedKey={selectedKey}
          onChange={handleChange}
          onSelect={onSelectField}
        />
        {canApprove && (
          <div className="space-y-3 rounded-lg border border-border p-3">
            <h4 className="text-xs font-semibold text-foreground">Approval</h4>
            {warnings.map((warning) => (
              <label
                key={warning.message}
                className="flex items-start gap-2 text-xs text-muted-foreground"
              >
                <input
                  type="checkbox"
                  checked={acknowledgedWarnings.includes(warning.message)}
                  onChange={(event) =>
                    setAcknowledgedWarnings((current) =>
                      event.target.checked
                        ? [...current, warning.message]
                        : current.filter((message) => message !== warning.message),
                    )
                  }
                />
                Acknowledge: {warning.message}
              </label>
            ))}
            <label className="flex items-start gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={replaceExisting}
                onChange={(event) => setReplaceExisting(event.target.checked)}
              />
              Replace existing financials for this company and year (requires override permission).
            </label>
            <button
              type="button"
              disabled={saving || !companyId || !fiscalYear || !/^[A-Z]{3}$/.test(currency)}
              onClick={() => onApprove(acknowledgedWarnings, replaceExisting)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-success px-3 py-2 text-xs font-semibold text-success-foreground disabled:opacity-50"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> Approve and persist
            </button>
          </div>
        )}
        {canReject && (
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
            <label htmlFor="rejection-reason" className="text-xs font-semibold text-foreground">
              Rejection reason
            </label>
            <textarea
              id="rejection-reason"
              value={rejectionReason}
              onChange={(event) => setRejectionReason(event.target.value)}
              maxLength={1000}
              className="rounded-md border border-border bg-background px-2.5 py-2 text-sm text-foreground"
            />
            <button
              type="button"
              disabled={saving || !rejectionReason.trim()}
              onClick={() => onReject(rejectionReason.trim())}
              className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-destructive/40 px-3 py-2 text-xs font-semibold text-destructive disabled:opacity-50"
            >
              <XCircle className="h-3.5 w-3.5" /> Reject document
            </button>
          </div>
        )}
        {document.status === "approved" && (
          <p className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">
            Approved financial values are persisted for the linked reporting period.
          </p>
        )}
      </div>
    </div>
  );
}
