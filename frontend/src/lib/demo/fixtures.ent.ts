/**
 * Demo Mode fixtures for the Enterprise Platform (`/api/ent/*`, Track 4).
 *
 * These populate the enterprise SaaS control-plane pages (UX, workspaces,
 * developer, marketplace, integration, data/MDM, operations, security, customer
 * success, deployment, monitoring, BI and launch readiness) so a product demo
 * shows a fully-provisioned platform instead of empty states.
 *
 * The tenants / customers are the SAME real companies used across every other
 * demo view (Reliance Industries, Tata Steel, Infosys, …) and the same fixed
 * roster of bankers, so the story stays coherent across modules.
 *
 * All monetary values are absolute Indian Rupees (₹). `cr(48)` === ₹48 Cr.
 * Each entry is a factory returning a FRESH object literal per call.
 */

import {
  COMPANIES,
  MONTHS_12,
  cr,
  daysAgo,
  daysAhead,
  userById,
} from "./enterprise-data";

/** Deterministic-but-varied series generator over the 12 month labels. */
const series = (base: number, step: number, wobble: number) =>
  MONTHS_12.map((month, i) => ({
    month,
    value: Math.round(base + step * i + wobble * Math.sin(i * 1.3)),
  }));

// The eight largest borrowers double as the platform's marquee tenants.
const TENANTS = COMPANIES.slice(0, 8);

// ---------------------------------------------------------------------------
// M1 — UX / personalization
// ---------------------------------------------------------------------------

const uxPreferences = () => ({
  user_id: 4,
  theme: "system",
  density: "comfortable",
  accent: "indigo",
  reduced_motion: false,
  sidebar_collapsed: false,
  default_landing: "/portfolio",
  keyboard_shortcuts_enabled: true,
  number_format: "en-IN",
  updated_at: daysAgo(2),
});

const uxLayouts = () => ({
  layouts: [
    { layout_id: "lay_exec_home", name: "Executive Home", scope: "personal", owner: userById(4).name, widgets: 8, is_default: true, updated_at: daysAgo(1) },
    { layout_id: "lay_risk_wall", name: "Risk War Room", scope: "team", owner: userById(4).name, widgets: 11, is_default: false, updated_at: daysAgo(4) },
    { layout_id: "lay_analyst_desk", name: "Analyst Desk", scope: "personal", owner: userById(1).name, widgets: 6, is_default: false, updated_at: daysAgo(3) },
    { layout_id: "lay_treasury", name: "Treasury Cockpit", scope: "department", owner: userById(6).name, widgets: 9, is_default: false, updated_at: daysAgo(6) },
    { layout_id: "lay_board", name: "Board Pack", scope: "organization", owner: userById(4).name, widgets: 12, is_default: false, updated_at: daysAgo(9) },
  ],
});

// ---------------------------------------------------------------------------
// M2 — Workspaces
// ---------------------------------------------------------------------------

const workspaces = () => ({
  workspaces: [
    { workspace_id: "ws_corp_west", name: "Corporate Credit — West", workspace_type: "team", owner: userById(2).name, members: 9, items: 24, updated_at: daysAgo(0) },
    { workspace_id: "ws_risk_compliance", name: "Risk & Compliance", workspace_type: "department", owner: userById(4).name, members: 14, items: 41, updated_at: daysAgo(1) },
    { workspace_id: "ws_treasury", name: "Treasury & ALM", workspace_type: "team", owner: userById(6).name, members: 6, items: 18, updated_at: daysAgo(2) },
    { workspace_id: "ws_exec", name: "Executive Committee", workspace_type: "organization", owner: userById(4).name, members: 11, items: 33, updated_at: daysAgo(1) },
    { workspace_id: "ws_priya_desk", name: "Priya — Personal Desk", workspace_type: "personal", owner: userById(1).name, members: 1, items: 12, updated_at: daysAgo(0) },
    { workspace_id: "ws_shared_syndication", name: "Syndication Deal Room", workspace_type: "shared", owner: userById(3).name, members: 8, items: 27, updated_at: daysAgo(3) },
  ],
});

// ---------------------------------------------------------------------------
// M3 — Developer platform
// ---------------------------------------------------------------------------

