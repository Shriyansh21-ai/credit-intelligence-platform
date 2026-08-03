import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const KEY = "enterprise-platform";

// M1 UX
export const usePreferences = () => useQuery({ queryKey: [KEY, "prefs"], queryFn: api.getPreferences });
export const useSavePreferences = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.savePreferences,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "prefs"] }) });
};
export const useCommandCatalog = (query?: string, enabled = true) =>
  useQuery({ queryKey: [KEY, "commands", query ?? ""], queryFn: () => api.commandCatalog(query), enabled });

// M2 Workspaces
export const useWorkspaces = () => useQuery({ queryKey: [KEY, "workspaces"], queryFn: api.listWorkspaces });
export const useCreateWorkspace = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createWorkspace,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "workspaces"] }) });
};

// M3 Developer
export const useApiKeys = () => useQuery({ queryKey: [KEY, "keys"], queryFn: api.listApiKeys });
export const useApiExplorer = () => useQuery({ queryKey: [KEY, "explorer"], queryFn: api.apiExplorer });
export const useCreateApiKey = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createApiKey,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "keys"] }) });
};
export const useWebhooks = () => useQuery({ queryKey: [KEY, "webhooks"], queryFn: api.listWebhooks });
export const useSandboxRequest = () => useMutation({ mutationFn: api.sandboxRequest });

// M4 Marketplace
export const usePlugins = () => useQuery({ queryKey: [KEY, "plugins"], queryFn: api.listPlugins });
export const useMarketplaceAnalytics = () =>
  useQuery({ queryKey: [KEY, "mkt-analytics"], queryFn: api.marketplaceAnalytics });
export const usePublishPlugin = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.publishPlugin,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "plugins"] }) });
};

// M5 Integration
export const usePipelines = () => useQuery({ queryKey: [KEY, "pipelines"], queryFn: api.listPipelines });
export const useSavePipeline = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.savePipeline,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "pipelines"] }) });
};
export const useRunPipeline = () => useMutation({ mutationFn: api.runPipeline });

// M6 Data
export const useDataCatalog = () => useQuery({ queryKey: [KEY, "catalog"], queryFn: api.dataCatalog });
export const useUpsertGolden = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.upsertGolden,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "catalog"] }) });
};
export const useDetectDuplicates = () => useMutation({ mutationFn: api.detectDuplicates });

// M7 Operations
export const useOpsDashboard = () => useQuery({ queryKey: [KEY, "ops-dash"], queryFn: api.opsDashboard });
export const useIncidents = () => useQuery({ queryKey: [KEY, "incidents"], queryFn: api.listIncidents });
export const useOpenIncident = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.openIncident,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "incidents"] });
                       qc.invalidateQueries({ queryKey: [KEY, "ops-dash"] }); } });
};
export const useRunbooks = () => useQuery({ queryKey: [KEY, "runbooks"], queryFn: api.listRunbooks });
export const useSeedRunbooks = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.seedRunbooks,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "runbooks"] }) });
};

// M8 Security
export const useSecurityDashboard = () =>
  useQuery({ queryKey: [KEY, "sec-dash"], queryFn: api.securityDashboard });
export const useSecurityEvents = () =>
  useQuery({ queryKey: [KEY, "sec-events"], queryFn: api.listSecurityEvents });
export const useAnalyzeSession = () => useMutation({ mutationFn: api.analyzeSession });

// M9 Customer Success
export const useSuccessDashboard = () =>
  useQuery({ queryKey: [KEY, "success-dash"], queryFn: api.successDashboard });
export const useCustomers = () => useQuery({ queryKey: [KEY, "customers"], queryFn: api.listCustomers });
export const useCreateCustomer = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createCustomer,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "customers"] });
                       qc.invalidateQueries({ queryKey: [KEY, "success-dash"] }); } });
};

// M10 Deployment
export const useEnvironments = () => useQuery({ queryKey: [KEY, "envs"], queryFn: api.listEnvironments });
export const useVersionDashboard = () =>
  useQuery({ queryKey: [KEY, "versions"], queryFn: api.versionDashboard });
export const useSeedEnvironments = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.seedEnvironments,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "envs"] }) });
};
export const useDeploy = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.deploy,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "envs"] });
                       qc.invalidateQueries({ queryKey: [KEY, "versions"] }); } });
};
export const useRollback = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.rollback,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "envs"] });
                       qc.invalidateQueries({ queryKey: [KEY, "versions"] }); } });
};

// M11 Monitoring
export const useMonitoringDashboard = () =>
  useQuery({ queryKey: [KEY, "mon-dash"], queryFn: api.monitoringDashboard });

// M12 BI
export const useBiAnalytics = (category: string) =>
  useQuery({ queryKey: [KEY, "bi", category], queryFn: () => api.biAnalytics(category) });
export const useBoardReport = () => useQuery({ queryKey: [KEY, "board"], queryFn: api.boardReport });

// M13 Launch
export const useReadiness = () => useQuery({ queryKey: [KEY, "readiness"], queryFn: api.readinessSummary });
export const useChecklists = () => useQuery({ queryKey: [KEY, "checklists"], queryFn: api.listChecklists });
export const useGenerateAllChecklists = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.generateAllChecklists,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "readiness"] });
                       qc.invalidateQueries({ queryKey: [KEY, "checklists"] }); } });
};
