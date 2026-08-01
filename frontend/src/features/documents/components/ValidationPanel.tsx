import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import type { ValidationIssue } from "../types";

export function ValidationPanel({ issues }: { issues: ValidationIssue[] }) {
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  if (issues.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-success/30 bg-success/10 px-3 py-2.5 text-sm text-success">
        <CheckCircle2 className="h-4 w-4" /> All checks passed.
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {errors.map((issue, i) => (
        <div key={`e${i}`} className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{issue.message}</span>
        </div>
      ))}
      {warnings.map((issue, i) => (
        <div key={`w${i}`} className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{issue.message}</span>
        </div>
      ))}
    </div>
  );
}