const developerExplorer = () => ({
  total_paths: 1042,
  total_operations: 1873,
  openapi_version: "3.1.0",
  api_version: "v1.0.0",
  tags: [
    { name: "credit", operations: 214 },
    { name: "risk", operations: 187 },
    { name: "treasury", operations: 96 },
    { name: "portfolio", operations: 142 },
    { name: "ml", operations: 168 },
    { name: "saas", operations: 205 },
    { name: "enterprise", operations: 104 },
  ],
  authenticated: true,
});

const developerKeys = () => ({
  api_keys: [
    { api_key_id: "key_prod_01", name: "Core Banking Integration", prefix: "ak_live_9f4c", environment: "production", status: "active", scopes: ["credit:read", "portfolio:read"], created_at: daysAgo(210), last_used_at: daysAgo(0) },
    { api_key_id: "key_prod_02", name: "Bureau Ingestion Service", prefix: "ak_live_2b7e", environment: "production", status: "active", scopes: ["bureau:write"], created_at: daysAgo(168), last_used_at: daysAgo(0) },
    { api_key_id: "key_prod_03", name: "Board Reporting Export", prefix: "ak_live_5a1d", environment: "production", status: "active", scopes: ["bi:read"], created_at: daysAgo(94), last_used_at: daysAgo(1) },
    { api_key_id: "key_stg_01", name: "Staging Smoke Tests", prefix: "ak_test_c30f", environment: "staging", status: "active", scopes: ["*:read"], created_at: daysAgo(60), last_used_at: daysAgo(0) },
    { api_key_id: "key_stg_02", name: "Partner Sandbox — Razorpay", prefix: "ak_test_88ba", environment: "sandbox", status: "active", scopes: ["payments:read"], created_at: daysAgo(45), last_used_at: daysAgo(2) },
    { api_key_id: "key_prod_04", name: "Legacy ETL (deprecated)", prefix: "ak_live_71e0", environment: "production", status: "revoked", scopes: ["data:read"], created_at: daysAgo(420), last_used_at: daysAgo(38) },
  ],
});

const developerWebhooks = () => ({
  webhooks: [
    { webhook_id: "wh_01", url: "https://ops.bank.internal/hooks/credit-decision", events: ["decision.approved", "decision.rejected"], status: "active", secret_set: true, last_delivery: daysAgo(0), success_rate_pct: 99.8 },
    { webhook_id: "wh_02", url: "https://siem.bank.internal/hooks/security", events: ["security.anomaly", "access.review.completed"], status: "active", secret_set: true, last_delivery: daysAgo(0), success_rate_pct: 100 },
    { webhook_id: "wh_03", url: "https://slack.com/api/hooks/T02/collections", events: ["incident.opened", "sla.breached"], status: "active", secret_set: true, last_delivery: daysAgo(1), success_rate_pct: 99.2 },
    { webhook_id: "wh_04", url: "https://erp.bank.internal/hooks/disbursement", events: ["disbursement.completed"], status: "active", secret_set: true, last_delivery: daysAgo(0), success_rate_pct: 98.6 },
    { webhook_id: "wh_05", url: "https://partner.razorpay.dev/hooks/test", events: ["payment.reconciled"], status: "paused", secret_set: true, last_delivery: daysAgo(5), success_rate_pct: 96.1 },
  ],
});

const developerRequests = () => ({
  requests: [
    { request_id: "req_9001", method: "GET", path: "/api/portfolio/summary", status_code: 200, latency_ms: 84, api_key: "ak_live_9f4c", at: daysAgo(0) },
    { request_id: "req_9002", method: "POST", path: "/api/credit/applications", status_code: 201, latency_ms: 212, api_key: "ak_live_9f4c", at: daysAgo(0) },
    { request_id: "req_9003", method: "GET", path: "/api/fin/treasury/kpis", status_code: 200, latency_ms: 61, api_key: "ak_live_5a1d", at: daysAgo(0) },
    { request_id: "req_9004", method: "POST", path: "/api/bureau/pull", status_code: 200, latency_ms: 438, api_key: "ak_live_2b7e", at: daysAgo(1) },
    { request_id: "req_9005", method: "GET", path: "/api/ml/models", status_code: 200, latency_ms: 73, api_key: "ak_test_c30f", at: daysAgo(1) },
    { request_id: "req_9006", method: "POST", path: "/api/credit/decisions/4216", status_code: 422, latency_ms: 55, api_key: "ak_live_9f4c", at: daysAgo(1) },
    { request_id: "req_9007", method: "GET", path: "/api/ent/bi/board-report", status_code: 200, latency_ms: 129, api_key: "ak_live_5a1d", at: daysAgo(2) },
  ],
  total: 1846203,
  window: "last 7 days",
});

