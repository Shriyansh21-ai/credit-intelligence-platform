/**
 * Demo Mode fixtures for the AI Intelligence Platform (Track 2, `/api/aip/*`).
 *
 * Populates every AIP page's on-load lists, summaries, rosters, catalogs and
 * dashboards with professional banking-domain sample data so nothing renders an
 * empty state during a product demo. All content references the SAME real
 * companies and bankers as the canonical dataset (`enterprise-data.ts`) so the
 * AI views stay coherent with Portfolio, Risk, Monitoring and Customer 360.
 *
 * Each entry is a factory returning a FRESH object literal (no shared mutable
 * state). Register by request-path suffix — matching is `clean === key ||
 * clean.endsWith(key)`.
 */

import {
  COMPANIES,
  MONTHS_12,
  USERS,
  companyByRef,
  cr,
  daysAgo,
  ebitdaOf,
  eclOf,
  pdOf,
  userById,
} from "./enterprise-data";

const byRef = (ref: string) => companyByRef(ref) ?? COMPANIES[0];
const pct = (n: number) => Math.round(n * 1000) / 1000;

// --- M1 RAG ----------------------------------------------------------------

const ragStats = () => ({
  sources: 16,
  documents: 486,
  chunks: 12_840,
  vectors: 12_840,
});

const ragSources = () => [
  { id: 1, key: "credit-policies", name: "Corporate Credit Policy Manual", source_type: "credit_policy", document_count: 38 },
  { id: 2, key: "rbi-circulars", name: "RBI Master Circulars & Directions", source_type: "rbi_circular", document_count: 74 },
  { id: 3, key: "basel-guidelines", name: "Basel III / IFRS 9 Guidance", source_type: "basel_guideline", document_count: 21 },
  { id: 4, key: "annual-reports", name: "Borrower Annual Reports (FY25)", source_type: "annual_report", document_count: 96 },
  { id: 5, key: "financial-statements", name: "Audited Financial Statements", source_type: "financial_statement", document_count: 132 },
  { id: 6, key: "loan-agreements", name: "Sanctioned Facility Agreements", source_type: "loan_agreement", document_count: 68 },
  { id: 7, key: "committee-notes", name: "Credit Committee Minutes", source_type: "committee_note", document_count: 41 },
  { id: 8, key: "audit-reports", name: "Statutory & Internal Audit Reports", source_type: "audit_report", document_count: 16 },
];

const ragDocuments = () => [
  { id: 101, title: "Corporate Credit Policy — Large Exposure Framework v4.2", doc_type: "credit_policy", version: 4, chunk_count: 62 },
  { id: 102, title: "RBI Master Direction — Prudential Norms on Income Recognition, Asset Classification (IRAC)", doc_type: "rbi_circular", version: 3, chunk_count: 88 },
  { id: 103, title: "Reliance Industries Ltd — Annual Report FY2025", doc_type: "annual_report", version: 1, chunk_count: 214 },
  { id: 104, title: "Tata Steel Ltd — Audited Consolidated Financials FY2025", doc_type: "financial_statement", version: 1, chunk_count: 96 },
  { id: 105, title: "Infosys Ltd — Annual Report & MD&A FY2025", doc_type: "annual_report", version: 1, chunk_count: 178 },
  { id: 106, title: "Basel III — Expected Credit Loss (ECL) Staging Guidance", doc_type: "basel_guideline", version: 2, chunk_count: 44 },
  { id: 107, title: "JSW Steel Ltd — Term Loan Facility Agreement (₹680 Cr)", doc_type: "loan_agreement", version: 2, chunk_count: 51 },
  { id: 108, title: "Adani Ports & SEZ Ltd — Credit Committee Note (Watchlist Review)", doc_type: "committee_note", version: 1, chunk_count: 33 },
  { id: 109, title: "ITC Ltd — Statutory Audit Report FY2025", doc_type: "audit_report", version: 1, chunk_count: 40 },
  { id: 110, title: "RBI Circular — Guidelines on Large Exposures Framework", doc_type: "rbi_circular", version: 1, chunk_count: 29 },
];

