/**
 * Demo Mode sample datasets. A representative slice of an enterprise lending
 * book — ten named corporate borrowers across industries, a mix of healthy and
 * distressed credits, and live fraud cases — used to populate dashboards when
 * Demo Mode is on.
 *
 * The registry is keyed by request-path suffix. Add entries here to extend
 * demo coverage to more endpoints; unregistered paths pass through untouched
 * (and render their polished empty states).
 *
 * All monetary values are Indian Rupees (₹). Amounts are absolute rupees, so a
 * value of 185_000_000 renders as ₹18.5 Cr.
 */

import type {
  AdminDashboard,
  AnalystDashboard,
  ComplianceDashboard,
  ManagerDashboard,
  MonitoringDashboard,
  OperationsDashboard,
  PortfolioDashboard,
} from "@/features/operations";

const DAY = 86_400_000;
// Deterministic base time so demo data is stable across renders/SSR.
const BASE = Date.UTC(2026, 6, 28, 9, 30);
const daysAgo = (n: number) => new Date(BASE - n * DAY).toISOString();

/**
 * The demo lending book. A single roster of named borrowers drives every
 * dashboard so the same companies appear consistently across Operations,
 * Portfolio, Manager, Analyst and Monitoring views — the way a real book would.
 */
interface Borrower {
  id: number;
  reference: string;
  name: string;
  industry: string;
  /** Sanctioned / requested exposure in absolute rupees. */
  exposure: number;
  /** Internal risk rating (S&P-style scale). */
  rating: string;
  /** Asset classification per RBI IRAC norms. */
  grade: "Standard" | "Watch" | "Substandard";
  status:
    | "approved"
    | "under_review"
    | "pending_approval"
    | "committee_review"
    | "disbursed"
    | "rejected";
  risk: "Low" | "Medium" | "High" | "Critical";
  /** Blended credit score (300–850). */
  score: number;
  updatedDaysAgo: number;
}

const STATUS_LABEL: Record<Borrower["status"], string> = {
  approved: "Approved",
  under_review: "Under Review",
  pending_approval: "Pending Approval",
  committee_review: "Committee Review",
  disbursed: "Disbursed",
  rejected: "Rejected",
};

const BORROWERS: Borrower[] = [
  { id: 4201, reference: "APP-2026-4201", name: "BlueWave Infrastructure Ltd", industry: "Infrastructure", exposure: 880_000_000, rating: "BBB+", grade: "Standard", status: "committee_review", risk: "Medium", score: 702, updatedDaysAgo: 0 },
  { id: 4202, reference: "APP-2026-4202", name: "Green Energy Solutions Pvt Ltd", industry: "Renewable Energy", exposure: 630_000_000, rating: "A", grade: "Standard", status: "disbursed", risk: "Low", score: 781, updatedDaysAgo: 1 },
  { id: 4203, reference: "APP-2026-4203", name: "Nova Steel Industries Ltd", industry: "Manufacturing", exposure: 420_000_000, rating: "BBB", grade: "Standard", status: "under_review", risk: "Medium", score: 688, updatedDaysAgo: 1 },
  { id: 4204, reference: "APP-2026-4204", name: "Vertex Chemicals Pvt Ltd", industry: "Chemicals", exposure: 312_000_000, rating: "BBB-", grade: "Watch", status: "under_review", risk: "Medium", score: 671, updatedDaysAgo: 2 },
  { id: 4205, reference: "APP-2026-4205", name: "Zenith Pharmaceuticals Ltd", industry: "Pharmaceuticals", exposure: 273_000_000, rating: "A-", grade: "Standard", status: "approved", risk: "Low", score: 754, updatedDaysAgo: 2 },
  { id: 4206, reference: "APP-2026-4206", name: "Global Auto Components Pvt Ltd", industry: "Auto Components", exposure: 229_000_000, rating: "BB+", grade: "Standard", status: "pending_approval", risk: "Medium", score: 655, updatedDaysAgo: 3 },
  { id: 4207, reference: "APP-2026-4207", name: "ABC Manufacturing Pvt Ltd", industry: "Manufacturing", exposure: 185_000_000, rating: "BBB+", grade: "Standard", status: "approved", risk: "Low", score: 733, updatedDaysAgo: 4 },
  { id: 4208, reference: "APP-2026-4208", name: "Apex Electronics Ltd", industry: "Electronics", exposure: 158_000_000, rating: "BB+", grade: "Watch", status: "pending_approval", risk: "Medium", score: 634, updatedDaysAgo: 5 },
  { id: 4209, reference: "APP-2026-4209", name: "Orion Textiles Pvt Ltd", industry: "Textiles", exposure: 126_000_000, rating: "B+", grade: "Substandard", status: "committee_review", risk: "High", score: 571, updatedDaysAgo: 6 },
  { id: 4210, reference: "APP-2026-4210", name: "Prime Logistics Ltd", industry: "Logistics", exposure: 94_000_000, rating: "BB", grade: "Watch", status: "rejected", risk: "High", score: 544, updatedDaysAgo: 8 },
];

