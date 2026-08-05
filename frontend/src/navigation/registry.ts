/**
 * Central navigation registry — the single source of truth for the entire app's
 * navigation surface. Sidebar, command palette, universal search and breadcrumbs
 * are all generated from this file; nothing is hardcoded in the chrome anymore.
 *
 * To add a page: add one {@link NavItem} to the relevant module below and it will
 * automatically appear in the sidebar, be searchable in the palette, gain a
 * breadcrumb trail and be favourite-able / pin-able. No other file needs editing.
 *
 * This is a pure UX/metadata layer: it does not change routes, RBAC or APIs. The
 * optional `permissions` field is metadata only (reserved for future gating); the
 * backend remains the sole enforcement point.
 */

import {
  Activity,
  BarChart3,
  Bot,
  Boxes,
  Brain,
  Briefcase,
  ClipboardList,
  Compass,
  Cpu,
  Download,
  FileStack,
  FileText,
  FlaskConical,
  Gauge,
  GitBranch,
  HeartPulse,
  Landmark,
  Layers,
  LayoutDashboard,
  LineChart,
  type LucideIcon,
  Microscope,
  MessageSquareText,
  Network,
  PieChart,
  Plug,
  Radar,
  RefreshCw,
  Settings,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Siren,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
  UserCog,
  Users,
  Wallet,
  Waves,
  Webhook,
  Workflow,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Workspaces (role-oriented views that filter the navigation).
// ---------------------------------------------------------------------------

export type WorkspaceId =
  | "all"
  | "credit"
  | "risk"
  | "ml"
  | "operations"
  | "admin"
  | "treasury"
  | "compliance";

export interface Workspace {
  id: WorkspaceId;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const WORKSPACES: Workspace[] = [
  { id: "all", label: "All Workspaces", icon: Compass, description: "Every module across the platform" },
  { id: "credit", label: "Credit Analysis", icon: Briefcase, description: "Assessment, decisioning and analysis" },
  { id: "risk", label: "Risk", icon: Gauge, description: "Risk intelligence, monitoring and stress" },
  { id: "ml", label: "ML", icon: Cpu, description: "Model training, registry and MLOps" },
  { id: "operations", label: "Operations", icon: ClipboardList, description: "Credit operations and workflows" },
  { id: "admin", label: "Admin", icon: Settings, description: "Platform administration and governance" },
  { id: "treasury", label: "Treasury", icon: Wallet, description: "Treasury and financial intelligence" },
  { id: "compliance", label: "Compliance", icon: ShieldCheck, description: "Security, compliance and audit" },
];

// ---------------------------------------------------------------------------
// Types.
// ---------------------------------------------------------------------------

export interface NavItem {
  /** Stable, unique id (derived from the route). */
  id: string;
  title: string;
  href: string;
  icon: LucideIcon;
  description?: string;
  keywords?: string[];
  /** Parent module id (filled in automatically by the registry builder). */
  moduleId: string;
  /** Parent module title (filled in automatically). */
  moduleTitle: string;
  /** Workspaces this item belongs to (inherited from its module). */
  workspaces: WorkspaceId[];
  /** Reserved metadata — not enforced on the client; backend owns RBAC. */
  permissions?: string[];
  hidden?: boolean;
}

export interface NavModule {
  id: string;
  title: string;
  icon: LucideIcon;
  workspaces: WorkspaceId[];
  /** Always show this module regardless of the active workspace (e.g. Home). */
  always?: boolean;
  items: NavItem[];
}

/** Raw item shape authored below; module fields are back-filled by the builder. */
type RawItem = Omit<NavItem, "moduleId" | "moduleTitle" | "workspaces">;
interface RawModule {
  id: string;
  title: string;
  icon: LucideIcon;
  workspaces: WorkspaceId[];
  always?: boolean;
  items: RawItem[];
}

// ---------------------------------------------------------------------------
// Module + page definitions. Every href below is a real, existing route.
// ---------------------------------------------------------------------------

const RAW_MODULES: RawModule[] = [
  {
    id: "home",
    title: "Workspace",
    icon: LayoutDashboard,
    workspaces: ["all"],
    always: true,
    items: [
      { id: "dashboard", title: "Dashboard", href: "/", icon: LayoutDashboard, description: "Portfolio overview and key metrics", keywords: ["home", "overview", "kpi", "summary"] },
      { id: "enterprise", title: "Enterprise Assessment", href: "/enterprise", icon: Briefcase, description: "Company credit assessment", keywords: ["assessment", "company", "underwriting", "credit"] },
      { id: "documents", title: "Documents", href: "/documents", icon: FileStack, description: "Document intelligence and extraction", keywords: ["files", "ocr", "statements", "upload"] },
      { id: "analysis", title: "Financial Analysis", href: "/analysis", icon: LineChart, description: "Financial statement analysis", keywords: ["financials", "ratios", "cashflow", "statements"] },
      { id: "fraud", title: "Fraud Detection", href: "/fraud", icon: ShieldAlert, description: "Transaction fraud and anomaly scoring", keywords: ["fraud", "anomaly", "transaction", "aml", "suspicious"] },
    ],
  },
  {
    id: "risk",
    title: "AI Risk Intelligence",
    icon: Gauge,
    workspaces: ["risk"],
    items: [
      { id: "risk-intelligence", title: "Risk Intelligence", href: "/risk-intelligence", icon: Gauge, description: "AI risk scoring and drivers", keywords: ["risk", "score", "pd", "probability"] },
      { id: "explainability", title: "Explainability", href: "/explainability", icon: Microscope, description: "Model explanations and SHAP", keywords: ["shap", "explain", "xai", "reasons"] },
      { id: "scenario", title: "Scenario Simulator", href: "/scenario", icon: SlidersHorizontal, description: "What-if scenario simulation", keywords: ["scenario", "what-if", "simulate"] },
      { id: "stress-testing", title: "Stress Testing", href: "/stress-testing", icon: Activity, description: "Portfolio stress tests", keywords: ["stress", "shock", "scenario"] },
      { id: "portfolio-intelligence", title: "Portfolio Intelligence", href: "/portfolio-intelligence", icon: PieChart, description: "Portfolio risk analytics", keywords: ["portfolio", "concentration", "exposure"] },
      { id: "feature-importance", title: "Feature Importance", href: "/feature-importance", icon: Layers, description: "Risk feature contributions", keywords: ["features", "importance", "drivers"] },
      { id: "alerts", title: "Risk Alerts", href: "/alerts", icon: Siren, description: "Risk alerting and triggers", keywords: ["alerts", "triggers", "notifications"] },
      { id: "analyst-report", title: "Analyst Report", href: "/analyst-report", icon: FileText, description: "Generated analyst reports", keywords: ["report", "memo", "narrative"] },
    ],
  },
  {
    id: "operations",
    title: "Credit Operations",
    icon: ClipboardList,
    workspaces: ["operations", "credit"],
    items: [
      { id: "operations", title: "Credit Operations", href: "/operations", icon: ClipboardList, description: "Operations control center", keywords: ["operations", "queue", "cases"] },
      { id: "analyst-dashboard", title: "Analyst Dashboard", href: "/analyst-dashboard", icon: UserCog, description: "Analyst workspace", keywords: ["analyst", "queue", "review"] },
      { id: "manager-dashboard", title: "Manager Dashboard", href: "/manager-dashboard", icon: Users, description: "Manager oversight", keywords: ["manager", "team", "approvals"] },
      { id: "portfolio-dashboard", title: "Portfolio Dashboard", href: "/portfolio-dashboard", icon: Wallet, description: "Portfolio operations view", keywords: ["portfolio", "book", "exposure"] },
      { id: "monitoring-dashboard", title: "Monitoring Dashboard", href: "/monitoring-dashboard", icon: HeartPulse, description: "Live monitoring", keywords: ["monitoring", "health", "live"] },
      { id: "compliance-dashboard", title: "Compliance Dashboard", href: "/compliance-dashboard", icon: ShieldQuestion, description: "Compliance operations", keywords: ["compliance", "audit", "controls"] },
      { id: "admin-dashboard", title: "Administrator", href: "/admin-dashboard", icon: Settings, description: "Administration console", keywords: ["admin", "users", "roles", "settings"] },
    ],
  },
  {
    id: "ml",
    title: "ML Platform",
    icon: Cpu,
    workspaces: ["ml"],
    items: [
      { id: "ml-training", title: "Training", href: "/ml-training", icon: Cpu, description: "Model training pipelines", keywords: ["train", "pipeline", "mlops"] },
      { id: "ml-registry", title: "Model Registry", href: "/ml-registry", icon: Boxes, description: "Model versions and registry", keywords: ["registry", "versions", "models"] },
      { id: "ml-inference", title: "Inference", href: "/ml-inference", icon: Gauge, description: "Real-time inference", keywords: ["inference", "serving", "predict"] },
      { id: "ml-performance", title: "Performance", href: "/ml-performance", icon: BarChart3, description: "Model performance metrics", keywords: ["performance", "auc", "metrics"] },
      { id: "ml-feature-importance", title: "Feature Importance", href: "/ml-feature-importance", icon: Layers, description: "Model feature importance", keywords: ["features", "importance", "shap"] },
      { id: "ml-drift", title: "Drift Detection", href: "/ml-drift", icon: Waves, description: "Data and concept drift", keywords: ["drift", "psi", "monitoring"] },
      { id: "ml-stress", title: "ML Stress Testing", href: "/ml-stress", icon: Activity, description: "Model stress testing", keywords: ["stress", "robustness"] },
    ],
  },
  {
    id: "ecosystem",
    title: "Banking Ecosystem",
    icon: Plug,
    workspaces: ["operations", "admin"],
    items: [
      { id: "integrations-connectors", title: "Connectors", href: "/integrations-connectors", icon: Plug, description: "External data connectors", keywords: ["connectors", "integration", "gst", "mca", "bureau"] },
      { id: "integrations-import", title: "Data Imports", href: "/integrations-import", icon: Download, description: "Bulk data imports", keywords: ["import", "upload", "etl"] },
      { id: "account-aggregator", title: "Account Aggregator", href: "/account-aggregator", icon: Landmark, description: "Account aggregator flows", keywords: ["aa", "account aggregator", "bank data"] },
      { id: "collateral", title: "Collateral", href: "/collateral", icon: Boxes, description: "Collateral management", keywords: ["collateral", "security", "assets"] },
      { id: "customer360", title: "Customer 360", href: "/customer360", icon: Users, description: "Unified customer view", keywords: ["customer", "360", "profile"] },
      { id: "integrations-sync", title: "Portfolio Sync", href: "/integrations-sync", icon: RefreshCw, description: "Portfolio synchronisation", keywords: ["sync", "erp", "reconcile"] },
      { id: "api-platform", title: "Open API Platform", href: "/api-platform", icon: Webhook, description: "Open API and webhooks", keywords: ["api", "webhooks", "developer"] },
    ],
  },
  {
    id: "autonomous",
    title: "Autonomous Intelligence",
    icon: Bot,
    workspaces: ["risk", "ml"],
    items: [
      { id: "knowledge-graph", title: "Knowledge Graph", href: "/knowledge-graph", icon: Network, description: "Entity knowledge graph", keywords: ["graph", "entities", "relationships"] },
      { id: "risk-monitoring", title: "Risk Monitoring", href: "/risk-monitoring", icon: Radar, description: "Continuous risk monitoring", keywords: ["monitoring", "risk", "signals"] },
      { id: "early-warning", title: "Early Warning", href: "/early-warning", icon: Siren, description: "Early warning system", keywords: ["ews", "early warning", "alerts"] },
      { id: "copilot", title: "AI Copilot", href: "/copilot", icon: Bot, description: "Conversational risk copilot", keywords: ["copilot", "assistant", "chat", "ai"] },
      { id: "simulation", title: "Scenario Simulation", href: "/simulation", icon: FlaskConical, description: "Autonomous scenario simulation", keywords: ["simulation", "scenario"] },
      { id: "stress-testing-9", title: "Stress Testing (Portfolio)", href: "/stress-testing-9", icon: Activity, description: "Portfolio-wide stress testing", keywords: ["stress", "portfolio"] },
      { id: "portfolio-optimization", title: "Portfolio Optimization", href: "/portfolio-optimization", icon: TrendingUp, description: "Portfolio optimisation", keywords: ["optimization", "allocation", "portfolio"] },
      { id: "rm-workspace", title: "RM Workspace", href: "/rm-workspace", icon: UserCog, description: "Relationship manager workspace", keywords: ["rm", "relationship", "manager"] },
      { id: "command-center", title: "Command Center", href: "/command-center", icon: Compass, description: "Autonomous command center", keywords: ["command", "center", "control"] },
      { id: "nl-analytics", title: "NL Analytics", href: "/nl-analytics", icon: MessageSquareText, description: "Natural-language analytics", keywords: ["nlq", "natural language", "query", "ask"] },
      { id: "model-governance", title: "Model Governance", href: "/model-governance", icon: GitBranch, description: "Model governance and lineage", keywords: ["governance", "lineage", "audit"] },
    ],
  },
  {
    id: "banking-os",
    title: "Banking OS",
    icon: Landmark,
    workspaces: ["admin", "operations"],
    items: [
      { id: "executive-center", title: "Executive Center", href: "/executive-center", icon: PieChart, description: "Executive command view", keywords: ["executive", "ceo", "board"] },
      { id: "policy-engine", title: "Policy Engine", href: "/policy-engine", icon: ShieldQuestion, description: "Credit policy engine", keywords: ["policy", "rules", "engine", "decisioning"] },
      { id: "enterprise-search", title: "Enterprise Search", href: "/enterprise-search", icon: Layers, description: "Enterprise-wide search", keywords: ["search", "find", "discovery"] },
      { id: "committee-workspace", title: "Committee Workspace", href: "/committee-workspace", icon: Users, description: "Credit committee workspace", keywords: ["committee", "approvals", "vote"] },
      { id: "scenario-planning", title: "Scenario Planning", href: "/scenario-planning", icon: SlidersHorizontal, description: "Strategic scenario planning", keywords: ["scenario", "planning", "strategy"] },
      { id: "workflow-studio", title: "Workflow Studio", href: "/workflow-studio", icon: Workflow, description: "Visual workflow builder", keywords: ["workflow", "studio", "automation"] },
      { id: "recommendation-marketplace", title: "Recommendation Marketplace", href: "/recommendation-marketplace", icon: Plug, description: "Recommendation marketplace", keywords: ["recommendations", "marketplace"] },
      { id: "data-fabric", title: "Data Fabric", href: "/data-fabric", icon: Boxes, description: "Enterprise data fabric", keywords: ["data", "fabric", "lake"] },
      { id: "graph-analytics", title: "Graph Analytics", href: "/graph-analytics", icon: Network, description: "Graph-based analytics", keywords: ["graph", "network", "analytics"] },
      { id: "prompt-studio", title: "Prompt Studio", href: "/prompt-studio", icon: MessageSquareText, description: "Prompt engineering studio", keywords: ["prompt", "studio", "llm"] },
      { id: "llm-console", title: "Multi-LLM Console", href: "/llm-console", icon: Cpu, description: "Multi-LLM orchestration console", keywords: ["llm", "console", "models", "gpt"] },
      { id: "fairness-governance", title: "Fairness & Drift", href: "/fairness-governance", icon: Waves, description: "Fairness and drift governance", keywords: ["fairness", "bias", "drift", "governance"] },
    ],
  },
  {
    id: "ai-platform",
    title: "AI Intelligence Platform",
    icon: Sparkles,
    workspaces: ["ml", "credit"],
    items: [
      { id: "aip-rag", title: "RAG Platform", href: "/aip-rag", icon: Layers, description: "Retrieval-augmented generation", keywords: ["rag", "retrieval", "vector", "embeddings", "knowledge"] },
      { id: "aip-agents", title: "Multi-Agent System", href: "/aip-agents", icon: Bot, description: "Autonomous agent orchestration", keywords: ["agents", "multi-agent", "orchestration"] },
      { id: "aip-memory", title: "Long-Term Memory", href: "/aip-memory", icon: Brain, description: "Agent long-term memory", keywords: ["memory", "recall", "context"] },
      { id: "aip-prompts", title: "Prompt Engineering", href: "/aip-prompts", icon: MessageSquareText, description: "Prompt management", keywords: ["prompt", "engineering", "templates"] },
      { id: "aip-evaluation", title: "AI Evaluation", href: "/aip-evaluation", icon: Gauge, description: "Model and agent evaluation", keywords: ["eval", "evaluation", "benchmark"] },
      { id: "aip-investigation", title: "Investigation", href: "/aip-investigation", icon: Microscope, description: "AI-assisted investigation", keywords: ["investigation", "forensics", "case"] },
      { id: "aip-reports", title: "Report Generation", href: "/aip-reports", icon: FileText, description: "AI report generation", keywords: ["report", "generation", "narrative"] },
      { id: "aip-workflows", title: "Workflow Builder", href: "/aip-workflows", icon: GitBranch, description: "AI workflow builder", keywords: ["workflow", "builder", "automation"] },
      { id: "aip-assistant", title: "AI Assistant", href: "/aip-assistant", icon: Sparkles, description: "General AI assistant", keywords: ["assistant", "chat", "copilot"] },
      { id: "aip-research", title: "Research Assistant", href: "/aip-research", icon: FlaskConical, description: "Deep research assistant", keywords: ["research", "deep", "analysis"] },
      { id: "aip-learning", title: "Continuous Learning", href: "/aip-learning", icon: RefreshCw, description: "Continuous learning loops", keywords: ["learning", "feedback", "retrain"] },
      { id: "aip-governance", title: "AI Governance", href: "/aip-governance", icon: ShieldQuestion, description: "AI governance and policy", keywords: ["governance", "policy", "guardrails"] },
      { id: "aip-explainability", title: "Explainable AI", href: "/aip-explainability", icon: Compass, description: "Explainable AI center", keywords: ["explainable", "xai", "transparency"] },
      { id: "aip-monitoring", title: "AI Monitoring", href: "/aip-monitoring", icon: HeartPulse, description: "AI system monitoring", keywords: ["monitoring", "observability", "health"] },
    ],
  },
  {
    id: "financial",
    title: "Financial Intelligence Platform",
    icon: Wallet,
    workspaces: ["treasury", "risk"],
    items: [
      { id: "fin-treasury", title: "Treasury Intelligence", href: "/fin-treasury", icon: Wallet, description: "Treasury analytics", keywords: ["treasury", "liquidity", "cash"] },
      { id: "fin-portfolio", title: "Portfolio Intelligence", href: "/fin-portfolio", icon: PieChart, description: "Advanced portfolio analytics", keywords: ["portfolio", "allocation", "risk"] },
      { id: "fin-regulatory", title: "Basel III / IFRS 9", href: "/fin-regulatory", icon: Landmark, description: "Regulatory capital and provisioning", keywords: ["basel", "ifrs9", "regulatory", "capital", "ecl"] },
      { id: "fin-economic", title: "Economic Scenarios", href: "/fin-economic", icon: LineChart, description: "Macroeconomic scenarios", keywords: ["economic", "macro", "gdp"] },
      { id: "fin-esg", title: "Climate & ESG", href: "/fin-esg", icon: Activity, description: "Climate and ESG risk", keywords: ["esg", "climate", "sustainability"] },
      { id: "fin-market", title: "Market Intelligence", href: "/fin-market", icon: Radar, description: "Market data and signals", keywords: ["market", "prices", "signals"] },
      { id: "fin-altdata", title: "Alternative Data", href: "/fin-altdata", icon: Network, description: "Alternative data sources", keywords: ["alt data", "alternative", "signals"] },
      { id: "fin-forecast", title: "Forecasting", href: "/fin-forecast", icon: Gauge, description: "Financial forecasting", keywords: ["forecast", "projection", "predict"] },
      { id: "fin-quant", title: "Quantitative Risk", href: "/fin-quant", icon: SlidersHorizontal, description: "Quantitative risk models", keywords: ["quant", "var", "monte carlo"] },
      { id: "fin-benchmark", title: "Benchmarking", href: "/fin-benchmark", icon: Boxes, description: "Peer benchmarking", keywords: ["benchmark", "peers", "comparison"] },
      { id: "fin-executive", title: "Executive Center", href: "/fin-executive", icon: Briefcase, description: "Financial executive view", keywords: ["executive", "cfo", "summary"] },
      { id: "fin-optimize", title: "Decision Optimization", href: "/fin-optimize", icon: Sparkles, description: "Decision optimisation", keywords: ["optimization", "decision", "allocation"] },
      { id: "fin-twin", title: "Financial Digital Twin", href: "/fin-twin", icon: Cpu, description: "Financial digital twin", keywords: ["digital twin", "simulation", "model"] },
      { id: "fin-strategic", title: "Strategic Intelligence", href: "/fin-strategic", icon: FileStack, description: "Strategic intelligence", keywords: ["strategy", "strategic", "planning"] },
    ],
  },
  {
    id: "enterprise",
    title: "Enterprise Platform",
    icon: Boxes,
    workspaces: ["admin"],
    items: [
      { id: "ent-ux", title: "Enterprise UX", href: "/ent-ux", icon: Sparkles, description: "Enterprise UX center", keywords: ["ux", "experience", "design"] },
      { id: "ent-workspaces", title: "Workspaces", href: "/ent-workspaces", icon: Layers, description: "Workspace management", keywords: ["workspaces", "teams", "spaces"] },
      { id: "ent-developer", title: "Developer Platform", href: "/ent-developer", icon: Cpu, description: "Developer platform", keywords: ["developer", "sdk", "api"] },
      { id: "ent-marketplace", title: "Plugin Marketplace", href: "/ent-marketplace", icon: Plug, description: "Plugin marketplace", keywords: ["plugins", "marketplace", "extensions"] },
      { id: "ent-integration", title: "Integration Studio", href: "/ent-integration", icon: Webhook, description: "Integration studio", keywords: ["integration", "connectors", "studio"] },
      { id: "ent-data", title: "Data Management", href: "/ent-data", icon: FileStack, description: "Master data management", keywords: ["data", "mdm", "management"] },
      { id: "ent-operations", title: "Operations Center", href: "/ent-operations", icon: Activity, description: "Enterprise operations center", keywords: ["operations", "ops", "runbook"] },
      { id: "ent-security", title: "Security Center", href: "/ent-security", icon: ShieldCheck, description: "Enterprise security center", keywords: ["security", "access", "controls"] },
      { id: "ent-success", title: "Customer Success", href: "/ent-success", icon: Users, description: "Customer success", keywords: ["success", "customers", "adoption"] },
      { id: "ent-deployment", title: "Deployment", href: "/ent-deployment", icon: RefreshCw, description: "Deployment management", keywords: ["deployment", "release", "rollout"] },
      { id: "ent-monitoring", title: "Monitoring", href: "/ent-monitoring", icon: Radar, description: "Enterprise monitoring", keywords: ["monitoring", "observability", "uptime"] },
      { id: "ent-bi", title: "Business Intelligence", href: "/ent-bi", icon: PieChart, description: "Business intelligence", keywords: ["bi", "analytics", "reports"] },
      { id: "ent-launch", title: "Launch Readiness", href: "/ent-launch", icon: ClipboardList, description: "Launch readiness", keywords: ["launch", "readiness", "checklist"] },
    ],
  },
  {
    id: "security",
    title: "Security & Compliance",
    icon: ShieldCheck,
    workspaces: ["compliance", "admin"],
    items: [
      { id: "security-dashboard", title: "Security Center", href: "/security-dashboard", icon: ShieldCheck, description: "Security posture and findings", keywords: ["security", "compliance", "owasp", "posture", "threats"] },
    ],
  },
  {
    id: "legacy",
    title: "Legacy",
    icon: Brain,
    workspaces: ["credit"],
    items: [
      { id: "predict", title: "Credit Prediction", href: "/predict", icon: Brain, description: "Consumer credit scoring (legacy)", keywords: ["predict", "score", "consumer", "legacy"] },
    ],
  },
];

// ---------------------------------------------------------------------------
// Build the resolved registry (back-fill module fields onto each item).
// ---------------------------------------------------------------------------

export const NAV_MODULES: NavModule[] = RAW_MODULES.map((m) => ({
  id: m.id,
  title: m.title,
  icon: m.icon,
  workspaces: m.workspaces,
  always: m.always,
  items: m.items.map((it) => ({
    ...it,
    moduleId: m.id,
    moduleTitle: m.title,
    workspaces: m.workspaces,
  })),
}));

/** Flat list of every navigable page — used by search and the palette. */
export const NAV_ITEMS: NavItem[] = NAV_MODULES.flatMap((m) => m.items).filter((it) => !it.hidden);

const ITEMS_BY_ID = new Map(NAV_ITEMS.map((it) => [it.id, it]));
const MODULES_BY_ID = new Map(NAV_MODULES.map((m) => [m.id, m]));

export function getItemById(id: string): NavItem | undefined {
  return ITEMS_BY_ID.get(id);
}

export function getModuleById(id: string): NavModule | undefined {
  return MODULES_BY_ID.get(id);
}

/**
 * Resolve a pathname to the best-matching nav item. Exact match wins; otherwise
 * the longest href that prefixes the path (so nested/child routes still light up
 * their parent). The root "/" only matches exactly.
 */
export function resolvePathToItem(pathname: string): NavItem | undefined {
  const path = pathname.replace(/\/+$/, "") || "/";
  let best: NavItem | undefined;
  let bestLen = -1;
  for (const it of NAV_ITEMS) {
    const href = it.href.replace(/\/+$/, "") || "/";
    if (href === "/") {
      if (path === "/" && bestLen < 0) best = it;
      continue;
    }
    if (path === href || path.startsWith(href + "/")) {
      if (href.length > bestLen) {
        best = it;
        bestLen = href.length;
      }
    }
  }
  return best;
}

export interface Crumb {
  label: string;
  href?: string;
}

/** Breadcrumb trail for a path: Home › Module › Page. */
export function breadcrumbsFor(pathname: string): Crumb[] {
  const item = resolvePathToItem(pathname);
  const home: Crumb = { label: "Dashboard", href: "/" };
  if (!item) return [home];
  if (item.id === "dashboard") return [home];
  const module = getModuleById(item.moduleId);
  const crumbs: Crumb[] = [home];
  if (module && module.id !== "home") {
    // Module crumb links to the module's first page.
    crumbs.push({ label: module.title, href: module.items[0]?.href });
  }
  crumbs.push({ label: item.title });
  return crumbs;
}

/** Whether a module should be visible in the given workspace. */
export function moduleInWorkspace(module: NavModule, workspace: WorkspaceId): boolean {
  if (workspace === "all" || module.always) return true;
  return module.workspaces.includes(workspace);
}
