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
