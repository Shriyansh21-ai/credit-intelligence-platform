export type ReviewStatus =
  | "draft"
  | "in_review"
  | "pending_approval"
  | "approved"
  | "declined"
  | "deferred"
  | "returned_for_revision";

export type ReviewRecommendation =
  | "recommend_approval"
  | "recommend_approval_with_conditions"
  | "recommend_decline"
  | "request_information"
  | "escalate";

export type DecisionOutcome =
  | "approved"
  | "approved_with_conditions"
  | "declined"
  | "deferred"
  | "returned_for_revision";

export interface ReviewCaseSummary {
  id: number;
  reference: string;
  company_id: number;
  company_name: string | null;
  review_type: string;
  title: string;
  status: ReviewStatus;
  analyst_id: number;
  reviewer_id: number | null;
  due_date: string | null;
  reporting_periods: number[];
  updated_at: string | null;
}

export interface ReviewDashboard {
  counts: {
    draft: number;
    in_review: number;
    pending_approval: number;
    approved: number;
    declined: number;
    deferred_or_returned: number;
  };
  my_cases: ReviewCaseSummary[];
  approval_queue: ReviewCaseSummary[];
  can_create: boolean;
}

export interface ReviewCompany {
  id: number;
  name: string;
  industry: string;
  is_demo: boolean;
}

export interface ReviewAssessment {
  id: number;
  version: number;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  risk_indicators: string[];
  data_quality_concerns: string[];
  mitigations: string[];
  outstanding_questions: string[];
  evidence_refs: { financial_ids: number[]; document_ids: number[] };
  recommendation: ReviewRecommendation;
  recommendation_rationale: string;
  author_id: number;
  submitted_at: string | null;
  created_at: string | null;
}

export interface ReviewDecision {
  id: number;
  assessment_id: number;
  previous_decision_id: number | null;
  outcome: DecisionOutcome;
  cycle_number: number;
  rationale: string;
  conditions: Array<{
    description: string;
    responsible_user_id?: number | null;
    due_date?: string | null;
  }>;
  evidence_refs: { financial_ids: number[]; document_ids: number[] };
  reporting_periods: number[];
  policy_version: string | null;
  actor_id: number;
  created_at: string | null;
}

export interface ReviewCondition {
  id: number;
  decision_id: number;
  description: string;
  responsible_user_id: number | null;
  due_date: string | null;
  status: "open" | "completed" | "waived";
  completion_notes: string | null;
  created_by: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreditReviewDetail extends ReviewCaseSummary {
  tenant_id: number;
  company: {
    id: number;
    name: string;
    industry: string;
    sector: string | null;
    country: string | null;
    currency: string | null;
    is_demo: boolean;
    data_source: string;
  };
  purpose: string | null;
  cycle_number: number;
  created_by: number;
  revision: number;
  created_at: string | null;
  financials: Array<{
    id: number;
    fiscal_year: number;
    currency: string | null;
    unit: string;
    revenue: number | null;
    ebitda: number | null;
    ebit: number | null;
    net_income: number | null;
    total_assets: number | null;
    total_liabilities: number | null;
    equity: number | null;
    current_assets: number | null;
    current_liabilities: number | null;
    cash: number | null;
    debt: number | null;
    operating_cash_flow: number | null;
    free_cash_flow: number | null;
    approved: boolean;
    source_document_id: number;
    source_document_name: string;
  }>;
  risk_profile: {
    credit_score: number | null;
    risk_grade: string | null;
    current_ratio: number | null;
    quick_ratio: number | null;
    debt_to_equity: number | null;
    interest_coverage: number | null;
  } | null;
  exposure: {
    exposure: number | null;
    outstanding_amount: number | null;
    utilization: number | null;
    delinquency_days: number | null;
  } | null;
  portfolio_risk_evidence: {
    limits: Array<{
      id: number;
      scope: string;
      scope_key: string;
      currency: string;
      threshold: number;
      calculation_status: string;
      reason: string | null;
      eligible_exposure: number | null;
      utilization: number | null;
      remaining_headroom: number | null;
      status: string;
      breach: {
        status: string;
        observed_exposure: number;
        acknowledgement_reason: string | null;
      } | null;
    }>;
    covenants: Array<{
      id: number;
      name: string;
      metric_key: string;
      operator: string;
      threshold: number;
      unit: string;
      is_active: string;
      evaluations: Array<{
        fiscal_year: number | null;
        calculated_value: number | null;
        status: string;
        evidence_status: string;
        source_document_id: number | null;
        acknowledgement_reason: string | null;
      }>;
    }>;
    active_covenant_count: number;
  };
  missing_data_warnings: string[];
  assessments: ReviewAssessment[];
  decisions: ReviewDecision[];
  conditions: ReviewCondition[];
  condition_history: Array<{
    condition_id: number;
    actor_id: number;
    action: string;
    previous_value: Record<string, unknown> | null;
    new_value: Record<string, unknown>;
    reason: string | null;
    created_at: string | null;
  }>;
  history: Array<{
    action: string;
    actor_id: number | null;
    actor_email: string | null;
    previous_value: Record<string, unknown> | null;
    new_value: Record<string, unknown> | null;
    reason: string | null;
    timestamp: string | null;
  }>;
  actions: {
    can_assess: boolean;
    can_assign: boolean;
    can_submit_for_approval: boolean;
    can_decide: boolean;
    can_resume: boolean;
    can_reopen: boolean;
    can_manage_conditions: boolean;
  };
}

export interface ReviewFilters {
  status?: string;
  review_type?: string;
  company_id?: number;
  assigned_to?: "mine" | "all";
}
