/**
 * Demo Mode sample datasets for three enterprise platform surfaces:
 *   • Integrations  (Phase 7 banking-ecosystem — /api/integrations, /api/collateral,
 *                    /api/customer360, /api/platform)
 *   • ML Platform   (Phase 6 — /api/ml/*)
 *   • Security      (Stage 4 — /api/sec/*)
 *
 * Keyed by request-path suffix, matched by the interceptor in ./index.ts via
 * `clean === key || clean.endsWith(key)`. Every factory returns a FRESH object
 * literal so callers can mutate without corrupting the fixture.
 *
 * Companies, bankers and financials are drawn from the canonical demo book in
 * ./enterprise-data so the SAME borrowers (Reliance, Tata Steel, Infosys …) stay
 * consistent across every dashboard. Monetary values are absolute Indian Rupees
 * (₹); `cr(742)` === ₹742 Cr.
 *
 * NOTE: to activate these, PLATFORM_FIXTURES must be merged into the registry the
 * interceptor iterates (spread into DEMO_FIXTURES in ./fixtures.ts, or into the
 * loop in ./index.ts). This file only defines the data.
 */

import {
  COMPANIES,
  companyByRef,
  cr,
  daysAgo,
  ebitdaOf,
  MONTHS_12,
} from "./enterprise-data";

// ===========================================================================
// INTEGRATIONS — connector framework, observability, collateral, customer 360,
// sync, open API platform.
// ===========================================================================

interface ConnectorSpec {
  key: string;
  category: string;
  token: string; // key.split("_")[0] used for health lookup on the connectors page
  mode: "mock" | "sandbox" | "production";
  health: "healthy" | "degraded" | "unavailable";
  calls: number;
  successRate: number;
  retries: number;
  avgMs: number;
  p95Ms: number;
  cacheHits: number;
}

const CONNECTOR_SPECS: ConnectorSpec[] = [
  { key: "gst_returns", category: "tax", token: "gst", mode: "production", health: "healthy", calls: 4821, successRate: 0.994, retries: 63, avgMs: 214, p95Ms: 486, cacheHits: 1290 },
  { key: "mca_registry", category: "registry", token: "mca", mode: "production", health: "healthy", calls: 2610, successRate: 0.991, retries: 41, avgMs: 268, p95Ms: 552, cacheHits: 742 },
  { key: "cibil_bureau", category: "bureau", token: "cibil", mode: "production", health: "healthy", calls: 3574, successRate: 0.997, retries: 28, avgMs: 331, p95Ms: 690, cacheHits: 512 },
  { key: "experian_bureau", category: "bureau", token: "experian", mode: "sandbox", health: "degraded", calls: 986, successRate: 0.962, retries: 74, avgMs: 402, p95Ms: 1120, cacheHits: 138 },
  { key: "account_aggregator", category: "account_aggregator", token: "account", mode: "production", health: "healthy", calls: 5218, successRate: 0.989, retries: 96, avgMs: 289, p95Ms: 604, cacheHits: 1874 },
  { key: "bank_statement", category: "banking", token: "bank", mode: "production", health: "healthy", calls: 3960, successRate: 0.985, retries: 88, avgMs: 244, p95Ms: 528, cacheHits: 1461 },
  { key: "erp_ledger", category: "erp", token: "erp", mode: "sandbox", health: "healthy", calls: 1487, successRate: 0.978, retries: 52, avgMs: 356, p95Ms: 812, cacheHits: 402 },
  { key: "payments_gateway", category: "payments", token: "payments", mode: "production", health: "healthy", calls: 2743, successRate: 0.996, retries: 19, avgMs: 176, p95Ms: 372, cacheHits: 690 },
];

function connectorsFixture() {
  return {
    connectors: CONNECTOR_SPECS.map((c) => ({
      key: c.key,
      category: c.category,
      modes: ["mock", "sandbox", "production"],
    })),
    configs: CONNECTOR_SPECS.map((c) => ({
      connector_key: c.key,
      category: c.category,
      provider_mode: c.mode,
      enabled: true,
      config: {},
      has_credentials: c.mode !== "mock",
      rate_limit_per_sec: 20,
      timeout_seconds: 15,
      updated_at: daysAgo(2),
    })),
  };
}

