import type { EnterpriseAssessmentFormValues } from "./validation";

export interface SelectOption {
  value: string;
  label: string;
}

export const INDUSTRY_OPTIONS: SelectOption[] = [
  { value: "Manufacturing", label: "Manufacturing" },
  { value: "Retail", label: "Retail & Trade" },
  { value: "Technology", label: "Technology / Software" },
  { value: "Services", label: "Professional Services" },
  { value: "Construction", label: "Construction & Real Estate" },
  { value: "Healthcare", label: "Healthcare & Pharma" },
  { value: "Logistics", label: "Logistics & Transport" },
  { value: "Agriculture", label: "Agriculture & Agri-business" },
  { value: "Hospitality", label: "Hospitality & Tourism" },
  { value: "Other", label: "Other" },
];

export const BUSINESS_TYPE_OPTIONS: SelectOption[] = [
  { value: "Private Limited", label: "Private Limited" },
  { value: "Public Limited", label: "Public Limited" },
  { value: "Partnership", label: "Partnership" },
  { value: "LLP", label: "Limited Liability Partnership" },
  { value: "Proprietorship", label: "Sole Proprietorship" },
  { value: "Other", label: "Other" },
];

export const RISK_BAND_OPTIONS: SelectOption[] = [
  { value: "low", label: "Low" },
  { value: "moderate", label: "Moderate" },
  { value: "high", label: "High" },
];

export const CONCENTRATION_OPTIONS: SelectOption[] = [
  { value: "diversified", label: "Diversified" },
  { value: "balanced", label: "Balanced" },
  { value: "concentrated", label: "Concentrated" },
];

export const COMPLIANCE_OPTIONS: SelectOption[] = [
  { value: "compliant", label: "Compliant" },
  { value: "partial", label: "Partially compliant" },
  { value: "non_compliant", label: "Non-compliant" },
];

export const EXPANSION_STAGE_OPTIONS: SelectOption[] = [
  { value: "startup", label: "Startup" },
  { value: "growth", label: "Growth" },
  { value: "expansion", label: "Expansion" },
  { value: "mature", label: "Mature" },
  { value: "decline", label: "Decline / Turnaround" },
];

export const PRIOR_DEFAULTS_OPTIONS: SelectOption[] = [
  { value: "none", label: "No prior defaults" },
  { value: "present", label: "Has prior defaults" },
];

/** A realistic mid-market company used as the form's starting point. */
export const DEFAULT_FORM_VALUES: EnterpriseAssessmentFormValues = {
  business_profile: {
    company_name: "Meridian Industrial Pvt Ltd",
    industry: "Manufacturing",
    business_type: "Private Limited",
    years_in_business: 9,
    employee_count: 140,
    head_office: "Pune",
    country: "India",
    registration_number: "",
    gst_number: "",
    website: "",
  },
  financials: {
    annual_revenue: 24000000,
    gross_profit: 8400000,
    net_profit: 2600000,
    ebitda: 3800000,
    operating_expenses: 4600000,
    cash_and_cash_equivalents: 4200000,
    working_capital: 4800000,
    current_assets: 9200000,
    current_liabilities: 4400000,
    inventory: 2100000,
    accounts_receivable: 3100000,
    accounts_payable: 1800000,
    long_term_debt: 3200000,
    short_term_debt: 900000,
    operating_cash_flow: 3300000,
    interest_expense: 320000,
    free_cash_flow: 1900000,
    net_worth: 9600000,
  },
  banking: {
    average_monthly_balance: 2100000,
    average_monthly_inflow: 2400000,
    average_monthly_outflow: 2050000,
    existing_loans: 2,
    existing_emi: 90000,
    credit_utilization: 34,
    tax_compliance: "compliant",
    gst_compliance: "compliant",
    cheque_bounce_count: 0,
    previous_defaults: "none",
  },
  risk_profile: {
    industry_risk: "moderate",
    geographical_risk: "low",
    supplier_concentration: "balanced",
    customer_concentration: "balanced",
    business_expansion_stage: "growth",
  },
};
