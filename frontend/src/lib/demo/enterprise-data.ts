/**
 * Canonical demo dataset — the single source of truth for Demo Mode.
 *
 * A believable corporate-lending book for a large Indian bank: real, recognisable
 * borrowers across sectors with internally-consistent financials (revenue, EBITDA,
 * leverage, DSCR, PD/LGD/ECL, rating, ESG) and a fixed roster of bankers. Every
 * demo fixture imports from here so the SAME company shows coherent numbers across
 * Portfolio, Risk, Treasury, ESG, Monitoring, Customer 360 and AI views (req. #9).
 *
 * All monetary values are absolute Indian Rupees (₹). `cr(18.5)` === ₹18.5 Cr.
 * Time is derived from a fixed BASE so SSR and client renders are identical.
 */

const DAY = 86_400_000;
export const DEMO_BASE = Date.UTC(2026, 6, 28, 9, 30); // 2026-07-28, stable
export const daysAgo = (n: number) => new Date(DEMO_BASE - n * DAY).toISOString();
export const daysAhead = (n: number) => new Date(DEMO_BASE + n * DAY).toISOString();
/** ₹ crore → absolute rupees. */
export const cr = (n: number) => Math.round(n * 10_000_000);

export type Rating = "AAA" | "AA+" | "AA" | "AA-" | "A+" | "A" | "A-" | "BBB+" | "BBB" | "BBB-" | "BB+" | "BB" | "B+";
export type Grade = "Standard" | "Watch" | "Substandard";
export type RiskBand = "Low" | "Medium" | "High" | "Critical";
export type CreditStatus =
  | "approved"
  | "disbursed"
  | "under_review"
  | "pending_approval"
  | "committee_review"
  | "rejected";

/** Through-the-cycle PD anchored to the internal rating scale. */
const PD_BY_RATING: Record<Rating, number> = {
  AAA: 0.0008, "AA+": 0.0012, AA: 0.0018, "AA-": 0.0026, "A+": 0.004, A: 0.006, "A-": 0.009,
  "BBB+": 0.014, BBB: 0.021, "BBB-": 0.031, "BB+": 0.046, BB: 0.068, "B+": 0.11,
};

export interface DemoBank {
  id: string;
  name: string;
  short: string;
}

export const BANKS: DemoBank[] = [
  { id: "hdfc", name: "HDFC Bank", short: "HDFC" },
  { id: "icici", name: "ICICI Bank", short: "ICICI" },
  { id: "sbi", name: "State Bank of India", short: "SBI" },
  { id: "axis", name: "Axis Bank", short: "Axis" },
  { id: "kotak", name: "Kotak Mahindra Bank", short: "Kotak" },
  { id: "yes", name: "Yes Bank", short: "Yes" },
];

export interface DemoUser {
  id: number;
  name: string;
  email: string;
  role: string;
  title: string;
  region: string;
  initials: string;
  actions_30d: number;
  last_active: string;
}

export const USERS: DemoUser[] = [
  { id: 1, name: "Priya Menon", email: "priya.menon@bank.com", role: "credit_analyst", title: "Senior Credit Analyst", region: "West", initials: "PM", actions_30d: 412, last_active: daysAgo(0) },
  { id: 2, name: "Arjun Rao", email: "arjun.rao@bank.com", role: "portfolio_manager", title: "Portfolio Manager", region: "South", initials: "AR", actions_30d: 356, last_active: daysAgo(0) },
  { id: 3, name: "Neha Gupta", email: "neha.gupta@bank.com", role: "relationship_manager", title: "Relationship Manager", region: "North", initials: "NG", actions_30d: 289, last_active: daysAgo(1) },
  { id: 4, name: "Vikram Singh", email: "vikram.singh@bank.com", role: "chief_risk_officer", title: "Chief Risk Officer", region: "West", initials: "VS", actions_30d: 198, last_active: daysAgo(0) },
  { id: 5, name: "Ananya Iyer", email: "ananya.iyer@bank.com", role: "compliance_officer", title: "Compliance Officer", region: "South", initials: "AI", actions_30d: 241, last_active: daysAgo(1) },
  { id: 6, name: "Rahul Desai", email: "rahul.desai@bank.com", role: "treasury_manager", title: "Treasury Manager", region: "West", initials: "RD", actions_30d: 176, last_active: daysAgo(2) },
];

