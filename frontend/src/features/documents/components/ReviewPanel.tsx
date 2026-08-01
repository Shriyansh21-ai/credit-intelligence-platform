import { useEffect, useMemo, useState } from "react";
import { Save } from "lucide-react";
import type { DocumentExtraction, ExtractedField } from "../types";
import { EditableFinancialForm } from "./EditableFinancialForm";
import { ValidationPanel } from "./ValidationPanel";

interface ReviewPanelProps {
  extraction: DocumentExtraction;
  saving: boolean;
  selectedKey: string | null;
  onSelectField: (key: string) => void;
  onSave: (fields: Record<string, string | number | null>) => void;
}

function toInputValue(field: ExtractedField): string {
  return field.value === null || field.value === undefined ? "" : String(field.value);
}

/** Editable review of the extracted fields with confidence cues + validation. */
export function ReviewPanel({ extraction, saving, selectedKey, onSelectField, onSave }: ReviewPanelProps) {
  const initial = useMemo(() => {
    const values: Record<string, string> = {};
    extraction.fields.forEach((f) => (values[f.key] = toInputValue(f)));
    return values;
  }, [extraction]);

  const [values, setValues] = useState<Record<string, string>>(initial);
  const [dirty, setDirty] = useState<Record<string, boolean>>({});

  // Re-sync when a new extraction version arrives (after save/extract).
  useEffect(() => {
    setValues(initial);
    setDirty({});
  }, [initial]);

  function handleChange(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
    setDirty((prev) => ({ ...prev, [key]: true }));
  }

  const hasChanges = Object.values(dirty).some(Boolean);

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
    onSave(payload);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Extracted Fields</h3>
          <p className="text-[11px] text-muted-foreground">
            Version {extraction.version} · {extraction.source ?? "—"} ·{" "}
            {extraction.overall_confidence != null ? `${Math.round(extraction.overall_confidence * 100)}% avg confidence` : "—"}
          </p>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <ValidationPanel issues={extraction.validation} />
        <EditableFinancialForm
          fields={extraction.fields}
          values={values}
          edited={dirty}
          selectedKey={selectedKey}
          onChange={handleChange}
          onSelect={onSelectField}
        />
      </div>
    </div>
  );
}
