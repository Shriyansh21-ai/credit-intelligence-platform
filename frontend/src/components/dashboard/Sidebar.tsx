import { Link, useRouterState } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Brain,
  Briefcase,
  FileStack,
  ShieldAlert,
  ShieldCheck,
  BarChart3,
  LineChart,
  Settings,
  LogOut,
  Sparkles,
  X,
  Gauge,
  Microscope,
  SlidersHorizontal,
  Activity,
  PieChart,
  Layers,
  Siren,
  FileText,
  ClipboardList,
  ShieldQuestion,
  UserCog,
  Users,
  Wallet,
  HeartPulse,
  Cpu,
  Boxes,
  Waves,
  Plug,
  Download,
  Landmark,
  RefreshCw,
  Webhook,
  Network,
  Radar,
  Bot,
  FlaskConical,
  TrendingUp,
  MessageSquareText,
  GitBranch,
  Compass,
} from "lucide-react";
import { cn } from "@/lib/utils";

const primaryNav = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { label: "Enterprise Assessment", icon: Briefcase, href: "/enterprise" },
  { label: "Documents", icon: FileStack, href: "/documents" },
  { label: "Financial Analysis", icon: LineChart, href: "/analysis" },
  { label: "Fraud Detection", icon: ShieldAlert, href: "/fraud" },
  { label: "Fraud History", icon: ShieldCheck, href: "/fraud" },
  { label: "Analytics", icon: BarChart3, href: "/" },
  { label: "Settings", icon: Settings, href: "/" },
];

// Phase 4 — Enterprise AI Risk Intelligence layer.
const riskNav = [
  { label: "Risk Intelligence", icon: Gauge, href: "/risk-intelligence" },
  { label: "Explainability", icon: Microscope, href: "/explainability" },
  { label: "Scenario Simulator", icon: SlidersHorizontal, href: "/scenario" },
  { label: "Stress Testing", icon: Activity, href: "/stress-testing" },
  { label: "Portfolio Intelligence", icon: PieChart, href: "/portfolio-intelligence" },
  { label: "Feature Importance", icon: Layers, href: "/feature-importance" },
  { label: "Risk Alerts", icon: Siren, href: "/alerts" },
  { label: "Analyst Report", icon: FileText, href: "/analyst-report" },
];

// Phase 5 — Credit Decision Platform: enterprise operations dashboards.
const operationsNav = [
  { label: "Credit Operations", icon: ClipboardList, href: "/operations" },
  { label: "Analyst Dashboard", icon: UserCog, href: "/analyst-dashboard" },
  { label: "Manager Dashboard", icon: Users, href: "/manager-dashboard" },
  { label: "Portfolio Dashboard", icon: Wallet, href: "/portfolio-dashboard" },
  { label: "Monitoring Dashboard", icon: HeartPulse, href: "/monitoring-dashboard" },
  { label: "Compliance Dashboard", icon: ShieldQuestion, href: "/compliance-dashboard" },
  { label: "Administrator", icon: Settings, href: "/admin-dashboard" },
];

// Phase 6 — Enterprise ML Platform (MLOps) dashboards.
const mlPlatformNav = [
  { label: "Training", icon: Cpu, href: "/ml-training" },
  { label: "Model Registry", icon: Boxes, href: "/ml-registry" },
  { label: "Inference", icon: Gauge, href: "/ml-inference" },
  { label: "Performance", icon: BarChart3, href: "/ml-performance" },
  { label: "Feature Importance", icon: Layers, href: "/ml-feature-importance" },
  { label: "Drift Detection", icon: Waves, href: "/ml-drift" },
  { label: "ML Stress Testing", icon: Activity, href: "/ml-stress" },
];

// Phase 7 — Banking Ecosystem Integration Platform.
const integrationsNav = [
  { label: "Connectors", icon: Plug, href: "/integrations-connectors" },
  { label: "Data Imports", icon: Download, href: "/integrations-import" },
  { label: "Account Aggregator", icon: Landmark, href: "/account-aggregator" },
  { label: "Collateral", icon: Boxes, href: "/collateral" },
  { label: "Customer 360", icon: Users, href: "/customer360" },
  { label: "Portfolio Sync", icon: RefreshCw, href: "/integrations-sync" },
  { label: "Open API Platform", icon: Webhook, href: "/api-platform" },
];