// --- M2 Agents -------------------------------------------------------------

const agentRoster = () => ({
  roles: [
    { role: "planner", title: "Planning & Orchestration Agent" },
    { role: "financial_analyst", title: "Financial Statement Analysis Agent" },
    { role: "credit_memo", title: "Credit Memo Drafting Agent" },
    { role: "covenant_monitor", title: "Covenant Monitoring Agent" },
    { role: "fraud_screen", title: "Fraud & AML Screening Agent" },
    { role: "compliance", title: "Regulatory Compliance Agent" },
    { role: "esg", title: "ESG Assessment Agent" },
    { role: "industry_benchmark", title: "Industry Benchmarking Agent" },
    { role: "risk_scoring", title: "Risk Scoring & PD/LGD Agent" },
    { role: "collateral", title: "Collateral Valuation Agent" },
    { role: "market_intel", title: "Market & News Intelligence Agent" },
    { role: "synthesis", title: "Executive Synthesis Agent" },
  ],
});

const DECISIONS = ["Approve", "Approve with conditions", "Refer to committee", "Decline", "Approve with conditions"];
const agentRuns = () => ({
  runs: COMPANIES.slice(0, 8).map((c, i) => ({
    run_id: `AGT-${2600 + i}`,
    goal: `Assess creditworthiness for a term loan — ${c.name}`,
    company_ref: c.ref,
    decision: c.status === "rejected" ? "Decline" : c.grade === "Watch" ? "Refer to committee" : DECISIONS[i % DECISIONS.length],
    confidence: pct(0.72 + (c.score - 566) / 900),
    agents: 12,
    created_at: daysAgo(i),
  })),
});

// --- M3 Memory -------------------------------------------------------------

const memoryStats = () => ({
  total: 8642,
  active: 7918,
  summaries: 412,
  by_type: {
    semantic: 2140,
    episodic: 1876,
    procedural: 984,
    org: 612,
    tenant: 344,
    user: 902,
    conversation: 1088,
    case: 421,
    committee: 168,
    customer: 107,
  },
});

// --- M4 Prompts ------------------------------------------------------------

const prompts = () => [
  { id: 1, key: "credit_memo_draft", name: "Credit Memo Draft", task: "credit_memo", current_version: 7, deployed_version: 6 },
  { id: 2, key: "financial_spreading", name: "Financial Spreading & Ratios", task: "financial_analysis", current_version: 5, deployed_version: 5 },
  { id: 3, key: "covenant_check", name: "Covenant Compliance Check", task: "monitoring", current_version: 4, deployed_version: 4 },
  { id: 4, key: "fraud_narrative", name: "Fraud/AML Alert Narrative", task: "fraud", current_version: 3, deployed_version: 2 },
  { id: 5, key: "esg_assessment", name: "ESG Risk Assessment", task: "esg", current_version: 6, deployed_version: 6 },
  { id: 6, key: "committee_brief", name: "Credit Committee Brief", task: "report", current_version: 8, deployed_version: 7 },
  { id: 7, key: "regulatory_qa", name: "Regulatory Q&A (RBI/Basel)", task: "compliance", current_version: 4, deployed_version: 4 },
  { id: 8, key: "sector_outlook", name: "Sector Outlook Summary", task: "research", current_version: 3, deployed_version: 3 },
];

// --- M5 Eval ---------------------------------------------------------------

const evalSummary = () => ({
  count: 342,
  mean_overall: 0.871,
  pass_rate: 0.914,
});

const GRADES = ["A", "A", "B", "A", "C", "B", "A"];
const evalList = () => ({
  evaluations: COMPANIES.slice(0, 7).map((c, i) => ({
    id: 900 + i,
    target_type: i % 2 === 0 ? "credit_memo" : "rag_answer",
    target_ref: c.ref,
    grade: c.grade === "Substandard" ? "C" : GRADES[i % GRADES.length],
    overall_score: pct(0.78 + (c.score - 566) / 1200),
    created_at: daysAgo(i * 2),
  })),
});