function observabilityOverviewFixture() {
  const totalCalls = CONNECTOR_SPECS.reduce((a, c) => a + c.calls, 0);
  const totalCache = CONNECTOR_SPECS.reduce((a, c) => a + c.cacheHits, 0);
  const weightedSuccess =
    CONNECTOR_SPECS.reduce((a, c) => a + c.successRate * c.calls, 0) / totalCalls;
  return {
    connectors: CONNECTOR_SPECS.map((c) => ({
      connector_key: c.key,
      category: c.category,
      modes_available: ["mock", "sandbox", "production"],
      active_mode: c.mode,
      enabled: true,
      recent: { calls: c.calls, failures: Math.round(c.calls * (1 - c.successRate)) },
    })),
    live_metrics: CONNECTOR_SPECS.map((c) => {
      const failures = Math.round(c.calls * (1 - c.successRate));
      return {
        category: c.category,
        provider: `${c.mode}_${c.token}`,
        calls: c.calls,
        successes: c.calls - failures,
        failures,
        retries: c.retries,
        cache_hits: c.cacheHits,
        circuit_rejections: c.health === "degraded" ? 12 : 0,
        success_rate: c.successRate,
        failure_rate: +(1 - c.successRate).toFixed(4),
        avg_latency_ms: c.avgMs,
        max_latency_ms: c.p95Ms + 340,
        p50_latency_ms: Math.round(c.avgMs * 0.82),
        p95_latency_ms: c.p95Ms,
      };
    }),
    totals: {
      calls: totalCalls,
      successes: Math.round(totalCalls * weightedSuccess),
      failures: Math.round(totalCalls * (1 - weightedSuccess)),
      retries: CONNECTOR_SPECS.reduce((a, c) => a + c.retries, 0),
      cache_hits: totalCache,
      success_rate: +weightedSuccess.toFixed(4),
    },
  };
}

function observabilityHealthFixture() {
  return {
    health: CONNECTOR_SPECS.map((c) => ({
      provider: `${c.mode}_${c.token}`,
      category: c.category,
      mode: c.mode,
      status: c.health,
      detail:
        c.health === "healthy"
          ? "All probes passing; circuit closed."
          : c.health === "degraded"
            ? "Elevated latency and retry rate; circuit half-open."
            : "Upstream unreachable; circuit open.",
      circuit_state:
        c.health === "degraded" ? "half_open" : c.health === "unavailable" ? "open" : "closed",
      latency_ms: c.avgMs,
    })),
  };
}

// -- Collateral -------------------------------------------------------------

function collateralTypesFixture() {
  return {
    types: [
      { type: "real_estate", display: "Real Estate", default_haircut: 0.25, liquidity: "low" },
      { type: "plant_machinery", display: "Plant & Machinery", default_haircut: 0.4, liquidity: "low" },
      { type: "vehicles", display: "Vehicles", default_haircut: 0.35, liquidity: "medium" },
      { type: "inventory", display: "Inventory / Stock", default_haircut: 0.5, liquidity: "medium" },
      { type: "receivables", display: "Trade Receivables", default_haircut: 0.5, liquidity: "medium" },
      { type: "fixed_deposit", display: "Fixed Deposit", default_haircut: 0.05, liquidity: "high" },
      { type: "bank_guarantee", display: "Bank Guarantee", default_haircut: 0.1, liquidity: "high" },
      { type: "insurance", display: "Insurance / Assignment", default_haircut: 0.3, liquidity: "medium" },
    ],
  };
}

const RELIANCE = companyByRef("APP-2026-4201") ?? COMPANIES[0]; // ENT-001 → Reliance Industries

interface CollatSpec {
  id: number;
  type: string;
  display: string;
  description: string;
  marketCr: number;
  haircut: number;
  loanCr: number;
}

const COLLATERAL_ITEMS: CollatSpec[] = [
  { id: 9101, type: "real_estate", display: "Real Estate", description: "Corporate HQ — Maker Chambers IV, Nariman Point, Mumbai", marketCr: 480, haircut: 0.25, loanCr: 300 },
  { id: 9102, type: "real_estate", display: "Real Estate", description: "Industrial land parcel — Jamnagar SEZ, Gujarat", marketCr: 220, haircut: 0.3, loanCr: 120 },
  { id: 9103, type: "plant_machinery", display: "Plant & Machinery", description: "Refinery process units — Jamnagar Complex", marketCr: 360, haircut: 0.4, loanCr: 180 },
  { id: 9104, type: "plant_machinery", display: "Plant & Machinery", description: "Petrochemical cracker unit & downstream trains", marketCr: 180, haircut: 0.4, loanCr: 90 },
  { id: 9105, type: "receivables", display: "Trade Receivables", description: "Domestic fuel-retail receivables — hypothecated", marketCr: 140, haircut: 0.5, loanCr: 52 },
  { id: 9106, type: "fixed_deposit", display: "Fixed Deposit", description: "Lien-marked fixed deposit — State Bank of India", marketCr: 60, haircut: 0.05, loanCr: 40 },
];

