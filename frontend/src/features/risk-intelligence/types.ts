/** Types for the Enterprise AI Risk Intelligence layer (Phase 4). */

export interface ModelMeta {
  model_type: string;
  algorithm: string;
  trained: boolean;
  backend_available: boolean;
  inference_mode: string;
  is_default?: boolean;
  description: string;
}

export interface Feature {
  feature_name: string;
  category: string;
  description: string;
  value: number | null;
  unit: string;
  source: string;
  confidence: number;
}

export interface FeatureVector {
  id?: number;
  assessment_id?: number | null;
  feature_set_version: string;
  feature_count: number;
  populated_count: number;
  low_confidence_count: number;
  coverage: number;
  features: Feature[];
  features_by_category: Record<string, Feature[]>;
  category_summary: Record<string, { count: number; populated: number; mean_confidence: number }>;
}

export interface Prediction {
  model_type: string;
  probability_of_default: number;
  risk_score: number;
  risk_grade: string;
  approval: boolean;
  inference_mode: string;
  contributions: Record<string, number>;
  model_metadata: ModelMeta;
  feature_importance: Record<string, number>;
}

export interface Contribution {
  feature: string;
  label: string;
  value: number | null;
  unit: string;
  contribution: number;
  impact_pp: number;
  direction: "increases_risk" | "reduces_risk" | "neutral";
  narrative: string;
}

export interface WaterfallStep {
  label: string;
  impact_pp: number;
  cumulative_pd: number;
}

export interface Explanation {
  model_type: string;
  method: string;
  probability_of_default: number;
  base_probability: number;
  risk_score: number;
  risk_grade: string;
  summary: string;
  contributions: Contribution[];
  top_positive_contributors: Contribution[];
  top_negative_contributors: Contribution[];
  waterfall: WaterfallStep[];
  global_importance: Array<{ feature: string; label: string; importance: number }>;
}

export interface Alert {
  alert_type: string;
  category: string;
  severity: "critical" | "high" | "medium" | "low";
  priority: number;
  title: string;
  business_impact: string;
  suggested_action: string;
  timeline: string;
  evidence: Record<string, unknown>;
}

export interface AlertScan {
  alerts: Alert[];
  alert_count: number;
  highest_severity: string | null;
  by_severity: Record<string, number>;
}

export interface DistributionRow {
  key: string;
  client_count: number;
  exposure: number;
  exposure_share: number;
  expected_loss: number;
  average_pd: number;
}

export interface Portfolio {
  summary: {
    client_count: number;
    total_exposure: number;
    expected_loss: number;
    unexpected_loss: number;
    expected_loss_rate: number;
    portfolio_default_probability: number;
    weighted_average_score: number;
    portfolio_health: { score: number; status: string };
  };
  distributions: {
    by_industry: DistributionRow[];
    by_rating: DistributionRow[];
    by_region: DistributionRow[];
  };
  concentration: {
    industry_hhi: number;
    region_hhi: number;
    rating_hhi: number;
    top_industry_share: number;
    assessment: string;
  };
  top_risk_clients: Array<{
    client_id: number;
    company_name: string;
    industry: string;
    region: string;
    rating: string;
    score: number;
    probability_of_default: number;
    exposure: number;
    expected_loss: number;
  }>;
}

export interface ScenarioFactor {
  factor: string;
  label: string;
  description: string;
  value_unit: string;
}

export interface Snapshot {
  enterprise_credit_score: number;
  risk_grade: string;
  probability_of_default: number;
  loss_given_default: number;
  expected_loss: number;
  recommended_loan_amount: number;
  recommended_interest_rate: number;
  decision: string;
  health_scores: Record<string, number | null>;
  ml_probability_of_default: number;
}

export interface ScenarioResult {
  adjustments: Array<{ factor: string; value: number }>;
  baseline: Snapshot;
  scenario: Snapshot;
  delta: Record<string, number | boolean | Record<string, number>>;
}

export interface StressCase {
  snapshot: Snapshot;
  delta: Record<string, number | boolean | Record<string, number>>;
}

export interface StressResult {
  base_case: StressCase;
  optimistic_case: StressCase;
  expected_case: StressCase;
  worst_case: StressCase;
  scenarios: Array<{ name: string; label: string; description: string; cases: Record<string, StressCase> }>;
  comparison: {
    by_case: Record<string, Array<{ case: string; value: number | string | Record<string, number | null> }>>;
    by_scenario: Array<{
      scenario: string;
      label: string;
      worst_probability_of_default: number;
      worst_expected_loss: number;
      worst_score: number;
      score_impact: number;
    }>;
  };
}

export interface CreditMemo {
  report_type: string;
  executive_summary: string;
  business_overview: Record<string, string | number | null>;
  financial_summary: Record<string, unknown>;
  credit_strengths: string[];
  weaknesses: string[];
  business_risks: RiskItem[];
  industry_risks: RiskItem[];
  financial_risks: RiskItem[];
  management_risks: RiskItem[];
  recommendation: {
    decision: string;
    recommended_loan_amount: number;
    recommended_interest_rate: string;
    recommended_tenure: string;
    collateral: string;
    monitoring_frequency: string;
    loan_recommendation: string;
  };
  alerts_summary: { alert_count: number; highest_severity: string | null; by_severity: Record<string, number> };
  analyst_notes: string[];
  final_recommendation: string;
}

export interface RiskItem {
  title: string;
  severity: string;
  impact: string;
  action: string;
}
