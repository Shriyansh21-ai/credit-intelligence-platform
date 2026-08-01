/** Types for the Phase 6 Enterprise ML Platform dashboards. */

export interface Algorithm {
  algorithm: string;
  backend_available: boolean;
  default_hyperparameters: Record<string, unknown>;
}

export interface MLModel {
  id: number;
  model_key: string;
  name: string;
  algorithm: string;
  version: number;
  is_current: boolean;
  dataset_id: number | null;
  parent_model_id: number | null;
  hyperparameters: Record<string, unknown>;
  metrics: ModelMetrics;
  feature_set_version: string;
  feature_count: number;
  training_time_seconds: number | null;
  author: string | null;
  approval_status: string;
  production_status: string;
  trained_at: string | null;
  created_at: string | null;
  report?: TrainingReport;
  feature_names?: string[];
}

export interface ModelMetrics {
  roc_auc?: number;
  ks_statistic?: number;
  gini?: number;
  brier_score?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  [k: string]: number | Record<string, number> | unknown;
}

export interface TrainingReport {
  algorithm: string;
  metrics: ModelMetrics;
  cross_validation: { scoring: string; scores: number[]; mean: number; std: number };
  feature_importances: Record<string, number>;
  dataset: { name: string; n_rows: number; positive_rate: number; content_hash: string };
  training_time_seconds: number;
  n_train: number;
  n_test: number;
}

export interface DeploymentEvent {
  id: number;
  action: string;
  from_status: string | null;
  to_status: string | null;
  actor: string | null;
  note: string | null;
  created_at: string | null;
}

export interface PredictionLog {
  id: number;
  model_key: string | null;
  model_version: number | null;
  inference_type: string;
  entity_id: number | null;
  probability_of_default: number | null;
  risk_score: number | null;
  risk_grade: string | null;
  approval: boolean | null;
  inference_mode: string | null;
  latency_ms: number | null;
  cached: boolean;
  success: boolean;
  created_at: string | null;
}

export interface MonitoringSummary {
  prediction_volume: { total: number; success: number; failed: number; cached: number; by_type: Record<string, number> };
  success_rate: number | null;
  failure_rate: number | null;
  latency_ms: { count: number; avg: number | null; p50: number | null; p95: number | null; p99: number | null; max: number | null };
  model_confidence: { avg: number | null; low_confidence_share: number | null };
  pd_distribution: { avg: number | null; p50: number | null; p95: number | null };
  class_distribution: { approved: number; declined: number; approval_rate: number | null; grade_distribution: Record<string, number> };
  data_quality: { populated_rate: number | null; missing_rate: number | null };
}

export interface DriftReport {
  id: number;
  model_id: number | null;
  model_key: string | null;
  report_type: string;
  psi_overall: number | null;
  drift_score: number | null;
  n_features: number | null;
  n_drifted: number | null;
  missing_feature_rate: number | null;
  drifted_features: string[];
  threshold: number | null;
  breached: boolean;
  created_at: string | null;
}

export interface PerformanceRecord {
  id: number;
  evaluated_at: string | null;
  n_samples: number;
  metrics: ModelMetrics;
  business_kpis: Record<string, number>;
  note: string | null;
}

export interface StressScenario {
  name: string;
  label: string;
  description: string;
}
