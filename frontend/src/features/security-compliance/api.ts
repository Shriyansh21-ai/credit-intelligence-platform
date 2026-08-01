/**
 * Stage 4 — Enterprise Security & Compliance API surface (/api/sec/*).
 *
 * Thin typed wrappers over the shared HTTP client; one function per backend
 * endpoint. Feature hooks (see hooks.ts) wrap these in React Query.
 */
import { apiGet, apiPatch, apiPost } from "@/lib/http";

export type Json = Record<string, unknown>;

// -- Posture & dashboard (M14) ---------------------------------------------
export const getPosture = () => apiGet<Json>("/api/sec/posture");
export const getDashboard = () => apiGet<Json>("/api/sec/posture/dashboard");
export const listSnapshots = () => apiGet<{ snapshots: Json[] }>("/api/sec/posture/snapshots");
export const takeSnapshot = () => apiPost<Json>("/api/sec/posture/snapshot", {});

// -- Threat model (M1) ------------------------------------------------------
export const getThreatModel = () => apiGet<Json>("/api/sec/threat");
export const getStride = () => apiGet<Json>("/api/sec/threat/stride");
export const getAttackSurface = () => apiGet<Json>("/api/sec/threat/attack-surface");
export const getAttackTrees = () => apiGet<{ attack_trees: Json[] }>("/api/sec/threat/attack-trees");

// -- OWASP (M2) -------------------------------------------------------------
export const getOwasp = () => apiGet<Json>("/api/sec/owasp");

// -- Auth & tenant (M3, M4) -------------------------------------------------
export const getAuthz = () => apiGet<Json>("/api/sec/authz");
export const getTenantIsolation = () => apiGet<Json>("/api/sec/authz/tenant-isolation");

// -- Secrets / data / supply / container (M5, M6, M8, M9) -------------------
export const getSecrets = () => apiGet<Json>("/api/sec/secrets");
export const getDataProtection = () => apiGet<Json>("/api/sec/data");
export const getSupplyChain = () => apiGet<Json>("/api/sec/supply-chain");
export const getContainer = () => apiGet<Json>("/api/sec/container");

// -- AI / ML security (M10, M11) --------------------------------------------
export const getAiSecurity = () => apiGet<Json>("/api/sec/ai/security");
export const getMlSecurity = () => apiGet<Json>("/api/sec/ai/ml-security");

// -- Compliance (M7) --------------------------------------------------------
export const getComplianceMatrix = () => apiGet<Json>("/api/sec/compliance/matrix");
export const getGapAnalysis = () => apiGet<Json>("/api/sec/compliance/gap-analysis");
export const assessFramework = (framework: string) =>
  apiPost<Json>("/api/sec/compliance/assess", { framework });

// -- Privacy (M12) ----------------------------------------------------------
export const getPrivacy = () => apiGet<Json>("/api/sec/privacy");
export const listPrivacyRequests = (status?: string) =>
  apiGet<{ requests: Json[] }>(`/api/sec/privacy/requests${status ? `?status=${status}` : ""}`);
export const createPrivacyRequest = (body: Json) =>
  apiPost<Json>("/api/sec/privacy/requests", body);
export const updatePrivacyRequest = (id: number, body: Json) =>
  apiPatch<Json>(`/api/sec/privacy/requests/${id}`, body);

// -- Scans & findings (M13) -------------------------------------------------
export const scanTypes = () => apiGet<{ scan_types: string[] }>("/api/sec/scans/types");
export const runScan = (scanType: string) =>
  apiPost<Json>("/api/sec/scans", { scan_type: scanType });
export const listScans = () => apiGet<{ scans: Json[] }>("/api/sec/scans");
export const listFindings = (status?: string) =>
  apiGet<{ findings: Json[] }>(`/api/sec/findings${status ? `?status=${status}` : ""}`);
export const updateFinding = (id: number, status: string) =>
  apiPatch<Json>(`/api/sec/findings/${id}`, { status });

// -- Risk register ----------------------------------------------------------
export const listRisks = (status?: string) =>
  apiGet<{ risks: Json[] }>(`/api/sec/risk${status ? `?status=${status}` : ""}`);
export const createRisk = (body: Json) => apiPost<Json>("/api/sec/risk", body);
export const updateRisk = (id: number, body: Json) => apiPatch<Json>(`/api/sec/risk/${id}`, body);
