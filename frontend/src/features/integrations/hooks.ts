import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const KEY = "integrations";

export const useConnectors = () =>
  useQuery({ queryKey: [KEY, "connectors"], queryFn: api.getConnectors });

export const useOverview = () =>
  useQuery({ queryKey: [KEY, "overview"], queryFn: api.getOverview });

export const useHealth = () =>
  useQuery({ queryKey: [KEY, "health"], queryFn: api.getHealth });

export const useCallLogs = (limit = 100) =>
  useQuery({ queryKey: [KEY, "call-logs", limit], queryFn: () => api.getCallLogs(limit) });

export const useSetMode = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, mode }: { key: string; mode: string }) => api.setConnectorMode(key, mode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [KEY, "connectors"] });
      qc.invalidateQueries({ queryKey: [KEY, "overview"] });
    },
  });
};

export const useImportData = () => {
  const qc = useMutation({
    mutationFn: ({ connectorKey, body }: { connectorKey: string; body: Record<string, unknown> }) =>
      api.importData(connectorKey, body),
  });
  return qc;
};

export const useSyncJobs = () =>
  useQuery({ queryKey: [KEY, "sync-jobs"], queryFn: api.getSyncJobs });

export const useRunSync = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.runSync(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "sync-jobs"] }),
  });
};

export const useCollateralTypes = () =>
  useQuery({ queryKey: [KEY, "collateral-types"], queryFn: api.getCollateralTypes });

export const useEntityCollateral = (entityRef: string | null) =>
  useQuery({
    queryKey: [KEY, "collateral", entityRef],
    queryFn: () => api.getEntityCollateral(entityRef as string),
    enabled: !!entityRef,
  });

export const useCreateCollateral = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createCollateral(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "collateral"] }),
  });
};

export const useCustomer360 = (entityRef: string | null) =>
  useQuery({
    queryKey: [KEY, "customer360", entityRef],
    queryFn: () => api.getCustomer360(entityRef as string),
    enabled: !!entityRef,
  });

export const useApiKeys = () =>
  useQuery({ queryKey: [KEY, "api-keys"], queryFn: api.getApiKeys });

export const useCreateApiKey = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createApiKey(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "api-keys"] }),
  });
};

export const useRevokeApiKey = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.revokeApiKey(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "api-keys"] }),
  });
};

export const useWebhooks = () =>
  useQuery({ queryKey: [KEY, "webhooks"], queryFn: api.getWebhooks });

export const useApiUsage = () =>
  useQuery({ queryKey: [KEY, "api-usage"], queryFn: api.getApiUsage });