// ---------------------------------------------------------------------------
// M4 — Marketplace
// ---------------------------------------------------------------------------

const marketplace = () => ({
  plugins: [
    { plugin_id: "plg_bureau", name: "Credit Bureau Connector", latest_version: "3.2.1", category: "connector", status: "published", install_count: 47, publisher: "Platform Team", rating: 4.8 },
    { plugin_id: "plg_gst", name: "GST Data Connector", latest_version: "2.7.0", category: "connector", status: "published", install_count: 41, publisher: "Platform Team", rating: 4.7 },
    { plugin_id: "plg_esg", name: "ESG Data Provider", latest_version: "1.9.4", category: "data", status: "published", install_count: 33, publisher: "Sustainalytics Partner", rating: 4.5 },
    { plugin_id: "plg_slack", name: "Slack Alerts", latest_version: "2.1.0", category: "notification", status: "published", install_count: 52, publisher: "Platform Team", rating: 4.9 },
    { plugin_id: "plg_mca", name: "MCA / Company Registry", latest_version: "1.4.2", category: "connector", status: "published", install_count: 29, publisher: "Platform Team", rating: 4.4 },
    { plugin_id: "plg_aa", name: "Account Aggregator Gateway", latest_version: "1.2.0", category: "connector", status: "published", install_count: 26, publisher: "Sahamati Partner", rating: 4.3 },
    { plugin_id: "plg_dash_esg", name: "ESG Risk Dashboard", latest_version: "0.9.0", category: "dashboard", status: "in_review", install_count: 0, publisher: "Analytics Guild", rating: 0 },
    { plugin_id: "plg_ifrs9", name: "IFRS-9 ECL Calculator", latest_version: "2.0.3", category: "analytics", status: "published", install_count: 38, publisher: "Risk Engineering", rating: 4.6 },
  ],
});

const marketplaceAnalytics = () => ({
  total_plugins: 8,
  published: 6,
  total_installs: 266,
  revenue_ready: 5,
});

// ---------------------------------------------------------------------------
// M5 — Integration studio
// ---------------------------------------------------------------------------

const integration = () => ({
  pipelines: [
    { pipeline_id: "pipe_bureau_sync", name: "Nightly Bureau Sync", node_count: 5, status: "active", last_run: daysAgo(0), last_status: "success" },
    { pipeline_id: "pipe_gst_ingest", name: "GST Returns Ingestion", node_count: 4, status: "active", last_run: daysAgo(0), last_status: "success" },
    { pipeline_id: "pipe_erp_disb", name: "ERP Disbursement Feed", node_count: 6, status: "active", last_run: daysAgo(0), last_status: "success" },
    { pipeline_id: "pipe_esg_enrich", name: "ESG Score Enrichment", node_count: 4, status: "active", last_run: daysAgo(1), last_status: "success" },
    { pipeline_id: "pipe_collateral", name: "Collateral Valuation Refresh", node_count: 5, status: "paused", last_run: daysAgo(3), last_status: "warning" },
    { pipeline_id: "pipe_aa_pull", name: "Account Aggregator Pull", node_count: 3, status: "active", last_run: daysAgo(0), last_status: "success" },
  ],
});

