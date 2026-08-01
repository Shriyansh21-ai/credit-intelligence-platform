import { AlertCircle, Loader2, Sparkles } from "lucide-react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";
import type { FormEventHandler } from "react";
import { BusinessProfileSection } from "./sections/BusinessProfileSection";
import { FinancialSection } from "./sections/FinancialSection";
import { BankingSection } from "./sections/BankingSection";
import { RiskSection } from "./sections/RiskSection";
import type { EnterpriseAssessmentFormValues } from "../validation";

interface AssessmentFormProps {
  register: UseFormRegister<EnterpriseAssessmentFormValues>;
  errors: FieldErrors<EnterpriseAssessmentFormValues>;
  onSubmit: FormEventHandler<HTMLFormElement>;
  loading: boolean;
  error: string | null;
}

export function AssessmentForm({ register, errors, onSubmit, loading, error }: AssessmentFormProps) {
  const hasErrors = Object.keys(errors).length > 0;

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <BusinessProfileSection register={register} errors={errors} />
      <FinancialSection register={register} errors={errors} />
      <BankingSection register={register} errors={errors} />
      <RiskSection register={register} errors={errors} />

      {(error || hasErrors) && (
        <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error ?? "Please correct the highlighted fields before running the assessment."}</span>
        </div>
      )}

      <div className="flex items-center justify-end gap-3">
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-gradient-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Running assessment…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" /> Run Enterprise Assessment
            </>
          )}
        </button>
      </div>
    </form>
  );
}
