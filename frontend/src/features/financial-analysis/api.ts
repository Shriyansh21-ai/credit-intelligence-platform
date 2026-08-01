import { apiGet, apiPost } from "@/lib/http";
import type { AnalysisResult, Trends } from "./types";

/** The user's most recent financial analysis (default dashboard view). */
export function getLatestAnalysis(): Promise<AnalysisResult> {
  return apiGet<AnalysisResult>("/analysis/latest");
}

/** Full analysis for a specific assessment. */
export function getAnalysis(assessmentId: number): Promise<AnalysisResult> {
  return apiGet<AnalysisResult>(`/analysis/${assessmentId}`);
}

/** Multi-period trends across the user's analysed periods. */
export function getTrends(): Promise<Trends> {
  return apiGet<Trends>("/analysis/trends");
}

/** Compute an ad-hoc analysis from raw financials (optionally persisted). */
export function computeAnalysis(payload: {
  financials?: Record<string, number>;
  document_fields?: Array<Record<string, unknown>>;
  context?: Record<string, unknown>;
  assessment_id?: number;
  persist?: boolean;
}): Promise<AnalysisResult> {
  return apiPost<AnalysisResult>("/analysis/compute", payload);
}