export interface DemoCompany {
  id: number;
  ref: string;
  name: string;
  sector: string;
  region: string;
  bank: string; // lead bank short name
  rating: Rating;
  grade: Grade;
  status: CreditStatus;
  risk: RiskBand;
  /** Blended internal score (300–850). */
  score: number;
  /** Sanctioned exposure (₹). */
  exposure: number;
  /** Drawn / outstanding (₹). */
  outstanding: number;
  /** Annual revenue (₹). */
  revenue: number;
  /** EBITDA margin (0–1). */
  ebitdaMargin: number;
  /** Net worth (₹). */
  netWorth: number;
  /** Gross debt (₹). */
  debt: number;
  /** Debt-service coverage ratio (x). */
  dscr: number;
  /** ESG composite (0–100). */
  esg: number;
  /** Loss given default (0–1). */
  lgd: number;
  analystId: number;
  ownerId: number;
  updatedDaysAgo: number;
  nextReviewDaysAhead: number;
}

/** Author the book with headline figures; derived fields (EBITDA, PD, ECL, WC) come from helpers. */
const RAW: Omit<DemoCompany, "id">[] = [
  { ref: "APP-2026-4201", name: "Reliance Industries Ltd", sector: "Energy", region: "West", bank: "SBI", rating: "AAA", grade: "Standard", status: "disbursed", risk: "Low", score: 812, exposure: cr(920), outstanding: cr(742), revenue: cr(9740), ebitdaMargin: 0.17, netWorth: cr(7850), debt: cr(3120), dscr: 3.4, esg: 71, lgd: 0.35, analystId: 1, ownerId: 2, updatedDaysAgo: 0, nextReviewDaysAhead: 82 },
  { ref: "APP-2026-4202", name: "Tata Steel Ltd", sector: "Manufacturing", region: "East", bank: "ICICI", rating: "AA", grade: "Standard", status: "disbursed", risk: "Low", score: 768, exposure: cr(760), outstanding: cr(612), revenue: cr(2430), ebitdaMargin: 0.19, netWorth: cr(1180), debt: cr(890), dscr: 2.6, esg: 64, lgd: 0.4, analystId: 1, ownerId: 2, updatedDaysAgo: 1, nextReviewDaysAhead: 61 },
  { ref: "APP-2026-4203", name: "Infosys Ltd", sector: "SaaS", region: "South", bank: "HDFC", rating: "AAA", grade: "Standard", status: "approved", risk: "Low", score: 826, exposure: cr(540), outstanding: cr(180), revenue: cr(1870), ebitdaMargin: 0.24, netWorth: cr(950), debt: cr(120), dscr: 6.8, esg: 82, lgd: 0.3, analystId: 3, ownerId: 2, updatedDaysAgo: 1, nextReviewDaysAhead: 120 },
  { ref: "APP-2026-4204", name: "Larsen & Toubro Ltd", sector: "Infrastructure", region: "West", bank: "Axis", rating: "AAA", grade: "Standard", status: "disbursed", risk: "Low", score: 798, exposure: cr(880), outstanding: cr(690), revenue: cr(2210), ebitdaMargin: 0.13, netWorth: cr(1340), debt: cr(760), dscr: 2.9, esg: 69, lgd: 0.38, analystId: 1, ownerId: 3, updatedDaysAgo: 2, nextReviewDaysAhead: 74 },
  { ref: "APP-2026-4205", name: "JSW Steel Ltd", sector: "Manufacturing", region: "West", bank: "SBI", rating: "AA-", grade: "Standard", status: "under_review", risk: "Medium", score: 712, exposure: cr(680), outstanding: cr(560), revenue: cr(1760), ebitdaMargin: 0.18, netWorth: cr(870), debt: cr(940), dscr: 2.1, esg: 58, lgd: 0.42, analystId: 1, ownerId: 2, updatedDaysAgo: 2, nextReviewDaysAhead: 40 },
  { ref: "APP-2026-4206", name: "Adani Ports & SEZ Ltd", sector: "Logistics", region: "West", bank: "ICICI", rating: "AA-", grade: "Watch", status: "committee_review", risk: "Medium", score: 694, exposure: cr(820), outstanding: cr(705), revenue: cr(690), ebitdaMargin: 0.55, netWorth: cr(1020), debt: cr(1180), dscr: 1.9, esg: 52, lgd: 0.45, analystId: 3, ownerId: 3, updatedDaysAgo: 3, nextReviewDaysAhead: 28 },
  { ref: "APP-2026-4207", name: "Apollo Hospitals Enterprise Ltd", sector: "Healthcare", region: "South", bank: "HDFC", rating: "AA", grade: "Standard", status: "approved", risk: "Low", score: 744, exposure: cr(410), outstanding: cr(298), revenue: cr(720), ebitdaMargin: 0.16, netWorth: cr(430), debt: cr(310), dscr: 2.4, esg: 74, lgd: 0.4, analystId: 3, ownerId: 3, updatedDaysAgo: 3, nextReviewDaysAhead: 96 },
  { ref: "APP-2026-4208", name: "Asian Paints Ltd", sector: "FMCG", region: "West", bank: "Kotak", rating: "AAA", grade: "Standard", status: "disbursed", risk: "Low", score: 804, exposure: cr(360), outstanding: cr(120), revenue: cr(1420), ebitdaMargin: 0.21, netWorth: cr(980), debt: cr(90), dscr: 8.1, esg: 78, lgd: 0.3, analystId: 1, ownerId: 2, updatedDaysAgo: 4, nextReviewDaysAhead: 110 },
  { ref: "APP-2026-4209", name: "ITC Ltd", sector: "FMCG", region: "East", bank: "SBI", rating: "AAA", grade: "Standard", status: "approved", risk: "Low", score: 815, exposure: cr(470), outstanding: cr(210), revenue: cr(1690), ebitdaMargin: 0.34, netWorth: cr(1520), debt: cr(60), dscr: 12.4, esg: 76, lgd: 0.28, analystId: 3, ownerId: 2, updatedDaysAgo: 4, nextReviewDaysAhead: 130 },
  { ref: "APP-2026-4210", name: "Hindustan Unilever Ltd", sector: "FMCG", region: "West", bank: "HDFC", rating: "AAA", grade: "Standard", status: "disbursed", risk: "Low", score: 820, exposure: cr(430), outstanding: cr(150), revenue: cr(1560), ebitdaMargin: 0.23, netWorth: cr(1110), debt: cr(40), dscr: 15.2, esg: 84, lgd: 0.27, analystId: 1, ownerId: 2, updatedDaysAgo: 5, nextReviewDaysAhead: 118 },
  { ref: "APP-2026-4211", name: "Britannia Industries Ltd", sector: "FMCG", region: "South", bank: "Axis", rating: "AA+", grade: "Standard", status: "approved", risk: "Low", score: 758, exposure: cr(280), outstanding: cr(160), revenue: cr(640), ebitdaMargin: 0.19, netWorth: cr(320), debt: cr(180), dscr: 3.1, esg: 67, lgd: 0.38, analystId: 3, ownerId: 3, updatedDaysAgo: 5, nextReviewDaysAhead: 88 },
  { ref: "APP-2026-4212", name: "Mahindra Logistics Ltd", sector: "Logistics", region: "West", bank: "Kotak", rating: "A", grade: "Standard", status: "under_review", risk: "Medium", score: 668, exposure: cr(210), outstanding: cr(168), revenue: cr(560), ebitdaMargin: 0.06, netWorth: cr(190), debt: cr(240), dscr: 1.7, esg: 61, lgd: 0.44, analystId: 3, ownerId: 3, updatedDaysAgo: 6, nextReviewDaysAhead: 22 },
  { ref: "APP-2026-4213", name: "Delhivery Ltd", sector: "Logistics", region: "North", bank: "ICICI", rating: "A-", grade: "Watch", status: "under_review", risk: "Medium", score: 642, exposure: cr(240), outstanding: cr(205), revenue: cr(820), ebitdaMargin: 0.04, netWorth: cr(360), debt: cr(150), dscr: 1.4, esg: 59, lgd: 0.46, analystId: 3, ownerId: 3, updatedDaysAgo: 6, nextReviewDaysAhead: 18 },
  { ref: "APP-2026-4214", name: "Nykaa (FSN E-Commerce Ltd)", sector: "Retail", region: "West", bank: "Axis", rating: "A-", grade: "Standard", status: "pending_approval", risk: "Medium", score: 656, exposure: cr(190), outstanding: cr(96), revenue: cr(640), ebitdaMargin: 0.05, netWorth: cr(280), debt: cr(70), dscr: 1.8, esg: 63, lgd: 0.43, analystId: 1, ownerId: 3, updatedDaysAgo: 7, nextReviewDaysAhead: 34 },
  { ref: "APP-2026-4215", name: "Zomato Ltd", sector: "FinTech", region: "North", bank: "HDFC", rating: "BBB+", grade: "Watch", status: "committee_review", risk: "Medium", score: 628, exposure: cr(220), outstanding: cr(140), revenue: cr(780), ebitdaMargin: 0.03, netWorth: cr(410), debt: cr(50), dscr: 1.3, esg: 55, lgd: 0.48, analystId: 3, ownerId: 3, updatedDaysAgo: 7, nextReviewDaysAhead: 20 },
  { ref: "APP-2026-4216", name: "Swiggy (Bundl Technologies)", sector: "FinTech", region: "South", bank: "ICICI", rating: "BBB", grade: "Watch", status: "under_review", risk: "High", score: 594, exposure: cr(180), outstanding: cr(150), revenue: cr(590), ebitdaMargin: -0.02, netWorth: cr(260), debt: cr(120), dscr: 0.9, esg: 51, lgd: 0.5, analystId: 3, ownerId: 3, updatedDaysAgo: 8, nextReviewDaysAhead: 12 },
  { ref: "APP-2026-4217", name: "Razorpay Software Pvt Ltd", sector: "FinTech", region: "South", bank: "Kotak", rating: "A-", grade: "Standard", status: "approved", risk: "Medium", score: 662, exposure: cr(160), outstanding: cr(88), revenue: cr(240), ebitdaMargin: 0.08, netWorth: cr(180), debt: cr(30), dscr: 2.2, esg: 66, lgd: 0.42, analystId: 1, ownerId: 2, updatedDaysAgo: 9, nextReviewDaysAhead: 70 },
  { ref: "APP-2026-4218", name: "Freshworks Inc (India)", sector: "SaaS", region: "South", bank: "HDFC", rating: "A", grade: "Standard", status: "approved", risk: "Low", score: 704, exposure: cr(150), outstanding: cr(60), revenue: cr(310), ebitdaMargin: 0.11, netWorth: cr(280), debt: cr(20), dscr: 4.6, esg: 72, lgd: 0.35, analystId: 1, ownerId: 2, updatedDaysAgo: 10, nextReviewDaysAhead: 92 },
  { ref: "APP-2026-4219", name: "boAt (Imagine Marketing Ltd)", sector: "Retail", region: "West", bank: "Axis", rating: "BBB+", grade: "Standard", status: "pending_approval", risk: "Medium", score: 636, exposure: cr(120), outstanding: cr(84), revenue: cr(360), ebitdaMargin: 0.07, netWorth: cr(140), debt: cr(90), dscr: 1.9, esg: 57, lgd: 0.45, analystId: 1, ownerId: 3, updatedDaysAgo: 11, nextReviewDaysAhead: 30 },
  { ref: "APP-2026-4220", name: "Ather Energy Ltd", sector: "Automotive", region: "South", bank: "Yes", rating: "BBB", grade: "Substandard", status: "rejected", risk: "High", score: 566, exposure: cr(140), outstanding: cr(132), revenue: cr(180), ebitdaMargin: -0.08, netWorth: cr(90), debt: cr(160), dscr: 0.7, esg: 60, lgd: 0.55, analystId: 4, ownerId: 3, updatedDaysAgo: 13, nextReviewDaysAhead: 8 },
];

