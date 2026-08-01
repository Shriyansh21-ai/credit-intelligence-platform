// Phase 7 — Banking Ecosystem Integration Platform types.

export interface ConnectorCatalogEntry {
  key: string;
  category: string | null;
  modes: string[];
}

export interface ConnectorConfig {
  connector_key: string;
  category: string;
  provider_mode: string;
  enabled: boolean;
  config: Record<string, unknown>;
  has_credentials: boolean;
  rate_limit_per_sec: number | null;
  timeout_seconds: number | null;
  updated_at: string | null;
}

export interface ConnectorList {
  connectors: ConnectorCatalogEntry[];
  configs: ConnectorConfig[];
}

export interface ProviderMetrics {
  category: string;
  provider: string;
  calls: number;
  successes: number;
  failures: number;
  retries: number;
  cache_hits: number;
  circuit_rejections: number;
  success_rate: number;
  failure_rate: number;
  avg_latency_ms: number;
  max_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
}

export interface HealthReport {
  provider: string;
  category: string;
  mode: string;
  status: string;
  detail: string;
  circuit_state: string;
  latency_ms: number | null;
}

export interface Overview {
  connectors: Array<{
    connector_key: string;
    category: string | null;
    modes_available: string[];
    active_mode: string;
    enabled: boolean;
    recent: Record<string, number>;
  }>;
  live_metrics: ProviderMetrics[];
  totals: Record<string, number>;
}

export interface Snapshot {
  id: number;
  connector_key: string;
  provider: string;
  mode: string;
  dataset: string;
  entity_ref: string;
  version: number;
  is_current: boolean;
  payload: Record<string, unknown>;
  content_hash: string;
  fetched_at: string | null;
}

export interface Consent {
  id: number;
  handle: string;
  entity_ref: string;
  status: string;
  purpose: string;
  scope: Record<string, unknown>;
  accounts: unknown[];
  expires_at: string | null;
}

export interface BankStatement {
  id: number;
  entity_ref: string;
  account_ref: string;
  bank_name: string | null;
  opening_balance: number | null;
  closing_balance: number | null;
  txn_count: number;
}

export interface CollateralItem {
  id: number;
  collateral_type: string;
  display: string;
  description: string;
  market_value: number;
  haircut_pct: number;
  realizable_value: number;
  loan_amount: number | null;
  ltv: number | null;
  coverage_ratio: number | null;
  status: string;
}

export interface CoverageSummary {
  item_count: number;
  total_market_value: number;
  total_realizable_value: number;
  total_exposure: number;
  coverage_ratio: number | null;
  secured: boolean;
  by_type: Record<string, number>;
}

export interface SyncJob {
  id: number;
  sync_type: string;
  connectors: string[];
  status: string;
  stats: Record<string, number>;
  conflicts: unknown[];
  total: number;
  processed: number;
  failed: number;
  created_at: string | null;
}

export interface ApiKey {
  id: number;
  name: string;
  key_prefix: string;
  scopes: string[];
  active: boolean;
  rate_limit_per_min: number;
  api_key?: string;
}

export interface WebhookSubscription {
  id: number;
  url: string;
  events: string[];
  active: boolean;
  has_secret: boolean;
}

export interface Customer360 {
  entity_ref: string | null;
  application: Record<string, unknown> | null;
  assessment: Record<string, unknown> | null;
  gst: Record<string, unknown> | null;
  mca: Record<string, unknown> | null;
  bureau: Record<string, unknown> | null;
  erp: Record<string, unknown> | null;
  payments: Record<string, unknown> | null;
  bank_analytics: Record<string, unknown> | null;
  collateral: { summary?: CoverageSummary; items?: CollateralItem[] };
  relationship_network: { nodes: unknown[]; edges: unknown[]; node_count: number; edge_count: number };
  timeline: Array<{ at: string; type: string; detail: string }>;
  completeness: { sources_present: number; sources_total: number; score: number; detail: Record<string, boolean> };
}
