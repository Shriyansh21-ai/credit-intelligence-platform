/**
 * Wire types for the Financial Analysis Engine (Phase 3).
 *
 * These mirror the backend payload produced by
 * `services/financial_analysis/analysis_service.serialize_record` and the
 * `/analysis/*` routes.
 */

export type HealthStatus =
  | "excellent"
  | "good"
  | "moderate"
  | "weak"
  | "critical"
  | "unavailable";

export type Sentiment = "positive" | "neutral" | "negative";
export type Severity = "critical" | "high" | "medium" | "low";
export type Priority = "high" | "medium" | "low";
export type RatioUnit = "ratio" | "percent" | "currency" | "days";

export interface Period {
  label: string | null;
  period_type: string;
  fiscal_year: number | null;
}

export interface HealthScore {
  key: string;
  label: string;
  score: number | null;
  status: HealthStatus;
  summary: string;
}

export interface Ratio {
  key: string;
  label: string;
  category: string;
  unit: RatioUnit;
  value: number | null;
  formula: string;
  ideal_range: string;
  status: HealthStatus;
  interpretation: string;
}

export interface Insight {
  key: string;
  title: string;
  detail: string;
  category: string;
  sentiment: Sentiment;
}

export interface RiskFlag {
  code: string;
  title: string;
  severity: Severity;
  reason: string;
  recommendation: string;
}

export interface Recommendation {
  key: string;
  title: string;
  detail: string;
  priority: Priority;
  category: string;
}

export interface AnalysisResult {
  id?: number;
  assessment_id: number | null;
  version: number;
  created_at: string | null;
  period: Period;
  statement: Record<string, unknown>;
  overall_health: { label?: string; score: number | null; status: HealthStatus };
  health_scores: Record<string, HealthScore>;
  ratios: Ratio[];
  insights: Insight[];
  risk_flags: RiskFlag[];
  recommendations: Recommendation[];
  risk_flag_count: number;
  highest_severity: Severity | null;
  engine_version: string;
}

export interface TrendMetric {
  key: string;
  label: string;
  unit: RatioUnit;
  series: Array<{ period: string; value: number | null }>;
  changes: Array<{ from: string; to: string; change: number | null }>;
  cagr: number | null;
  direction: "improving" | "declining" | "stable" | "insufficient_data";
}

export interface Trends {
  period_count: number;
  periods: string[];
  sufficient_data: boolean;
  metrics: Record<string, TrendMetric>;
  summary: string;
}

/** Dimension order for radar/health displays. */
export const HEALTH_DIMENSIONS = [
  "liquidity",
  "profitability",
  "leverage",
  "efficiency",
  "cash_flow",
  "business_stability",
  "growth",
] as const;
