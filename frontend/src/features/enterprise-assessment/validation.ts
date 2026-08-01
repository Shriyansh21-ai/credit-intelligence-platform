import { z } from "zod";

/**
 * Validation schema for the Enterprise Credit Assessment form.
 *
 * Mirrors the backend Pydantic contract (schemas/enterprise.py):
 *   - monetary values that cannot be negative use `.min(0)`
 *   - percentages are bounded to 0..100
 *   - business age is capped to a realistic range
 *
 * The inferred `EnterpriseAssessmentFormValues` type is the single source of
 * truth for the form and API payload shape.
 */

const nonNegativeMoney = (label: string) =>
  z.coerce.number({ invalid_type_error: `${label} must be a number` }).min(0, `${label} cannot be negative`);

const signedMoney = (label: string) =>
  z.coerce.number({ invalid_type_error: `${label} must be a number` });

const optionalText = z.string().trim().max(200).optional().or(z.literal(""));

export const riskBandSchema = z.enum(["low", "moderate", "high"]);
export const concentrationSchema = z.enum(["diversified", "balanced", "concentrated"]);
export const complianceSchema = z.enum(["compliant", "partial", "non_compliant"]);
export const expansionStageSchema = z.enum(["startup", "growth", "mature", "expansion", "decline"]);
export const priorDefaultsSchema = z.enum(["none", "present"]);

export const businessProfileSchema = z.object({
  company_name: z.string().trim().min(1, "Company name is required").max(200),
  industry: z.string().trim().min(1, "Industry is required"),
  business_type: z.string().trim().min(1, "Business type is required"),
  years_in_business: z.coerce
    .number({ invalid_type_error: "Enter a number" })
    .int("Must be a whole number")
    .min(0, "Cannot be negative")
    .max(200, "Enter a realistic number of years"),
  employee_count: z.coerce
    .number({ invalid_type_error: "Enter a number" })
    .int("Must be a whole number")
    .min(1, "At least 1 employee"),
  head_office: z.string().trim().min(1, "Head office is required"),
  country: z.string().trim().min(1, "Country is required"),
  registration_number: optionalText,
  gst_number: optionalText,
  website: optionalText,
});

export const financialInformationSchema = z.object({
  annual_revenue: nonNegativeMoney("Annual revenue"),
  gross_profit: signedMoney("Gross profit"),
  net_profit: signedMoney("Net profit"),
  ebitda: signedMoney("EBITDA"),
  operating_expenses: nonNegativeMoney("Operating expenses"),
  cash_and_cash_equivalents: nonNegativeMoney("Cash"),
  working_capital: signedMoney("Working capital"),
  current_assets: nonNegativeMoney("Current assets"),
  current_liabilities: nonNegativeMoney("Current liabilities"),
  inventory: nonNegativeMoney("Inventory"),
  accounts_receivable: nonNegativeMoney("Accounts receivable"),
  accounts_payable: nonNegativeMoney("Accounts payable"),
  long_term_debt: nonNegativeMoney("Long-term debt"),
  short_term_debt: nonNegativeMoney("Short-term debt"),
  operating_cash_flow: signedMoney("Operating cash flow"),
  interest_expense: nonNegativeMoney("Interest expense"),
  free_cash_flow: signedMoney("Free cash flow"),
  net_worth: signedMoney("Net worth"),
});

export const bankingInformationSchema = z.object({
  average_monthly_balance: nonNegativeMoney("Average monthly balance"),
  average_monthly_inflow: nonNegativeMoney("Average monthly inflow"),
  average_monthly_outflow: nonNegativeMoney("Average monthly outflow"),
  existing_loans: z.coerce.number().int("Must be a whole number").min(0, "Cannot be negative"),
  existing_emi: nonNegativeMoney("Existing EMI"),
  credit_utilization: z.coerce
    .number({ invalid_type_error: "Enter a number" })
    .min(0, "Min 0%")
    .max(100, "Max 100%"),
  tax_compliance: complianceSchema,
  gst_compliance: complianceSchema,
  cheque_bounce_count: z.coerce.number().int("Must be a whole number").min(0, "Cannot be negative"),
  previous_defaults: priorDefaultsSchema,
});

export const businessRiskSchema = z.object({
  industry_risk: riskBandSchema,
  geographical_risk: riskBandSchema,
  supplier_concentration: concentrationSchema,
  customer_concentration: concentrationSchema,
  business_expansion_stage: expansionStageSchema,
});

export const enterpriseAssessmentSchema = z.object({
  business_profile: businessProfileSchema,
  financials: financialInformationSchema,
  banking: bankingInformationSchema,
  risk_profile: businessRiskSchema,
});

export type EnterpriseAssessmentFormValues = z.infer<typeof enterpriseAssessmentSchema>;
