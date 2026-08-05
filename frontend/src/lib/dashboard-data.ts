export type RiskLevel = "Low" | "Medium" | "High" | "Critical";
export type ApprovalStatus = "Approved" | "Rejected" | "Review";
export type Severity = "Low" | "Medium" | "High" | "Critical";

export interface Assessment {
  id: string;
  customer: string;
  email: string;
  score: number;
  risk: RiskLevel;
  status: ApprovalStatus;
  probability: number;
  date: string;
}

export interface FraudAlert {
  id: string;
  customer: string;
  type: string;
  severity: Severity;
  anomaly: number;
  detectedAt: string;
}

export const kpis = [
  {
    key: "score",
    label: "Average Credit Score",
    value: "742",
    delta: 2.4,
    trend: "up" as const,
    icon: "Gauge",
  },
  {
    key: "approval",
    label: "Approval Rate",
    value: "68.4%",
    delta: 4.1,
    trend: "up" as const,
    icon: "CheckCircle2",
  },
  {
    key: "predictions",
    label: "Total Predictions",
    value: "128,420",
    delta: 12.7,
    trend: "up" as const,
    icon: "Activity",
  },
  {
    key: "fraud",
    label: "Fraud Rate",
    value: "0.42%",
    delta: -0.08,
    trend: "down" as const,
    icon: "ShieldAlert",
  },
  {
    key: "customers",
    label: "Active Customers",
    value: "24,318",
    delta: 6.2,
    trend: "up" as const,
    icon: "Users",
  },
  {
    key: "alerts",
    label: "Risk Alerts",
    value: "37",
    delta: -14.0,
    trend: "down" as const,
    icon: "AlertTriangle",
  },
];

export const riskDistribution = [
  { name: "Low", value: 4820, color: "var(--color-chart-1)" },
  { name: "Medium", value: 2640, color: "var(--color-chart-2)" },
  { name: "High", value: 980, color: "var(--color-chart-4)" },
  { name: "Critical", value: 220, color: "var(--color-chart-5)" },
];

export const volumeTrend = [
  { month: "Jan", predictions: 6200, fraud: 28 },
  { month: "Feb", predictions: 7100, fraud: 31 },
  { month: "Mar", predictions: 8400, fraud: 26 },
  { month: "Apr", predictions: 9100, fraud: 34 },
  { month: "May", predictions: 10240, fraud: 29 },
  { month: "Jun", predictions: 11820, fraud: 22 },
  { month: "Jul", predictions: 12640, fraud: 25 },
  { month: "Aug", predictions: 13880, fraud: 19 },
  { month: "Sep", predictions: 14920, fraud: 17 },
  { month: "Oct", predictions: 16280, fraud: 21 },
  { month: "Nov", predictions: 17240, fraud: 16 },
  { month: "Dec", predictions: 18560, fraud: 14 },
];

export const approvalTrend = [
  { week: "W1", approved: 920, rejected: 380 },
  { week: "W2", approved: 1040, rejected: 410 },
  { week: "W3", approved: 1180, rejected: 360 },
  { week: "W4", approved: 1260, rejected: 420 },
  { week: "W5", approved: 1340, rejected: 380 },
  { week: "W6", approved: 1420, rejected: 340 },
  { week: "W7", approved: 1510, rejected: 320 },
  { week: "W8", approved: 1620, rejected: 290 },
];

export const assessments: Assessment[] = [
  {
    id: "CR-10241",
    customer: "Amelia Hart",
    email: "amelia@northwind.io",
    score: 812,
    risk: "Low",
    status: "Approved",
    probability: 0.94,
    date: "2026-05-30",
  },
  {
    id: "CR-10242",
    customer: "Devon Okafor",
    email: "devon@lumen.co",
    score: 684,
    risk: "Medium",
    status: "Review",
    probability: 0.71,
    date: "2026-05-30",
  },
  {
    id: "CR-10243",
    customer: "Priya Raman",
    email: "priya@orbital.ai",
    score: 758,
    risk: "Low",
    status: "Approved",
    probability: 0.88,
    date: "2026-05-29",
  },
  {
    id: "CR-10244",
    customer: "Marco Bellini",
    email: "marco@vela.co",
    score: 542,
    risk: "High",
    status: "Rejected",
    probability: 0.31,
    date: "2026-05-29",
  },
  {
    id: "CR-10245",
    customer: "Hana Park",
    email: "hana@meridian.io",
    score: 791,
    risk: "Low",
    status: "Approved",
    probability: 0.92,
    date: "2026-05-28",
  },
  {
    id: "CR-10246",
    customer: "Sebastian Cole",
    email: "seb@northgate.fi",
    score: 612,
    risk: "Medium",
    status: "Review",
    probability: 0.64,
    date: "2026-05-28",
  },
  {
    id: "CR-10247",
    customer: "Yara Khalil",
    email: "yara@solaris.io",
    score: 488,
    risk: "Critical",
    status: "Rejected",
    probability: 0.18,
    date: "2026-05-27",
  },
  {
    id: "CR-10248",
    customer: "Theo Nakamura",
    email: "theo@kite.co",
    score: 723,
    risk: "Low",
    status: "Approved",
    probability: 0.86,
    date: "2026-05-27",
  },
];