const integrationNodeTypes = () => ({
  node_types: [
    { type: "source", label: "Source", description: "Read from a connector, database or file drop", inputs: 0, outputs: 1 },
    { type: "transform", label: "Transform", description: "Map, filter, aggregate or enrich records", inputs: 1, outputs: 1 },
    { type: "router", label: "Router", description: "Route events on rules to multiple branches", inputs: 1, outputs: 2 },
    { type: "validator", label: "Validator", description: "Apply data-quality rules and reject bad rows", inputs: 1, outputs: 2 },
    { type: "sink", label: "Sink", description: "Write to a destination system or warehouse", inputs: 1, outputs: 0 },
  ],
});

// ---------------------------------------------------------------------------
// M6 — Data management (MDM)
// ---------------------------------------------------------------------------

const dataCatalog = () => ({
  entities: {
    customer: { records: 1284, avg_quality: 0.96, stewards: 3, last_updated: daysAgo(0) },
    application: { records: 2137, avg_quality: 0.94, stewards: 2, last_updated: daysAgo(0) },
    collateral: { records: 872, avg_quality: 0.91, stewards: 2, last_updated: daysAgo(1) },
    counterparty: { records: 640, avg_quality: 0.93, stewards: 1, last_updated: daysAgo(1) },
    facility: { records: 1508, avg_quality: 0.95, stewards: 2, last_updated: daysAgo(0) },
    guarantor: { records: 418, avg_quality: 0.89, stewards: 1, last_updated: daysAgo(2) },
  },
  total_records: 6859,
  golden_records: 1284,
});

const dataGolden = () => ({
  entity_type: "customer",
  records: TENANTS.map((c, i) => ({
    golden_id: `gold_${c.id}`,
    natural_key: c.name,
    record: { name: c.name, sector: c.sector, region: c.region, rating: c.rating, cin: `L${(24000 + i * 137).toString().padStart(5, "0")}MH${1998 + i}PLC${(100000 + c.id).toString()}` },
    quality: +(0.9 + (c.id % 5) * 0.018).toFixed(2),
    sources_merged: 2 + (c.id % 3),
    steward: userById(5).name,
    updated_at: daysAgo(c.id % 9),
  })),
});

// ---------------------------------------------------------------------------
// M7 — Operations center
// ---------------------------------------------------------------------------

const operationsDashboard = () => ({
  overall_status: "healthy",
  components: {
    platform: { status: "healthy", score: 99 },
    ai: { status: "warning", score: 86 },
    ml: { status: "healthy", score: 97 },
    connectors: { status: "healthy", score: 98 },
    storage: { status: "healthy", score: 99 },
    queue: { status: "degraded", score: 78 },
    jobs: { status: "healthy", score: 96 },
  },
  open_incidents: 2,
  active_runbooks: 6,
  uptime_30d_pct: 99.97,
});

const operationsIncidents = () => ({
  incidents: [
    { incident_id: "inc_4501", title: "AI copilot latency spike", component: "ai", severity: "sev2", status: "investigating", opened_at: daysAgo(0), assignee: userById(4).name },
    { incident_id: "inc_4498", title: "Job queue backlog on bureau sync", component: "queue", severity: "sev3", status: "monitoring", opened_at: daysAgo(1), assignee: userById(2).name },
    { incident_id: "inc_4492", title: "GST connector 429 rate-limit errors", component: "connectors", severity: "sev3", status: "resolved", opened_at: daysAgo(4), assignee: userById(3).name },
    { incident_id: "inc_4487", title: "Elevated p99 on portfolio API", component: "platform", severity: "sev2", status: "resolved", opened_at: daysAgo(7), assignee: userById(1).name },
    { incident_id: "inc_4479", title: "Storage volume nearing 80% on staging", component: "storage", severity: "sev4", status: "resolved", opened_at: daysAgo(11), assignee: userById(6).name },
  ],
});

const operationsRunbooks = () => ({
  runbooks: [
    { runbook_id: "rb_ai_latency", title: "AI Latency Degradation", category: "ai", steps: 7, last_run: daysAgo(0) },
    { runbook_id: "rb_queue_backlog", title: "Job Queue Backlog Recovery", category: "queue", steps: 5, last_run: daysAgo(1) },
    { runbook_id: "rb_connector_ratelimit", title: "Connector Rate-Limit Handling", category: "connectors", steps: 4, last_run: daysAgo(4) },
    { runbook_id: "rb_db_failover", title: "Primary Database Failover", category: "storage", steps: 9, last_run: daysAgo(30) },
    { runbook_id: "rb_incident_bridge", title: "Sev1 Incident Bridge", category: "process", steps: 6, last_run: daysAgo(18) },
    { runbook_id: "rb_key_rotation", title: "Emergency API Key Rotation", category: "security", steps: 5, last_run: daysAgo(9) },
  ],
});

