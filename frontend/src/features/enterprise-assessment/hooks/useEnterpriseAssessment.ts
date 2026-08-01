import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { runEnterpriseAssessment } from "../api";
import { DEFAULT_FORM_VALUES } from "../constants";
import { enterpriseAssessmentSchema, type EnterpriseAssessmentFormValues } from "../validation";
import type { EnterpriseAssessmentResult } from "../types";

/**
 * Encapsulates the enterprise assessment form state, validation and submission
 * so the page component stays presentational.
 */
export function useEnterpriseAssessment() {
  const form = useForm<EnterpriseAssessmentFormValues>({
    resolver: zodResolver(enterpriseAssessmentSchema),
    defaultValues: DEFAULT_FORM_VALUES,
    mode: "onBlur",
  });

  const [result, setResult] = useState<EnterpriseAssessmentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = form.handleSubmit(async (values) => {
    setLoading(true);
    setError(null);
    try {
      const response = await runEnterpriseAssessment(values);
      setResult(response);
      if (typeof window !== "undefined") {
        window.requestAnimationFrame(() =>
          document.getElementById("assessment-result")?.scrollIntoView({ behavior: "smooth", block: "start" }),
        );
      }
    } catch (err) {
      console.error("Enterprise assessment failed:", err);
      setError(err instanceof Error ? err.message : "Failed to run enterprise assessment.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  });

  return { form, result, loading, error, onSubmit };
}
