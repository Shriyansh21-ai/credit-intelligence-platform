/**
 * Demo Mode fixtures for the Autonomous Intelligence feature (`/api/ai/*`).
 *
 * Populates every Phase 9 "AI Brain" page (Knowledge Graph, Real-Time Risk
 * Monitoring, Early Warning, Copilot, Simulation, Stress Testing, Portfolio
 * Optimization, RM Workspace, Command Center, NL Analytics, Model Governance)
 * with coherent, banking-grade sample data drawn from the SAME canonical roster
 * of real Indian corporates used everywhere else in Demo Mode.
 *
 * Keyed by request-path suffix; the interceptor strips the query string, so
 * query-parameterised endpoints are keyed by the path BEFORE `?`. Each factory
 * returns a FRESH object literal so callers can never mutate shared state.
 *
 * All monetary values are absolute Indian Rupees (₹): `cr(18.5)` === ₹18.5 Cr.
 */

import {
  BOOK, COMPANIES, MONTHS_12,
  companyByRef, cr, daysAgo, eclOf, pdOf,
  type DemoCompany,
} from "./enterprise-data";

const clone = <T>(v: T): T => structuredClone(v);

// ---------------------------------------------------------------------------
// Shared derivations from the canonical book
// ---------------------------------------------------------------------------

const TOTAL_EXPOSURE = COMPANIES.reduce((s, c) => s + c.exposure, 0);
const TOTAL_ECL = COMPANIES.reduce((s, c) => s + eclOf(c), 0);
const DISTRESSED = COMPANIES.filter(
  (c) => c.grade !== "Standard" || c.risk === "High" || c.risk === "Critical",
);
const HIGH_RISK = COMPANIES.filter((c) => c.risk === "High" || c.risk === "Critical");

const nodeRisk = (c: DemoCompany) => Math.round((850 - c.score) / 4);
const ewsBandOf = (c: DemoCompany) =>
  c.grade === "Substandard" ? "red" : c.grade === "Watch" ? "amber" : "green";

// ---------------------------------------------------------------------------
// M1 — Knowledge Graph
// ---------------------------------------------------------------------------

const graphStats = {
  entities: 96,
  relationships: 154,
  by_entity_type: {
    company: 20, director: 26, promoter: 12, subsidiary: 14,
    supplier: 10, customer: 5, lender: 6, guarantor: 5, sector: 10,
  },
  by_relationship_type: {
    director_of: 26, promoter_of: 12, subsidiary_of: 14, supplier_of: 24,
    customer_of: 15, lends_to: 20, guarantor_of: 11, belongs_to_sector: 20,
  },
};

const companyNodes = COMPANIES.map((c) => ({
  id: c.id, ref: c.ref, name: c.name, entity_type: "company",
  risk_score: nodeRisk(c),
  propagated_risk: Math.min(
    100,
    nodeRisk(c) + (c.grade === "Substandard" ? 14 : c.grade === "Watch" ? 8 : 3),
  ),
  depth: 1,
}));

const sectorNodes = ["Energy", "Manufacturing", "FinTech", "Logistics"].map((s, i) => ({
  id: 5000 + i, ref: `SECTOR-${s.toUpperCase()}`, name: s,
  entity_type: "sector", risk_score: null, propagated_risk: null, depth: 0,
}));

const extraNodes = [
  { id: 6001, ref: "ENT-RIL-HOLD", name: "Reliance Strategic Holdings", entity_type: "promoter", risk_score: 12, propagated_risk: 15, depth: 2 },
  { id: 6002, ref: "ENT-TATA-SONS", name: "Tata Sons Pvt Ltd", entity_type: "guarantor", risk_score: 10, propagated_risk: 13, depth: 2 },
  { id: 6003, ref: "ENT-JSW-CEMENT", name: "JSW Cement Ltd", entity_type: "subsidiary", risk_score: 34, propagated_risk: 41, depth: 2 },
  { id: 6004, ref: "ENT-ADANI-LOG", name: "Adani Logistics Ltd", entity_type: "subsidiary", risk_score: 48, propagated_risk: 58, depth: 2 },
  { id: 6005, ref: "ENT-BLUEDART", name: "Blue Dart Express Ltd", entity_type: "supplier", risk_score: 22, propagated_risk: 27, depth: 2 },
];

