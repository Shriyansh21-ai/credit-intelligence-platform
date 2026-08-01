/**
 * AI Intelligence Platform (Track 2) API client.
 *
 * Thin wrappers over the `/api/aip/*` endpoints using the shared HTTP client.
 * Grouped by milestone (RAG, agents, memory, prompts, eval, investigation,
 * reports, workflows, chat, research, learning, governance, explain, monitoring).
 */

import { apiGet, apiPost } from "@/lib/http";

// --- M1 RAG ---
export const listSources = () => apiGet<any[]>("/api/aip/rag/sources");
export const createSource = (b: any) => apiPost<any>("/api/aip/rag/sources", b);
export const ingestDocument = (b: any) => apiPost<any>("/api/aip/rag/documents", b);
export const listDocuments = () => apiGet<any[]>("/api/aip/rag/documents");
export const ragSearch = (b: any) => apiPost<any>("/api/aip/rag/search", b);
export const ragAnswer = (b: any) => apiPost<any>("/api/aip/rag/answer", b);
export const ragStats = () => apiGet<any>("/api/aip/rag/stats");

// --- M2 Agents ---
export const agentRoster = () => apiGet<any>("/api/aip/agents/roster");
export const agentPlan = (b: any) => apiPost<any>("/api/aip/agents/plan", b);
export const runAgents = (b: any) => apiPost<any>("/api/aip/agents/run", b);
export const listAgentRuns = () => apiGet<any>("/api/aip/agents/runs");

// --- M3 Memory ---
export const memoryWrite = (b: any) => apiPost<any>("/api/aip/memory/write", b);
export const memoryRecall = (b: any) => apiPost<any>("/api/aip/memory/recall", b);
export const memoryStats = () => apiGet<any>("/api/aip/memory/stats");

// --- M4 Prompts ---
export const listPrompts = () => apiGet<any[]>("/api/aip/prompts");
export const createPrompt = (b: any) => apiPost<any>("/api/aip/prompts", b);
export const seedPrompts = () => apiPost<any>("/api/aip/prompts/seed-defaults", {});
export const createPromptVersion = (b: any) => apiPost<any>("/api/aip/prompts/versions", b);
export const renderPrompt = (b: any) => apiPost<any>("/api/aip/prompts/render", b);
export const evaluatePrompt = (b: any) => apiPost<any>("/api/aip/prompts/evaluate", b);
export const approvePrompt = (b: any) => apiPost<any>("/api/aip/prompts/approve", b);
export const deployPrompt = (b: any) => apiPost<any>("/api/aip/prompts/deploy", b);
export const promptVersions = (id: number) => apiGet<any[]>(`/api/aip/prompts/${id}/versions`);

// --- M5 Eval ---
export const evalScore = (b: any) => apiPost<any>("/api/aip/eval/score", b);
export const evalSummary = () => apiGet<any>("/api/aip/eval/summary");
export const evalList = () => apiGet<any>("/api/aip/eval/list");

// --- M6 Investigation ---
export const runInvestigation = (b: any) => apiPost<any>("/api/aip/investigate/run", b);
export const listInvestigations = () => apiGet<any>("/api/aip/investigate/list");

// --- M7 Reports ---
export const reportTypes = () => apiGet<any>("/api/aip/reports/types");
export const generateReport = (b: any) => apiPost<any>("/api/aip/reports/generate", b);
export const listReports = () => apiGet<any>("/api/aip/reports/list");

// --- M8 Workflows ---
export const nodeTypes = () => apiGet<any>("/api/aip/workflows/node-types");
export const listWorkflows = () => apiGet<any[]>("/api/aip/workflows");
export const saveWorkflow = (b: any) => apiPost<any>("/api/aip/workflows", b);
export const runWorkflow = (b: any) => apiPost<any>("/api/aip/workflows/run", b);

// --- M9 Chat ---
export const createConversation = (b: any) => apiPost<any>("/api/aip/chat/conversations", b);
export const listConversations = () => apiGet<any[]>("/api/aip/chat/conversations");
export const chatAsk = (b: any) => apiPost<any>("/api/aip/chat/ask", b);

// --- M10 Research ---
export const researchTypes = () => apiGet<any>("/api/aip/research/types");
export const runResearch = (b: any) => apiPost<any>("/api/aip/research/run", b);
export const listResearch = () => apiGet<any>("/api/aip/research/list");

// --- M11 Learning ---
export const submitFeedback = (b: any) => apiPost<any>("/api/aip/learning/feedback", b);
export const submitSignal = (b: any) => apiPost<any>("/api/aip/learning/signal", b);
export const evaluateTriggers = (b: any) => apiPost<any>("/api/aip/learning/evaluate-triggers", b);
export const learningStats = () => apiGet<any>("/api/aip/learning/stats");
export const listTrainingEvents = () => apiGet<any>("/api/aip/learning/training-events");

// --- M12 Governance ---
export const assetTypes = () => apiGet<any>("/api/aip/governance/asset-types");
export const registerAsset = (b: any) => apiPost<any>("/api/aip/governance/assets", b);
export const transitionAsset = (b: any) => apiPost<any>("/api/aip/governance/assets/transition", b);
export const listAssets = () => apiGet<any>("/api/aip/governance/assets");
export const governanceSummary = () => apiGet<any>("/api/aip/governance/summary");

// --- M13 Explain ---
export const explainDecision = (b: any) => apiPost<any>("/api/aip/explain/decision", b);
export const listExplanations = () => apiGet<any>("/api/aip/explain/list");

// --- M14 Monitoring ---
export const runMonitoring = () => apiPost<any>("/api/aip/monitoring/run", {});
export const monitoringDashboard = () => apiGet<any>("/api/aip/monitoring/dashboard");
export const listIncidents = () => apiGet<any>("/api/aip/monitoring/incidents");
