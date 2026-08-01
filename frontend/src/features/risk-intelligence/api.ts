import { apiGet, apiPost } from "@/lib/http";
import type {
  AlertScan,
  CreditMemo,
  Explanation,
  FeatureVector,
  ModelMeta,
  Portfolio,
  Prediction,
  ScenarioFactor,
  ScenarioResult,
  StressResult,
} from "./types";

export const listModels = () => apiGet<{ models: ModelMeta[] }>("/api/ml/models");

export const getLatestFeatures = () => apiGet<FeatureVector>("/api/ml/features");
export const getFeatures = (id: number) => apiGet<FeatureVector>(`/api/ml/features/${id}`);

export const getPrediction = (id: number) => apiGet<Prediction>(`/api/ml/predict/${id}`);
export const getExplanation = (id: number) => apiGet<Explanation>(`/api/ml/explain/${id}`);

export const getAssessmentAlerts = (id: number) =>
  apiGet<{ assessment_id: number; alerts: AlertScan["alerts"] }>(`/api/ml/alerts/${id}`);
export const getUserAlerts = () => apiGet<{ alerts: AlertScan["alerts"] }>("/api/ml/alerts");

export const getPortfolio = (filters?: { industry?: string; rating?: string; region?: string }) => {
  const q = new URLSearchParams();
  if (filters?.industry) q.set("industry", filters.industry);
  if (filters?.rating) q.set("rating", filters.rating);
  if (filters?.region) q.set("region", filters.region);
  const qs = q.toString();
  return apiGet<Portfolio>(`/api/ml/portfolio${qs ? `?${qs}` : ""}`);
};

export const getScenarioFactors = () =>
  apiGet<{ factors: ScenarioFactor[] }>("/api/ml/scenario/factors");

export const runScenario = (payload: {
  assessment_id: number;
  adjustments: Array<{ factor: string; value: number }>;
}) => apiPost<ScenarioResult>("/api/ml/scenario", payload);

export const getStressTest = (id: number) => apiGet<StressResult>(`/api/ml/stress-test/${id}`);

export const getReport = (id: number) => apiGet<CreditMemo>(`/api/ml/report/${id}`);
