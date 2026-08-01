/**
 * Enterprise Platform (Track 4) API client.
 *
 * Thin wrappers over the `/api/ent/*` endpoints using the shared HTTP client.
 * Grouped by milestone (ux, workspaces, developer, marketplace, integration,
 * data, operations, security, success, deployment, monitoring, bi, launch).
 */

import { apiGet, apiPost } from "@/lib/http";

// --- M1 UX ---
export const getPreferences = () => apiGet<any>("/api/ent/ux/preferences");
export const savePreferences = (b: any) => apiPost<any>("/api/ent/ux/preferences", b);
export const listLayouts = () => apiGet<any>("/api/ent/ux/layouts");
export const saveLayout = (b: any) => apiPost<any>("/api/ent/ux/layouts", b);
export const commandCatalog = (query?: string) =>
  apiGet<any>(`/api/ent/ux/commands${query ? `?query=${encodeURIComponent(query)}` : ""}`);

// --- M2 Workspaces ---
export const listWorkspaces = () => apiGet<any>("/api/ent/workspaces");
export const createWorkspace = (b: any) => apiPost<any>("/api/ent/workspaces", b);
export const addWorkspaceMember = (b: any) => apiPost<any>("/api/ent/workspaces/members", b);
export const addWorkspaceItem = (b: any) => apiPost<any>("/api/ent/workspaces/items", b);

// --- M3 Developer ---
export const apiExplorer = () => apiGet<any>("/api/ent/developer/explorer");
export const listApiKeys = () => apiGet<any>("/api/ent/developer/keys");
export const createApiKey = (b: any) => apiPost<any>("/api/ent/developer/keys", b);
export const listWebhooks = () => apiGet<any>("/api/ent/developer/webhooks");
export const createWebhook = (b: any) => apiPost<any>("/api/ent/developer/webhooks", b);
export const testWebhook = (b: any) => apiPost<any>("/api/ent/developer/webhooks/test", b);
export const sandboxRequest = (b: any) => apiPost<any>("/api/ent/developer/sandbox", b);
export const requestHistory = () => apiGet<any>("/api/ent/developer/requests");

// --- M4 Marketplace ---
export const listPlugins = () => apiGet<any>("/api/ent/marketplace");
export const publishPlugin = (b: any) => apiPost<any>("/api/ent/marketplace/publish", b);
export const marketplaceAnalytics = () => apiGet<any>("/api/ent/marketplace/analytics/summary");

// --- M5 Integration ---
export const listPipelines = () => apiGet<any>("/api/ent/integration");
export const savePipeline = (b: any) => apiPost<any>("/api/ent/integration", b);
export const runPipeline = (b: any) => apiPost<any>("/api/ent/integration/run", b);
export const nodeTypes = () => apiGet<any>("/api/ent/integration/node-types");

// --- M6 Data ---
export const dataCatalog = () => apiGet<any>("/api/ent/data/catalog");
export const upsertGolden = (b: any) => apiPost<any>("/api/ent/data/golden", b);
export const listGolden = (entityType: string) =>
  apiGet<any>(`/api/ent/data/golden?entity_type=${encodeURIComponent(entityType)}`);
export const detectDuplicates = (b: any) => apiPost<any>("/api/ent/data/duplicates", b);

// --- M7 Operations ---
export const opsDashboard = () => apiGet<any>("/api/ent/operations/dashboard");
export const listIncidents = () => apiGet<any>("/api/ent/operations/incidents");
export const openIncident = (b: any) => apiPost<any>("/api/ent/operations/incidents", b);
export const seedRunbooks = () => apiPost<any>("/api/ent/operations/runbooks/seed", {});
export const listRunbooks = () => apiGet<any>("/api/ent/operations/runbooks");

// --- M8 Security ---
export const securityDashboard = () => apiGet<any>("/api/ent/security/dashboard");
export const listSecurityEvents = () => apiGet<any>("/api/ent/security/events");
export const analyzeSession = (b: any) => apiPost<any>("/api/ent/security/analyze-session", b);
export const startAccessReview = (b: any) => apiPost<any>("/api/ent/security/access-reviews", b);

// --- M9 Customer Success ---
export const successDashboard = () => apiGet<any>("/api/ent/success/dashboard");
export const listCustomers = () => apiGet<any>("/api/ent/success");
export const createCustomer = (b: any) => apiPost<any>("/api/ent/success", b);
export const customerRecommendations = (id: number) =>
  apiGet<any>(`/api/ent/success/${id}/recommendations`);

// --- M10 Deployment ---
export const listEnvironments = () => apiGet<any>("/api/ent/deployment/environments");
export const seedEnvironments = () => apiPost<any>("/api/ent/deployment/environments/seed", {});
export const deploy = (b: any) => apiPost<any>("/api/ent/deployment/deploy", b);
export const rollback = (b: any) => apiPost<any>("/api/ent/deployment/rollback", b);
export const versionDashboard = () => apiGet<any>("/api/ent/deployment/versions");
export const deploymentHistory = () => apiGet<any>("/api/ent/deployment/history");

// --- M11 Monitoring ---
export const monitoringDashboard = () => apiGet<any>("/api/ent/monitoring/dashboard");
export const dependencyGraph = () => apiGet<any>("/api/ent/monitoring/dependency-graph");
export const costMonitoring = () => apiGet<any>("/api/ent/monitoring/cost");
export const slaDashboard = () => apiGet<any>("/api/ent/monitoring/sla");

// --- M12 BI ---
export const biAnalytics = (category: string) =>
  apiGet<any>(`/api/ent/bi/analytics?category=${encodeURIComponent(category)}`);
export const boardReport = () => apiGet<any>("/api/ent/bi/board-report");
export const listBiDashboards = () => apiGet<any>("/api/ent/bi/dashboards");

// --- M13 Launch ---
export const readinessSummary = () => apiGet<any>("/api/ent/launch/readiness");
export const generateAllChecklists = () => apiPost<any>("/api/ent/launch/generate-all", {});
export const listChecklists = () => apiGet<any>("/api/ent/launch/checklists");
