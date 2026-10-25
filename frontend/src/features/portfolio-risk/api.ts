import { apiGet, apiPatch, apiPost } from "@/lib/http";

export interface PortfolioRiskOverview {
  company_count: number;
  companies_with_exposure: number;
  exposure_by_currency: Array<{ currency: string; total_exposure: number }>;
  data_quality: {
    missing_or_invalid_exposure_records: number;
    exposure_records_without_currency: number;
  };
}

export interface ExposureLimit {
  id: number;
  scope: "portfolio" | "company" | "sector";
  scope_key: string;
  currency: string;
  threshold: number;
  approaching_ratio: number | null;
  is_active: boolean;
  calculation_status: "calculated" | "insufficient_data";
  reason: string | null;
  eligible_exposure: number | null;
  utilization: number | null;
  remaining_headroom: number | null;
  status: "within_limit" | "approaching" | "breached" | "insufficient_data" | "inactive";
  company_count: number;
  breach: {
    id: number;
    status: "open" | "acknowledged" | "resolved";
    observed_exposure: number;
    acknowledgement_reason: string | null;
  } | null;
}

export interface PortfolioRiskCompany {
  id: number;
  name: string;
  sector: string | null;
  currency: string | null;
  is_demo: boolean;
}

export interface CompanyCovenant {
  id: number;
  company_id: number;
  metric_key: string;
  name: string;
  operator: "min" | "max";
  threshold: number;
  unit: string;
  effective_date: string | null;
  review_frequency_months: number | null;
  is_active: string;
  evaluations: Array<{
    id: number;
    financial_record_id: number | null;
    source_document_id: number | null;
    source_document_extraction_id: number | null;
    fiscal_year: number | null;
    calculated_value: number | null;
    threshold: number;
    status: "compliant" | "breached" | "insufficient_data" | "not_yet_due" | "inactive";
    evidence_status: string;
    acknowledged_at: string | null;
    acknowledgement_reason: string | null;
    created_at: string;
  }>;
}

export const getPortfolioRiskOverview = () =>
  apiGet<PortfolioRiskOverview>("/api/portfolio-risk/overview");

export const getPortfolioRiskCompanies = () =>
  apiGet<{ companies: PortfolioRiskCompany[] }>("/api/portfolio-risk/companies?limit=200");

export const getExposureLimits = () =>
  apiGet<{ limits: ExposureLimit[]; can_manage: boolean }>("/api/portfolio-risk/limits");

export const createExposureLimit = (payload: {
  scope: "portfolio" | "company" | "sector";
  company_id?: number;
  sector?: string;
  currency: string;
  threshold: number;
  approaching_ratio?: number;
}) => apiPost<ExposureLimit>("/api/portfolio-risk/limits", payload);

export const updateExposureLimit = (
  id: number,
  payload: {
    threshold?: number;
    approaching_ratio?: number;
    clear_approaching_ratio?: boolean;
    is_active?: boolean;
    reason: string;
  },
) => apiPatch<ExposureLimit>(`/api/portfolio-risk/limits/${id}`, payload);

export const evaluateExposureLimits = () =>
  apiPost<{ results: Array<{ limit_id: number; status: string }> }>(
    "/api/portfolio-risk/limits/evaluate",
    {},
  );

export const acknowledgeExposureBreach = (id: number, reason: string) =>
  apiPost(`/api/portfolio-risk/breaches/${id}/acknowledge`, { reason });

export const getCompanyCovenants = (companyId: number) =>
  apiGet<{ covenants: CompanyCovenant[]; can_manage: boolean }>(
    `/api/portfolio-risk/companies/${companyId}/covenants`,
  );

export const createCompanyCovenant = (
  companyId: number,
  payload: {
    metric_key: "current_ratio_min" | "debt_to_equity_max" | "debt_to_ebitda_max";
    name: string;
    threshold: number;
    review_frequency_months?: number;
  },
) => apiPost(`/api/portfolio-risk/companies/${companyId}/covenants`, payload);

export const evaluateCompanyCovenant = (id: number) =>
  apiPost(`/api/portfolio-risk/covenants/${id}/evaluate`, {});

export const acknowledgeCovenantEvaluation = (id: number, reason: string) =>
  apiPost(`/api/portfolio-risk/covenant-evaluations/${id}/acknowledge`, { reason });
