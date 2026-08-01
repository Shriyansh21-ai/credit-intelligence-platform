import { apiGet } from "@/lib/http";
import type {
  AdminDashboard,
  AnalystDashboard,
  ComplianceDashboard,
  ManagerDashboard,
  MonitoringDashboard,
  MyAccess,
  OperationsDashboard,
  PortfolioDashboard,
} from "./types";

export const getOperations = () => apiGet<OperationsDashboard>("/api/dashboards/operations");
export const getAdmin = () => apiGet<AdminDashboard>("/api/dashboards/admin");
export const getAnalyst = () => apiGet<AnalystDashboard>("/api/dashboards/analyst");
export const getManager = () => apiGet<ManagerDashboard>("/api/dashboards/manager");
export const getPortfolio = () => apiGet<PortfolioDashboard>("/api/dashboards/portfolio");
export const getCompliance = () => apiGet<ComplianceDashboard>("/api/dashboards/compliance");
export const getMonitoring = () => apiGet<MonitoringDashboard>("/api/dashboards/monitoring");

export const getMyAccess = () => apiGet<MyAccess>("/api/rbac/me");