const toApplicationRow = (b: Borrower) => ({
  id: b.id,
  reference: b.reference,
  company_name: b.name,
  industry: b.industry,
  requested_amount: b.exposure,
  status: b.status,
  status_label: STATUS_LABEL[b.status],
  risk_rating: b.rating,
  updated_at: daysAgo(b.updatedDaysAgo),
});

// ---------------------------------------------------------------------------
// Home dashboard (legacy /dashboard/overview shape)
// ---------------------------------------------------------------------------

const recentPredictions = BORROWERS.map((b) => ({
  id: b.reference,
  applicant: b.name,
  credit_score: b.score,
  risk_level: b.risk,
  approval: b.status !== "rejected",
  probability: Math.min(0.99, Math.max(0.28, b.score / 850)),
  created_at: daysAgo(b.updatedDaysAgo),
}));

const recentFraudChecks = [
  { id: "FR-9012", entity: "Prime Logistics Ltd", fraud_detected: true, fraud_score: 88, anomaly_score: 91, created_at: daysAgo(0) },
  { id: "FR-9011", entity: "Orion Textiles Pvt Ltd", fraud_detected: true, fraud_score: 76, anomaly_score: 72, created_at: daysAgo(1) },
  { id: "FR-9010", entity: "Apex Electronics Ltd", fraud_detected: false, fraud_score: 34, anomaly_score: 29, created_at: daysAgo(2) },
  { id: "FR-9009", entity: "ABC Manufacturing Pvt Ltd", fraud_detected: false, fraud_score: 18, anomaly_score: 22, created_at: daysAgo(3) },
  { id: "FR-9008", entity: "Vertex Chemicals Pvt Ltd", fraud_detected: true, fraud_score: 81, anomaly_score: 84, created_at: daysAgo(4) },
  { id: "FR-9007", entity: "Zenith Pharmaceuticals Ltd", fraud_detected: false, fraud_score: 12, anomaly_score: 15, created_at: daysAgo(6) },
];

const dashboardOverview = {
  success: true,
  user: "Demo Analyst",
  portfolio_summary: {
    total_predictions: 1284,
    approved: 967,
    approval_rate: 0.753,
    average_credit_score: 712,
  },
  fraud_summary: { total_checks: 842, fraud_detected: 37, fraud_rate: 4.4 },
  enterprise_summary: {
    total_enterprise_assessments: 156,
    average_enterprise_score: 684,
    high_risk_accounts: 23,
  },
  recent_predictions: recentPredictions,
  recent_fraud_checks: recentFraudChecks,
};

const riskHistory = {
  success: true,
  data: recentPredictions.map((p, i) => ({
    id: i + 1,
    credit_score: p.credit_score,
    risk_level: p.risk_level,
    approval: p.approval,
    probability: p.probability,
    ai_analysis: `${p.applicant} shows ${p.risk_level.toLowerCase()} credit risk driven by leverage, debt-service coverage and sector outlook.`,
    created_at: p.created_at,
  })),
};

const fraudHistory = {
  success: true,
  data: recentFraudChecks.map((f, i) => ({
    id: i + 1,
    entity: f.entity,
    amount: 4_500_000 + i * 1_250_000,
    frequency: 3 + i,
    account_age: 8 + i * 4,
    fraud_detected: f.fraud_detected,
    fraud_score: f.fraud_score,
    anomaly_score: f.anomaly_score,
    ai_analysis: f.fraud_detected
      ? "Unusual transaction velocity and round-tripping relative to declared turnover."
      : "Transaction pattern consistent with historical banking behaviour.",
    created_at: f.created_at,
  })),
};

const fraudSummary = {
  success: true,
  total_checks: 842,
  fraud_detected: 37,
  fraud_rate: 4.4,
  high_risk: 23,
};

const portfolioSummary = {
  success: true,
  total_predictions: 1284,
  approved: 967,
  approval_rate: 0.753,
  average_credit_score: 712,
  risk_distribution: { Low: 612, Medium: 448, High: 164, Critical: 60 },
};