// ---------------------------------------------------------------------------
// M8 — Security center
// ---------------------------------------------------------------------------

const securityDashboard = () => ({
  posture: "Strong",
  security_score: 91,
  open_events: 7,
  critical_events: 1,
  mfa_coverage_pct: 100,
  devices_trusted: 214,
  access_reviews_pending: 2,
  last_key_rotation: daysAgo(9),
});

const securityEvents = () => ({
  events: [
    { event_id: "sec_7701", event_type: "impossible_travel", subject_ref: "arjun.rao@bank.com", severity: "critical", status: "open", detected_at: daysAgo(0) },
    { event_id: "sec_7698", event_type: "privilege_escalation_attempt", subject_ref: "svc-etl@bank.com", severity: "high", status: "investigating", detected_at: daysAgo(0) },
    { event_id: "sec_7695", event_type: "new_device_login", subject_ref: "neha.gupta@bank.com", severity: "medium", status: "open", detected_at: daysAgo(1) },
    { event_id: "sec_7690", event_type: "repeated_failed_login", subject_ref: "unknown@ext.net", severity: "medium", status: "contained", detected_at: daysAgo(1) },
    { event_id: "sec_7684", event_type: "anomalous_data_export", subject_ref: "priya.menon@bank.com", severity: "high", status: "resolved", detected_at: daysAgo(3) },
    { event_id: "sec_7677", event_type: "api_key_used_after_hours", subject_ref: "ak_live_2b7e", severity: "low", status: "resolved", detected_at: daysAgo(5) },
  ],
});

// ---------------------------------------------------------------------------
// M9 — Customer success
// ---------------------------------------------------------------------------

const successCustomers = () => ({
  customers: TENANTS.map((c, i) => ({
    customer_id: c.id,
    name: c.name,
    health_score: [92, 88, 95, 71, 64, 58, 84, 90][i] ?? 80,
    stage: ["adopted", "adopted", "champion", "onboarding", "at_risk", "at_risk", "adopted", "champion"][i] ?? "adopted",
    arr: cr([58, 42, 36, 28, 24, 21, 18, 15][i] ?? 12),
    plan: ["Enterprise", "Enterprise", "Enterprise", "Growth", "Growth", "Growth", "Growth", "Enterprise"][i] ?? "Growth",
    renewal_at: daysAhead(60 + i * 22),
    csm: userById((i % 3) + 1).name,
  })),
});

const successDashboard = () => ({
  customers: 42,
  total_arr: cr(486),
  avg_health: 79,
  at_risk: 5,
  nrr_pct: 118,
  gross_churn_pct: 4.2,
  onboarding_in_progress: 3,
  open_tickets: 14,
});

// ---------------------------------------------------------------------------
// M10 — Deployment platform
// ---------------------------------------------------------------------------

const deploymentEnvironments = () => ({
  environments: [
    { environment_id: "env_prod", name: "Production", current_version: "1.0.0", status: "healthy", region: "ap-south-1", last_deploy: daysAgo(3) },
    { environment_id: "env_staging", name: "Staging", current_version: "1.1.0-rc.2", status: "healthy", region: "ap-south-1", last_deploy: daysAgo(0) },
    { environment_id: "env_test", name: "Test", current_version: "1.1.0-rc.3", status: "degraded", region: "ap-south-1", last_deploy: daysAgo(0) },
    { environment_id: "env_dev", name: "Development", current_version: "1.2.0-dev", status: "healthy", region: "ap-south-1", last_deploy: daysAgo(0) },
    { environment_id: "env_dr", name: "Disaster Recovery", current_version: "1.0.0", status: "healthy", region: "ap-southeast-1", last_deploy: daysAgo(3) },
  ],
});