function collateralEntityFixture() {
  const items = COLLATERAL_ITEMS.map((s) => {
    const market = cr(s.marketCr);
    const realizable = cr(Math.round(s.marketCr * (1 - s.haircut)));
    const loan = cr(s.loanCr);
    return {
      id: s.id,
      collateral_type: s.type,
      display: s.display,
      description: s.description,
      market_value: market,
      haircut_pct: s.haircut,
      realizable_value: realizable,
      loan_amount: loan,
      ltv: +(loan / market).toFixed(3),
      coverage_ratio: +(realizable / loan).toFixed(3),
      status: "active",
    };
  });
  const totalMarket = items.reduce((a, i) => a + i.market_value, 0);
  const totalRealizable = items.reduce((a, i) => a + i.realizable_value, 0);
  const exposure = RELIANCE.outstanding;
  const byType: Record<string, number> = {};
  for (const i of items) byType[i.collateral_type] = (byType[i.collateral_type] ?? 0) + 1;
  return {
    summary: {
      item_count: items.length,
      total_market_value: totalMarket,
      total_realizable_value: totalRealizable,
      total_exposure: exposure,
      coverage_ratio: +(totalRealizable / exposure).toFixed(3),
      secured: totalRealizable >= exposure,
      by_type: byType,
    },
    items,
  };
}

// -- Customer 360 (default lookup GSTIN 27ABCDE1234F1Z5 → Reliance) ----------

function customer360Fixture() {
  const c = RELIANCE;
  const collateral = collateralEntityFixture();
  return {
    entity_ref: "27ABCDE1234F1Z5",
    application: {
      reference: c.ref,
      company_name: c.name,
      sector: c.sector,
      requested_amount: c.exposure,
      status: c.status,
      lead_bank: "State Bank of India",
    },
    assessment: {
      internal_rating: c.rating,
      blended_score: c.score,
      risk_band: c.risk,
      pd_through_the_cycle: 0.0008,
      lgd: c.lgd,
      recommendation: "Maintain — investment grade, ample debt-service headroom.",
    },
    gst: {
      gstin: "27ABCDE1234F1Z5",
      legal_name: c.name,
      registration_status: "Active",
      returns_filed_12m: 12,
      filing_compliance: "On-time",
      annual_turnover: c.revenue,
      last_return: "GSTR-3B · Jul 2026",
    },
    mca: {
      cin: "L17110MH1973PLC019786",
      incorporation_date: "1973-05-08",
      company_status: "Active",
      directors: 11,
      authorized_capital: cr(1400),
      paid_up_capital: cr(676),
      open_charges: 8,
    },
    bureau: {
      provider: "CIBIL Commercial",
      commercial_score: 842,
      rating: c.rating,
      total_outstanding: c.debt,
      dpd_30plus_12m: 0,
      enquiries_6m: 4,
    },
    erp: {
      source: "SAP S/4HANA",
      revenue: c.revenue,
      ebitda: ebitdaOf(c),
      receivables: cr(612),
      payables: cr(488),
      inventory: cr(540),
    },
    payments: {
      monthly_txn_volume: cr(1240),
      success_rate: 0.994,
      avg_settlement_delay_days: 1.2,
      counterparty_risk: "Low",
      bounce_rate: 0.004,
    },
    bank_analytics: {
      primary_bank: "State Bank of India",
      avg_monthly_balance: cr(318),
      net_cash_flow_12m: cr(1420),
      bank_health_score: 91,
      liquidity_trend: "Improving",
      cheque_bounces_12m: 0,
    },
    collateral,
    relationship_network: {
      nodes: [
        { id: "reliance", label: c.name, type: "borrower" },
        { id: "ril_retail", label: "Reliance Retail Ventures", type: "subsidiary" },
        { id: "ril_jio", label: "Jio Platforms Ltd", type: "subsidiary" },
        { id: "sbi", label: "State Bank of India", type: "lender" },
        { id: "dir_1", label: "Board Director", type: "director" },
        { id: "supplier_1", label: "Bharat Petroleum (counterparty)", type: "counterparty" },
      ],
      edges: [
        { source: "reliance", target: "ril_retail", relation: "holds" },
        { source: "reliance", target: "ril_jio", relation: "holds" },
        { source: "sbi", target: "reliance", relation: "lends_to" },
        { source: "dir_1", target: "reliance", relation: "director_of" },
        { source: "reliance", target: "supplier_1", relation: "trades_with" },
      ],
      node_count: 6,
      edge_count: 5,
    },
    timeline: [
      { at: daysAgo(0), type: "monitoring", detail: "Quarterly covenant test passed — Net debt/EBITDA 1.9x vs 3.5x cap." },
      { at: daysAgo(3), type: "gst_import", detail: "GSTR-3B for Jul 2026 imported; filing on time." },
      { at: daysAgo(9), type: "bureau_pull", detail: "CIBIL Commercial refreshed — score 842, no delinquencies." },
      { at: daysAgo(14), type: "bank_analytics", detail: "12-month AA statement analysed; bank-health score 91." },
      { at: daysAgo(22), type: "collateral", detail: "Jamnagar plant & machinery revalued at ₹360 Cr." },
      { at: daysAgo(38), type: "assessment", detail: "Annual review completed; rating reaffirmed AAA." },
      { at: daysAgo(61), type: "disbursement", detail: "Working-capital tranche of ₹120 Cr disbursed." },
      { at: daysAgo(96), type: "approval", detail: "Credit committee sanctioned ₹920 Cr facility." },
    ],
    completeness: {
      sources_present: 8,
      sources_total: 9,
      score: 0.89,
      detail: {
        assessment: true,
        gst: true,
        mca: true,
        bureau: true,
        erp: true,
        payments: true,
        bank_analytics: true,
        collateral: true,
        monitoring: false,
      },
    },
  };
}