const graphEdges = [
  { id: 1, source: 4202, target: 4204, rel_type: "supplier_of", strength: 0.82, exposure: cr(120) },
  { id: 2, source: 4205, target: 4204, rel_type: "supplier_of", strength: 0.71, exposure: cr(96) },
  { id: 3, source: 6003, target: 4205, rel_type: "subsidiary_of", strength: 1.0, exposure: cr(80) },
  { id: 4, source: 6004, target: 4206, rel_type: "subsidiary_of", strength: 1.0, exposure: cr(140) },
  { id: 5, source: 6002, target: 4202, rel_type: "guarantor_of", strength: 0.9, exposure: cr(300) },
  { id: 6, source: 6001, target: 4201, rel_type: "promoter_of", strength: 1.0, exposure: null },
  { id: 7, source: 4206, target: 4201, rel_type: "supplier_of", strength: 0.54, exposure: cr(210) },
  { id: 8, source: 6005, target: 4214, rel_type: "supplier_of", strength: 0.62, exposure: cr(44) },
  { id: 9, source: 4213, target: 4214, rel_type: "supplier_of", strength: 0.6, exposure: cr(52) },
  { id: 10, source: 4216, target: 4215, rel_type: "customer_of", strength: 0.38, exposure: cr(30) },
  { id: 11, source: 4201, target: 5000, rel_type: "belongs_to_sector", strength: 1.0, exposure: null },
  { id: 12, source: 4216, target: 5002, rel_type: "belongs_to_sector", strength: 1.0, exposure: null },
  { id: 13, source: 4206, target: 5003, rel_type: "belongs_to_sector", strength: 1.0, exposure: null },
  { id: 14, source: 6002, target: 4204, rel_type: "guarantor_of", strength: 0.68, exposure: cr(150) },
];

const graphNetwork = () => {
  const nodes = [...companyNodes, ...sectorNodes, ...extraNodes];
  return {
    nodes,
    edges: graphEdges,
    node_count: nodes.length,
    edge_count: graphEdges.length,
  };
};

// ---------------------------------------------------------------------------
// M2 — Real-Time Risk Monitoring
// ---------------------------------------------------------------------------

const monitoringSignals = {
  signals: [
    { id: 901, source: "financial", signal_type: "margin_compression", severity: "high", direction: "negative", detail: "Swiggy (Bundl Technologies) — EBITDA margin turned negative to -2% from +4% QoQ.", priority_score: 88, detected_at: daysAgo(0) },
    { id: 902, source: "payment", signal_type: "payment_delay", severity: "critical", direction: "negative", detail: "Ather Energy Ltd — term-loan EMI overdue 31 days; DPD bucket 30+.", priority_score: 94, detected_at: daysAgo(0) },
    { id: 903, source: "market", signal_type: "leverage_spike", severity: "high", direction: "negative", detail: "Adani Ports & SEZ Ltd — net debt / EBITDA rose to 3.6x, above 3.5x covenant.", priority_score: 82, detected_at: daysAgo(1) },
    { id: 904, source: "mca", signal_type: "director_change", severity: "medium", direction: "negative", detail: "Delhivery Ltd — two independent directors resigned within 60 days.", priority_score: 61, detected_at: daysAgo(1) },
    { id: 905, source: "news", signal_type: "adverse_media", severity: "medium", direction: "negative", detail: "Zomato Ltd — regulatory review of platform commission structure reported.", priority_score: 57, detected_at: daysAgo(2) },
    { id: 906, source: "gst", signal_type: "revenue_decline", severity: "high", direction: "negative", detail: "Mahindra Logistics Ltd — GST turnover down 18% YoY on freight softness.", priority_score: 74, detected_at: daysAgo(2) },
    { id: 907, source: "bureau", signal_type: "external_downgrade", severity: "medium", direction: "negative", detail: "Nykaa (FSN E-Commerce Ltd) — external agency revised outlook to Negative.", priority_score: 55, detected_at: daysAgo(3) },
    { id: 908, source: "financial", signal_type: "working_capital_stress", severity: "high", direction: "negative", detail: "Swiggy (Bundl Technologies) — working-capital cycle stretched to 128 days.", priority_score: 79, detected_at: daysAgo(3) },
    { id: 909, source: "payment", signal_type: "dscr_breach", severity: "critical", direction: "negative", detail: "Ather Energy Ltd — DSCR fell to 0.7x, below 1.0x covenant floor.", priority_score: 91, detected_at: daysAgo(4) },
    { id: 910, source: "portfolio", signal_type: "concentration_risk", severity: "medium", direction: "negative", detail: "Logistics sector exposure approaching 14% single-sector soft limit.", priority_score: 48, detected_at: daysAgo(4) },
    { id: 911, source: "document", signal_type: "auditor_resignation", severity: "high", direction: "negative", detail: "boAt (Imagine Marketing Ltd) — statutory auditor sought early rotation.", priority_score: 68, detected_at: daysAgo(5) },
    { id: 912, source: "market", signal_type: "commodity_shock", severity: "medium", direction: "negative", detail: "JSW Steel Ltd — coking-coal spot prices up 22%, margin headwind.", priority_score: 52, detected_at: daysAgo(5) },
    { id: 913, source: "gst", signal_type: "tax_default", severity: "medium", direction: "negative", detail: "Delhivery Ltd — delayed GST remittance flagged for two consecutive filings.", priority_score: 50, detected_at: daysAgo(6) },
    { id: 914, source: "financial", signal_type: "cashflow_deterioration", severity: "high", direction: "negative", detail: "Zomato Ltd — operating cash flow negative for a second straight quarter.", priority_score: 71, detected_at: daysAgo(6) },
    { id: 915, source: "news", signal_type: "positive_signal", severity: "low", direction: "positive", detail: "Infosys Ltd — large multi-year deal win improves revenue visibility.", priority_score: 22, detected_at: daysAgo(7) },
    { id: 916, source: "bureau", signal_type: "covenant_breach", severity: "critical", direction: "negative", detail: "Adani Ports & SEZ Ltd — maximum-leverage covenant breached, waiver pending.", priority_score: 86, detected_at: daysAgo(7) },
  ],
};