const deploymentVersions = () => ({
  environments: {
    Production: "1.0.0",
    Staging: "1.1.0-rc.2",
    Test: "1.1.0-rc.3",
    Development: "1.2.0-dev",
    "Disaster Recovery": "1.0.0",
  },
  success_rate_pct: 97.4,
  total_deployments: 342,
  latest_version: "1.0.0",
  rollbacks_90d: 4,
});

const deploymentHistory = () => ({
  deployments: [
    { deployment_id: "dep_512", environment: "Production", version: "1.0.0", strategy: "blue_green", status: "succeeded", actor: userById(4).name, notes: "v1.0.0 GA release", at: daysAgo(3) },
    { deployment_id: "dep_509", environment: "Staging", version: "1.1.0-rc.2", strategy: "rolling", status: "succeeded", actor: userById(2).name, notes: "Release candidate for 1.1", at: daysAgo(0) },
    { deployment_id: "dep_505", environment: "Production", version: "0.9.4", strategy: "canary", status: "succeeded", actor: userById(4).name, notes: "Canary 10% then full", at: daysAgo(12) },
    { deployment_id: "dep_501", environment: "Production", version: "0.9.3", strategy: "blue_green", status: "rolled_back", actor: userById(2).name, notes: "Rolled back — elevated error rate", at: daysAgo(19) },
    { deployment_id: "dep_498", environment: "Test", version: "1.1.0-rc.1", strategy: "rolling", status: "succeeded", actor: userById(1).name, notes: "Feature freeze build", at: daysAgo(22) },
    { deployment_id: "dep_494", environment: "Disaster Recovery", version: "1.0.0", strategy: "blue_green", status: "succeeded", actor: userById(6).name, notes: "DR parity restore", at: daysAgo(3) },
  ],
});

// ---------------------------------------------------------------------------
// M11 — Monitoring platform
// ---------------------------------------------------------------------------

const costByService = [
  { service: "AI Inference (LLM)", usd: 8420, share_pct: 34 },
  { service: "ML Training & Scoring", usd: 5210, share_pct: 21 },
  { service: "Compute (API)", usd: 4180, share_pct: 17 },
  { service: "Managed Database", usd: 3060, share_pct: 12 },
  { service: "Object Storage", usd: 1740, share_pct: 7 },
  { service: "Data Egress", usd: 1290, share_pct: 5 },
  { service: "Observability", usd: 980, share_pct: 4 },
];

const dependencyGraphData = {
  nodes: [
    { id: "gateway", label: "API Gateway", tier: "edge", health: "healthy" },
    { id: "credit", label: "Credit Service", tier: "core", health: "healthy" },
    { id: "risk", label: "Risk Engine", tier: "core", health: "healthy" },
    { id: "ml", label: "ML Scoring", tier: "core", health: "healthy" },
    { id: "ai", label: "AI Copilot", tier: "core", health: "warning" },
    { id: "db", label: "Primary DB", tier: "data", health: "healthy" },
    { id: "cache", label: "Redis Cache", tier: "data", health: "healthy" },
    { id: "queue", label: "Job Queue", tier: "data", health: "degraded" },
  ],
  edges: [
    { from: "gateway", to: "credit", calls_per_min: 4200, p95_ms: 96 },
    { from: "gateway", to: "risk", calls_per_min: 1850, p95_ms: 142 },
    { from: "credit", to: "ml", calls_per_min: 980, p95_ms: 210 },
    { from: "credit", to: "db", calls_per_min: 5100, p95_ms: 18 },
    { from: "risk", to: "ml", calls_per_min: 640, p95_ms: 205 },
    { from: "ai", to: "cache", calls_per_min: 720, p95_ms: 9 },
    { from: "credit", to: "queue", calls_per_min: 310, p95_ms: 44 },
  ],
};

const monitoringDashboard = () => ({
  latency: { p50_ms: 42, p95_ms: 118, p99_ms: 236, error_rate_pct: 0.14 },
  sla: { compliance_pct: 99.96, uptime_pct: 99.97, target_pct: 99.9, breaches_30d: 1 },
  cost: {
    total_usd: 24880,
    currency: "USD",
    period: "current month",
    by_service: costByService,
    trend: series(21000, 380, 900),
  },
  dependency_graph: dependencyGraphData,
  throughput_rpm: 8250,
  traces_sampled_24h: 1420000,
});