// Phase 9 — Autonomous AI Banking Intelligence Platform (the "AI Brain").
const autonomousNav = [
  { label: "Knowledge Graph", icon: Network, href: "/knowledge-graph" },
  { label: "Risk Monitoring", icon: Radar, href: "/risk-monitoring" },
  { label: "Early Warning", icon: Siren, href: "/early-warning" },
  { label: "AI Copilot", icon: Bot, href: "/copilot" },
  { label: "Scenario Simulation", icon: FlaskConical, href: "/simulation" },
  { label: "Stress Testing (Portfolio)", icon: Activity, href: "/stress-testing-9" },
  { label: "Portfolio Optimization", icon: TrendingUp, href: "/portfolio-optimization" },
  { label: "RM Workspace", icon: UserCog, href: "/rm-workspace" },
  { label: "Command Center", icon: Compass, href: "/command-center" },
  { label: "NL Analytics", icon: MessageSquareText, href: "/nl-analytics" },
  { label: "Model Governance", icon: GitBranch, href: "/model-governance" },
];

// Phase 10 — Enterprise Banking Operating System (the AI-native control plane).
const bankingOsNav = [
  { label: "Executive Center", icon: PieChart, href: "/executive-center" },
  { label: "Policy Engine", icon: ShieldQuestion, href: "/policy-engine" },
  { label: "Enterprise Search", icon: Layers, href: "/enterprise-search" },
  { label: "Committee Workspace", icon: Users, href: "/committee-workspace" },
  { label: "Scenario Planning", icon: SlidersHorizontal, href: "/scenario-planning" },
  { label: "Workflow Studio", icon: GitBranch, href: "/workflow-studio" },
  { label: "Recommendation Marketplace", icon: Plug, href: "/recommendation-marketplace" },
  { label: "Data Fabric", icon: Boxes, href: "/data-fabric" },
  { label: "Graph Analytics", icon: Network, href: "/graph-analytics" },
  { label: "Prompt Studio", icon: MessageSquareText, href: "/prompt-studio" },
  { label: "Multi-LLM Console", icon: Cpu, href: "/llm-console" },
  { label: "Fairness & Drift", icon: Waves, href: "/fairness-governance" },
];

// Track 2 — Enterprise AI Intelligence Platform (RAG, agents, memory, prompts,
// eval, investigation, reports, workflows, chat, research, learning, governance,
// explainability, monitoring). Additive AI layer over every prior phase.
const aiPlatformNav = [
  { label: "RAG Platform", icon: Layers, href: "/aip-rag" },
  { label: "Multi-Agent System", icon: Bot, href: "/aip-agents" },
  { label: "Long-Term Memory", icon: Brain, href: "/aip-memory" },
  { label: "Prompt Engineering", icon: MessageSquareText, href: "/aip-prompts" },
  { label: "AI Evaluation", icon: Gauge, href: "/aip-evaluation" },
  { label: "Investigation", icon: Microscope, href: "/aip-investigation" },
  { label: "Report Generation", icon: FileText, href: "/aip-reports" },
  { label: "Workflow Builder", icon: GitBranch, href: "/aip-workflows" },
  { label: "AI Assistant", icon: Sparkles, href: "/aip-assistant" },
  { label: "Research Assistant", icon: FlaskConical, href: "/aip-research" },
  { label: "Continuous Learning", icon: RefreshCw, href: "/aip-learning" },
  { label: "AI Governance", icon: ShieldQuestion, href: "/aip-governance" },
  { label: "Explainable AI", icon: Compass, href: "/aip-explainability" },
  { label: "AI Monitoring", icon: HeartPulse, href: "/aip-monitoring" },
];

// Track 3 — Advanced Financial Intelligence Platform (treasury, portfolio,
// regulatory, economic, ESG, market, alt-data, forecasting, quant, benchmarking,
// executive, optimization, digital twin, strategic). Additive quantitative layer.
const financialIntelligenceNav = [
  { label: "Treasury Intelligence", icon: Wallet, href: "/fin-treasury" },
  { label: "Portfolio Intelligence", icon: PieChart, href: "/fin-portfolio" },
  { label: "Basel III / IFRS 9", icon: Landmark, href: "/fin-regulatory" },
  { label: "Economic Scenarios", icon: LineChart, href: "/fin-economic" },
  { label: "Climate & ESG", icon: Activity, href: "/fin-esg" },
  { label: "Market Intelligence", icon: Radar, href: "/fin-market" },
  { label: "Alternative Data", icon: Network, href: "/fin-altdata" },
  { label: "Forecasting", icon: Gauge, href: "/fin-forecast" },
  { label: "Quantitative Risk", icon: SlidersHorizontal, href: "/fin-quant" },
  { label: "Benchmarking", icon: Boxes, href: "/fin-benchmark" },
  { label: "Executive Center", icon: Briefcase, href: "/fin-executive" },
  { label: "Decision Optimization", icon: Sparkles, href: "/fin-optimize" },
  { label: "Financial Digital Twin", icon: Cpu, href: "/fin-twin" },
  { label: "Strategic Intelligence", icon: FileStack, href: "/fin-strategic" },
];

