import { apiGet, apiPost, apiPatch } from "@/lib/http";

import type {
  Alert, CopilotAnswer, EWSResult, Json, Network, Recommendation, Signal,
} from "./types";

// -- M1 Knowledge Graph -----------------------------------------------------
export const getGraphStats = () => apiGet<Json>("/api/ai/graph/stats");
export const getNetwork = (rootId?: number, maxDepth = 2) =>
  apiGet<Network>(`/api/ai/graph/network?max_depth=${maxDepth}${rootId ? `&root_id=${rootId}` : ""}`);
export const listEntities = (entityType?: string) =>
  apiGet<Array<Record<string, unknown>>>(
    `/api/ai/graph/entities${entityType ? `?entity_type=${entityType}` : ""}`);
export const createEntity = (body: Json) => apiPost<Json>("/api/ai/graph/entities", body);
export const createRelationship = (body: Json) => apiPost<Json>("/api/ai/graph/relationships", body);
export const ingestNetwork = (body: Json) => apiPost<Json>("/api/ai/graph/ingest", body);
export const seedGraph = (body: Json) => apiPost<Json>("/api/ai/graph/seed", body);
export const propagateRisk = () => apiPost<Json>("/api/ai/graph/propagate-risk", {});
export const connectedExposure = (id: number) =>
  apiGet<Json>(`/api/ai/graph/entities/${id}/exposure`);

// -- M2 Monitoring ----------------------------------------------------------
export const runMonitoring = (body: Json) => apiPost<Json>("/api/ai/monitoring/run", body);
export const getSignals = (companyRef?: string) =>
  apiGet<{ signals: Signal[] }>(`/api/ai/monitoring/signals${companyRef ? `?company_ref=${encodeURIComponent(companyRef)}` : ""}`);
export const getMonitoringSources = () => apiGet<{ sources: string[] }>("/api/ai/monitoring/sources");

// -- M3 EWS -----------------------------------------------------------------
export const evaluateEws = (body: Json) => apiPost<EWSResult>("/api/ai/ews/evaluate", body);
export const getEwsCatalog = () => apiGet<Json>("/api/ai/ews/catalog");
export const getEwsHistory = (companyRef: string) =>
  apiGet<Json>(`/api/ai/ews/history?company_ref=${encodeURIComponent(companyRef)}`);

// -- Alerts -----------------------------------------------------------------
export const getAlerts = (params = "") => apiGet<{ alerts: Alert[] }>(`/api/ai/alerts${params}`);
export const getAlertSummary = () => apiGet<Json>("/api/ai/alerts/summary");
export const updateAlert = (id: number, status: string) =>
  apiPatch<Alert>(`/api/ai/alerts/${id}`, { status });

// -- M4 Copilot -------------------------------------------------------------
export const askCopilot = (body: Json) => apiPost<CopilotAnswer>("/api/ai/copilot/ask", body);
export const getProviderStatus = () => apiGet<Json>("/api/ai/copilot/provider");

// -- M5 Simulation ----------------------------------------------------------
export const getScenarios = () =>
  apiGet<{ scenarios: Array<{ key: string; label: string; unit: string }> }>("/api/ai/simulation/scenarios");
export const runSimulation = (body: Json) => apiPost<Json>("/api/ai/simulation/run", body);

// -- M6 Stress --------------------------------------------------------------
export const getStressScenarios = () => apiGet<Json>("/api/ai/stress/scenarios");
export const runStress = (body: Json) => apiPost<Json>("/api/ai/stress/run", body);
export const compareStress = (scope = "portfolio") =>
  apiGet<Json>(`/api/ai/stress/compare?scope=${scope}`);

// -- M7 Portfolio -----------------------------------------------------------
export const optimizePortfolio = (body: Json) => apiPost<Json>("/api/ai/portfolio/optimize", body);
export const getPortfolioAnalysis = () => apiGet<Json>("/api/ai/portfolio/analysis");

// -- M8 RM ------------------------------------------------------------------
export const getRmWorkspace = (companyRef: string) =>
  apiGet<Json>(`/api/ai/rm/workspace/${encodeURIComponent(companyRef)}`);
export const addInteraction = (body: Json) => apiPost<Json>("/api/ai/rm/interactions", body);

// -- M9 Command center ------------------------------------------------------
export const getCommandDashboard = (persona: string, region?: string) =>
  apiGet<Json>(`/api/ai/command/dashboard/${persona}${region ? `?region=${region}` : ""}`);
export const getPersonas = () => apiGet<{ personas: string[] }>("/api/ai/command/personas");

// -- M10 NL analytics -------------------------------------------------------
export const nlQuery = (question: string) =>
  apiPost<Json>("/api/ai/nlq/query", { question, persist: true });
export const getNlHistory = () => apiGet<Json>("/api/ai/nlq/history");

// -- M11 Recommendations ----------------------------------------------------
export const generateRecommendations = (body: Json) =>
  apiPost<{ recommendations: Recommendation[]; summary: string }>("/api/ai/recommendations/generate", body);
export const listRecommendations = (companyRef?: string) =>
  apiGet<{ recommendations: Recommendation[] }>(
    `/api/ai/recommendations${companyRef ? `?company_ref=${encodeURIComponent(companyRef)}` : ""}`);

// -- M12 Workflow -----------------------------------------------------------
export const planWorkflow = (body: Json) => apiPost<Json>("/api/ai/workflow/plan", body);
export const runWorkflow = (body: Json) => apiPost<Json>("/api/ai/workflow/run", body);

// -- M13 Governance ---------------------------------------------------------
export const getGovernanceDashboard = () => apiGet<Json>("/api/ai/governance/dashboard");
export const validateModel = (id: number) => apiPost<Json>(`/api/ai/governance/models/${id}/validate`, {});
export const getLineage = (key: string) => apiGet<Json>(`/api/ai/governance/models/${key}/lineage`);
export const getChampionChallenger = (key: string) =>
  apiGet<Json>(`/api/ai/governance/models/${key}/champion-challenger`);

// -- M14 Data lake ----------------------------------------------------------
export const getDatalakeCatalog = () => apiGet<Json>("/api/ai/datalake/catalog");
export const getDatalakeStats = () => apiGet<Json>("/api/ai/datalake/stats");
export const runIngestionAll = () => apiPost<Json>("/api/ai/datalake/run-ingestion", {});
export const datalakeAggregate = (body: Json) => apiPost<Json>("/api/ai/datalake/aggregate", body);
