/**
 * Demo Mode fixtures for the Advanced Financial Intelligence Platform (Track 3).
 *
 * Keyed by `/api/fin/*` request-path suffix. Every factory returns a FRESH
 * object literal so callers can mutate freely. All figures are grounded in the
 * canonical demo book (`enterprise-data.ts`) — the same real Indian corporates
 * (Reliance, Tata Steel, Infosys, …) appear consistently across Treasury,
 * Portfolio, Regulatory, ESG, Market, Forecast, Quant and Strategic views.
 *
 * Only on-load GET endpoints are covered (lists, dashboards, KPIs, catalogs,
 * types). Id-parameterised detail endpoints fire after a selection and are POST,
 * so they are intentionally omitted.
 *
 * Monetary values are absolute Indian Rupees (₹) via `cr()`; display strings use
 * the ₹-crore convention (e.g. "₹4,820 Cr").
 */

import { BOOK, COMPANIES, MONTHS_12, cr, daysAgo, eclOf, pdOf } from "./enterprise-data";

/** Absolute rupees → "₹N Cr" display string. */
const inr = (n: number) => "₹" + Math.round(n / 10_000_000).toLocaleString("en-IN") + " Cr";
const pct = (x: number) => (x * 100).toFixed(1) + "%";

// ---------------------------------------------------------------------------
// M1 Treasury
// ---------------------------------------------------------------------------

const treasuryKpis = () => ({
  liquidity_coverage_ratio: "138%",
  net_stable_funding_ratio: "121%",
  net_interest_margin: "3.4%",
  cash_position: inr(cr(4820)),
  high_quality_liquid_assets: inr(cr(6240)),
  funding_gap_30d: inr(cr(-310)),
  loan_to_deposit_ratio: "87%",
  cost_of_funds: "5.7%",
  wholesale_funding_ratio: "28%",
  intraday_liquidity_buffer: inr(cr(1180)),
});

const fundingSources = () => [
  { id: 1, name: "Retail Savings & Term Deposits", source_type: "deposit", amount: cr(4200), rate: 0.052 },
  { id: 2, name: "Bulk / Wholesale Deposits", source_type: "deposit", amount: cr(1850), rate: 0.071 },
  { id: 3, name: "Certificates of Deposit", source_type: "money_market", amount: cr(920), rate: 0.068 },
  { id: 4, name: "Interbank Call & Notice Money", source_type: "interbank", amount: cr(540), rate: 0.061 },
  { id: 5, name: "Tier-II Subordinated Bonds", source_type: "bond", amount: cr(760), rate: 0.083 },
  { id: 6, name: "Refinance — NABARD / SIDBI", source_type: "refinance", amount: cr(430), rate: 0.058 },
  { id: 7, name: "External Commercial Borrowing (USD)", source_type: "ecb", amount: cr(610), rate: 0.049 },
];

// ---------------------------------------------------------------------------
// M2 Portfolio
// ---------------------------------------------------------------------------

const portfolios = () => [
  { id: 1, key: "large-corp", name: "Large Corporate Book", portfolio_type: "corporate" },
  { id: 2, key: "mid-sme", name: "Mid-Market & SME", portfolio_type: "sme" },
  { id: 3, key: "infra-pf", name: "Infrastructure Project Finance", portfolio_type: "project_finance" },
  { id: 4, key: "wc-facilities", name: "Working Capital Facilities", portfolio_type: "working_capital" },
  { id: 5, key: "scf", name: "Supply Chain Finance", portfolio_type: "supply_chain" },
  { id: 6, key: "new-age", name: "Emerging Corporates & New-Age Tech", portfolio_type: "commercial" },
];

// ---------------------------------------------------------------------------
// M3 Regulatory (Basel III / IFRS 9)
// ---------------------------------------------------------------------------

const regulatoryDashboard = () => ({
  results: {
    crar: pct(BOOK.crar),
    tier1_capital_ratio: "13.1%",
    cet1_ratio: "12.2%",
    leverage_ratio: "7.9%",
    total_rwa: inr(cr(6120)),
    credit_rwa: inr(cr(5180)),
    market_rwa: inr(cr(540)),
    operational_rwa: inr(cr(400)),
    ecl_12m: inr(cr(99)),
    ecl_lifetime: inr(cr(143)),
    ecl_total: inr(BOOK.ecl_total),
    provision_coverage_ratio: pct(BOOK.provision_coverage),
    gross_npa_ratio: pct(BOOK.npa_ratio),
    net_npa_ratio: "0.9%",
    // nested objects are filtered out by the page (typeof v === "object")
    staging: { stage1_pct: 88.4, stage2_pct: 8.1, stage3_pct: 3.5 },
  },
});