const monitoringSources = {
  sources: [
    "financial", "connector", "payment", "gst", "mca", "bureau",
    "portfolio", "news", "document", "market",
  ],
};

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

const alerts = {
  alerts: [
    { id: 5101, company_ref: "APP-2026-4220", category: "Payment Delay", alert_type: "dpd_breach", title: "Ather Energy — EMI overdue 31 days, DSCR below covenant", severity: "critical", confidence: 0.93, priority_score: 94, business_impact: "₹13.2 Cr outstanding at risk of slippage to NPA next quarter.", recommended_action: "Escalate to Credit Committee; initiate restructuring discussion.", status: "open" },
    { id: 5102, company_ref: "APP-2026-4216", category: "Financial Deterioration", alert_type: "margin_negative", title: "Swiggy — EBITDA margin turned negative, WC cycle stretched", severity: "critical", confidence: 0.88, priority_score: 89, business_impact: "Liquidity buffer thinning; covenant test at risk within 90 days.", recommended_action: "Request updated cash-flow projections and monthly monitoring.", status: "open" },
    { id: 5103, company_ref: "APP-2026-4206", category: "Covenant Breach", alert_type: "leverage_breach", title: "Adani Ports — net debt/EBITDA breached 3.5x limit", severity: "high", confidence: 0.85, priority_score: 82, business_impact: "Leverage covenant breach; waiver negotiation required.", recommended_action: "Seek covenant waiver and re-price for elevated risk.", status: "open" },
    { id: 5104, company_ref: "APP-2026-4213", category: "External Rating Action", alert_type: "outlook_negative", title: "Delhivery — outlook revised to Negative", severity: "high", confidence: 0.8, priority_score: 76, business_impact: "Potential one-notch downgrade raises RWA and pricing.", recommended_action: "Advance next review; reassess internal rating.", status: "open" },
    { id: 5105, company_ref: "APP-2026-4212", category: "Financial Deterioration", alert_type: "revenue_decline", title: "Mahindra Logistics — GST turnover down 18% YoY", severity: "high", confidence: 0.77, priority_score: 72, business_impact: "Freight softness compressing coverage ratios.", recommended_action: "Tighten monitoring; validate order-book pipeline.", status: "open" },
    { id: 5106, company_ref: "APP-2026-4215", category: "News / Adverse Media", alert_type: "regulatory_review", title: "Zomato — regulatory review of platform fees", severity: "medium", confidence: 0.66, priority_score: 58, business_impact: "Revenue model uncertainty; monitor for earnings impact.", recommended_action: "Track development; no immediate limit change.", status: "open" },
    { id: 5107, company_ref: "APP-2026-4219", category: "Governance", alert_type: "auditor_change", title: "boAt — statutory auditor early rotation sought", severity: "medium", confidence: 0.6, priority_score: 54, business_impact: "Governance red flag; verify continuity of controls.", recommended_action: "Request board rationale and audit-committee minutes.", status: "open" },
  ],
};

