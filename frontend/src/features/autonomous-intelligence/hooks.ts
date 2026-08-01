import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const KEY = "autonomous";

// Graph
export const useGraphStats = () =>
  useQuery({ queryKey: [KEY, "graph-stats"], queryFn: api.getGraphStats });
export const useNetwork = (rootId?: number, maxDepth = 2) =>
  useQuery({ queryKey: [KEY, "network", rootId, maxDepth], queryFn: () => api.getNetwork(rootId, maxDepth) });
export const useEntities = (entityType?: string) =>
  useQuery({ queryKey: [KEY, "entities", entityType], queryFn: () => api.listEntities(entityType) });
export const usePropagateRisk = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.propagateRisk,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "network"] }) });
};

// Monitoring + alerts
export const useSignals = (companyRef?: string) =>
  useQuery({ queryKey: [KEY, "signals", companyRef], queryFn: () => api.getSignals(companyRef) });
export const useAlerts = (params = "") =>
  useQuery({ queryKey: [KEY, "alerts", params], queryFn: () => api.getAlerts(params) });
export const useAlertSummary = () =>
  useQuery({ queryKey: [KEY, "alert-summary"], queryFn: api.getAlertSummary });
export const useRunMonitoring = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.runMonitoring,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "signals"] });
                       qc.invalidateQueries({ queryKey: [KEY, "alerts"] }); } });
};
export const useUpdateAlert = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, status }: { id: number; status: string }) => api.updateAlert(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "alerts"] }) });
};

// EWS
export const useEvaluateEws = () => useMutation({ mutationFn: api.evaluateEws });

// Copilot
export const useAskCopilot = () => useMutation({ mutationFn: api.askCopilot });
export const useProviderStatus = () =>
  useQuery({ queryKey: [KEY, "provider"], queryFn: api.getProviderStatus });

// Simulation / stress
export const useScenarios = () =>
  useQuery({ queryKey: [KEY, "scenarios"], queryFn: api.getScenarios });
export const useRunSimulation = () => useMutation({ mutationFn: api.runSimulation });
export const useStressScenarios = () =>
  useQuery({ queryKey: [KEY, "stress-scenarios"], queryFn: api.getStressScenarios });
export const useRunStress = () => useMutation({ mutationFn: api.runStress });

// Portfolio
export const usePortfolioAnalysis = () =>
  useQuery({ queryKey: [KEY, "portfolio"], queryFn: api.getPortfolioAnalysis });
export const useOptimize = () => useMutation({ mutationFn: api.optimizePortfolio });

// RM
export const useRmWorkspace = (companyRef: string | null) =>
  useQuery({ queryKey: [KEY, "rm", companyRef], queryFn: () => api.getRmWorkspace(companyRef as string),
    enabled: !!companyRef });

// Command center
export const useCommandDashboard = (persona: string) =>
  useQuery({ queryKey: [KEY, "command", persona], queryFn: () => api.getCommandDashboard(persona) });

// NLQ
export const useNlQuery = () => useMutation({ mutationFn: api.nlQuery });

// Recommendations / workflow
export const useGenerateRecommendations = () => useMutation({ mutationFn: api.generateRecommendations });
export const usePlanWorkflow = () => useMutation({ mutationFn: api.planWorkflow });

// Governance
export const useGovernanceDashboard = () =>
  useQuery({ queryKey: [KEY, "governance"], queryFn: api.getGovernanceDashboard });

// Data lake
export const useDatalakeCatalog = () =>
  useQuery({ queryKey: [KEY, "datalake-catalog"], queryFn: api.getDatalakeCatalog });
export const useDatalakeStats = () =>
  useQuery({ queryKey: [KEY, "datalake-stats"], queryFn: api.getDatalakeStats });
export const useRunIngestion = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.runIngestionAll,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "datalake-catalog"] });
                       qc.invalidateQueries({ queryKey: [KEY, "datalake-stats"] }); } });
};
