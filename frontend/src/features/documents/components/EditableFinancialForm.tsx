import { Pencil } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ExtractedField } from "../types";
import { ConfidenceBadge } from "./Badges";

const confidenceBorder: Record<string, string> = {
  high: "border-l-success",
  medium: "border-l-warning",
  low: "border-l-destructive",
};

interface EditableFinancialFormProps {
  fields: ExtractedField[];
  values: Record<string, string>;
  edited: Record<string, boolean>;
  selectedKey: string | null;
  onChange: (key: string, value: string) => void;
  onSelect: (key: string) => void;
}

export function EditableFinancialForm({
  fields,
  values,
  edited,
  selectedKey,
  onChange,
  onSelect,
}: EditableFinancialFormProps) {
  if (fields.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border bg-secondary/20 px-4 py-6 text-center text-sm text-muted-foreground">
        No fields were extracted. Run extraction, or the document may not contain recognisable financial data.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {fields.map((field) => {
        const isEdited = edited[field.key] ?? field.edited;
        return (
          <div
            key={field.key}
            onClick={() => onSelect(field.key)}
            className={cn(
              "rounded-lg border border-l-2 bg-background p-3 transition-colors",
              confidenceBorder[field.confidence_level],
              selectedKey === field.key ? "border-ring ring-1 ring-ring/30" : "border-border",
            )}
          >
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <label htmlFor={`field-${field.key}`} className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                {field.label}
                {isEdited && <Pencil className="h-3 w-3 text-primary" aria-label="Edited" />}
              </label>
              <ConfidenceBadge level={field.confidence_level} score={field.confidence} />
            </div>
            <input
              id={`field-${field.key}`}
              type={field.type === "currency" ? "number" : "text"}
              inputMode={field.type === "currency" ? "decimal" : undefined}
              step={field.type === "currency" ? "any" : undefined}
              value={values[field.key] ?? ""}
              onFocus={() => onSelect(field.key)}
              onChange={(e) => onChange(field.key, e.target.value)}
              className="w-full rounded-md border border-border bg-card px-2.5 py-1.5 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
            />
          </div>
        );
      })}
    </div>
  );
}
