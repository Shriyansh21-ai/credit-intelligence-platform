import { apiGet, apiPost } from "@/lib/http";

import type {
  Algorithm,
  DeploymentEvent,
  DriftReport,
  MLModel,
  MonitoringSummary,
  PerformanceRecord,
  PredictionLog,
  StressScenario,
  TrainingReport,
} from "./types";

// -- Training (M2) ----------------------------------------------------------
export const getAlgorithms = () =>
  apiGet<{ algorithms: Algorithm[] }>("/api/ml/training/algorithms");

export const trainModel = (body: {
  algorithm: string;
  dataset_seed?: number;
  n_rows?: number;
  tune?: boolean;
}) => apiPost<{ training_report: TrainingReport; model?: MLModel }>("/api/ml/training/train", body);

// -- Registry (M3) ----------------------------------------------------------
export const getModels = () => apiGet<{ models: MLModel[] }>("/api/ml/registry/models");
export const getModel = (id: number) => apiGet<MLModel>(`/api/ml/registry/models/${id}`);
export const getModelHistory = (id: number) =>
  apiGet<{ events: DeploymentEvent[] }>(`/api/ml/registry/models/${id}/history`);
export const submitModel = (id: number) =>
  apiPost<MLModel>(`/api/ml/registry/models/${id}/submit`, {});
export const approveModel = (id: number) =>
  apiPost<MLModel>(`/api/ml/registry/models/${id}/approve`, {});
export const promoteModel = (id: number) =>
  apiPost<MLModel>(`/api/ml/registry/models/${id}/promote`, {});
export const rollbackModel = (modelKey: string) =>
  apiPost<MLModel>(`/api/ml/registry/models/${modelKey}/rollback`, {});

// -- Serving (M4) / Monitoring (M6, M8) ------------------------------------
export const getServingHistory = (limit = 50) =>
  apiGet<{ predictions: PredictionLog[] }>(`/api/ml/serving/history?limit=${limit}`);
export const getMonitoringSummary = (modelId?: number) =>
  apiGet<MonitoringSummary>(
    `/api/ml/monitoring/summary${modelId ? `?model_id=${modelId}` : ""}`,
  );
export const getUsage = () =>
  apiGet<{ total_predictions: number; by_model: Record<string, number>; by_inference_type: Record<string, number> }>(
    "/api/ml/monitoring/usage",
  );
export const evaluatePerformance = (modelId: number) =>
  apiPost<PerformanceRecord>(`/api/ml/monitoring/performance/${modelId}/evaluate`, {});
export const getPerformanceTrend = (modelId: number) =>
  apiGet<{ trend: PerformanceRecord[] }>(`/api/ml/monitoring/performance/${modelId}/trend`);

// -- Drift (M7) -------------------------------------------------------------
export const getDriftHistory = (limit = 50) =>
  apiGet<{ reports: DriftReport[] }>(`/api/ml/drift/history?limit=${limit}`);

// -- Stress (M12) -----------------------------------------------------------
export const getStressScenarios = () =>
  apiGet<{ scenarios: StressScenario[] }>("/api/ml/stress-ml/scenarios");

// -- Feature store (M1) -----------------------------------------------------
export const getFeatureCatalog = () =>
  apiGet<{ feature_set_version: string; feature_count: number; categories: Record<string, Array<{ feature_name: string; category: string; description: string; unit: string }>> }>(
    "/api/ml/feature-store/catalog",
  );