export const fraudAlerts: FraudAlert[] = [
  {
    id: "FR-8821",
    customer: "Yara Khalil",
    type: "Velocity anomaly",
    severity: "Critical",
    anomaly: 0.97,
    detectedAt: "2m ago",
  },
  {
    id: "FR-8820",
    customer: "Marco Bellini",
    type: "Device mismatch",
    severity: "High",
    anomaly: 0.84,
    detectedAt: "14m ago",
  },
  {
    id: "FR-8819",
    customer: "Lina Ortega",
    type: "Geo deviation",
    severity: "Medium",
    anomaly: 0.62,
    detectedAt: "47m ago",
  },
  {
    id: "FR-8818",
    customer: "Owen Patel",
    type: "Synthetic identity",
    severity: "High",
    anomaly: 0.79,
    detectedAt: "1h ago",
  },
  {
    id: "FR-8817",
    customer: "Noor Saleh",
    type: "Card testing",
    severity: "Low",
    anomaly: 0.41,
    detectedAt: "2h ago",
  },
];

/**
 * Compact sparkline series (last ~12 points) per KPI key — presentation-only,
 * used to render the trend micro-chart on each KPI card.
 */
export const kpiSparklines: Record<string, number[]> = {
  score: [726, 728, 731, 730, 734, 736, 735, 738, 740, 739, 741, 742],
  approval: [61, 62, 63, 64, 63, 65, 66, 66, 67, 67, 68, 68.4],
  predictions: [96, 101, 108, 112, 115, 118, 121, 123, 124, 126, 127, 128.4],
  fraud: [0.61, 0.58, 0.55, 0.54, 0.5, 0.49, 0.47, 0.46, 0.45, 0.44, 0.43, 0.42],
  enterprise_score: [700, 704, 708, 710, 712, 715, 716, 718, 719, 720, 721, 722],
  enterprise_assessments: [18, 19, 20, 21, 22, 24, 25, 27, 28, 29, 30, 31],
  high_risk_accounts: [58, 56, 55, 53, 52, 50, 49, 47, 46, 45, 43, 41],
  fraud_checks: [88, 92, 98, 104, 108, 112, 116, 120, 123, 126, 128, 132],
  fraud_detected: [64, 61, 58, 55, 52, 50, 47, 45, 43, 41, 38, 33],
  customers: [201, 205, 210, 214, 218, 221, 225, 228, 231, 235, 239, 243],
  alerts: [58, 55, 52, 49, 47, 45, 43, 41, 40, 39, 38, 37],
};

/** Human-readable comparison window shown under each KPI value. */
export const KPI_COMPARE_LABEL = "vs prior 30 days";

export type ActivityKind =
  | "decision"
  | "fraud"
  | "workflow"
  | "model"
  | "alert"
  | "report";

export interface ActivityItem {
  id: string;
  kind: ActivityKind;
  actor: string;
  action: string;
  target: string;
  time: string;
  status?: "success" | "warning" | "danger" | "info";
}

/**
 * Recent activity / workflow stream for the dashboard — a modern enterprise
 * feed (decisions, fraud, workflow, model ops). Presentation-only demo data.
 */
export const activityFeed: ActivityItem[] = [
  {
    id: "a1",
    kind: "decision",
    actor: "Priya Raman",
    action: "approved credit line for",
    target: "Orbital AI · ₹4.2Cr",
    time: "2m ago",
    status: "success",
  },
  {
    id: "a2",
    kind: "fraud",
    actor: "Fraud Engine",
    action: "flagged a velocity anomaly on",
    target: "CR-10247 · Yara Khalil",
    time: "6m ago",
    status: "danger",
  },
  {
    id: "a3",
    kind: "workflow",
    actor: "Credit Committee",
    action: "advanced to stage 3 —",
    target: "Northwind Foods facility",
    time: "18m ago",
    status: "info",
  },
  {
    id: "a4",
    kind: "model",
    actor: "MLOps",
    action: "detected drift on feature",
    target: "utilization_ratio (4.1σ)",
    time: "41m ago",
    status: "warning",
  },
  {
    id: "a5",
    kind: "decision",
    actor: "Devon Okafor",
    action: "sent to manual review",
    target: "Lumen Co · ₹1.1Cr",
    time: "1h ago",
    status: "info",
  },
  {
    id: "a6",
    kind: "report",
    actor: "Analyst Studio",
    action: "generated Q2 portfolio memo for",
    target: "Meridian Holdings",
    time: "2h ago",
    status: "success",
  },
  {
    id: "a7",
    kind: "alert",
    actor: "Early Warning",
    action: "raised a watchlist signal on",
    target: "Vela Co · covenant breach",
    time: "3h ago",
    status: "warning",
  },
];

export const insights = [
  {
    title: "Approval rate up 12%",
    body: "Driven by improved scoring on thin-file applicants in the SMB segment.",
    tone: "positive" as const,
  },
  {
    title: "Medium-risk volume +8%",
    body: "Watch the 620–680 score band — exposure grew $2.4M week over week.",
    tone: "neutral" as const,
  },
  {
    title: "Fraud alerts below threshold",
    body: "Anomaly rate at 0.42%, 38% under your SLA ceiling of 0.68%.",
    tone: "positive" as const,
  },
  {
    title: "Model drift detected",
    body: "Feature 'utilization_ratio' shifted 4.1σ — recommend retraining within 7 days.",
    tone: "warning" as const,
  },
];