// ---------------------------------------------------------------------------
// M4 Economic scenarios
// ---------------------------------------------------------------------------

const economicIndicators = () => ({
  indicators: [
    { id: 1, name: "Real GDP Growth (YoY)", value: "6.8%" },
    { id: 2, name: "CPI Inflation (YoY)", value: "4.9%" },
    { id: 3, name: "RBI Repo Rate", value: "6.25%" },
    { id: 4, name: "10Y G-Sec Yield", value: "6.94%" },
    { id: 5, name: "USD / INR", value: "83.7" },
    { id: 6, name: "Unemployment Rate", value: "7.1%" },
    { id: 7, name: "Index of Industrial Production (YoY)", value: "5.3%" },
    { id: 8, name: "Current Account Deficit (% GDP)", value: "1.2%" },
    { id: 9, name: "Bank Credit Growth (YoY)", value: "14.2%" },
  ],
});

const economicScenarios = () => ({
  scenarios: [
    { scenario_id: 1, name: "Baseline — RBI Consensus", scenario_type: "baseline" },
    { scenario_id: 2, name: "Adverse — Global Slowdown", scenario_type: "adverse" },
    { scenario_id: 3, name: "Severely Adverse — Stagflation Shock", scenario_type: "severely_adverse" },
    { scenario_id: 4, name: "Optimistic — Broad-based Recovery", scenario_type: "optimistic" },
    { scenario_id: 5, name: "Custom — Rate Spike + INR Depreciation", scenario_type: "custom" },
  ],
});

const economicScenarioTypes = () => ({
  scenario_types: ["optimistic", "baseline", "adverse", "severely_adverse", "custom"],
  labels: {
    optimistic: "Optimistic",
    baseline: "Baseline",
    adverse: "Adverse",
    severely_adverse: "Severely Adverse",
    custom: "Custom",
  },
});

// ---------------------------------------------------------------------------
// M5 ESG
// ---------------------------------------------------------------------------

const esgList = () => ({
  assessments: COMPANIES.slice(0, 10).map((c, i) => ({
    esg_id: i + 1,
    subject_ref: c.ref,
    name: c.name,
    industry: c.sector,
    esg_score: c.esg,
    environmental: Math.max(0, c.esg - 6),
    social: Math.min(100, c.esg + 2),
    governance: Math.min(100, c.esg + 4),
  })),
});

const esgPortfolio = () => {
  const rated = COMPANIES;
  const weighted = Math.round(rated.reduce((s, c) => s + c.esg, 0) / rated.length);
  return {
    weighted_esg_score: weighted,
    environmental: weighted - 5,
    social: weighted + 2,
    governance: weighted + 4,
    rated_exposure: inr(cr(6180)),
    coverage: "92%",
    carbon_intensity_tco2e_per_cr: 42.6,
    green_financing: inr(cr(1120)),
    green_share: "18%",
    climate_var_pct: 3.8,
    distribution: { leaders: 6, average: 9, laggards: 5 },
    by_band: [
      { band: "Leader (A)", count: 6, exposure: inr(cr(2340)) },
      { band: "Average (B)", count: 9, exposure: inr(cr(2860)) },
      { band: "Laggard (C)", count: 5, exposure: inr(cr(980)) },
    ],
    top_performers: COMPANIES.filter((c) => c.esg >= 78).slice(0, 4).map((c) => ({ name: c.name, esg: c.esg })),
    laggards: [...COMPANIES].sort((a, b) => a.esg - b.esg).slice(0, 4).map((c) => ({ name: c.name, esg: c.esg })),
    esg_trend: MONTHS_12.map((m, i) => ({ month: m, score: 62 + i + (i % 3) })),
  };
};

// ---------------------------------------------------------------------------
// M6 Market
// ---------------------------------------------------------------------------

const marketQuotesData = () => [
  { symbol: "NIFTY 50", name: "NSE Nifty 50", price: 25180.4, change: 156.2, change_pct: 0.62 },
  { symbol: "SENSEX", name: "BSE Sensex", price: 82640.1, change: 428.7, change_pct: 0.52 },
  { symbol: "BANKNIFTY", name: "Nifty Bank", price: 54320.6, change: -184.3, change_pct: -0.34 },
  { symbol: "USDINR", name: "USD / INR Spot", price: 83.72, change: 0.09, change_pct: 0.11 },
  { symbol: "GSEC10Y", name: "10Y G-Sec Yield", price: 6.94, change: -0.03, change_pct: -0.43 },
  { symbol: "BRENT", name: "Brent Crude (USD/bbl)", price: 79.4, change: 1.1, change_pct: 1.4 },
  { symbol: "GOLD", name: "Gold (₹/10g)", price: 71850, change: 320, change_pct: 0.45 },
];