const monitoringCost = () => ({
  total_usd: 24880,
  currency: "USD",
  period: "current month",
  forecast_usd: 26150,
  by_service: costByService.map((s) => ({ ...s })),
  trend: series(21000, 380, 900),
});

const monitoringDependencyGraph = () => ({
  nodes: dependencyGraphData.nodes.map((n) => ({ ...n })),
  edges: dependencyGraphData.edges.map((e) => ({ ...e })),
});

const monitoringSla = () => ({
  overall_compliance_pct: 99.96,
  window: "trailing 30 days",
  services: [
    { name: "API Gateway", target_pct: 99.9, actual_pct: 99.98, status: "meeting", error_budget_pct: 80 },
    { name: "Credit Service", target_pct: 99.9, actual_pct: 99.95, status: "meeting", error_budget_pct: 55 },
    { name: "Risk Engine", target_pct: 99.9, actual_pct: 99.92, status: "meeting", error_budget_pct: 22 },
    { name: "ML Scoring", target_pct: 99.5, actual_pct: 99.71, status: "meeting", error_budget_pct: 58 },
    { name: "AI Copilot", target_pct: 99.5, actual_pct: 99.34, status: "at_risk", error_budget_pct: -12 },
    { name: "Job Queue", target_pct: 99.0, actual_pct: 99.12, status: "meeting", error_budget_pct: 12 },
  ],
});

// ---------------------------------------------------------------------------
// M12 — Business intelligence
// ---------------------------------------------------------------------------

const biAnalytics = () => ({
  category: "executive",
  metrics: {
    active_tenants: 42,
    total_arr: cr(486),
    net_revenue_retention_pct: 118,
    gross_margin_pct: 74,
    active_users_30d: 1180,
    portfolio_exposure: cr(8640),
    approval_rate_pct: 75.3,
    npa_ratio_pct: 3.1,
    ai_decisions_automated_pct: 62,
    arr_trend: series(cr(360), cr(11), cr(6)),
    active_users_trend: series(880, 27, 40),
  },
  generated_at: daysAgo(0),
});

const boardReport = () => ({
  headline: "Platform crossed ₹486 Cr ARR across 42 enterprise tenants with 118% net revenue retention; portfolio quality held with NPA at 3.1% and 62% of credit decisions AI-automated.",
  period: "Q1 FY2026-27",
  sections: {
    growth: { arr: cr(486), arr_growth_qoq_pct: 14.2, new_logos: 6, net_revenue_retention_pct: 118 },
    portfolio: { exposure: cr(8640), outstanding: cr(6180), approval_rate_pct: 75.3, npa_ratio_pct: 3.1, provision_coverage_pct: 68 },
    risk: { crar_pct: 16.4, ecl_total: cr(142), watchlist_accounts: 5, critical_alerts: 3 },
    platform: { uptime_pct: 99.97, sla_compliance_pct: 99.96, automated_decisions_pct: 62, monthly_infra_usd: 24880 },
    people: { active_users_30d: 1180, mfa_coverage_pct: 100, security_score: 91 },
  },
  generated_at: daysAgo(0),
});

const biDashboards = () => ({
  dashboards: [
    { dashboard_id: "bid_exec", name: "Executive Overview", category: "executive", widgets: 10, owner: userById(4).name, shared: true },
    { dashboard_id: "bid_revenue", name: "Revenue & ARR", category: "revenue", widgets: 8, owner: userById(6).name, shared: true },
    { dashboard_id: "bid_customer", name: "Customer Health", category: "customer", widgets: 7, owner: userById(3).name, shared: true },
    { dashboard_id: "bid_risk", name: "Portfolio Risk", category: "risk", widgets: 12, owner: userById(4).name, shared: true },
    { dashboard_id: "bid_ops", name: "Operational KPIs", category: "operational", widgets: 9, owner: userById(2).name, shared: false },
    { dashboard_id: "bid_growth", name: "Growth & Adoption", category: "growth", widgets: 6, owner: userById(1).name, shared: false },
  ],
});