// --- M6 Investigation ------------------------------------------------------

const INVESTIGATIONS: Array<[string, string]> = [
  ["APP-2026-4220", "Decline — going-concern risk; negative EBITDA and DSCR 0.7x."],
  ["APP-2026-4216", "Refer to committee — margin turned negative, working-capital stretch."],
  ["APP-2026-4206", "Enhanced monitoring — leverage covenant breach at Adani Ports."],
  ["APP-2026-4215", "Watchlist — adverse media on platform-fee regulatory review."],
  ["APP-2026-4213", "Enhanced due diligence — outlook revised Negative; thin DSCR."],
  ["APP-2026-4205", "Approve with conditions — pledge top-up on JSW Steel exposure."],
];
const investigateList = () => ({
  investigations: INVESTIGATIONS.map(([ref, rec], i) => ({
    investigation_id: `INV-${1400 + i}`,
    company_ref: ref,
    company_name: byRef(ref).name,
    decision: rec.split(" — ")[0],
    recommendation: rec,
    confidence: pct(0.66 + i * 0.03),
    created_at: daysAgo(i + 1),
  })),
});

// --- M7 Reports ------------------------------------------------------------

const reportTypes = () => ({
  report_types: [
    "credit_memo",
    "investment_memo",
    "risk_assessment",
    "fraud_report",
    "portfolio_review",
    "committee_brief",
    "executive_summary",
    "regulatory_report",
    "due_diligence",
    "financial_analysis",
    "board_deck",
  ],
});

const REPORT_KIND = ["Credit Memo", "Risk Assessment", "Committee Brief", "Due Diligence", "Portfolio Review", "Financial Analysis"];
const reportsList = () => ({
  reports: COMPANIES.slice(0, 8).map((c, i) => ({
    report_id: `RPT-${3300 + i}`,
    title: `${REPORT_KIND[i % REPORT_KIND.length]} — ${c.name}`,
    company_ref: c.ref,
    confidence: pct(0.7 + (c.score - 566) / 1000),
    created_at: daysAgo(i),
  })),
});

// --- M8 Workflows ----------------------------------------------------------

const nodeTypes = () => ({
  node_types: ["start", "agent", "rag", "api", "connector", "approval", "memory", "condition", "report", "end"],
});

const workflows = () => [
  { id: 1, key: "credit-origination-flow", name: "Credit Origination Flow", version: 5, node_count: 9 },
  { id: 2, key: "annual-review-flow", name: "Annual Review Flow", version: 3, node_count: 7 },
  { id: 3, key: "covenant-monitoring-flow", name: "Covenant Monitoring Flow", version: 4, node_count: 6 },
  { id: 4, key: "fraud-escalation-flow", name: "Fraud Escalation Flow", version: 2, node_count: 8 },
  { id: 5, key: "esg-screening-flow", name: "ESG Screening Flow", version: 2, node_count: 5 },
  { id: 6, key: "committee-packet-flow", name: "Committee Packet Assembly", version: 6, node_count: 10 },
];

// --- M9 Chat ---------------------------------------------------------------

const conversations = () => [
  { conversation_id: 5101, title: "Reliance Industries — refinancing appetite", company_ref: "APP-2026-4201", turns: 6, updated_at: daysAgo(0) },
  { conversation_id: 5102, title: "Why is Swiggy on the watchlist?", company_ref: "APP-2026-4216", turns: 4, updated_at: daysAgo(1) },
  { conversation_id: 5103, title: "Adani Ports covenant headroom", company_ref: "APP-2026-4206", turns: 8, updated_at: daysAgo(2) },
  { conversation_id: 5104, title: "Compare Tata Steel vs JSW Steel leverage", company_ref: "APP-2026-4202", turns: 5, updated_at: daysAgo(3) },
  { conversation_id: 5105, title: "Infosys — IT sector exposure concentration", company_ref: "APP-2026-4203", turns: 3, updated_at: daysAgo(5) },
];

