/** Types for the Phase 5 enterprise dashboards (Milestone 11). */

export interface ApplicationRow {
  id: number;
  reference: string | null;
  company_name: string;
  industry: string | null;
  requested_amount: number | null;
  status: string;
  status_label: string | null;
  risk_rating: string | null;
  updated_at: string | null;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface OperationsDashboard {
  totals: {
    applications: number;
    pending_approvals: number;
    open_tasks: number;
    open_alerts: number;
    total_exposure: number;
  };
  status_breakdown: StatusCount[];
  recent_applications: ApplicationRow[];
}

export interface AdminDashboard {
  totals: { users: number; roles: number; config_keys: number; applications: number };
  audit: {
    total: number;
    by_action: { action: string; count: number }[];
    by_status: { status: string; count: number }[];
  };
  status_breakdown: StatusCount[];
}

export interface AnalystDashboard {
  totals: { my_open_tasks: number; my_applications: number; unread_notifications: number };
  my_tasks_by_status: { status: string; count: number }[];
  my_applications: ApplicationRow[];
}

export interface ManagerDashboard {
  totals: { pending_approvals: number; total_exposure: number };
  pending_by_stage: { stage: string; count: number }[];
  approval_actions: { action: string; count: number }[];
  exposure_by_rating: { rating: string; exposure: number }[];
  pending_applications: ApplicationRow[];
}

export interface PortfolioGroup {
  value: string;
  count: number;
  exposure: number;
}

export interface PortfolioDashboard {
  totals: { applications: number; total_exposure: number };
  by_status: PortfolioGroup[];
  by_industry: PortfolioGroup[];
  by_rating: PortfolioGroup[];
  by_grade: PortfolioGroup[];
}

export interface ComplianceDashboard {
  totals: {
    open_covenant_alerts: number;
    open_monitoring_alerts: number;
    audit_events: number;
  };
  audit: {
    total: number;
    by_action: { action: string; count: number }[];
    by_status: { status: string; count: number }[];
  };
  recent_audit: { timestamp: string | null; user: string | null; action: string; status: string }[];
}

export interface MonitoringDashboard {
  totals: { open_alerts: number };
  by_category: { category: string; count: number }[];
  by_severity: { severity: string; count: number }[];
  recent_alerts: {
    application_id: number;
    category: string;
    severity: string;
    status: string;
    message: string;
    created_at: string | null;
  }[];
}

export interface MyAccess {
  user_id: number;
  email: string | null;
  roles: string[];
  permissions: string[];
}