export const COMPANIES: DemoCompany[] = RAW.map((c, i) => ({ id: 4201 + i, ...c }));

// ---- Derived per-company analytics (kept consistent everywhere) ------------

export const pdOf = (c: DemoCompany) => PD_BY_RATING[c.rating] ?? 0.02;
export const ebitdaOf = (c: DemoCompany) => Math.round(c.revenue * c.ebitdaMargin);
export const eclOf = (c: DemoCompany) => Math.round(pdOf(c) * c.lgd * c.outstanding);
export const leverageOf = (c: DemoCompany) => +(c.debt / Math.max(1, ebitdaOf(c))).toFixed(2);
/** Working capital ≈ 12–22% of revenue, sector-flavoured but deterministic. */
export const workingCapitalOf = (c: DemoCompany) => Math.round(c.revenue * (0.12 + (c.id % 5) * 0.02));

export const SECTORS = [
  "Manufacturing", "Logistics", "Retail", "Healthcare", "FinTech",
  "SaaS", "Energy", "Infrastructure", "FMCG", "Automotive",
] as const;

export const REGIONS = ["West", "South", "North", "East"] as const;

export const userById = (id: number) => USERS.find((u) => u.id === id) ?? USERS[0];
export const companyByRef = (ref: string) => COMPANIES.find((c) => c.ref === ref);

