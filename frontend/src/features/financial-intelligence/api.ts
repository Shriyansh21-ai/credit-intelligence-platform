/**
 * Advanced Financial Intelligence Platform (Track 3) API client.
 *
 * Thin wrappers over the `/api/fin/*` endpoints using the shared HTTP client.
 * Grouped by milestone (treasury, portfolio, regulatory, economic, esg, market,
 * altdata, forecast, quant, benchmark, executive, optimize, twin, strategic).
 */

import { apiGet, apiPost } from "@/lib/http";

// --- M1 Treasury ---
export const treasurySourceTypes = () => apiGet<any>("/api/fin/treasury/source-types");
export const listFundingSources = () => apiGet<any[]>("/api/fin/treasury/funding-sources");
export const createFundingSource = (b: any) => apiPost<any>("/api/fin/treasury/funding-sources", b);
export const cashPosition = (b: any) => apiPost<any>("/api/fin/treasury/cash-position", b);
export const liquidityBuckets = (b: any) => apiPost<any>("/api/fin/treasury/liquidity-buckets", b);
export const fundingGap = (b: any) => apiPost<any>("/api/fin/treasury/funding-gap", b);
export const nim = (b: any) => apiPost<any>("/api/fin/treasury/nim", b);
export const alm = (b: any) => apiPost<any>("/api/fin/treasury/alm", b);
export const lcr = (b: any) => apiPost<any>("/api/fin/treasury/lcr", b);
export const nsfr = (b: any) => apiPost<any>("/api/fin/treasury/nsfr", b);
export const cashForecast = (b: any) => apiPost<any>("/api/fin/treasury/cash-forecast", b);
export const fundingOptimization = (b: any) => apiPost<any>("/api/fin/treasury/funding-optimization", b);
export const treasuryKpis = () => apiGet<any>("/api/fin/treasury/kpis");
export const treasuryDashboard = () => apiGet<any>("/api/fin/treasury/dashboard");

// --- M2 Portfolio ---
export const listPortfolios = () => apiGet<any[]>("/api/fin/portfolio");
export const createPortfolio = (b: any) => apiPost<any>("/api/fin/portfolio", b);
export const addPosition = (b: any) => apiPost<any>("/api/fin/portfolio/positions", b);
export const syncPortfolio = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/sync`, {});
export const portfolioSummary = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/summary`, {});
export const portfolioConcentration = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/concentration`, {});
export const portfolioLoss = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/loss`, {});
export const portfolioRaroc = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/raroc`, {});
export const portfolioSimulate = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/simulate`, {});
export const portfolioOptimize = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/optimize`, {});
export const portfolioEws = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/ews`, {});
export const portfolioInsights = (id: number) => apiPost<any>(`/api/fin/portfolio/${id}/insights`, {});

// --- M3 Regulatory ---
export const regEcl = (b: any) => apiPost<any>("/api/fin/regulatory/ecl", b);
export const regRwa = (b: any) => apiPost<any>("/api/fin/regulatory/rwa", b);
export const regCar = (b: any) => apiPost<any>("/api/fin/regulatory/car", b);
export const regLeverage = (b: any) => apiPost<any>("/api/fin/regulatory/leverage", b);
export const regDashboard = () => apiGet<any>("/api/fin/regulatory/dashboard");

// --- M4 Economic ---
export const econTypes = () => apiGet<any>("/api/fin/economic/scenario-types");
export const econIndicators = () => apiGet<any>("/api/fin/economic/indicators");
export const econSeed = () => apiPost<any>("/api/fin/economic/seed", {});
export const econGenerate = (b: any) => apiPost<any>("/api/fin/economic/scenarios", b);
export const econPropagate = (b: any) => apiPost<any>("/api/fin/economic/propagate", b);
export const econList = () => apiGet<any>("/api/fin/economic/scenarios");

// --- M5 ESG ---
export const esgAssess = (b: any) => apiPost<any>("/api/fin/esg/assess", b);
export const esgClimate = (b: any) => apiPost<any>("/api/fin/esg/climate-stress", b);
export const esgPortfolio = () => apiGet<any>("/api/fin/esg/portfolio");
export const esgList = () => apiGet<any>("/api/fin/esg/list");

// --- M6 Market ---
export const marketSeed = () => apiPost<any>("/api/fin/market/seed", {});
export const marketQuotes = () => apiGet<any>("/api/fin/market/quotes");
export const marketYieldCurve = () => apiPost<any>("/api/fin/market/yield-curve", {});
export const marketNews = () => apiGet<any>("/api/fin/market/news");
export const marketAddNews = (b: any) => apiPost<any>("/api/fin/market/news", b);
export const marketSentiment = () => apiGet<any>("/api/fin/market/sentiment");
export const marketDashboard = () => apiGet<any>("/api/fin/market/dashboard");

// --- M7 Alt-Data ---
export const altSignalTypes = () => apiGet<any>("/api/fin/altdata/signal-types");
export const altIngest = (b: any) => apiPost<any>("/api/fin/altdata/signals", b);
export const altSignals = (subject: string) => apiGet<any>(`/api/fin/altdata/signals?subject_ref=${encodeURIComponent(subject)}`);
export const altComposite = (b: any) => apiPost<any>("/api/fin/altdata/composite", b);

// --- M8 Forecasting ---
export const forecastTypes = () => apiGet<any>("/api/fin/forecast/types");
export const forecastRun = (b: any) => apiPost<any>("/api/fin/forecast/run", b);
export const forecastList = () => apiGet<any>("/api/fin/forecast/list");

// --- M9 Quant Risk ---
export const quantTypes = () => apiGet<any>("/api/fin/quant/types");
export const quantVar = (b: any) => apiPost<any>("/api/fin/quant/var", b);
export const quantMonteCarlo = (b: any) => apiPost<any>("/api/fin/quant/montecarlo", b);
export const quantStress = (b: any) => apiPost<any>("/api/fin/quant/stress", b);
export const quantList = () => apiGet<any>("/api/fin/quant/list");

// --- M10 Benchmarking ---
export const benchmarkRun = (b: any) => apiPost<any>("/api/fin/benchmark/run", b);
export const benchmarkList = () => apiGet<any>("/api/fin/benchmark/list");

// --- M11 Executive ---
export const execPersonas = () => apiGet<any>("/api/fin/executive/personas");
export const execDashboard = (b: any) => apiPost<any>("/api/fin/executive/dashboard", b);
export const execList = () => apiGet<any>("/api/fin/executive/list");

// --- M12 Optimization ---
export const optTypes = () => apiGet<any>("/api/fin/optimize/types");
export const optLoanPricing = (b: any) => apiPost<any>("/api/fin/optimize/loan-pricing", b);
export const optCreditLimit = (b: any) => apiPost<any>("/api/fin/optimize/credit-limit", b);
export const optList = () => apiGet<any>("/api/fin/optimize/list");

// --- M13 Digital Twin ---
export const twinTypes = () => apiGet<any>("/api/fin/twin/types");
export const twinCreate = (b: any) => apiPost<any>("/api/fin/twin", b);
export const twinList = () => apiGet<any>("/api/fin/twin");
export const twinSimulate = (id: number, b: any) => apiPost<any>(`/api/fin/twin/${id}/simulate`, b);

// --- M14 Strategic ---
export const strategicTypes = () => apiGet<any>("/api/fin/strategic/types");
export const strategicGenerate = (b: any) => apiPost<any>("/api/fin/strategic/generate", b);
export const strategicList = () => apiGet<any>("/api/fin/strategic/list");
