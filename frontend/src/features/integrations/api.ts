import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/http";

import type {
  ApiKey,
  BankStatement,
  ConnectorList,
  Consent,
  Customer360,
  HealthReport,
  Overview,
  Snapshot,
  SyncJob,
  WebhookSubscription,
} from "./types";

// -- Connectors (M1) --------------------------------------------------------
export const getConnectors = () => apiGet<ConnectorList>("/api/integrations/connectors");
export const setConnectorMode = (key: string, provider_mode: string) =>
  apiPut<Record<string, unknown>>(`/api/integrations/connectors/${key}/mode`, { provider_mode });

// -- Observability (M13) ----------------------------------------------------
export const getOverview = () => apiGet<Overview>("/api/integrations/observability/overview");
export const getMetrics = () =>
  apiGet<{ providers: unknown[]; totals: Record<string, number> }>("/api/integrations/observability/metrics");
export const getHealth = () => apiGet<{ health: HealthReport[] }>("/api/integrations/observability/health");
export const getCallLogs = (limit = 100) =>
  apiGet<{ calls: Array<Record<string, unknown>> }>(`/api/integrations/observability/call-logs?limit=${limit}`);

// -- Data import + snapshots (M2/M3/M6/M7/M8) -------------------------------
export const importData = (connectorKey: string, body: Record<string, unknown>) =>
  apiPost<{ response: Record<string, unknown>; snapshot: Snapshot | null }>(
    `/api/integrations/data/${connectorKey}/import`, body);
export const importBundle = (connectorKey: string, body: Record<string, unknown>) =>
  apiPost<Record<string, unknown>>(`/api/integrations/data/${connectorKey}/import`, body);
export const getSnapshot = (connectorKey: string, entityRef: string, dataset = "default") =>
  apiGet<Snapshot>(`/api/integrations/data/${connectorKey}/${encodeURIComponent(entityRef)}?dataset=${dataset}`);
export const getSnapshotHistory = (connectorKey: string, entityRef: string, dataset = "default") =>
  apiGet<{ versions: Snapshot[] }>(
    `/api/integrations/data/${connectorKey}/${encodeURIComponent(entityRef)}/history?dataset=${dataset}`);

// -- Account Aggregator (M4/M5) ---------------------------------------------
export const createConsent = (body: Record<string, unknown>) =>
  apiPost<Consent>("/api/integrations/aa/consents", body);
export const refreshConsent = (id: number) =>
  apiPost<Consent>(`/api/integrations/aa/consents/${id}/refresh`, {});
export const importStatement = (body: Record<string, unknown>) =>
  apiPost<BankStatement>("/api/integrations/aa/statements/import", body);
export const analyzeStatement = (id: number) =>
  apiPost<Record<string, unknown>>(`/api/integrations/aa/statements/${id}/analyze`, {});
export const entityAnalytics = (entityRef: string) =>
  apiGet<Record<string, unknown>>(`/api/integrations/aa/entities/${encodeURIComponent(entityRef)}/analytics`);

// -- Synchronization (M11) --------------------------------------------------
export const runSync = (body: Record<string, unknown>) =>
  apiPost<SyncJob>("/api/integrations/sync/run", body);
export const getSyncJobs = () => apiGet<{ jobs: SyncJob[] }>("/api/integrations/sync/jobs");
export const getDeadLetters = () =>
  apiGet<{ dead_letters: Array<Record<string, unknown>> }>("/api/integrations/sync/dead-letters");

// -- Collateral (M9) --------------------------------------------------------
export const getCollateralTypes = () =>
  apiGet<{ types: Array<{ type: string; display: string; default_haircut: number; liquidity: string }> }>(
    "/api/collateral/types");
export const createCollateral = (body: Record<string, unknown>) =>
  apiPost<Record<string, unknown>>("/api/collateral", body);
export const revalueCollateral = (id: number, body: Record<string, unknown>) =>
  apiPost<Record<string, unknown>>(`/api/collateral/${id}/revalue`, body);
export const getEntityCollateral = (entityRef: string) =>
  apiGet<Record<string, unknown>>(`/api/collateral/entities/${encodeURIComponent(entityRef)}`);

// -- Customer 360 (M10) -----------------------------------------------------
export const getCustomer360 = (entityRef: string) =>
  apiGet<Customer360>(`/api/customer360/entities/${encodeURIComponent(entityRef)}`);

// -- Open API platform (M12) ------------------------------------------------
export const getApiKeys = () => apiGet<{ keys: ApiKey[] }>("/api/platform/keys");
export const createApiKey = (body: Record<string, unknown>) => apiPost<ApiKey>("/api/platform/keys", body);
export const revokeApiKey = (id: number) => apiDelete(`/api/platform/keys/${id}`);
export const getWebhooks = () =>
  apiGet<{ subscriptions: WebhookSubscription[] }>("/api/platform/webhooks");
export const getWebhookEvents = () => apiGet<{ events: string[] }>("/api/platform/webhooks/events");
export const createWebhook = (body: Record<string, unknown>) =>
  apiPost<WebhookSubscription>("/api/platform/webhooks", body);
export const getApiUsage = () =>
  apiGet<{ total_calls: number; by_endpoint: Record<string, number>; by_status: Record<string, number>; avg_latency_ms: number }>(
    "/api/platform/usage");
