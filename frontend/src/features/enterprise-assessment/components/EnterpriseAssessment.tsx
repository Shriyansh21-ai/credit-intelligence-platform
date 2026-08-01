import { useEnterpriseAssessment } from "../hooks/useEnterpriseAssessment";
import { AssessmentForm } from "./AssessmentForm";
import { AssessmentResult } from "./result/AssessmentResult";

/**
 * Orchestrates the full Enterprise Credit Assessment experience: a multi-section
 * input form followed by the prediction result. Kept presentational — all state
 * lives in `useEnterpriseAssessment`.
 */
export function EnterpriseAssessment() {
  const {
    form: {
      register,
      formState: { errors },
    },
    result,
    loading,
    error,
    onSubmit,
  } = useEnterpriseAssessment();

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Enterprise Credit Assessment</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Evaluate a business borrower across financial performance, banking conduct and risk exposure to produce a
          calibrated credit score, probability of default and lending recommendation.
        </p>
      </div>

      <AssessmentForm register={register} errors={errors} onSubmit={onSubmit} loading={loading} error={error} />

      {result && <AssessmentResult result={result} />}
    </div>
  );
}
