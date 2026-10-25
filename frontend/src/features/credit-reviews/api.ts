import { apiGet, apiPatch, apiPost } from "@/lib/http";
import type {
  CreditReviewDetail,
  DecisionOutcome,
  ReviewCompany,
  ReviewDashboard,
  ReviewFilters,
  ReviewRecommendation,
  ReviewStatus,
} from "./types";

export function getReviewDashboard(): Promise<ReviewDashboard> {
  return apiGet<ReviewDashboard>("/api/credit-reviews/dashboard");
}

export function getReviewCompanies(): Promise<ReviewCompany[]> {
  return apiGet<ReviewCompany[]>("/api/credit-reviews/companies");
}

export function getReviewAssignmentCandidates(): Promise<
  Array<{
    id: number;
    name: string | null;
    email: string;
    can_be_analyst: boolean;
    can_be_reviewer: boolean;
  }>
> {
  return apiGet<
    Array<{
      id: number;
      name: string | null;
      email: string;
      can_be_analyst: boolean;
      can_be_reviewer: boolean;
    }>
  >("/api/credit-reviews/assignment-candidates");
}

export async function getReviewCases(filters: ReviewFilters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  const query = params.toString();
  return apiGet<{
    items: ReviewDashboard["my_cases"];
    total: number;
  }>(`/api/credit-reviews/cases${query ? `?${query}` : ""}`);
}

export function getReviewCase(caseId: number): Promise<CreditReviewDetail> {
  return apiGet<CreditReviewDetail>(`/api/credit-reviews/cases/${caseId}`);
}

export function createReviewCase(payload: {
  company_id: number;
  review_type: string;
  title: string;
  purpose?: string;
  due_date?: string;
}): Promise<CreditReviewDetail> {
  return apiPost<CreditReviewDetail>("/api/credit-reviews/cases", payload);
}

export function assignReviewCase(
  caseId: number,
  payload: { analyst_id: number; reviewer_id?: number | null },
): Promise<CreditReviewDetail> {
  return apiPatch<CreditReviewDetail>(`/api/credit-reviews/cases/${caseId}/assignment`, payload);
}

export function saveReviewAssessment(
  caseId: number,
  payload: {
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
    submit: boolean;
  },
): Promise<CreditReviewDetail> {
  return apiPost<CreditReviewDetail>(`/api/credit-reviews/cases/${caseId}/assessments`, payload);
}

export function submitReviewForApproval(caseId: number): Promise<CreditReviewDetail> {
  return apiPost<CreditReviewDetail>(`/api/credit-reviews/cases/${caseId}/submit-for-approval`, {});
}

export function decideReview(
  caseId: number,
  payload: {
    outcome: DecisionOutcome;
    rationale: string;
    conditions: Array<{ description: string }>;
  },
): Promise<CreditReviewDetail> {
  return apiPost<CreditReviewDetail>(`/api/credit-reviews/cases/${caseId}/decisions`, payload);
}

export function resumeReview(caseId: number, reason: string): Promise<CreditReviewDetail> {
  return apiPost<CreditReviewDetail>(`/api/credit-reviews/cases/${caseId}/resume`, { reason });
}

export function reopenReview(caseId: number, reason: string): Promise<CreditReviewDetail> {
  return apiPost<CreditReviewDetail>(`/api/credit-reviews/cases/${caseId}/reopen`, { reason });
}

export function updateReviewCondition(
  caseId: number,
  conditionId: number,
  payload: { status: "completed" | "waived"; notes: string },
): Promise<CreditReviewDetail> {
  return apiPatch<CreditReviewDetail>(
    `/api/credit-reviews/cases/${caseId}/conditions/${conditionId}`,
    payload,
  );
}

export type ReviewStatusFilter = ReviewStatus | "";