// -- Portfolio synchronization ----------------------------------------------

function syncJobsFixture() {
  const mk = (
    id: number,
    sync_type: string,
    status: string,
    processed: number,
    skipped: number,
    conflicts: number,
    failed: number,
    ageDays: number,
  ) => ({
    id,
    sync_type,
    connectors: ["gst", "mca", "bureau", "erp", "payments"],
    status,
    stats: { processed, skipped, conflicts, failed },
    conflicts: Array.from({ length: conflicts }, (_, i) => ({
      entity_ref: `ENT-${100 + i}`,
      field: ["turnover", "rating", "outstanding"][i % 3],
      resolution: "kept_latest",
    })),
    total: processed + skipped + failed,
    processed,
    failed,
    created_at: daysAgo(ageDays),
  });
  return {
    jobs: [
      mk(5108, "full", "completed", 128, 0, 3, 0, 0),
      mk(5107, "incremental", "completed", 46, 82, 1, 0, 1),
      mk(5106, "incremental", "partial", 61, 54, 4, 5, 2),
      mk(5105, "full", "completed", 132, 0, 2, 0, 4),
      mk(5104, "incremental", "running", 38, 47, 0, 0, 0),
      mk(5103, "full", "failed", 74, 0, 6, 18, 6),
      mk(5102, "incremental", "completed", 52, 76, 1, 0, 8),
    ],
  };
}

// -- Open API platform ------------------------------------------------------

function apiKeysFixture() {
  return {
    keys: [
      { id: 71, name: "Partner Integration — HDFC Originations", key_prefix: "ak_live_9f2a", scopes: ["read", "write"], active: true, rate_limit_per_min: 600 },
      { id: 72, name: "Bureau Pull Service", key_prefix: "ak_live_3c7b", scopes: ["read"], active: true, rate_limit_per_min: 300 },
      { id: 73, name: "Treasury Analytics Export", key_prefix: "ak_live_a51d", scopes: ["read"], active: true, rate_limit_per_min: 120 },
      { id: 74, name: "Fintech Sandbox — Razorpay", key_prefix: "ak_test_6e04", scopes: ["read", "write"], active: true, rate_limit_per_min: 60 },
      { id: 75, name: "Legacy ETL (decommissioned)", key_prefix: "ak_live_0b88", scopes: ["read", "write"], active: false, rate_limit_per_min: 600 },
      { id: 76, name: "Mobile RM App", key_prefix: "ak_live_ef19", scopes: ["read", "write"], active: true, rate_limit_per_min: 240 },
    ],
  };
}

function webhooksFixture() {
  return {
    subscriptions: [
      { id: 21, url: "https://originations.hdfc.internal/hooks/credit-decision", events: ["decision.approved", "decision.rejected"], active: true, has_secret: true },
      { id: 22, url: "https://risk.icici.internal/hooks/covenant-breach", events: ["monitoring.alert.raised", "covenant.breached"], active: true, has_secret: true },
      { id: 23, url: "https://treasury.sbi.internal/hooks/exposure-update", events: ["exposure.updated", "disbursement.completed"], active: true, has_secret: true },
      { id: 24, url: "https://partner.razorpay.dev/hooks/kyc", events: ["kyc.verified", "bureau.pulled"], active: false, has_secret: false },
      { id: 25, url: "https://ops.axis.internal/hooks/sync-complete", events: ["sync.completed", "sync.failed"], active: true, has_secret: true },
    ],
  };
}