/** Portfolio-level roll-ups used by many dashboards (book is larger than the named sample). */
export const BOOK = {
  applications: 1284,
  total_exposure: cr(8640),
  total_outstanding: cr(6180),
  approved: 967,
  approval_rate: 0.753,
  avg_score: 712,
  npa_ratio: 0.031,
  gross_npa: cr(191),
  provision_coverage: 0.68,
  crar: 0.164,
  ecl_total: cr(142),
};

/** 12-month labels ending at the demo base month, e.g. Aug'25 … Jul'26. */
export const MONTHS_12 = [
  "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
];

export type NotificationSeverity = "critical" | "warning" | "info" | "success";

export interface DemoNotification {
  id: string;
  title: string;
  detail: string;
  severity: NotificationSeverity;
  category: string;
  created_at: string;
  unread: boolean;
}

/** Realistic activity feed for the top-bar bell — coherent with the demo book. */
export const NOTIFICATIONS: DemoNotification[] = [
  { id: "N-4821", title: "Covenant breach — Ather Energy Ltd", detail: "DSCR fell to 0.7x, below the 1.0x covenant floor. Facility flagged for review.", severity: "critical", category: "Covenant", created_at: daysAgo(0), unread: true },
  { id: "N-4820", title: "Fraud investigation opened — Swiggy", detail: "Transaction-velocity anomaly (score 76) routed to the financial-crime queue.", severity: "critical", category: "Fraud", created_at: daysAgo(0), unread: true },
  { id: "N-4819", title: "Exposure increased — Adani Ports & SEZ", detail: "Drawn exposure rose to ₹705 Cr; net debt / EBITDA now 3.6x (limit 3.5x).", severity: "warning", category: "Exposure", created_at: daysAgo(0), unread: true },
  { id: "N-4818", title: "Treasury liquidity warning", detail: "Intraday LCR dipped to 118%; buffer within tolerance but trending down.", severity: "warning", category: "Treasury", created_at: daysAgo(1), unread: true },
  { id: "N-4817", title: "Model drift detected — PD Model v3.2", detail: "PSI 0.21 on the 'leverage' feature crossed the 0.20 amber threshold.", severity: "warning", category: "Model Risk", created_at: daysAgo(1), unread: false },
  { id: "N-4816", title: "Committee approved — Infosys Ltd", detail: "₹540 Cr working-capital facility approved by the credit committee.", severity: "success", category: "Committee", created_at: daysAgo(1), unread: false },
  { id: "N-4815", title: "OCR extraction complete — Reliance Industries", detail: "FY26 audited financials parsed; 42 line items reconciled at 99.3% confidence.", severity: "info", category: "Documents", created_at: daysAgo(2), unread: false },
  { id: "N-4814", title: "ESG report available — Tata Steel Ltd", detail: "Updated ESG assessment published; composite score 64/100 (sector avg 58).", severity: "info", category: "ESG", created_at: daysAgo(2), unread: false },
  { id: "N-4813", title: "Portfolio review completed — Q2 FY26", detail: "Quarterly book review closed. GNPA 3.1%, provision coverage 68%.", severity: "success", category: "Portfolio", created_at: daysAgo(3), unread: false },
];