// --- M10 Research ----------------------------------------------------------

const researchTypes = () => ({
  research_types: [
    "sector_analysis",
    "peer_comparison",
    "industry_benchmarking",
    "economic_indicators",
    "regulatory_updates",
    "macro_outlook",
    "supply_chain",
    "geopolitical",
    "esg_analysis",
  ],
});

const RESEARCH: Array<[string, string]> = [
  ["Indian steel sector outlook — margin pressure from imports", "sector_analysis"],
  ["FMCG peer comparison: HUL, ITC, Britannia, Asian Paints", "peer_comparison"],
  ["Logistics & warehousing benchmarking — Delhivery vs Mahindra Logistics", "industry_benchmarking"],
  ["RBI monetary policy & repo-rate impact on corporate borrowing costs", "economic_indicators"],
  ["New-age tech lending: Zomato, Swiggy, Nykaa unit economics", "sector_analysis"],
  ["EV two-wheeler supply-chain risk — Ather Energy battery sourcing", "supply_chain"],
];
const researchList = () => ({
  research: RESEARCH.map(([topic, rt], i) => ({
    research_id: `RES-${2200 + i}`,
    topic,
    research_type: rt,
    confidence: pct(0.68 + i * 0.02),
    created_at: daysAgo(i * 2 + 1),
  })),
});

// --- M11 Learning ----------------------------------------------------------

const learningStats = () => ({
  feedback: 1284,
  mean_rating: 0.842,
  signals: 3960,
  training_events: 18,
});

const TRAIN_STATUS = ["completed", "completed", "running", "completed", "queued", "completed"];
const TRAIN_TRIGGER = [
  "feedback_threshold",
  "data_drift",
  "default_signal",
  "accuracy_drop",
  "scheduled_retrain",
  "concept_drift",
];
const trainingEvents = () => ({
  training_events: TRAIN_TRIGGER.map((t, i) => ({
    id: 700 + i,
    trigger: t,
    version: `v2.${8 - i}.0`,
    status: TRAIN_STATUS[i % TRAIN_STATUS.length],
    samples: 4200 + i * 380,
    created_at: daysAgo(i * 3 + 1),
  })),
});

// --- M12 Governance --------------------------------------------------------

const assetTypes = () => ({
  asset_types: ["prompt", "model", "dataset", "agent", "workflow", "rag_index", "report"],
});

const GOV_STATES = ["deployed", "approved", "validated", "deployed", "registered", "retired", "deployed", "approved"];
const GOV_ASSETS: Array<[string, string]> = [
  ["prompt", "credit_memo_draft"],
  ["model", "pd_lgd_scorecard"],
  ["dataset", "corporate_book_fy25"],
  ["agent", "covenant_monitor"],
  ["workflow", "credit-origination-flow"],
  ["rag_index", "annual-reports"],
  ["report", "committee_brief"],
  ["model", "fraud_anomaly_detector"],
];
const governanceAssets = () => ({
  assets: GOV_ASSETS.map(([type, ref], i) => ({
    id: 400 + i,
    asset_type: type,
    asset_ref: ref,
    name: ref,
    version: `1.${(i % 5) + 1}`,
    state: GOV_STATES[i % GOV_STATES.length],
    checksum: `sha256:${(0xa1f2c3 + i * 7919).toString(16)}`,
    updated_at: daysAgo(i * 2),
  })),
});

const governanceSummary = () => ({
  total: 128,
  reproducible: 124,
  by_type: {
    prompt: 34,
    model: 12,
    dataset: 21,
    agent: 12,
    workflow: 9,
    rag_index: 16,
    report: 24,
  },
});

// --- M13 Explain -----------------------------------------------------------

const explainList = () => ({
  explanations: COMPANIES.slice(0, 6).map((c, i) => ({
    explanation_id: `XAI-${1800 + i}`,
    company_ref: c.ref,
    company_name: c.name,
    decision: c.status === "rejected" ? "Decline" : c.grade === "Watch" ? "Refer" : "Approve",
    p_favorable: pct(0.5 + (c.score - 640) / 500),
    created_at: daysAgo(i + 1),
  })),
});