const alertSummary = {
  total: 34,
  open: 19,
  acknowledged: 3,
  resolved: 12,
  by_severity: { critical: 3, high: 7, medium: 6, low: 3 },
  by_category: {
    "Payment Delay": 5,
    "Financial Deterioration": 6,
    "Covenant Breach": 4,
    "External Rating Action": 2,
    "News / Adverse Media": 2,
  },
};

// ---------------------------------------------------------------------------
// M3 — Early Warning System
// ---------------------------------------------------------------------------

const ewsCatalog = {
  signals: [
    { key: "cashflow_deterioration", name: "Cash-flow Deterioration", category: "Liquidity", severity_default: "high", description: "Operating cash flow declining over consecutive quarters." },
    { key: "margin_compression", name: "Margin Compression", category: "Profitability", severity_default: "high", description: "EBITDA / net margin falling below trailing average." },
    { key: "working_capital_stress", name: "Working-Capital Stress", category: "Liquidity", severity_default: "medium", description: "Cash-conversion cycle stretching beyond sector norm." },
    { key: "sales_decline", name: "Sales Decline", category: "Growth", severity_default: "medium", description: "Revenue contraction versus prior period or GST turnover drop." },
    { key: "leverage_spike", name: "Leverage Spike", category: "Solvency", severity_default: "high", description: "Net debt / EBITDA rising above covenant threshold." },
    { key: "director_change", name: "Director / KMP Change", category: "Governance", severity_default: "medium", description: "Unexpected resignation of directors or key managerial personnel." },
    { key: "auditor_resignation", name: "Auditor Resignation", category: "Governance", severity_default: "high", description: "Statutory auditor resignation or qualified opinion." },
    { key: "tax_default", name: "Tax / GST Default", category: "Compliance", severity_default: "medium", description: "Delayed or defaulted statutory tax remittances." },
    { key: "covenant_breach", name: "Covenant Breach", category: "Solvency", severity_default: "critical", description: "Breach of financial or non-financial loan covenant." },
    { key: "concentration_risk", name: "Concentration Risk", category: "Portfolio", severity_default: "medium", description: "Single-name, sector or geographic exposure nearing limits." },
  ],
  bands: [
    { band: "green", range: "0-39", label: "Stable" },
    { band: "amber", range: "40-69", label: "Watch" },
    { band: "red", range: "70-100", label: "Distressed" },
  ],
};

const ewsHistory = {
  company_ref: "APP-2026-4206",
  company_name: "Adani Ports & SEZ Ltd",
  history: [58, 55, 57, 60, 59, 62, 64, 63, 68, 71, 74, 78].map((score, i) => ({
    month: MONTHS_12[i],
    date: daysAgo((11 - i) * 30),
    ews_score: score,
    ews_band: score >= 70 ? "red" : score >= 40 ? "amber" : "green",
    signal_count: 2 + (i % 4),
  })),
};

// ---------------------------------------------------------------------------
// M4 — Copilot provider status
// ---------------------------------------------------------------------------

const copilotProvider = {
  active: "anthropic",
  claude_available: true,
  model: "claude-3.5-sonnet",
  fallback: "local",
  grounding: "deterministic",
  providers: [
    { name: "anthropic", available: true, model: "claude-3.5-sonnet" },
    { name: "local", available: true, model: "rule-based-templater" },
  ],
};

// ---------------------------------------------------------------------------
// M5 — Simulation scenario catalog
// ---------------------------------------------------------------------------