const yieldCurveData = () => [
  { tenor: "3M", yield: 6.58 },
  { tenor: "6M", yield: 6.66 },
  { tenor: "1Y", yield: 6.74 },
  { tenor: "2Y", yield: 6.81 },
  { tenor: "3Y", yield: 6.86 },
  { tenor: "5Y", yield: 6.9 },
  { tenor: "7Y", yield: 6.93 },
  { tenor: "10Y", yield: 6.94 },
  { tenor: "15Y", yield: 7.02 },
  { tenor: "30Y", yield: 7.11 },
];

const sentimentData = () => ({
  overall: "Cautiously Positive",
  score: 0.34,
  bullish_pct: 52,
  neutral_pct: 20,
  bearish_pct: 28,
  vix: 13.6,
});

const marketNewsData = () => [
  { news_id: 1, headline: "Reliance Industries commissions new petrochemicals line at Jamnagar; margins seen expanding", sentiment: "positive", category: "corporate", impact: "medium", published_at: daysAgo(0) },
  { news_id: 2, headline: "RBI holds repo at 6.25%, flags sticky food inflation as key upside risk", sentiment: "neutral", category: "macro", impact: "high", published_at: daysAgo(1) },
  { news_id: 3, headline: "Tata Steel guides higher on firm domestic demand and easing coking-coal costs", sentiment: "positive", category: "corporate", impact: "medium", published_at: daysAgo(1) },
  { news_id: 4, headline: "Adani Ports under covenant scrutiny as net debt / EBITDA nudges 3.5x ceiling", sentiment: "negative", category: "corporate", impact: "high", published_at: daysAgo(2) },
  { news_id: 5, headline: "IT services outlook mixed; Infosys deal pipeline resilient amid discretionary caution", sentiment: "neutral", category: "industry", impact: "low", published_at: daysAgo(3) },
  { news_id: 6, headline: "Swiggy widens quarterly loss; path to operating profitability pushed further out", sentiment: "negative", category: "corporate", impact: "medium", published_at: daysAgo(4) },
];

const marketDashboard = () => ({
  quotes: marketQuotesData(),
  yield_curve: yieldCurveData(),
  sentiment: sentimentData(),
  news: marketNewsData().slice(0, 4),
  index_history: MONTHS_12.map((m, i) => ({ month: m, nifty: 22800 + i * 210 + (i % 4) * 60 })),
});

// ---------------------------------------------------------------------------
// M7 Alt-Data
// ---------------------------------------------------------------------------

const altSignalTypes = () => ({
  signal_types: ["satellite", "shipping", "web_traffic", "reviews", "social", "hiring", "payments", "footfall"],
  labels: {
    satellite: "Satellite Imagery",
    shipping: "Port & Shipping Activity",
    web_traffic: "Web Traffic",
    reviews: "Customer Reviews",
    social: "Social Sentiment",
    hiring: "Hiring & Headcount",
    payments: "Payments Throughput",
    footfall: "Retail Footfall",
  },
});

// ---------------------------------------------------------------------------
// M8 Forecasting
// ---------------------------------------------------------------------------

const forecastTypes = () => ({
  forecast_types: ["revenue", "cash_flow", "working_capital", "profit", "growth", "risk", "default", "recovery"],
});

const forecastList = () => ({
  forecasts: [
    { forecast_id: 1, forecast_type: "revenue", horizon: 12, subject_ref: "APP-2026-4201", generated_at: daysAgo(0) },
    { forecast_id: 2, forecast_type: "cash_flow", horizon: 8, subject_ref: "APP-2026-4204", generated_at: daysAgo(1) },
    { forecast_id: 3, forecast_type: "working_capital", horizon: 12, subject_ref: "APP-2026-4205", generated_at: daysAgo(2) },
    { forecast_id: 4, forecast_type: "default", horizon: 24, subject_ref: "APP-2026-4216", generated_at: daysAgo(3) },
    { forecast_id: 5, forecast_type: "growth", horizon: 12, subject_ref: "APP-2026-4215", generated_at: daysAgo(4) },
    { forecast_id: 6, forecast_type: "recovery", horizon: 18, subject_ref: "APP-2026-4220", generated_at: daysAgo(5) },
  ],
});

