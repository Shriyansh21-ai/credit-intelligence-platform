/** Result types returned by POST /predict/enterprise-assessment. */

export type { EnterpriseAssessmentFormValues } from "./validation";

export interface HealthScore {
  score: number;
  label: string;
  rationale: string;
}

export interface HealthMetrics {
  liquidity_health: HealthScore;
  debt_health: HealthScore;
  working_capital_health: HealthScore;
  business_stability: HealthScore;
}

export interface PredictionSummary {
  enterprise_credit_score: number;
  risk_grade: string;
  probability_of_default: number;
  recommended_loan_amount: number;
  recommended_interest_rate: number;
}

export interface RiskMetrics {
  probability_of_default: number;
  loss_given_default: number;
  expected_loss: number;
}

export interface Recommendation {
  decision: string;
  loan_recommendation: string;
  interest_rate_recommendation: string;
  loan_tenure_recommendation: string;
  collateral_recommendation: string;
  monitoring: string;
}

export interface EnterpriseAssessmentResult {
  summary: PredictionSummary;
  risk_metrics: RiskMetrics;
  health_metrics: HealthMetrics;
  recommendation: Recommendation;
  key_ratios: Record<string, number>;
  narrative: string;

  // Backward-compatible flat fields (also returned by the API).
  enterprise_credit_score: number;
  probability_of_default: number;
  loss_given_default: number;
  expected_loss: number;
  risk_rating: string;
  ai_analysis: string;
  explanations: Record<string, number>;
}

export type HealthDimensionKey = keyof HealthMetrics;