const simulationScenarios = {
  scenarios: [
    { key: "revenue_drop", label: "Revenue Drop", unit: "fraction" },
    { key: "interest_increase", label: "Interest-Rate Increase", unit: "fraction" },
    { key: "fx_shock", label: "FX Depreciation", unit: "fraction" },
    { key: "commodity_shock", label: "Commodity Price Shock", unit: "fraction" },
    { key: "customer_default", label: "Key-Customer Default", unit: "fraction" },
    { key: "supplier_loss", label: "Supplier Loss", unit: "fraction" },
    { key: "recession", label: "Recession", unit: "fraction" },
    { key: "new_loan", label: "New Loan Drawdown", unit: "rupees_cr" },
    { key: "mna", label: "M&A / Acquisition", unit: "rupees_cr" },
  ],
};

// ---------------------------------------------------------------------------
// M6 — Stress testing
// ---------------------------------------------------------------------------

const stressScenarios = {
  scenarios: [
    { key: "base", label: "Baseline", description: "Central macro path; no incremental shock.", gdp_shock: 0.0, rate_shock: 0.0, pd_multiplier: 1.0 },
    { key: "moderate", label: "Adverse (Moderate)", description: "Mild recession, +150bps rates, 8% GDP slowdown.", gdp_shock: -0.08, rate_shock: 0.015, pd_multiplier: 1.6 },
    { key: "severe", label: "Severely Adverse", description: "Deep recession, +300bps rates, commodity spike.", gdp_shock: -0.16, rate_shock: 0.03, pd_multiplier: 2.4 },
  ],
};

const stressCompare = {
  scope: "portfolio",
  generated_at: daysAgo(0),
  total_exposure: TOTAL_EXPOSURE,
  scenarios: [
    { scenario: "base", expected_loss: TOTAL_ECL, capital_impact: cr(0), downgraded: 4, avg_pd: 0.021 },
    { scenario: "moderate", expected_loss: Math.round(TOTAL_ECL * 1.9), capital_impact: cr(96), downgraded: 27, avg_pd: 0.038 },
    { scenario: "severe", expected_loss: Math.round(TOTAL_ECL * 3.1), capital_impact: cr(214), downgraded: 58, avg_pd: 0.061 },
  ],
};

// ---------------------------------------------------------------------------
// M7 — Portfolio optimization analysis
// ---------------------------------------------------------------------------

const portfolioAnalysis = () => {
  const bySector: Record<string, number> = {};
  for (const c of COMPANIES) bySector[c.sector] = (bySector[c.sector] ?? 0) + c.exposure;
  const sectorExposure: Record<string, number> = {};
  let hhi = 0;
  for (const k of Object.keys(bySector)) {
    const share = +(bySector[k] / TOTAL_EXPOSURE).toFixed(3);
    sectorExposure[k] = share;
    hhi += share * share;
  }
  const topName = COMPANIES.reduce((a, b) => (b.exposure > a.exposure ? b : a));
  const topShare = +(topName.exposure / TOTAL_EXPOSURE).toFixed(3);
  return {
    position_count: BOOK.applications,
    total_exposure: BOOK.total_exposure,
    total_outstanding: BOOK.total_outstanding,
    net_return: cr(486),
    gross_return: cr(612),
    portfolio_raroc: 0.187,
    expected_loss: BOOK.ecl_total,
    sector_exposure: sectorExposure,
    concentration: {
      hhi: +hhi.toFixed(3),
      top_name_share: topShare,
      effective_names: Math.round(1 / hhi),
    },
    limit_breaches: [
      { type: "single_name", entity: "Reliance Industries Ltd", share: topShare, limit: 0.1 },
      { type: "sector", entity: "FMCG", share: sectorExposure["FMCG"] ?? 0.18, limit: 0.15 },
    ],
    recommendations: [
      "Trim Reliance Industries single-name exposure by ~₹90 Cr to return within the 10% concentration limit.",
      "Reduce FMCG sector weight; redeploy toward under-weight Healthcare and SaaS names for better RAROC.",
      "Hedge Logistics book against freight-cycle downturn; place Delhivery and Mahindra Logistics on active watch.",
      "Add two AAA/AA names to lift effective diversification and reduce HHI below 0.08.",
      "Re-price Watch-grade credits (Adani Ports, Zomato) to restore risk-adjusted return above hurdle.",
    ],
  };
};

// ---------------------------------------------------------------------------
// M8 — RM Workspace (keyed per representative company reference)
// ---------------------------------------------------------------------------