function apiUsageFixture() {
  return {
    total_calls: 184_921,
    by_endpoint: {
      "GET /api/v1/entities": 61240,
      "POST /api/v1/assessments": 38915,
      "GET /api/v1/bureau/score": 29648,
      "POST /api/v1/collateral": 12084,
      "GET /api/v1/portfolio/exposure": 43034,
    },
    by_status: { "200": 178402, "201": 4126, "400": 1284, "401": 612, "429": 341, "500": 156 },
    avg_latency_ms: 148.6,
  };
}

// ===========================================================================
// ML PLATFORM — training, registry, serving, monitoring, drift, stress.
// ===========================================================================

function algorithmsFixture() {
  return {
    algorithms: [
      { algorithm: "logistic_regression", backend_available: true, default_hyperparameters: { C: 1.0, penalty: "l2", max_iter: 500 } },
      { algorithm: "xgboost", backend_available: true, default_hyperparameters: { n_estimators: 400, max_depth: 5, learning_rate: 0.05, subsample: 0.8 } },
      { algorithm: "lightgbm", backend_available: true, default_hyperparameters: { n_estimators: 500, num_leaves: 31, learning_rate: 0.05 } },
      { algorithm: "random_forest", backend_available: true, default_hyperparameters: { n_estimators: 300, max_depth: 12 } },
      { algorithm: "gradient_boosting", backend_available: true, default_hyperparameters: { n_estimators: 250, max_depth: 3, learning_rate: 0.1 } },
      { algorithm: "decision_tree", backend_available: true, default_hyperparameters: { max_depth: 8, min_samples_leaf: 20 } },
      { algorithm: "neural_network", backend_available: false, default_hyperparameters: { hidden_layers: [64, 32], epochs: 50 } },
    ],
  };
}

const FEATURE_IMPORTANCES: Record<string, number> = {
  debt_service_coverage_ratio: 0.171,
  leverage_ratio: 0.142,
  interest_coverage_ratio: 0.108,
  bureau_score: 0.096,
  ebitda_margin: 0.083,
  current_ratio: 0.071,
  revenue_growth: 0.058,
  gst_filing_compliance: 0.049,
  delinquency_history: 0.044,
  account_vintage_months: 0.042,
  working_capital_days: 0.038,
  sector_risk_score: 0.033,
  cash_flow_volatility: 0.028,
  promoter_holding: 0.021,
  external_rating_notch: 0.016,
};

interface ModelSpec {
  id: number;
  model_key: string;
  algorithm: string;
  version: number;
  approval_status: string;
  production_status: string;
  roc_auc: number;
  ks: number;
  gini: number;
  brier: number;
  precision: number;
  recall: number;
  f1: number;
  accuracy: number;
  author: string;
  trainedDaysAgo: number;
}

const MODEL_SPECS: ModelSpec[] = [
  { id: 301, model_key: "corporate_pd_xgboost", algorithm: "xgboost", version: 4, approval_status: "approved", production_status: "production", roc_auc: 0.938, ks: 0.671, gini: 0.876, brier: 0.0712, precision: 0.841, recall: 0.788, f1: 0.814, accuracy: 0.902, author: "Priya Menon", trainedDaysAgo: 12 },
  { id: 303, model_key: "corporate_pd_lightgbm", algorithm: "lightgbm", version: 2, approval_status: "approved", production_status: "staging", roc_auc: 0.931, ks: 0.658, gini: 0.862, brier: 0.0741, precision: 0.833, recall: 0.779, f1: 0.805, accuracy: 0.896, author: "Priya Menon", trainedDaysAgo: 6 },
  { id: 304, model_key: "sme_pd_xgboost", algorithm: "xgboost", version: 3, approval_status: "pending", production_status: "none", roc_auc: 0.912, ks: 0.624, gini: 0.824, brier: 0.0863, precision: 0.802, recall: 0.744, f1: 0.772, accuracy: 0.878, author: "Arjun Rao", trainedDaysAgo: 3 },
  { id: 305, model_key: "sme_pd_lightgbm", algorithm: "lightgbm", version: 1, approval_status: "draft", production_status: "none", roc_auc: 0.898, ks: 0.601, gini: 0.796, brier: 0.0918, precision: 0.788, recall: 0.731, f1: 0.758, accuracy: 0.869, author: "Arjun Rao", trainedDaysAgo: 1 },
  { id: 306, model_key: "retail_pd_logistic", algorithm: "logistic_regression", version: 2, approval_status: "approved", production_status: "staging", roc_auc: 0.884, ks: 0.572, gini: 0.768, brier: 0.0994, precision: 0.761, recall: 0.708, f1: 0.734, accuracy: 0.857, author: "Neha Gupta", trainedDaysAgo: 18 },
  { id: 302, model_key: "corporate_pd_xgboost", algorithm: "xgboost", version: 3, approval_status: "approved", production_status: "archived", roc_auc: 0.926, ks: 0.643, gini: 0.852, brier: 0.0774, precision: 0.826, recall: 0.771, f1: 0.798, accuracy: 0.891, author: "Priya Menon", trainedDaysAgo: 74 },
];