// --- M14 Monitoring --------------------------------------------------------

const monitoringDashboard = () => ({
  health: "healthy",
  metrics: {
    hallucination: 0.021,
    retrieval_quality: 0.912,
    accuracy: 0.938,
    latency: 742,
    cost: 0.0184,
    feedback_score: 0.842,
    drift: 0.067,
  },
  // 12-month trend so charts render varied, non-flat series.
  trend: MONTHS_12.map((month, i) => ({
    month,
    accuracy: pct(0.9 + Math.sin(i / 2) * 0.03),
    latency: 680 + ((i * 37) % 180),
    drift: pct(0.03 + ((i * 13) % 60) / 1000),
    cost: pct(0.014 + ((i * 5) % 40) / 10000),
  })),
  open_incident_count: 3,
});

const INCIDENTS: Array<[string, string, string, string]> = [
  ["embedding_drift", "Embedding drift on annual-report corpus exceeded 0.05 threshold after FY25 filings ingested.", "medium", "open"],
  ["latency_breach", "P95 RAG answer latency crossed 1200ms during committee-packet batch generation.", "high", "open"],
  ["hallucination", "Grounding check flagged an unsupported figure in a Swiggy credit-memo draft.", "high", "acknowledged"],
  ["retrieval_quality", "Retrieval recall dropped on RBI-circular queries after re-chunking.", "medium", "open"],
  ["feedback_drop", "Analyst feedback score fell below 0.80 on covenant-narrative prompt v4.", "low", "resolved"],
  ["cost_spike", "Token cost per report rose 22% week-over-week on board-deck generation.", "low", "resolved"],
];
const incidentsList = () => ({
  incidents: INCIDENTS.map(([type, description, severity, status], i) => ({
    incident_id: `AIM-${560 + i}`,
    type,
    description,
    severity,
    status,
    created_at: daysAgo(i),
  })),
});

// Reference USERS/pdOf/ebitdaOf/eclOf so cross-view consistency helpers stay
// wired even where the page renders only headline fields.
void [USERS, userById, pdOf, ebitdaOf, eclOf, cr];

export const AIP_FIXTURES: Record<string, () => unknown> = {
  // M1 RAG
  "/api/aip/rag/stats": ragStats,
  "/api/aip/rag/sources": ragSources,
  "/api/aip/rag/documents": ragDocuments,
  // M2 Agents
  "/api/aip/agents/roster": agentRoster,
  "/api/aip/agents/runs": agentRuns,
  // M3 Memory
  "/api/aip/memory/stats": memoryStats,
  // M4 Prompts
  "/api/aip/prompts": prompts,
  // M5 Eval
  "/api/aip/eval/summary": evalSummary,
  "/api/aip/eval/list": evalList,
  // M6 Investigation
  "/api/aip/investigate/list": investigateList,
  // M7 Reports
  "/api/aip/reports/types": reportTypes,
  "/api/aip/reports/list": reportsList,
  // M8 Workflows
  "/api/aip/workflows/node-types": nodeTypes,
  "/api/aip/workflows": workflows,
  // M9 Chat
  "/api/aip/chat/conversations": conversations,
  // M10 Research
  "/api/aip/research/types": researchTypes,
  "/api/aip/research/list": researchList,
  // M11 Learning
  "/api/aip/learning/stats": learningStats,
  "/api/aip/learning/training-events": trainingEvents,
  // M12 Governance
  "/api/aip/governance/asset-types": assetTypes,
  "/api/aip/governance/assets": governanceAssets,
  "/api/aip/governance/summary": governanceSummary,
  // M13 Explain
  "/api/aip/explain/list": explainList,
  // M14 Monitoring
  "/api/aip/monitoring/dashboard": monitoringDashboard,
  "/api/aip/monitoring/incidents": incidentsList,
};
