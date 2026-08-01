import { apiPost } from "@/lib/http";
import type { EnterpriseAssessmentFormValues } from "./validation";
import type { EnterpriseAssessmentResult } from "./types";

/**
 * Run an enterprise credit assessment.
 *
 * The form values already match the backend's sectioned request contract, so
 * they are posted as-is.
 */
export function runEnterpriseAssessment(
  values: EnterpriseAssessmentFormValues,
): Promise<EnterpriseAssessmentResult> {
  return apiPost<EnterpriseAssessmentResult>("/predict/enterprise-assessment", values);
}