function modelMetrics(s: ModelSpec) {
  return {
    roc_auc: s.roc_auc,
    ks_statistic: s.ks,
    gini: s.gini,
    brier_score: s.brier,
    accuracy: s.accuracy,
    precision: s.precision,
    recall: s.recall,
    f1: s.f1,
  };
}

function modelBase(s: ModelSpec) {
  return {
    id: s.id,
    model_key: s.model_key,
    name: `${s.model_key} v${s.version}`,
    algorithm: s.algorithm,
    version: s.version,
    is_current: s.production_status === "production" || s.production_status === "staging",
    dataset_id: 5001,
    parent_model_id: null,
    hyperparameters: { n_estimators: 400, max_depth: 5, learning_rate: 0.05 },
    metrics: modelMetrics(s),
    feature_set_version: "fs_v7.2",
    feature_count: 42,
    training_time_seconds: 38.4,
    author: s.author,
    approval_status: s.approval_status,
    production_status: s.production_status,
    trained_at: daysAgo(s.trainedDaysAgo),
    created_at: daysAgo(s.trainedDaysAgo),
  };
}

function modelsFixture() {
  return { models: MODEL_SPECS.map(modelBase) };
}

// Detail for the production champion (id 301) — feature-importance page auto-loads it.
function championModelFixture() {
  const s = MODEL_SPECS[0];
  return {
    ...modelBase(s),
    feature_names: Object.keys(FEATURE_IMPORTANCES),
    report: {
      algorithm: s.algorithm,
      metrics: modelMetrics(s),
      cross_validation: {
        scoring: "roc_auc",
        scores: [0.934, 0.941, 0.929, 0.938, 0.936],
        mean: 0.9356,
        std: 0.0044,
      },
      feature_importances: { ...FEATURE_IMPORTANCES },
      dataset: {
        name: "corporate_book_2026Q2",
        n_rows: 48210,
        positive_rate: 0.062,
        content_hash: "a3f9c1e",
      },
      training_time_seconds: 38.4,
      n_train: 38568,
      n_test: 9642,
    },
  };
}

function monitoringSummaryFixture() {
  return {
    prediction_volume: {
      total: 28914,
      success: 28786,
      failed: 128,
      cached: 6142,
      by_type: { single: 21460, batch: 6820, what_if: 634 },
    },
    success_rate: 0.9956,
    failure_rate: 0.0044,
    latency_ms: { count: 28914, avg: 42.6, p50: 31, p95: 118, p99: 214, max: 512 },
    model_confidence: { avg: 0.871, low_confidence_share: 0.058 },
    pd_distribution: { avg: 0.061, p50: 0.038, p95: 0.214 },
    class_distribution: {
      approved: 21908,
      declined: 7006,
      approval_rate: 0.7577,
      grade_distribution: { A: 9420, B: 8611, C: 6248, D: 3105, E: 1530 },
    },
    data_quality: { populated_rate: 0.972, missing_rate: 0.028 },
  };
}

function servingHistoryFixture() {
  const grades = ["A", "A", "B", "B", "C", "C", "D", "E"];
  const modes = ["real_time", "real_time", "batch", "cached"];
  const preds = COMPANIES.slice(0, 16).map((c, i) => {
    const pd = +Math.min(0.42, Math.max(0.004, (850 - c.score) / 1400)).toFixed(4);
    return {
      id: 90210 - i,
      model_key: c.sector === "SaaS" || c.sector === "FinTech" || c.sector === "Retail" ? "sme_pd_xgboost" : "corporate_pd_xgboost",
      model_version: 4,
      inference_type: i % 4 === 2 ? "batch" : "single",
      entity_id: c.id,
      probability_of_default: pd,
      risk_score: c.score,
      risk_grade: grades[Math.min(grades.length - 1, Math.floor(pd * 20))],
      approval: c.status !== "rejected",
      inference_mode: modes[i % modes.length],
      latency_ms: 22 + (i % 7) * 11,
      cached: i % 4 === 3,
      success: true,
      created_at: daysAgo(Math.floor(i / 2)),
    };
  });
  return { predictions: preds };
}