function rmWorkspace(ref: string) {
  const c = companyByRef(ref) ?? COMPANIES[5];
  const band = c.risk === "High" || c.risk === "Critical" ? "At Risk"
    : c.risk === "Medium" ? "Stable" : "Healthy";
  const healthScore = Math.max(20, Math.min(95, Math.round(c.score / 8.5)));
  return {
    company_ref: c.ref,
    company_name: c.name,
    industry: c.sector,
    relationship_since: daysAgo(1240),
    health: { health_score: healthScore, band, trend: c.grade === "Standard" ? "improving" : "deteriorating" },
    ews: { ews_band: ewsBandOf(c), ews_score: nodeRisk(c) },
    next_best_action: c.grade === "Standard"
      ? { action: "cross_sell", detail: `Offer trade-finance line to ${c.name} on the back of strong DSCR (${c.dscr}x).`, source: "recommendation_engine" }
      : { action: "risk_review", detail: `Convene early review for ${c.name}; covenant headroom thinning.`, source: "early_warning" },
    open_alerts: (c.grade === "Standard" ? [] : [
      { id: 7001, severity: c.risk === "High" ? "critical" : "high", title: `${c.name} — covenant / coverage under pressure`, category: "Financial Deterioration" },
      { id: 7002, severity: "medium", title: `${c.name} — next review advanced`, category: "Monitoring" },
    ]),
    opportunities: [
      { name: "Working-capital limit enhancement", confidence: 0.72, product: "Cash Credit" },
      { name: "Supply-chain financing programme", confidence: 0.64, product: "Trade Finance" },
      { name: "Forex hedging mandate", confidence: 0.58, product: "Treasury" },
      { name: "Term-loan refinancing", confidence: 0.49, product: "Term Loan" },
    ],
    timeline: [
      { type: "review", detail: `${MONTHS_12[11]} — annual credit review completed; internal rating ${c.rating}.`, at: daysAgo(6) },
      { type: "meeting", detail: "Quarterly relationship review with CFO; capex plans discussed.", at: daysAgo(24) },
      { type: "disbursement", detail: `Drawdown of ₹${Math.round(c.outstanding / 1e7)} Cr against sanctioned limit.`, at: daysAgo(58) },
      { type: "alert", detail: "Monitoring engine flagged margin movement; acknowledged.", at: daysAgo(92) },
      { type: "covenant", detail: "DSCR covenant test passed at last compliance certificate.", at: daysAgo(120) },
      { type: "document", detail: "Audited financials FY received and spread.", at: daysAgo(160) },
    ],
    recommendations: [
      { action: "monitor", title: `Maintain monthly monitoring cadence for ${c.name}.` },
      { action: "cross_sell", title: "Pitch supply-chain finance to anchor supplier network." },
      { action: "reprice", title: "Align pricing with current internal rating and RAROC hurdle." },
    ],
    loan_history: [
      { facility: "Term Loan", sanctioned: c.exposure, outstanding: c.outstanding, rate: "9.4%", status: "Active" },
      { facility: "Cash Credit", sanctioned: cr(60), outstanding: cr(38), rate: "9.9%", status: "Active" },
    ],
  };
}

const RM_REFS = ["APP-2026-4206", "APP-2026-4220", "APP-2026-4216", "APP-2026-4201", "APP-2026-4203"];

// ---------------------------------------------------------------------------
// M9 — Executive Command Center (keyed per persona)
// ---------------------------------------------------------------------------

const industryExposure = () => {
  const bySector: Record<string, number> = {};
  for (const c of COMPANIES) bySector[c.sector] = (bySector[c.sector] ?? 0) + c.exposure;
  return Object.entries(bySector)
    .sort((a, b) => b[1] - a[1])
    .map(([industry, exposure]) => ({
      industry,
      exposure,
      share: +(exposure / TOTAL_EXPOSURE).toFixed(3),
    }));
};

const PERSONA_HEADLINE: Record<string, string> = {
  ceo: "Enterprise book resilient; three names on critical watch.",
  chief_risk_officer: "Aggregate PD stable; Logistics and FinTech pockets deteriorating.",
  chief_credit_officer: "Approval pipeline healthy; 19 open monitoring alerts to clear.",
  board: "Capital adequacy comfortable; provisions guided higher for stressed accounts.",
  regional_head: "West region carries largest exposure; South NPAs trending up.",
};