// ---------------------------------------------------------------------------
// M9 Quantitative Risk
// ---------------------------------------------------------------------------

const quantTypes = () => ({
  sim_types: ["monte_carlo", "parametric_var", "historical_var", "expected_shortfall", "stress_test", "sensitivity", "scenario_tree", "tail_risk"],
});

const quantList = () => ({
  simulations: [
    { simulation_id: 1, sim_type: "monte_carlo", created_at: daysAgo(0) },
    { simulation_id: 2, sim_type: "parametric_var", created_at: daysAgo(1) },
    { simulation_id: 3, sim_type: "expected_shortfall", created_at: daysAgo(2) },
    { simulation_id: 4, sim_type: "stress_test", created_at: daysAgo(3) },
    { simulation_id: 5, sim_type: "tail_risk", created_at: daysAgo(4) },
    { simulation_id: 6, sim_type: "sensitivity", created_at: daysAgo(6) },
  ],
});

// ---------------------------------------------------------------------------
// M10 Benchmarking
// ---------------------------------------------------------------------------

const POSITIONS = ["Sector leader", "Above peer median", "At peer median", "Below peer median", "Lagging peers"];
const benchmarkList = () => ({
  benchmarks: COMPANIES.slice(0, 6).map((c, i) => ({
    benchmark_id: i + 1,
    subject_ref: c.ref,
    name: c.name,
    industry: c.sector,
    competitive_position: POSITIONS[Math.min(POSITIONS.length - 1, Math.floor((830 - c.score) / 60))],
  })),
});

// ---------------------------------------------------------------------------
// M11 Executive
// ---------------------------------------------------------------------------

const execPersonas = () => ({
  personas: ["ceo", "cfo", "cro", "treasurer", "portfolio_manager", "board", "credit_committee", "regulator", "rm"],
  labels: {
    ceo: "Chief Executive Officer",
    cfo: "Chief Financial Officer",
    cro: "Chief Risk Officer",
    treasurer: "Treasurer",
    portfolio_manager: "Portfolio Manager",
    board: "Board of Directors",
    credit_committee: "Credit Committee",
    regulator: "Regulator View",
    rm: "Relationship Manager",
  },
});

const execList = () => ({
  dashboards: [
    { dashboard_id: 1, persona: "cro", title: "Chief Risk Officer Dashboard", generated_at: daysAgo(0) },
    { dashboard_id: 2, persona: "cfo", title: "Chief Financial Officer Dashboard", generated_at: daysAgo(1) },
    { dashboard_id: 3, persona: "treasurer", title: "Treasurer Dashboard", generated_at: daysAgo(2) },
    { dashboard_id: 4, persona: "credit_committee", title: "Credit Committee Dashboard", generated_at: daysAgo(3) },
    { dashboard_id: 5, persona: "board", title: "Board of Directors Dashboard", generated_at: daysAgo(5) },
  ],
});

// ---------------------------------------------------------------------------
// M12 Optimization
// ---------------------------------------------------------------------------

const optTypes = () => ({
  opt_types: ["loan_pricing", "credit_limit", "collateral", "portfolio_allocation", "capital_allocation", "liquidity", "recovery"],
});

const optList = () => ({
  optimizations: [
    { optimization_id: 1, opt_type: "loan_pricing", objective: "Maximise risk-adjusted return (RAROC)", created_at: daysAgo(0) },
    { optimization_id: 2, opt_type: "credit_limit", objective: "Cap expected loss within risk appetite", created_at: daysAgo(1) },
    { optimization_id: 3, opt_type: "capital_allocation", objective: "Optimise return on regulatory capital", created_at: daysAgo(2) },
    { optimization_id: 4, opt_type: "portfolio_allocation", objective: "Minimise concentration (HHI) at target yield", created_at: daysAgo(3) },
    { optimization_id: 5, opt_type: "liquidity", objective: "Minimise cost of funds subject to LCR ≥ 100%", created_at: daysAgo(4) },
    { optimization_id: 6, opt_type: "recovery", objective: "Maximise net present value of recovery", created_at: daysAgo(6) },
  ],
});

// ---------------------------------------------------------------------------
// M13 Digital Twin
// ---------------------------------------------------------------------------

const twinTypes = () => ({
  twin_types: ["company", "industry", "portfolio", "economy", "bank", "treasury", "market", "supply_chain", "counterparty"],
});