// Performance trend for the champion (id 301) — 6 monthly out-of-sample evaluations.
function performanceTrendFixture() {
  const s = MODEL_SPECS[0];
  const aucSeries = [0.921, 0.924, 0.929, 0.933, 0.936, 0.938];
  const trend = MONTHS_12.slice(6).map((m, i) => ({
    id: 6001 + i,
    evaluated_at: daysAgo((5 - i) * 30),
    n_samples: 4200 + i * 180,
    metrics: {
      roc_auc: aucSeries[i],
      ks_statistic: +(s.ks - 0.03 + i * 0.006).toFixed(3),
      gini: +(2 * aucSeries[i] - 1).toFixed(3),
      brier_score: +(s.brier + 0.006 - i * 0.0012).toFixed(4),
      precision: +(s.precision - 0.02 + i * 0.004).toFixed(3),
      recall: +(s.recall - 0.03 + i * 0.006).toFixed(3),
      f1: +(s.f1 - 0.025 + i * 0.005).toFixed(3),
      accuracy: +(s.accuracy - 0.015 + i * 0.003).toFixed(3),
    },
    business_kpis: {
      approval_rate: +(0.74 + i * 0.004).toFixed(3),
      observed_default_rate: +(0.071 - i * 0.002).toFixed(3),
      bad_rate_in_approved: +(0.028 - i * 0.001).toFixed(3),
      expected_loss: cr(148 - i * 3),
      expected_loss_per_obligor: Math.round(cr(148 - i * 3) / (4200 + i * 180)),
    },
    note: `${m} 2026 out-of-sample evaluation`,
  }));
  return { trend };
}

function driftHistoryFixture() {
  const mk = (
    id: number,
    model_key: string,
    model_id: number,
    report_type: string,
    psi: number,
    n_drifted: number,
    missing: number,
    drifted: string[],
    breached: boolean,
    ageDays: number,
  ) => ({
    id,
    model_id,
    model_key,
    report_type,
    psi_overall: psi,
    drift_score: +(psi * 1.6).toFixed(3),
    n_features: 42,
    n_drifted,
    missing_feature_rate: missing,
    drifted_features: drifted,
    threshold: 0.2,
    breached,
    created_at: daysAgo(ageDays),
  });
  return {
    reports: [
      mk(7101, "corporate_pd_xgboost", 301, "feature", 0.086, 3, 0.012, ["revenue_growth", "cash_flow_volatility", "working_capital_days"], false, 0),
      mk(7100, "corporate_pd_xgboost", 301, "prediction", 0.142, 6, 0.021, ["leverage_ratio", "ebitda_margin", "sector_risk_score", "bureau_score"], false, 7),
      mk(7099, "sme_pd_xgboost", 304, "feature", 0.263, 11, 0.048, ["gst_filing_compliance", "delinquency_history", "current_ratio", "revenue_growth"], true, 9),
      mk(7098, "retail_pd_logistic", 306, "feature", 0.191, 5, 0.034, ["account_vintage_months", "promoter_holding", "cash_flow_volatility"], false, 14),
      mk(7097, "corporate_pd_lightgbm", 303, "prediction", 0.118, 4, 0.018, ["interest_coverage_ratio", "leverage_ratio", "ebitda_margin"], false, 21),
      mk(7096, "sme_pd_lightgbm", 305, "feature", 0.312, 14, 0.061, ["gst_filing_compliance", "working_capital_days", "sector_risk_score", "delinquency_history"], true, 28),
      mk(7095, "corporate_pd_xgboost", 301, "feature", 0.074, 2, 0.009, ["revenue_growth", "cash_flow_volatility"], false, 35),
    ],
  };
}

function stressScenariosFixture() {
  return {
    scenarios: [
      { name: "baseline_recession", label: "Baseline Recession", description: "Broad-based GDP contraction with rising unemployment; leverage and coverage ratios deteriorate across the book." },
      { name: "interest_rate_shock", label: "Interest-Rate Shock", description: "Policy repo rate rises 250 bps; interest-coverage and debt-service ratios compress for floating-rate borrowers." },
      { name: "commodity_price_spike", label: "Commodity Price Spike", description: "Sharp input-cost inflation squeezes EBITDA margins in manufacturing, FMCG and energy-intensive sectors." },
      { name: "inr_depreciation", label: "INR Depreciation", description: "Rupee weakens 12% vs USD; unhedged foreign-currency borrowers face higher servicing and translation losses." },
      { name: "liquidity_crunch", label: "Liquidity Crunch", description: "System-wide funding stress lengthens working-capital cycles and raises refinancing risk for weaker credits." },
      { name: "sector_downturn_realestate", label: "Real-Estate Sector Downturn", description: "Property-linked collateral values fall 25%; LTV and coverage ratios weaken for secured exposures." },
      { name: "gdp_slowdown_mild", label: "Mild GDP Slowdown", description: "Growth decelerates 150 bps below trend; modest revenue-growth and demand softening across cyclicals." },
    ],
  };
}

