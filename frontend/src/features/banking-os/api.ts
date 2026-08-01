/**
 * Phase 10 — Enterprise Banking Operating System API surface (/api/os/*).
 *
 * Thin typed wrappers over the shared HTTP client; one function per backend
 * endpoint. Feature hooks (see hooks.ts) wrap these in React Query.
 */
import { apiGet, apiPost, apiPatch } from "@/lib/http";

export type Json = Record<string, unknown>;

// -- M7 Policy Engine -------------------------------------------------------
export const getPolicyDomains = () => apiGet<Json>("/api/os/policy/domains");
export const listPolicies = (domain?: string) =>
  apiGet<{ policies: Json[] }>(`/api/os/policy${domain ? `?domain=${domain}` : ""}`);
export const createPolicy = (body: Json) => apiPost<Json>("/api/os/policy", body);
export const getPolicy = (id: number) => apiGet<Json>(`/api/os/policy/${id}`);
export const addPolicyVersion = (id: number, body: Json) =>
  apiPost<Json>(`/api/os/policy/${id}/versions`, body);
export const evaluatePolicy = (key: string, body: Json) =>
  apiPost<Json>(`/api/os/policy/${encodeURIComponent(key)}/evaluate`, body);
export const policyPlayground = (body: Json) => apiPost<Json>("/api/os/policy/playground", body);

// -- M4 Committee Workspace -------------------------------------------------
export const listCommittees = () => apiGet<{ committees: Json[] }>("/api/os/committee/committees");
export const createCommittee = (body: Json) => apiPost<Json>("/api/os/committee/committees", body);
export const listMeetings = () => apiGet<{ meetings: Json[] }>("/api/os/committee/meetings");
export const createMeeting = (body: Json) => apiPost<Json>("/api/os/committee/meetings", body);
export const getMeeting = (id: number) => apiGet<Json>(`/api/os/committee/meetings/${id}`);
export const openMeeting = (id: number) => apiPost<Json>(`/api/os/committee/meetings/${id}/open`, {});
export const addAgendaItem = (body: Json) => apiPost<Json>("/api/os/committee/agenda", body);
export const castVote = (itemId: number, body: Json) =>
  apiPost<Json>(`/api/os/committee/agenda/${itemId}/vote`, body);
export const decideItem = (itemId: number) =>
  apiPost<Json>(`/api/os/committee/agenda/${itemId}/decide`, {});
export const committeeAnalytics = () => apiGet<Json>("/api/os/committee/analytics");

// -- M2 Enterprise Search ---------------------------------------------------
export const search = (body: Json) => apiPost<Json>("/api/os/search", body);
export const reindex = () => apiPost<Json>("/api/os/search/reindex", {});
export const autocomplete = (q: string) =>
  apiGet<{ suggestions: Json[] }>(`/api/os/search/autocomplete?q=${encodeURIComponent(q)}`);
export const searchFacets = () => apiGet<Json>("/api/os/search/facets");

// -- M8 Prompt Management ---------------------------------------------------
export const listPrompts = () => apiGet<{ prompts: Json[] }>("/api/os/prompt");
export const createPrompt = (body: Json) => apiPost<Json>("/api/os/prompt", body);
export const getPrompt = (id: number) => apiGet<Json>(`/api/os/prompt/${id}`);
export const addPromptVersion = (id: number, body: Json) =>
  apiPost<Json>(`/api/os/prompt/${id}/versions`, body);
export const approvePrompt = (id: number, v: number) =>
  apiPost<Json>(`/api/os/prompt/${id}/versions/${v}/approve`, {});
export const deployPrompt = (id: number, v: number) =>
  apiPost<Json>(`/api/os/prompt/${id}/versions/${v}/deploy`, {});
export const renderPrompt = (id: number, body: Json) =>
  apiPost<Json>(`/api/os/prompt/${id}/render`, body);

// -- M9 Multi-LLM Layer -----------------------------------------------------
export const listProviders = () => apiGet<Json>("/api/os/llm/providers");
export const registerProvider = (body: Json) => apiPost<Json>("/api/os/llm/providers", body);
export const routeLLM = (body: Json) => apiPost<Json>("/api/os/llm/route", body);
export const llmAnalytics = () => apiGet<Json>("/api/os/llm/analytics");

// -- M14 Data Fabric --------------------------------------------------------
export const fabricCatalog = () => apiGet<Json>("/api/os/fabric/catalog");
export const registerDataset = (body: Json) => apiPost<Json>("/api/os/fabric/datasets", body);
export const addLineage = (body: Json) => apiPost<Json>("/api/os/fabric/lineage", body);
export const datasetImpact = (name: string) =>
  apiGet<Json>(`/api/os/fabric/impact/${encodeURIComponent(name)}`);
export const runQuality = (body: Json) => apiPost<Json>("/api/os/fabric/quality", body);
export const fabricStats = () => apiGet<Json>("/api/os/fabric/stats");

// -- M11 Workflow Studio ----------------------------------------------------
export const listWorkflows = () => apiGet<{ definitions: Json[] }>("/api/os/workflow/definitions");
export const createWorkflow = (body: Json) => apiPost<Json>("/api/os/workflow/definitions", body);
export const validateWorkflow = (body: Json) => apiPost<Json>("/api/os/workflow/validate", body);
export const runWorkflow = (body: Json) => apiPost<Json>("/api/os/workflow/run", body);
export const listWorkflowRuns = () => apiGet<{ runs: Json[] }>("/api/os/workflow/runs");

// -- M12 Recommendation Marketplace -----------------------------------------
export const listPlugins = () => apiGet<{ plugins: Json[] }>("/api/os/marketplace/plugins");
export const seedPlugins = () => apiPost<Json>("/api/os/marketplace/seed", {});
export const togglePlugin = (key: string, body: Json) =>
  apiPatch<Json>(`/api/os/marketplace/plugins/${key}`, body);
export const runMarketplace = (body: Json) => apiPost<Json>("/api/os/marketplace/run", body);

// -- M5/M6 Scenario Planning ------------------------------------------------
export const scenarioLibrary = () => apiGet<Json>("/api/os/scenario/library");
export const runScenarios = (body: Json) => apiPost<Json>("/api/os/scenario/run", body);

// -- M13 Fairness / Drift ---------------------------------------------------
export const evaluateFairness = (body: Json) => apiPost<Json>("/api/os/fairness/evaluate", body);
export const fairnessHistory = () => apiGet<Json>("/api/os/fairness/history");

// -- M1 Graph Analytics -----------------------------------------------------
export const getUbo = (ref: string) =>
  apiGet<Json>(`/api/os/graph/ubo/${encodeURIComponent(ref)}`);
export const getConnectedLending = (ref: string) =>
  apiGet<Json>(`/api/os/graph/connected-lending/${encodeURIComponent(ref)}`);
export const getCrossHoldings = () => apiGet<Json>("/api/os/graph/cross-holdings");

// -- M10 Executive Center ---------------------------------------------------
export const execPersonas = () => apiGet<{ personas: string[] }>("/api/os/exec/personas");
export const execDashboard = (persona: string) =>
  apiGet<Json>(`/api/os/exec/dashboard/${persona}`);
