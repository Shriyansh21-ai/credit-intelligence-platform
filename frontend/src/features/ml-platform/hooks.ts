import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const KEY = "ml-platform";

export const useAlgorithms = () =>
  useQuery({ queryKey: [KEY, "algorithms"], queryFn: api.getAlgorithms });

export const useModels = () =>
  useQuery({ queryKey: [KEY, "models"], queryFn: api.getModels });

export const useModel = (id: number | null) =>
  useQuery({ queryKey: [KEY, "model", id], queryFn: () => api.getModel(id as number), enabled: id != null });

export const useServingHistory = (limit = 50) =>
  useQuery({ queryKey: [KEY, "serving-history", limit], queryFn: () => api.getServingHistory(limit) });

export const useMonitoringSummary = (modelId?: number) =>
  useQuery({ queryKey: [KEY, "monitoring", modelId ?? "all"], queryFn: () => api.getMonitoringSummary(modelId) });

export const useUsage = () =>
  useQuery({ queryKey: [KEY, "usage"], queryFn: api.getUsage });

export const useDriftHistory = (limit = 50) =>
  useQuery({ queryKey: [KEY, "drift", limit], queryFn: () => api.getDriftHistory(limit) });

export const usePerformanceTrend = (modelId: number | null) =>
  useQuery({
    queryKey: [KEY, "performance", modelId],
    queryFn: () => api.getPerformanceTrend(modelId as number),
    enabled: modelId != null,
  });

export const useStressScenarios = () =>
  useQuery({ queryKey: [KEY, "stress-scenarios"], queryFn: api.getStressScenarios });

export const useFeatureCatalog = () =>
  useQuery({ queryKey: [KEY, "feature-catalog"], queryFn: api.getFeatureCatalog });

// -- Mutations --------------------------------------------------------------
function useInvalidatingMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  });
}

export const useTrainModel = () => useInvalidatingMutation(api.trainModel);
export const useSubmitModel = () => useInvalidatingMutation(api.submitModel);
export const useApproveModel = () => useInvalidatingMutation(api.approveModel);
export const usePromoteModel = () => useInvalidatingMutation(api.promoteModel);
export const useRollbackModel = () => useInvalidatingMutation(api.rollbackModel);
export const useEvaluatePerformance = () => useInvalidatingMutation(api.evaluatePerformance);