const twinList = () => ({
  twins: [
    { twin_id: 1, name: "Reliance Industries — Company Twin", twin_type: "company", created_at: daysAgo(0) },
    { twin_id: 2, name: "Large Corporate Book — Portfolio Twin", twin_type: "portfolio", created_at: daysAgo(1) },
    { twin_id: 3, name: "Indian Steel Sector — Industry Twin", twin_type: "industry", created_at: daysAgo(2) },
    { twin_id: 4, name: "Bank Treasury — Treasury Twin", twin_type: "treasury", created_at: daysAgo(3) },
    { twin_id: 5, name: "India Macro — Economy Twin", twin_type: "economy", created_at: daysAgo(4) },
    { twin_id: 6, name: "Adani Ports Supply Chain — Supply-Chain Twin", twin_type: "supply_chain", created_at: daysAgo(5) },
  ],
});

// ---------------------------------------------------------------------------
// M14 Strategic
// ---------------------------------------------------------------------------

const strategicTypes = () => ({
  report_types: ["executive_briefing", "market", "industry", "competitor", "economic", "regulatory", "portfolio", "investment", "outlook"],
});

const strategicList = () => ({
  reports: [
    { report_id: 1, title: "Q3 FY26 Credit Portfolio Executive Briefing", report_type: "executive_briefing", created_at: daysAgo(0) },
    { report_id: 2, title: "Indian Steel & Metals — Industry Outlook", report_type: "industry", created_at: daysAgo(1) },
    { report_id: 3, title: "Rate & Liquidity Regime — Economic Report", report_type: "economic", created_at: daysAgo(2) },
    { report_id: 4, title: "Basel III / IFRS 9 Capital & Provisioning Review", report_type: "regulatory", created_at: daysAgo(3) },
    { report_id: 5, title: "Corporate Book Concentration & Loss Outlook", report_type: "portfolio", created_at: daysAgo(4) },
    { report_id: 6, title: "New-Age Tech Lending — Competitor Landscape", report_type: "competitor", created_at: daysAgo(6) },
  ],
});

// Reference derived helpers so figures stay internally consistent with the book.
void pdOf;
void eclOf;

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const FIN_FIXTURES: Record<string, () => unknown> = {
  // M1 Treasury
  "/api/fin/treasury/dashboard": () => ({ kpis: treasuryKpis() }),
  "/api/fin/treasury/kpis": () => ({ kpis: treasuryKpis(), as_of: daysAgo(0) }),
  "/api/fin/treasury/funding-sources": () => fundingSources(),
  // M2 Portfolio
  "/api/fin/portfolio": () => portfolios(),
  // M3 Regulatory
  "/api/fin/regulatory/dashboard": () => regulatoryDashboard(),
  // M4 Economic
  "/api/fin/economic/indicators": () => economicIndicators(),
  "/api/fin/economic/scenarios": () => economicScenarios(),
  "/api/fin/economic/scenario-types": () => economicScenarioTypes(),
  // M5 ESG
  "/api/fin/esg/list": () => esgList(),
  "/api/fin/esg/portfolio": () => esgPortfolio(),
  // M6 Market
  "/api/fin/market/dashboard": () => marketDashboard(),
  "/api/fin/market/quotes": () => ({ quotes: marketQuotesData() }),
  "/api/fin/market/news": () => ({ news: marketNewsData() }),
  "/api/fin/market/sentiment": () => ({ sentiment: sentimentData() }),
  // M7 Alt-Data
  "/api/fin/altdata/signal-types": () => altSignalTypes(),
  // M8 Forecasting
  "/api/fin/forecast/types": () => forecastTypes(),
  "/api/fin/forecast/list": () => forecastList(),
  // M9 Quant
  "/api/fin/quant/types": () => quantTypes(),
  "/api/fin/quant/list": () => quantList(),
  // M10 Benchmarking
  "/api/fin/benchmark/list": () => benchmarkList(),
  // M11 Executive
  "/api/fin/executive/personas": () => execPersonas(),
  "/api/fin/executive/list": () => execList(),
  // M12 Optimization
  "/api/fin/optimize/types": () => optTypes(),
  "/api/fin/optimize/list": () => optList(),
  // M13 Digital Twin
  "/api/fin/twin/types": () => twinTypes(),
  "/api/fin/twin": () => twinList(),
  // M14 Strategic
  "/api/fin/strategic/types": () => strategicTypes(),
  "/api/fin/strategic/list": () => strategicList(),
};
