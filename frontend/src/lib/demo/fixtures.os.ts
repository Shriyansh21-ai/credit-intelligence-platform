/**
 * Demo Mode fixtures for the Enterprise Banking Operating System (`/api/os/*`,
 * Phase 10). These populate the AI-native banking control-plane pages so a
 * product demo shows a fully-provisioned OS instead of empty states:
 *
 *   Executive Intelligence Center, Policy Engine, Enterprise Search, Loan
 *   Committee Workspace, Scenario Planning, Workflow Studio, Recommendation
 *   Marketplace, Data Fabric, Knowledge Graph Analytics, Prompt Studio,
 *   Multi-LLM Console and Fairness & Drift Governance.
 *
 * The borrowers / cases are the SAME real companies used across every other
 * demo view (Reliance Industries, Tata Steel, Infosys, Adani Ports, …) and the
 * same fixed roster of bankers, so the narrative stays coherent everywhere.
 *
 * Only GET endpoints fetched on page load are covered here — search, playground,
 * scenario runs, marketplace runs, LLM routing and fairness evaluation are POST
 * and cannot be intercepted (they render on user action). Each entry is a
 * factory returning a FRESH object literal per call.
 */

import {
  COMPANIES,
  MONTHS_12,
  cr,
  daysAgo,
  daysAhead,
  ebitdaOf,
  eclOf,
  userById,
} from "./enterprise-data";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

type Company = (typeof COMPANIES)[number];

/** Map 12 values onto the 12 month labels → { Aug: v0, … Jul: v11 }. */
const monthly = (vals: number[]): Record<string, number> =>
  Object.fromEntries(MONTHS_12.map((mo, i) => [mo, vals[i]]));

/** Aggregate sanctioned exposure + account count by a chosen dimension. */
const groupExp = (pick: (c: Company) => string): Record<string, { exposure: number; count: number }> => {
  const out: Record<string, { exposure: number; count: number }> = {};
  for (const c of COMPANIES) {
    (out[pick(c)] ??= { exposure: 0, count: 0 });
    out[pick(c)].exposure += c.exposure;
    out[pick(c)].count += 1;
  }
  return out;
};

const bySector = () => groupExp((c) => c.sector);
const byRegion = () => groupExp((c) => c.region);
const byRisk = () => groupExp((c) => c.risk);

// ---------------------------------------------------------------------------
// M10 — Executive Intelligence Center  (GET /api/os/exec/dashboard/{persona})
// Page reads: d.cards[] = {title, value, unit, intent}; d.charts = { name: series }
// where a series value that is an object renders as `₹{exposure} · {count}`.
// ---------------------------------------------------------------------------