// Track 4 — Enterprise Productization & Commercial Readiness. The productization
// surfaces that make the platform look, behave and scale like a commercial product.
const enterprisePlatformNav = [
  { label: "Enterprise UX", icon: Sparkles, href: "/ent-ux" },
  { label: "Workspaces", icon: Layers, href: "/ent-workspaces" },
  { label: "Developer Platform", icon: Cpu, href: "/ent-developer" },
  { label: "Plugin Marketplace", icon: Plug, href: "/ent-marketplace" },
  { label: "Integration Studio", icon: Webhook, href: "/ent-integration" },
  { label: "Data Management", icon: FileStack, href: "/ent-data" },
  { label: "Operations Center", icon: Activity, href: "/ent-operations" },
  { label: "Security Center", icon: ShieldCheck, href: "/ent-security" },
  { label: "Customer Success", icon: Users, href: "/ent-success" },
  { label: "Deployment", icon: RefreshCw, href: "/ent-deployment" },
  { label: "Monitoring", icon: Radar, href: "/ent-monitoring" },
  { label: "Business Intelligence", icon: PieChart, href: "/ent-bi" },
  { label: "Launch Readiness", icon: ClipboardList, href: "/ent-launch" },
];

// Stage 4 — Enterprise Security & Compliance Platform. The security control
// plane: posture, threat model, OWASP, compliance, findings and risk register.
const securityNav = [
  { label: "Security Center", icon: ShieldCheck, href: "/security-dashboard" },
];

// Consumer-credit scoring predates the enterprise pivot. Retained as a legacy
// tool but demoted from the primary workflow.
const legacyNav = [{ label: "Credit Prediction", icon: Brain, href: "/predict" }];

interface NavItem {
  label: string;
  icon: typeof LayoutDashboard;
  href: string;
}

function NavLink({ label, icon: Icon, href, pathname }: NavItem & { pathname: string }) {
  const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <Link
      to={href}
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
        isActive
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
      )}
    >
      {isActive && (
        <motion.span
          layoutId="sidebar-active"
          className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r-full bg-gradient-primary"
        />
      )}
      <Icon className="h-4 w-4 opacity-90" />
      <span>{label}</span>
    </Link>
  );
}

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-background/70 backdrop-blur-sm lg:hidden"
          aria-hidden
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 transform border-r border-sidebar-border bg-sidebar transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between px-5 py-5">
            <a href="#" className="flex items-center gap-2.5">
              <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-primary shadow-glow">
                <Sparkles className="h-4.5 w-4.5 text-primary-foreground" strokeWidth={2.5} />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold tracking-tight text-sidebar-foreground">
                  AI Credit
                </div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                  Intelligence
                </div>
              </div>
            </a>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground lg:hidden"
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <nav aria-label="Primary" className="hide-scrollbar flex-1 space-y-1 overflow-y-auto px-3 pb-2">
            <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Workspace
            </div>
            {primaryNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              AI Risk Intelligence
            </div>
            {riskNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Credit Operations
            </div>
            {operationsNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              ML Platform
            </div>
            {mlPlatformNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Banking Ecosystem
            </div>
            {integrationsNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Autonomous Intelligence
            </div>
            {autonomousNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Banking OS
            </div>
            {bankingOsNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              AI Intelligence Platform
            </div>
            {aiPlatformNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Financial Intelligence Platform
            </div>
            {financialIntelligenceNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Enterprise Platform
            </div>
            {enterprisePlatformNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Security & Compliance
            </div>
            {securityNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}

            <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Legacy
            </div>
            {legacyNav.map((item) => (
              <NavLink key={item.label} {...item} pathname={pathname} />
            ))}
          </nav>

          <div className="m-3 rounded-xl border border-sidebar-border bg-sidebar-accent/40 p-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-accent text-sm font-semibold text-accent-foreground">
                SD
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-sidebar-foreground">
                  Shriyansh Dev
                </div>
                <div className="truncate text-xs text-muted-foreground">Head of Risk</div>
              </div>
              <button
                className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
                aria-label="Log out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