// ===========================================================================
// SECURITY & COMPLIANCE — posture dashboard + compliance matrix.
// ===========================================================================

function securityDashboardFixture() {
  return {
    posture: {
      overall_score: 87.4,
      grade: "A-",
      dimensions: {
        application_security: 88,
        identity_and_access: 92,
        data_protection: 90,
        network_security: 85,
        threat_detection: 83,
        vulnerability_management: 79,
        compliance: 91,
        supply_chain: 76,
        ai_ml_security: 82,
      },
    },
    findings: {
      open_total: 34,
      by_severity: { critical: 1, high: 6, medium: 14, low: 9, info: 4 },
    },
    risk_register: {
      open_total: 12,
      top: [
        { title: "Third-party bureau connector lacks mTLS certificate pinning", inherent_score: 20, inherent_level: "high" },
        { title: "Privileged admin sessions without hardware MFA", inherent_score: 16, inherent_level: "high" },
        { title: "PII retention exceeds RBI-mandated purge window in analytics store", inherent_score: 15, inherent_level: "high" },
        { title: "Container base image with unpatched CVE in build pipeline", inherent_score: 12, inherent_level: "medium" },
        { title: "Model-inference endpoint without per-tenant rate limiting", inherent_score: 9, inherent_level: "medium" },
      ],
    },
    privacy: { open_requests: 7 },
    secrets: { insecure_critical: 0, total_secrets: 214, rotated_30d: 186 },
    sessions: { active_sessions: 142, devices: 318 },
    recent_scans: [
      { created_at: daysAgo(0), scan_type: "full", score: 87, grade: "A-", findings_count: 34, critical_count: 1 },
      { created_at: daysAgo(2), scan_type: "owasp", score: 89, grade: "A-", findings_count: 11, critical_count: 0 },
      { created_at: daysAgo(4), scan_type: "supply_chain", score: 76, grade: "B", findings_count: 9, critical_count: 0 },
      { created_at: daysAgo(6), scan_type: "ai_security", score: 82, grade: "B+", findings_count: 6, critical_count: 0 },
      { created_at: daysAgo(9), scan_type: "container", score: 79, grade: "B", findings_count: 8, critical_count: 1 },
      { created_at: daysAgo(13), scan_type: "tenant", score: 93, grade: "A", findings_count: 3, critical_count: 0 },
    ],
  };
}

function complianceMatrixFixture() {
  return {
    overall_readiness_score: 88,
    overall_readiness: "substantially_compliant",
    frameworks: [
      { name: "RBI Cyber Security Framework", score: 91, controls_total: 84, controls_met: 76 },
      { name: "ISO/IEC 27001:2022", score: 89, controls_total: 93, controls_met: 83 },
      { name: "SOC 2 Type II", score: 86, controls_total: 64, controls_met: 55 },
      { name: "PCI DSS v4.0", score: 82, controls_total: 78, controls_met: 64 },
      { name: "GDPR / DPDP Act 2023", score: 90, controls_total: 42, controls_met: 38 },
      { name: "NIST CSF 2.0", score: 87, controls_total: 106, controls_met: 92 },
    ],
  };
}

// ===========================================================================
// Registry — path-suffix → fresh-response factory.
// ===========================================================================

export const PLATFORM_FIXTURES: Record<string, () => unknown> = {
  // Integrations
  "/api/integrations/connectors": connectorsFixture,
  "/api/integrations/observability/overview": observabilityOverviewFixture,
  "/api/integrations/observability/health": observabilityHealthFixture,
  "/api/collateral/types": collateralTypesFixture,
  "/api/collateral/entities/ENT-001": collateralEntityFixture,
  "/api/customer360/entities/27ABCDE1234F1Z5": customer360Fixture,
  "/api/integrations/sync/jobs": syncJobsFixture,
  "/api/platform/keys": apiKeysFixture,
  "/api/platform/webhooks": webhooksFixture,
  "/api/platform/usage": apiUsageFixture,

  // ML platform
  "/api/ml/training/algorithms": algorithmsFixture,
  "/api/ml/registry/models": modelsFixture,
  "/api/ml/registry/models/301": championModelFixture,
  "/api/ml/monitoring/summary": monitoringSummaryFixture,
  "/api/ml/serving/history": servingHistoryFixture,
  "/api/ml/monitoring/performance/301/trend": performanceTrendFixture,
  "/api/ml/drift/history": driftHistoryFixture,
  "/api/ml/stress-ml/scenarios": stressScenariosFixture,

  // Security & compliance
  "/api/sec/posture/dashboard": securityDashboardFixture,
  "/api/sec/compliance/matrix": complianceMatrixFixture,
};