function commandDashboard(persona: string) {
  return {
    persona,
    headline: PERSONA_HEADLINE[persona] ?? PERSONA_HEADLINE.ceo,
    generated_at: daysAgo(0),
    kpis: {
      companies: COMPANIES.length,
      total_exposure: TOTAL_EXPOSURE,
      expected_loss: TOTAL_ECL,
      high_risk_count: HIGH_RISK.length,
      approval_rate: BOOK.approval_rate,
      npa_ratio: BOOK.npa_ratio,
      crar: BOOK.crar,
      avg_score: BOOK.avg_score,
    },
    watchlist: DISTRESSED.map((c) => ({
      company_ref: c.ref,
      name: c.name,
      industry: c.sector,
      rating: c.rating,
      grade: c.grade,
      pd: pdOf(c),
      exposure: c.exposure,
    })),
    industry_exposure: industryExposure(),
    capital_usage: { rwa: cr(6120), tier1: cr(1180), buffer: cr(240), utilisation: 0.83 },
    approvals_pipeline: [
      { stage: "Credit Review", count: 21 },
      { stage: "Risk Sign-off", count: 14 },
      { stage: "Credit Committee", count: 8 },
      { stage: "Board Approval", count: 4 },
    ],
    ml_drift: { models_monitored: 5, drifting: 1, last_check: daysAgo(1) },
    alerts: { open: 19, critical: 3, high: 7, medium: 6, low: 3 },
  };
}

const PERSONAS = ["ceo", "chief_risk_officer", "chief_credit_officer", "board", "regional_head"];

// ---------------------------------------------------------------------------
// M10 — NL Analytics history
// ---------------------------------------------------------------------------

const nlqHistory = {
  history: [
    { id: 12, question: "Which Watch-grade exposures breached DSCR covenants this quarter?", intent: "covenant_breach", confidence: 0.91, count: 4, created_at: daysAgo(0) },
    { id: 11, question: "Show high-risk FinTech companies with negative EBITDA margin.", intent: "risk_filter", confidence: 0.88, count: 3, created_at: daysAgo(0) },
    { id: 10, question: "Top borrowers by exposure in the West region.", intent: "top_exposure", confidence: 0.95, count: 5, created_at: daysAgo(1) },
    { id: 9, question: "Which customers deteriorated this month?", intent: "deterioration", confidence: 0.86, count: 6, created_at: daysAgo(1) },
    { id: 8, question: "List Logistics names approaching the sector concentration limit.", intent: "concentration", confidence: 0.83, count: 3, created_at: daysAgo(2) },
    { id: 7, question: "Which companies have improving cash flow versus last quarter?", intent: "improvement", confidence: 0.79, count: 7, created_at: daysAgo(3) },
    { id: 6, question: "Show expected credit loss by rating band.", intent: "ecl_by_rating", confidence: 0.9, count: 6, created_at: daysAgo(4) },
    { id: 5, question: "Which accounts have open critical alerts right now?", intent: "open_alerts", confidence: 0.92, count: 3, created_at: daysAgo(5) },
  ],
};

// ---------------------------------------------------------------------------
// M13 — Model Governance dashboard
// ---------------------------------------------------------------------------

const governanceDashboard = {
  model_keys: ["pd_xgb", "lgd_glm", "ead_ccf", "fraud_iforest", "ews_gbm"],
  total_versions: 23,
  validations: {
    total: 41,
    by_status: { passed: 32, failed: 5, pending: 4 },
  },
  by_production_status: { production: 5, staging: 3, development: 8, archived: 7 },
  by_approval_status: { approved: 14, pending: 5, rejected: 2, draft: 2 },
  recent_events: [
    { event_type: "validated", model_key: "pd_xgb", version: 7, detail: "AUC 0.842, KS 0.53 — passed all gates.", at: daysAgo(0) },
    { event_type: "promoted", model_key: "ews_gbm", version: 4, detail: "Promoted challenger to champion after 30-day shadow.", at: daysAgo(1) },
    { event_type: "registered", model_key: "lgd_glm", version: 3, detail: "New version registered with recalibrated downturn LGD.", at: daysAgo(2) },
    { event_type: "rejected", model_key: "fraud_iforest", version: 6, detail: "Failed stability gate; PSI 0.31 above threshold.", at: daysAgo(3) },
    { event_type: "deployed", model_key: "pd_xgb", version: 6, detail: "Rolled out to production inference cluster.", at: daysAgo(5) },
    { event_type: "flagged", model_key: "ead_ccf", version: 2, detail: "Drift monitor raised feature-distribution alert.", at: daysAgo(7) },
  ],
};