// ---------------------------------------------------------------------------
// Phase 5 enterprise dashboards (/api/dashboards/*)
// ---------------------------------------------------------------------------

const BOOK_APPLICATIONS = 1284;
const BOOK_EXPOSURE = 8_640_000_000; // ₹864 Cr

const recentApplications = BORROWERS.map(toApplicationRow);

const operationsDashboard: OperationsDashboard = {
  totals: {
    applications: BOOK_APPLICATIONS,
    pending_approvals: 47,
    open_tasks: 63,
    open_alerts: 19,
    total_exposure: BOOK_EXPOSURE,
  },
  status_breakdown: [
    { status: "approved", count: 612 },
    { status: "disbursed", count: 208 },
    { status: "under_review", count: 214 },
    { status: "pending_approval", count: 118 },
    { status: "committee_review", count: 74 },
    { status: "rejected", count: 58 },
  ],
  recent_applications: recentApplications,
};

const adminDashboard: AdminDashboard = {
  totals: { users: 84, roles: 12, config_keys: 156, applications: BOOK_APPLICATIONS },
  audit: {
    total: 24_918,
    by_action: [
      { action: "application.view", count: 9432 },
      { action: "decision.approve", count: 3187 },
      { action: "document.upload", count: 2761 },
      { action: "login.success", count: 4820 },
      { action: "config.update", count: 412 },
      { action: "decision.reject", count: 786 },
    ],
    by_status: [
      { status: "success", count: 24_106 },
      { status: "denied", count: 612 },
      { status: "error", count: 200 },
    ],
  },
  status_breakdown: operationsDashboard.status_breakdown,
};

const analystDashboard: AnalystDashboard = {
  totals: { my_open_tasks: 11, my_applications: 6, unread_notifications: 4 },
  my_tasks_by_status: [
    { status: "open", count: 7 },
    { status: "in_progress", count: 3 },
    { status: "blocked", count: 1 },
  ],
  my_applications: [
    BORROWERS[2],
    BORROWERS[3],
    BORROWERS[7],
    BORROWERS[8],
  ].map(toApplicationRow),
};

const managerDashboard: ManagerDashboard = {
  totals: { pending_approvals: 47, total_exposure: 3_920_000_000 },
  pending_by_stage: [
    { stage: "Credit Review", count: 21 },
    { stage: "Risk Sign-off", count: 14 },
    { stage: "Credit Committee", count: 8 },
    { stage: "Board Approval", count: 4 },
  ],
  approval_actions: [
    { action: "approved", count: 3187 },
    { action: "rejected", count: 786 },
    { action: "returned", count: 342 },
    { action: "escalated", count: 198 },
  ],
  exposure_by_rating: [
    { rating: "AAA", exposure: 620_000_000 },
    { rating: "AA", exposure: 1_480_000_000 },
    { rating: "A", exposure: 2_360_000_000 },
    { rating: "BBB", exposure: 2_540_000_000 },
    { rating: "BB", exposure: 1_120_000_000 },
    { rating: "B", exposure: 520_000_000 },
  ],
  pending_applications: [
    BORROWERS[0],
    BORROWERS[5],
    BORROWERS[7],
    BORROWERS[8],
  ].map(toApplicationRow),
};

const portfolioDashboard: PortfolioDashboard = {
  totals: { applications: BOOK_APPLICATIONS, total_exposure: BOOK_EXPOSURE },
  by_status: [
    { value: "approved", count: 612, exposure: 3_980_000_000 },
    { value: "disbursed", count: 208, exposure: 2_120_000_000 },
    { value: "under_review", count: 214, exposure: 1_260_000_000 },
    { value: "pending_approval", count: 118, exposure: 740_000_000 },
    { value: "committee_review", count: 74, exposure: 540_000_000 },
    { value: "rejected", count: 58, exposure: 0 },
  ],
  by_industry: [
    { value: "manufacturing", count: 268, exposure: 1_940_000_000 },
    { value: "information_technology", count: 156, exposure: 1_180_000_000 },
    { value: "infrastructure", count: 96, exposure: 1_320_000_000 },
    { value: "pharmaceuticals", count: 142, exposure: 860_000_000 },
    { value: "textiles", count: 118, exposure: 520_000_000 },
    { value: "chemicals", count: 88, exposure: 640_000_000 },
    { value: "renewable_energy", count: 74, exposure: 780_000_000 },
    { value: "logistics", count: 132, exposure: 480_000_000 },
    { value: "retail", count: 110, exposure: 410_000_000 },
    { value: "auto_components", count: 100, exposure: 610_000_000 },
  ],
  by_rating: [
    { value: "AAA", count: 42, exposure: 620_000_000 },
    { value: "AA", count: 168, exposure: 1_480_000_000 },
    { value: "A", count: 361, exposure: 2_360_000_000 },
    { value: "BBB", count: 402, exposure: 2_540_000_000 },
    { value: "BB", count: 214, exposure: 1_120_000_000 },
    { value: "B", count: 74, exposure: 520_000_000 },
    { value: "CCC", count: 23, exposure: 0 },
  ],
  by_grade: [
    { value: "standard", count: 1156, exposure: 7_940_000_000 },
    { value: "watch", count: 82, exposure: 480_000_000 },
    { value: "substandard", count: 34, exposure: 180_000_000 },
    { value: "doubtful", count: 12, exposure: 40_000_000 },
  ],
};

