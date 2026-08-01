import { useEffect, useState } from "react";

import { getAnalysis, getLatestAnalysis, getTrends } from "../api";
import type { AnalysisResult, Trends } from "../types";

interface State {
  analysis: AnalysisResult | null;
  trends: Trends | null;
  loading: boolean;
  error: string | null;
}

/**
 * Loads the financial analysis for a given assessment (or the user's latest
 * when no id is provided) plus the multi-period trend series.
 */
export function useFinancialAnalysis(assessmentId?: number): State {
  const [state, setState] = useState<State>({
    analysis: null,
    trends: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));

    const analysisPromise = assessmentId
      ? getAnalysis(assessmentId)
      : getLatestAnalysis();

    Promise.all([
      analysisPromise,
      // Trends are best-effort — a failure here shouldn't blank the page.
      getTrends().catch(() => null),
    ])
      .then(([analysis, trends]) => {
        if (cancelled) return;
        setState({ analysis, trends, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          analysis: null,
          trends: null,
          loading: false,
          error: err instanceof Error ? err.message : "Failed to load analysis",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [assessmentId]);

  return state;
}