// ---------------------------------------------------------------------------
// M13 — Launch readiness
// ---------------------------------------------------------------------------

const launchReadiness = () => ({
  overall_readiness_score: 94,
  grade: "A",
  commercial_ready: true,
  by_type: {
    production: 98,
    deployment: 96,
    security: 95,
    operational: 93,
    release: 97,
    disaster_recovery: 90,
    business_continuity: 88,
    scaling: 92,
    performance: 95,
    monitoring: 96,
  },
  blocking_items: 1,
  generated_at: daysAgo(0),
});

const launchChecklists = () => ({
  checklists: [
    { checklist_id: "cl_production", title: "Production Readiness", completed: 24, total: 25, readiness_score: 98 },
    { checklist_id: "cl_deployment", title: "Deployment & Release", completed: 18, total: 19, readiness_score: 96 },
    { checklist_id: "cl_security", title: "Security & Compliance", completed: 21, total: 22, readiness_score: 95 },
    { checklist_id: "cl_operational", title: "Operational Excellence", completed: 15, total: 16, readiness_score: 93 },
    { checklist_id: "cl_dr", title: "Disaster Recovery", completed: 9, total: 10, readiness_score: 90 },
    { checklist_id: "cl_bcp", title: "Business Continuity", completed: 7, total: 8, readiness_score: 88 },
    { checklist_id: "cl_scaling", title: "Scaling & Capacity", completed: 11, total: 12, readiness_score: 92 },
    { checklist_id: "cl_perf", title: "Performance & Load", completed: 12, total: 13, readiness_score: 95 },
    { checklist_id: "cl_monitoring", title: "Monitoring & Alerting", completed: 14, total: 15, readiness_score: 96 },
  ],
});

// ---------------------------------------------------------------------------
// Registry — path-suffix → fresh sample response factory.
// ---------------------------------------------------------------------------

export const ENT_FIXTURES: Record<string, () => unknown> = {
  // M1 UX
  "/api/ent/ux/preferences": uxPreferences,
  "/api/ent/ux/layouts": uxLayouts,
  // M2 Workspaces
  "/api/ent/workspaces": workspaces,
  // M3 Developer
  "/api/ent/developer/explorer": developerExplorer,
  "/api/ent/developer/keys": developerKeys,
  "/api/ent/developer/webhooks": developerWebhooks,
  "/api/ent/developer/requests": developerRequests,
  // M4 Marketplace
  "/api/ent/marketplace/analytics/summary": marketplaceAnalytics,
  "/api/ent/marketplace": marketplace,
  // M5 Integration
  "/api/ent/integration/node-types": integrationNodeTypes,
  "/api/ent/integration": integration,
  // M6 Data
  "/api/ent/data/catalog": dataCatalog,
  "/api/ent/data/golden": dataGolden,
  // M7 Operations
  "/api/ent/operations/dashboard": operationsDashboard,
  "/api/ent/operations/incidents": operationsIncidents,
  "/api/ent/operations/runbooks": operationsRunbooks,
  // M8 Security
  "/api/ent/security/dashboard": securityDashboard,
  "/api/ent/security/events": securityEvents,
  // M9 Customer success
  "/api/ent/success/dashboard": successDashboard,
  "/api/ent/success": successCustomers,
  // M10 Deployment
  "/api/ent/deployment/environments": deploymentEnvironments,
  "/api/ent/deployment/versions": deploymentVersions,
  "/api/ent/deployment/history": deploymentHistory,
  // M11 Monitoring
  "/api/ent/monitoring/dashboard": monitoringDashboard,
  "/api/ent/monitoring/cost": monitoringCost,
  "/api/ent/monitoring/dependency-graph": monitoringDependencyGraph,
  "/api/ent/monitoring/sla": monitoringSla,
  // M12 BI
  "/api/ent/bi/analytics": biAnalytics,
  "/api/ent/bi/board-report": boardReport,
  "/api/ent/bi/dashboards": biDashboards,
  // M13 Launch
  "/api/ent/launch/readiness": launchReadiness,
  "/api/ent/launch/checklists": launchChecklists,
};