const execDashboards: Record<string, () => unknown> = {
  ceo: () => ({
    persona: "ceo",
    generated_at: daysAgo(0),
    cards: [
      { title: "Portfolio Exposure", value: "₹864 Cr", intent: "neutral" },
      { title: "Gross NPA", value: 3.1, unit: "%", intent: "bad" },
      { title: "CRAR", value: 16.4, unit: "%", intent: "good" },
      { title: "Approval Rate", value: 75.3, unit: "%", intent: "good" },
      { title: "Net Interest Margin", value: 3.8, unit: "%", intent: "good" },
      { title: "Return on Assets", value: 1.9, unit: "%", intent: "good" },
      { title: "Active Borrowers", value: 1284, intent: "neutral" },
      { title: "Provision Coverage", value: 68, unit: "%", intent: "good" },
    ],
    charts: {
      portfolio_by_sector: bySector(),
      monthly_disbursement_cr: monthly([58, 64, 71, 66, 79, 83, 77, 88, 92, 86, 95, 101]),
    },
  }),
  chief_risk_officer: () => ({
    persona: "chief_risk_officer",
    generated_at: daysAgo(0),
    cards: [
      { title: "Risk-Weighted Assets", value: "₹612 Cr", intent: "neutral" },
      { title: "Expected Credit Loss", value: "₹142 Cr", intent: "bad" },
      { title: "Portfolio 1Y PD", value: 2.4, unit: "%", intent: "neutral" },
      { title: "High-Risk Exposure", value: 9.7, unit: "%", intent: "bad" },
      { title: "99% Credit VaR", value: "₹58 Cr", intent: "bad" },
      { title: "Watchlist Accounts", value: 47, intent: "bad" },
      { title: "Stressed Book", value: 6.2, unit: "%", intent: "bad" },
      { title: "CRAR", value: 16.4, unit: "%", intent: "good" },
    ],
    charts: {
      exposure_by_risk_band: byRisk(),
      ecl_trend_cr: monthly([118, 122, 127, 124, 131, 136, 134, 139, 142, 140, 141, 142]),
    },
  }),
  chief_credit_officer: () => ({
    persona: "chief_credit_officer",
    generated_at: daysAgo(0),
    cards: [
      { title: "Sanctions MTD", value: "₹214 Cr", intent: "good" },
      { title: "Approvals Pending", value: 38, intent: "neutral" },
      { title: "Avg Turnaround", value: 4.6, unit: " days", intent: "good" },
      { title: "Rejection Rate", value: 24.7, unit: "%", intent: "neutral" },
      { title: "Avg Ticket Size", value: "₹42 Cr", intent: "neutral" },
      { title: "Disbursed MTD", value: "₹186 Cr", intent: "good" },
      { title: "Committee Referrals", value: 11, intent: "neutral" },
      { title: "Covenant Breaches", value: 5, intent: "bad" },
    ],
    charts: {
      pipeline_by_stage: {
        Screening: 42,
        "Under Review": 31,
        "Committee Review": 14,
        "Pending Approval": 9,
        Sanctioned: 27,
      },
      sanction_trend_cr: monthly([142, 156, 168, 161, 179, 188, 174, 196, 205, 198, 210, 214]),
    },
  }),
  chief_compliance_officer: () => ({
    persona: "chief_compliance_officer",
    generated_at: daysAgo(0),
    cards: [
      { title: "Open AML Alerts", value: 63, intent: "bad" },
      { title: "SARs Filed YTD", value: 21, intent: "neutral" },
      { title: "KYC Pending", value: 44, intent: "bad" },
      { title: "Sanctions Screening Hits", value: 3, intent: "bad" },
      { title: "Regulatory Findings", value: 2, intent: "bad" },
      { title: "Policy Coverage", value: 98.4, unit: "%", intent: "good" },
      { title: "Audit Actions Closed", value: 87, unit: "%", intent: "good" },
      { title: "Training Completion", value: 94, unit: "%", intent: "good" },
    ],
    charts: {
      alerts_by_type: {
        "Transaction Monitoring": 28,
        "Sanctions Screening": 3,
        "PEP Review": 11,
        "Adverse Media": 14,
        "Structuring": 7,
      },
      kyc_refresh_trend: monthly([61, 58, 54, 49, 52, 47, 45, 43, 44, 41, 46, 44]),
    },
  }),
  portfolio: () => ({
    persona: "portfolio",
    generated_at: daysAgo(0),
    cards: [
      { title: "Sanctioned Exposure", value: "₹864 Cr", intent: "neutral" },
      { title: "Outstanding", value: "₹618 Cr", intent: "neutral" },
      { title: "Blended Yield", value: 9.4, unit: "%", intent: "good" },
      { title: "Top-10 Concentration", value: 61, unit: "%", intent: "bad" },
      { title: "Utilisation", value: 71.5, unit: "%", intent: "neutral" },
      { title: "Avg Internal Score", value: 712, intent: "good" },
      { title: "Reviews Due (30d)", value: 19, intent: "neutral" },
      { title: "Book Churn", value: 4.1, unit: "%", intent: "neutral" },
    ],
    charts: {
      exposure_by_region: byRegion(),
      yield_trend: monthly([9.1, 9.0, 9.2, 9.3, 9.2, 9.4, 9.5, 9.4, 9.4, 9.6, 9.5, 9.4]),
    },
  }),
  regulatory: () => ({
    persona: "regulatory",
    generated_at: daysAgo(0),
    cards: [
      { title: "Filings Due (30d)", value: 6, intent: "neutral" },
      { title: "Filings Submitted YTD", value: 148, intent: "good" },
      { title: "CRAR", value: 16.4, unit: "%", intent: "good" },
      { title: "LCR", value: 138, unit: "%", intent: "good" },
      { title: "Priority Sector Lending", value: 41.2, unit: "%", intent: "good" },
      { title: "Large Exposure Breaches", value: 0, intent: "good" },
      { title: "Leverage Ratio", value: 6.8, unit: "%", intent: "good" },
      { title: "Open Regulatory Queries", value: 4, intent: "neutral" },
    ],
    charts: {
      filings_by_type: {
        "RBI Returns": 62,
        "CRILC Reporting": 24,
        "AML/CFT Returns": 31,
        "Basel III Disclosures": 12,
        "Priority Sector": 19,
      },
      capital_adequacy_trend: monthly([15.8, 15.9, 16.0, 16.1, 16.0, 16.2, 16.3, 16.2, 16.4, 16.5, 16.4, 16.4]),
    },
  }),
  treasury: () => ({
    persona: "treasury",
    generated_at: daysAgo(0),
    cards: [
      { title: "Liquidity Coverage Ratio", value: 138, unit: "%", intent: "good" },
      { title: "Net Stable Funding Ratio", value: 121, unit: "%", intent: "good" },
      { title: "HQLA Buffer", value: "₹1,240 Cr", intent: "good" },
      { title: "Cost of Funds", value: 5.6, unit: "%", intent: "neutral" },
      { title: "Net Interest Margin", value: 3.8, unit: "%", intent: "good" },
      { title: "1Y Repricing Gap", value: "-₹96 Cr", intent: "bad" },
      { title: "Duration of Equity", value: 2.3, unit: " yrs", intent: "neutral" },
      { title: "Unencumbered HQLA", value: 82, unit: "%", intent: "good" },
    ],
    charts: {
      funding_mix: {
        "Retail Deposits": 46,
        "Wholesale Deposits": 22,
        "Interbank": 12,
        "Certificates of Deposit": 11,
        "Bonds": 9,
      },
      lcr_trend: monthly([131, 129, 133, 136, 134, 137, 140, 138, 138, 142, 139, 138]),
    },
  }),
};