// ---------------------------------------------------------------------------
// M14 — Data lake catalog + stats
// ---------------------------------------------------------------------------

const datalakeCatalog = {
  total_datasets: 8,
  datasets: [
    { name: "financials_spread", source: "core_banking", records: 184_320, updated_at: daysAgo(0), format: "delta" },
    { name: "gst_returns", source: "gstn_connector", records: 96_540, updated_at: daysAgo(0), format: "parquet" },
    { name: "mca_filings", source: "mca_connector", records: 41_210, updated_at: daysAgo(1), format: "parquet" },
    { name: "bureau_pulls", source: "bureau_connector", records: 63_880, updated_at: daysAgo(1), format: "parquet" },
    { name: "bank_statements", source: "account_aggregator", records: 512_640, updated_at: daysAgo(0), format: "delta" },
    { name: "monitoring_signals", source: "monitoring_engine", records: 28_470, updated_at: daysAgo(0), format: "delta" },
    { name: "news_events", source: "news_connector", records: 74_910, updated_at: daysAgo(2), format: "json" },
    { name: "market_prices", source: "market_data", records: 220_150, updated_at: daysAgo(0), format: "parquet" },
  ],
};

const datalakeStats = {
  total_datasets: 8,
  total_records: 1_222_120,
  last_ingestion: daysAgo(0),
  ingestion_runs_30d: 214,
  by_source: {
    core_banking: 184_320,
    gstn_connector: 96_540,
    mca_connector: 41_210,
    bureau_connector: 63_880,
    account_aggregator: 512_640,
    monitoring_engine: 28_470,
    news_connector: 74_910,
    market_data: 220_150,
  },
  monthly_volume: MONTHS_12.map((month, i) => ({
    month,
    records: 78_000 + i * 9_400 + (i % 3) * 5_200,
  })),
};

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

/** path-suffix → sample response factory (fresh object each call). */
export const AUTO_FIXTURES: Record<string, () => unknown> = {
  // Knowledge Graph
  "/api/ai/graph/stats": () => clone(graphStats),
  "/api/ai/graph/network": () => graphNetwork(),

  // Real-Time Risk Monitoring
  "/api/ai/monitoring/signals": () => clone(monitoringSignals),
  "/api/ai/monitoring/sources": () => clone(monitoringSources),

  // Alerts
  "/api/ai/alerts/summary": () => clone(alertSummary),
  "/api/ai/alerts": () => clone(alerts),

  // Early Warning
  "/api/ai/ews/catalog": () => clone(ewsCatalog),
  "/api/ai/ews/history": () => clone(ewsHistory),

  // Copilot
  "/api/ai/copilot/provider": () => clone(copilotProvider),

  // Simulation
  "/api/ai/simulation/scenarios": () => clone(simulationScenarios),

  // Stress testing
  "/api/ai/stress/scenarios": () => clone(stressScenarios),
  "/api/ai/stress/compare": () => clone(stressCompare),

  // Portfolio optimization
  "/api/ai/portfolio/analysis": () => portfolioAnalysis(),

  // RM Workspace (representative company references)
  ...Object.fromEntries(
    RM_REFS.map((ref) => [`/api/ai/rm/workspace/${ref}`, () => rmWorkspace(ref)]),
  ),

  // Command Center (one key per persona; path ends with the persona)
  "/api/ai/command/personas": () => ({ personas: [...PERSONAS] }),
  ...Object.fromEntries(
    PERSONAS.map((p) => [`/api/ai/command/dashboard/${p}`, () => commandDashboard(p)]),
  ),

  // NL Analytics
  "/api/ai/nlq/history": () => clone(nlqHistory),

  // Model Governance
  "/api/ai/governance/dashboard": () => clone(governanceDashboard),

  // Data lake
  "/api/ai/datalake/catalog": () => clone(datalakeCatalog),
  "/api/ai/datalake/stats": () => clone(datalakeStats),
};
