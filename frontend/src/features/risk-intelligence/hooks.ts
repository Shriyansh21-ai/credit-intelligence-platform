import { useQuery } from "@tanstack/react-query";

import * as api from "./api";

/** Resolves the active assessment id: the explicit one, else the user's latest. */
export function useAssessmentId(explicit?: number) {
  const latest = useQuery({
    queryKey: ["ri", "latest-features"],
    queryFn: api.getLatestFeatures,
    enabled: explicit === undefined,
    retry: false,
  });
  const resolved = explicit ?? latest.data?.assessment_id ?? undefined;
  return {
    assessmentId: resolved ?? undefined,
    loading: explicit === undefined && latest.isLoading,
    error: explicit === undefined && latest.isError
      ? (latest.error as Error)?.message ?? "No assessment found"
      : null,
  };
}

export const useModels = () =>
  useQuery({ queryKey: ["ri", "models"], queryFn: api.listModels });

export const useFeatures = (id?: number) =>
  useQuery({
    queryKey: ["ri", "features", id],
    queryFn: () => api.getFeatures(id as number),
    enabled: typeof id === "number",
  });

export const usePrediction = (id?: number) =>
  useQuery({
    queryKey: ["ri", "predict", id],
    queryFn: () => api.getPrediction(id as number),
    enabled: typeof id === "number",
  });

export const useExplanation = (id?: number) =>
  useQuery({
    queryKey: ["ri", "explain", id],
    queryFn: () => api.getExplanation(id as number),
    enabled: typeof id === "number",
  });

export const useAssessmentAlerts = (id?: number) =>
  useQuery({
    queryKey: ["ri", "alerts", id],
    queryFn: () => api.getAssessmentAlerts(id as number),
    enabled: typeof id === "number",
  });

export const useUserAlerts = () =>
  useQuery({ queryKey: ["ri", "user-alerts"], queryFn: api.getUserAlerts });

export const usePortfolio = (filters?: { industry?: string; rating?: string; region?: string }) =>
  useQuery({
    queryKey: ["ri", "portfolio", filters],
    queryFn: () => api.getPortfolio(filters),
  });

export const useScenarioFactors = () =>
  useQuery({ queryKey: ["ri", "scenario-factors"], queryFn: api.getScenarioFactors });

export const useStressTest = (id?: number) =>
  useQuery({
    queryKey: ["ri", "stress", id],
    queryFn: () => api.getStressTest(id as number),
    enabled: typeof id === "number",
  });

export const useReport = (id?: number) =>
  useQuery({
    queryKey: ["ri", "report", id],
    queryFn: () => api.getReport(id as number),
    enabled: typeof id === "number",
  });