const complianceDashboard: ComplianceDashboard = {
  totals: { open_covenant_alerts: 14, open_monitoring_alerts: 19, audit_events: 24_918 },
  audit: adminDashboard.audit,
  recent_audit: [
    { timestamp: daysAgo(0), user: "priya.menon@bank.com", action: "decision.approve", status: "success" },
    { timestamp: daysAgo(0), user: "arjun.rao@bank.com", action: "covenant.breach.ack", status: "success" },
    { timestamp: daysAgo(1), user: "system", action: "monitoring.alert.raise", status: "success" },
    { timestamp: daysAgo(1), user: "neha.gupta@bank.com", action: "document.upload", status: "success" },
    { timestamp: daysAgo(2), user: "vikram.singh@bank.com", action: "decision.reject", status: "success" },
    { timestamp: daysAgo(2), user: "external.api", action: "bureau.pull", status: "denied" },
  ],
};

const monitoringDashboard: MonitoringDashboard = {
  totals: { open_alerts: 19 },
  by_category: [
    { category: "Covenant Breach", count: 6 },
    { category: "Financial Deterioration", count: 5 },
    { category: "Payment Delay", count: 4 },
    { category: "External Rating Action", count: 2 },
    { category: "News / Adverse Media", count: 2 },
  ],
  by_severity: [
    { severity: "critical", count: 3 },
    { severity: "high", count: 7 },
    { severity: "medium", count: 6 },
    { severity: "low", count: 3 },
  ],
  recent_alerts: [
    { application_id: 4210, category: "Payment Delay", severity: "high", status: "open", message: "Prime Logistics Ltd — EMI overdue 31 days; DSCR fell below 1.0x covenant floor.", created_at: daysAgo(0) },
    { application_id: 4209, category: "Financial Deterioration", severity: "critical", status: "open", message: "Orion Textiles Pvt Ltd — Q3 EBITDA margin contracted 340 bps YoY; working-capital cycle stretched to 128 days.", created_at: daysAgo(0) },
    { application_id: 4204, category: "Covenant Breach", severity: "high", status: "open", message: "Vertex Chemicals Pvt Ltd — Net debt / EBITDA breached 3.5x maximum-leverage covenant.", created_at: daysAgo(1) },
    { application_id: 4208, category: "External Rating Action", severity: "medium", status: "open", message: "Apex Electronics Ltd — external agency revised outlook to Negative.", created_at: daysAgo(2) },
    { application_id: 4203, category: "News / Adverse Media", severity: "medium", status: "acknowledged", message: "Nova Steel Industries Ltd — adverse media on an environmental compliance notice.", created_at: daysAgo(3) },
  ],
};

/** path-suffix → sample response factory (fresh object each call). */
export const DEMO_FIXTURES: Record<string, () => unknown> = {
  "/dashboard/overview": () => structuredClone(dashboardOverview),
  "/risk-history": () => structuredClone(riskHistory),
  "/fraud-history": () => structuredClone(fraudHistory),
  "/fraud-summary": () => structuredClone(fraudSummary),
  "/portfolio-summary": () => structuredClone(portfolioSummary),
  "/api/dashboards/operations": () => structuredClone(operationsDashboard),
  "/api/dashboards/admin": () => structuredClone(adminDashboard),
  "/api/dashboards/analyst": () => structuredClone(analystDashboard),
  "/api/dashboards/manager": () => structuredClone(managerDashboard),
  "/api/dashboards/portfolio": () => structuredClone(portfolioDashboard),
  "/api/dashboards/compliance": () => structuredClone(complianceDashboard),
  "/api/dashboards/monitoring": () => structuredClone(monitoringDashboard),
};