// ---------------------------------------------------------------------------
// M7 — Policy Engine
// ---------------------------------------------------------------------------

const policyDomains = () => ({
  domains: [
    "loan", "aml", "kyc", "exposure", "collateral", "approval", "risk_appetite", "pricing",
  ],
  operators: ["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "between", "contains"],
});

const policies = () => ({
  policies: [
    { id: 1, name: "Minimum DSCR ≥ 1.25x", domain: "risk_appetite", current_version: 4, status: "active", pass_count: 1176, fail_count: 108, last_revised: daysAgo(12), owner: userById(4).name },
    { id: 2, name: "Maximum Leverage ≤ 3.5x (Debt/EBITDA)", domain: "risk_appetite", current_version: 3, status: "active", pass_count: 1092, fail_count: 192, last_revised: daysAgo(23), owner: userById(4).name },
    { id: 3, name: "Single-Borrower Exposure Cap ≤ 15% of Tier-1", domain: "exposure", current_version: 6, status: "active", pass_count: 1281, fail_count: 3, last_revised: daysAgo(8), owner: userById(2).name },
    { id: 4, name: "Sector Cap — Infrastructure ≤ 18% of Book", domain: "exposure", current_version: 2, status: "active", pass_count: 1284, fail_count: 0, last_revised: daysAgo(31), owner: userById(2).name },
    { id: 5, name: "Collateral Coverage ≥ 1.4x for Sub-Investment Grade", domain: "collateral", current_version: 5, status: "active", pass_count: 214, fail_count: 41, last_revised: daysAgo(19), owner: userById(1).name },
    { id: 6, name: "KYC Refresh Overdue → Block Disbursement", domain: "kyc", current_version: 2, status: "active", pass_count: 1240, fail_count: 44, last_revised: daysAgo(6), owner: userById(5).name },
    { id: 7, name: "AML — Structuring Pattern Flag", domain: "aml", current_version: 7, status: "active", pass_count: 1277, fail_count: 7, last_revised: daysAgo(4), owner: userById(5).name },
    { id: 8, name: "Reject PD above Risk Appetite (≥ 25%)", domain: "loan", current_version: 3, status: "active", pass_count: 1271, fail_count: 13, last_revised: daysAgo(15), owner: userById(1).name },
    { id: 9, name: "Committee Referral for Watch-Grade Renewals", domain: "approval", current_version: 1, status: "draft", pass_count: 0, fail_count: 0, last_revised: daysAgo(2), owner: userById(4).name },
    { id: 10, name: "Risk-Based Pricing Floor (Spread ≥ PD × LGD)", domain: "pricing", current_version: 2, status: "active", pass_count: 1258, fail_count: 26, last_revised: daysAgo(27), owner: userById(6).name },
  ],
});

// ---------------------------------------------------------------------------
// M4 — Loan Committee Workspace
// ---------------------------------------------------------------------------

const committees = () => ({
  committees: [
    { id: 1, name: "Executive Credit Committee", quorum: 4, members: [1, 2, 4, 5, 6].map((i) => ({ user_id: i, name: userById(i).name, role: userById(i).title })), authority_limit: cr(1000) },
    { id: 2, name: "Management Credit Committee", quorum: 3, members: [1, 2, 3].map((i) => ({ user_id: i, name: userById(i).name, role: userById(i).title })), authority_limit: cr(500) },
    { id: 3, name: "Risk & Provisioning Committee", quorum: 3, members: [1, 4, 5].map((i) => ({ user_id: i, name: userById(i).name, role: userById(i).title })), authority_limit: cr(250) },
    { id: 4, name: "Watchlist & Recovery Committee", quorum: 2, members: [2, 3, 4].map((i) => ({ user_id: i, name: userById(i).name, role: userById(i).title })), authority_limit: cr(150) },
  ],
});

const meetings = () => ({
  meetings: [
    { id: 101, committee_id: 1, title: "ECC #214 — Adani Ports renewal & JSW Steel enhancement", status: "in_session", scheduled_at: daysAgo(0), cases: ["Adani Ports & SEZ Ltd", "JSW Steel Ltd"] },
    { id: 102, committee_id: 2, title: "MCC #388 — Nykaa working-capital line", status: "scheduled", scheduled_at: daysAhead(2), cases: ["Nykaa (FSN E-Commerce Ltd)"] },
    { id: 103, committee_id: 3, title: "Provisioning review — Swiggy, Ather Energy downgrades", status: "scheduled", scheduled_at: daysAhead(4), cases: ["Swiggy (Bundl Technologies)", "Ather Energy Ltd"] },
    { id: 104, committee_id: 1, title: "ECC #213 — Reliance Industries syndication", status: "closed", scheduled_at: daysAgo(7), cases: ["Reliance Industries Ltd"] },
    { id: 105, committee_id: 4, title: "Watchlist review — Zomato, Delhivery covenant status", status: "closed", scheduled_at: daysAgo(11), cases: ["Zomato Ltd", "Delhivery Ltd"] },
    { id: 106, committee_id: 2, title: "MCC #387 — Mahindra Logistics term-loan restructure", status: "closed", scheduled_at: daysAgo(18), cases: ["Mahindra Logistics Ltd"] },
  ],
});

const committeeAnalytics = () => ({
  committees: 4,
  meetings: 27,
  agenda_items: 214,
  decided: 186,
  approved: 143,
  rejected: 28,
  deferred: 15,
  approval_rate: 0.769,
  avg_decision_minutes: 34,
  quorum_met_rate: 0.96,
});

// ---------------------------------------------------------------------------
// M2 — Enterprise Search  (GET /api/os/search/facets)
// ---------------------------------------------------------------------------

const searchFacets = () => ({
  total: 48213,
  by_doc_type: {
    company: 1284,
    application: 3921,
    document: 28470,
    report: 2140,
    alert: 6318,
    task: 4802,
    policy: 96,
    model: 42,
    committee_minute: 1140,
  },
  by_source: { core_banking: 21840, dms: 18960, risk_engine: 4210, crm: 3203 },
  last_indexed_at: daysAgo(0),
});

// ---------------------------------------------------------------------------
// M8 — Prompt Management Studio  (GET /api/os/prompt)
// ---------------------------------------------------------------------------

const prompts = () => ({
  prompts: [
    { id: 1, name: "Credit Memo Summariser", category: "underwriting", current_version: 6, deployed_version: 5, status: "active" },
    { id: 2, name: "Covenant Breach Explainer", category: "monitoring", current_version: 4, deployed_version: 4, status: "active" },
    { id: 3, name: "Adverse Media Screener", category: "compliance", current_version: 9, deployed_version: 8, status: "active" },
    { id: 4, name: "Early-Warning Signal Narrator", category: "risk", current_version: 3, deployed_version: 3, status: "active" },
    { id: 5, name: "Financial Spreading Extractor", category: "underwriting", current_version: 7, deployed_version: 6, status: "active" },
    { id: 6, name: "Committee Minutes Generator", category: "governance", current_version: 2, deployed_version: null, status: "draft" },
    { id: 7, name: "ESG Risk Commentary", category: "risk", current_version: 5, deployed_version: 4, status: "active" },
    { id: 8, name: "Customer 360 Relationship Brief", category: "relationship", current_version: 4, deployed_version: 3, status: "active" },
  ],
});

// ---------------------------------------------------------------------------
// M9 — Multi-LLM Console
// ---------------------------------------------------------------------------

const llmProviders = () => ({
  kinds: ["openai", "anthropic", "gemini", "llama", "mistral", "azure", "ollama"],
  providers: [
    { id: 1, name: "GPT-4o (OpenAI)", kind: "openai", quality_score: 0.94, avg_latency_ms: 820, enabled: true, est_cost: 0.012 },
    { id: 2, name: "Claude 3.5 Sonnet (Anthropic)", kind: "anthropic", quality_score: 0.96, avg_latency_ms: 910, enabled: true, est_cost: 0.011 },
    { id: 3, name: "Gemini 1.5 Pro (Google)", kind: "gemini", quality_score: 0.91, avg_latency_ms: 760, enabled: true, est_cost: 0.008 },
    { id: 4, name: "Llama 3.1 70B (self-hosted)", kind: "llama", quality_score: 0.86, avg_latency_ms: 540, enabled: true, est_cost: 0.002 },
    { id: 5, name: "Mistral Large", kind: "mistral", quality_score: 0.88, avg_latency_ms: 690, enabled: true, est_cost: 0.006 },
    { id: 6, name: "Azure OpenAI (EU residency)", kind: "azure", quality_score: 0.93, avg_latency_ms: 880, enabled: true, est_cost: 0.013 },
    { id: 7, name: "Ollama Mixtral (on-prem)", kind: "ollama", quality_score: 0.79, avg_latency_ms: 430, enabled: false, est_cost: 0.0 },
  ],
});

const llmAnalytics = () => ({
  total_invocations: 184290,
  total_cost: 1642.87,
  avg_latency_ms: 812,
  fallback_rate: 0.031,
  by_kind: {
    anthropic: 71240,
    openai: 58120,
    gemini: 29840,
    mistral: 14210,
    llama: 8640,
    azure: 2240,
  },
  cost_trend_usd: monthly([118, 124, 131, 129, 138, 142, 136, 149, 152, 147, 158, 168]),
});

// ---------------------------------------------------------------------------
// M14 — Data Fabric
// ---------------------------------------------------------------------------

const fabricCatalog = () => ({
  datasets: [
    { id: 1, name: "core.loan_accounts", domain: "lending", owner: userById(2).name, classification: "confidential", quality: 0.97, rows: 1284000 },
    { id: 2, name: "risk.pd_lgd_ead", domain: "risk", owner: userById(4).name, classification: "restricted", quality: 0.94, rows: 1284 },
    { id: 3, name: "crm.customer_360", domain: "relationship", owner: userById(3).name, classification: "confidential", quality: 0.91, rows: 486000 },
    { id: 4, name: "aml.transaction_monitoring", domain: "compliance", owner: userById(5).name, classification: "restricted", quality: 0.96, rows: 92400000 },
    { id: 5, name: "treasury.liquidity_positions", domain: "treasury", owner: userById(6).name, classification: "confidential", quality: 0.98, rows: 34200 },
    { id: 6, name: "ext.bureau_scores", domain: "external", owner: userById(1).name, classification: "restricted", quality: 0.89, rows: 1284000 },
    { id: 7, name: "ref.sector_benchmarks", domain: "reference", owner: userById(2).name, classification: "internal", quality: 0.99, rows: 240 },
    { id: 8, name: "pub.rbi_regulatory_returns", domain: "regulatory", owner: userById(5).name, classification: "public", quality: 1.0, rows: 148 },
  ],
});

const fabricStats = () => ({
  datasets: 68,
  lineage_edges: 214,
  contracts: 41,
  avg_quality: 0.942,
  by_classification: { restricted: 18, confidential: 27, internal: 16, public: 7 },
  by_domain: { lending: 14, risk: 11, compliance: 9, treasury: 7, relationship: 8, external: 6, reference: 8, regulatory: 5 },
  quality_trend: monthly([0.91, 0.92, 0.92, 0.93, 0.93, 0.93, 0.94, 0.94, 0.94, 0.94, 0.94, 0.94]),
});

// ---------------------------------------------------------------------------
// M11 — Workflow Studio
// ---------------------------------------------------------------------------

const workflows = () => ({
  definitions: [
    { id: 1, name: "Corporate Loan Origination", version: 7, node_count: 14, status: "active" },
    { id: 2, name: "Annual Credit Review", version: 4, node_count: 9, status: "active" },
    { id: 3, name: "Covenant Breach Escalation", version: 3, node_count: 11, status: "active" },
    { id: 4, name: "KYC / CDD Refresh", version: 5, node_count: 8, status: "active" },
    { id: 5, name: "Committee Referral & Voting", version: 2, node_count: 12, status: "active" },
    { id: 6, name: "NPA Recovery & Restructuring", version: 6, node_count: 16, status: "active" },
    { id: 7, name: "Collateral Revaluation", version: 1, node_count: 7, status: "draft" },
  ],
});

const workflowRuns = () => ({
  runs: [
    { id: 9012, definition_key: "Corporate Loan Origination", subject_ref: "Reliance Industries Ltd", status: "completed", started_at: daysAgo(6) },
    { id: 9013, definition_key: "Annual Credit Review", subject_ref: "Infosys Ltd", status: "completed", started_at: daysAgo(4) },
    { id: 9014, definition_key: "Committee Referral & Voting", subject_ref: "Adani Ports & SEZ Ltd", status: "waiting", started_at: daysAgo(1) },
    { id: 9015, definition_key: "Covenant Breach Escalation", subject_ref: "Swiggy (Bundl Technologies)", status: "waiting", started_at: daysAgo(1) },
    { id: 9016, definition_key: "NPA Recovery & Restructuring", subject_ref: "Ather Energy Ltd", status: "running", started_at: daysAgo(0) },
    { id: 9017, definition_key: "KYC / CDD Refresh", subject_ref: "Nykaa (FSN E-Commerce Ltd)", status: "completed", started_at: daysAgo(3) },
    { id: 9018, definition_key: "Annual Credit Review", subject_ref: "JSW Steel Ltd", status: "failed", started_at: daysAgo(2) },
    { id: 9019, definition_key: "Corporate Loan Origination", subject_ref: "Delhivery Ltd", status: "waiting", started_at: daysAgo(0) },
  ],
});

// ---------------------------------------------------------------------------
// M12 — Recommendation Marketplace  (GET /api/os/marketplace/plugins)
// ---------------------------------------------------------------------------

const plugins = () => ({
  plugins: [
    { id: 1, key: "exposure_rebalancer", name: "Exposure Rebalancer", category: "exposure", installed: true },
    { id: 2, key: "restructure_advisor", name: "Restructuring Advisor", category: "restructure", installed: true },
    { id: 3, key: "collateral_optimiser", name: "Collateral Optimiser", category: "collateral", installed: true },
    { id: 4, key: "risk_based_pricing", name: "Risk-Based Pricing Engine", category: "pricing", installed: true },
    { id: 5, key: "covenant_designer", name: "Covenant Designer", category: "covenants", installed: true },
    { id: 6, key: "guarantee_structurer", name: "Guarantee Structurer", category: "guarantees", installed: false },
    { id: 7, key: "early_warning", name: "Early-Warning Recommender", category: "monitoring", installed: true },
    { id: 8, key: "syndication_planner", name: "Syndication Planner", category: "exposure", installed: false },
  ],
});

// ---------------------------------------------------------------------------
// M5/M6 — Scenario Planning  (GET /api/os/scenario/library)
// ---------------------------------------------------------------------------

const scenarioLibrary = () => ({
  scenarios: ["best_case", "base_case", "worst_case", "stress", "black_swan"],
  factors: ["gdp_growth", "policy_rate", "inr_usd", "commodity_index", "credit_spread"],
});

// ---------------------------------------------------------------------------
// M13 — Fairness & Drift Governance  (GET /api/os/fairness/history)
// ---------------------------------------------------------------------------

const fairnessHistory = () => ({
  history: [
    { id: 1, model_key: "pd_model_v4", kind: "fairness", passed: true, disparate_impact_ratio: 0.91, evaluated_at: daysAgo(2) },
    { id: 2, model_key: "pd_model_v4", kind: "drift", passed: true, psi: 0.07, evaluated_at: daysAgo(2) },
    { id: 3, model_key: "lgd_model_v2", kind: "fairness", passed: false, disparate_impact_ratio: 0.74, evaluated_at: daysAgo(9) },
    { id: 4, model_key: "lgd_model_v2", kind: "drift", passed: true, psi: 0.11, evaluated_at: daysAgo(9) },
    { id: 5, model_key: "behaviour_score_v3", kind: "fairness", passed: true, disparate_impact_ratio: 0.88, evaluated_at: daysAgo(16) },
    { id: 6, model_key: "behaviour_score_v3", kind: "drift", passed: false, psi: 0.28, evaluated_at: daysAgo(16) },
    { id: 7, model_key: "ews_model_v1", kind: "fairness", passed: true, disparate_impact_ratio: 0.93, evaluated_at: daysAgo(24) },
  ],
});

// ---------------------------------------------------------------------------
// M1 — Knowledge Graph Analytics  (GET /api/os/graph/cross-holdings)
// ---------------------------------------------------------------------------

const crossHoldings = () => ({
  count: 3,
  cross_holdings: [
    ["Reliance Industries Ltd", "Adani Ports & SEZ Ltd", "Mahindra Logistics Ltd"],
    ["Tata Steel Ltd", "JSW Steel Ltd"],
    ["Zomato Ltd", "Swiggy (Bundl Technologies)", "Nykaa (FSN E-Commerce Ltd)"],
  ],
  nodes: COMPANIES.length,
  edges: 42,
});

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const OS_FIXTURES: Record<string, () => unknown> = {
  // M10 Executive Center — one key per persona (matched by endsWith)
  "/api/os/exec/dashboard/ceo": execDashboards.ceo,
  "/api/os/exec/dashboard/chief_risk_officer": execDashboards.chief_risk_officer,
  "/api/os/exec/dashboard/chief_credit_officer": execDashboards.chief_credit_officer,
  "/api/os/exec/dashboard/chief_compliance_officer": execDashboards.chief_compliance_officer,
  "/api/os/exec/dashboard/portfolio": execDashboards.portfolio,
  "/api/os/exec/dashboard/regulatory": execDashboards.regulatory,
  "/api/os/exec/dashboard/treasury": execDashboards.treasury,
  "/api/os/exec/personas": () => ({
    personas: [
      "ceo", "chief_risk_officer", "chief_credit_officer", "chief_compliance_officer",
      "portfolio", "regulatory", "treasury",
    ],
  }),

  // M7 Policy Engine
  "/api/os/policy/domains": policyDomains,
  "/api/os/policy": policies,

  // M4 Committee Workspace
  "/api/os/committee/committees": committees,
  "/api/os/committee/meetings": meetings,
  "/api/os/committee/analytics": committeeAnalytics,

  // M2 Enterprise Search
  "/api/os/search/facets": searchFacets,

  // M8 Prompt Studio
  "/api/os/prompt": prompts,

  // M9 Multi-LLM Console
  "/api/os/llm/providers": llmProviders,
  "/api/os/llm/analytics": llmAnalytics,

  // M14 Data Fabric
  "/api/os/fabric/catalog": fabricCatalog,
  "/api/os/fabric/stats": fabricStats,

  // M11 Workflow Studio
  "/api/os/workflow/definitions": workflows,
  "/api/os/workflow/runs": workflowRuns,

  // M12 Recommendation Marketplace
  "/api/os/marketplace/plugins": plugins,

  // M5/M6 Scenario Planning
  "/api/os/scenario/library": scenarioLibrary,

  // M13 Fairness & Drift Governance
  "/api/os/fairness/history": fairnessHistory,

  // M1 Knowledge Graph Analytics
  "/api/os/graph/cross-holdings": crossHoldings,
};

// Silence unused-import warnings for helpers kept available to future fixtures.
void ebitdaOf;
void eclOf;
