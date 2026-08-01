/**
 * React Query hooks for the Stage 4 Security & Compliance platform. Queries are
 * keyed by domain so mutations can invalidate precisely; every hook maps 1:1 to
 * an api.ts function.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const opts = { staleTime: 30_000 } as const;

// Posture & dashboard
export const usePosture = () =>
  useQuery({ queryKey: ["sec", "posture"], queryFn: api.getPosture, ...opts });
export const useSecurityDashboard = () =>
  useQuery({ queryKey: ["sec", "dashboard"], queryFn: api.getDashboard, ...opts });
export const useSnapshots = () =>
  useQuery({ queryKey: ["sec", "snapshots"], queryFn: api.listSnapshots, ...opts });
export const useTakeSnapshot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.takeSnapshot,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sec", "snapshots"] }),
  });
};

// Threat / OWASP / authz
export const useThreatModel = () =>
  useQuery({ queryKey: ["sec", "threat"], queryFn: api.getThreatModel, ...opts });
export const useOwasp = () =>
  useQuery({ queryKey: ["sec", "owasp"], queryFn: api.getOwasp, ...opts });
export const useAuthz = () =>
  useQuery({ queryKey: ["sec", "authz"], queryFn: api.getAuthz, ...opts });
export const useTenantIsolation = () =>
  useQuery({ queryKey: ["sec", "tenant"], queryFn: api.getTenantIsolation, ...opts });

// Secrets / data / supply / container
export const useSecrets = () =>
  useQuery({ queryKey: ["sec", "secrets"], queryFn: api.getSecrets, ...opts });
export const useDataProtection = () =>
  useQuery({ queryKey: ["sec", "data"], queryFn: api.getDataProtection, ...opts });
export const useSupplyChain = () =>
  useQuery({ queryKey: ["sec", "supply"], queryFn: api.getSupplyChain, ...opts });
export const useContainer = () =>
  useQuery({ queryKey: ["sec", "container"], queryFn: api.getContainer, ...opts });

// AI / ML security
export const useAiSecurity = () =>
  useQuery({ queryKey: ["sec", "ai"], queryFn: api.getAiSecurity, ...opts });
export const useMlSecurity = () =>
  useQuery({ queryKey: ["sec", "ml"], queryFn: api.getMlSecurity, ...opts });

// Compliance
export const useComplianceMatrix = () =>
  useQuery({ queryKey: ["sec", "compliance", "matrix"], queryFn: api.getComplianceMatrix, ...opts });
export const useGapAnalysis = () =>
  useQuery({ queryKey: ["sec", "compliance", "gaps"], queryFn: api.getGapAnalysis, ...opts });
export const useAssessFramework = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (framework: string) => api.assessFramework(framework),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sec", "compliance"] }),
  });
};

// Privacy
export const usePrivacy = () =>
  useQuery({ queryKey: ["sec", "privacy"], queryFn: api.getPrivacy, ...opts });
export const usePrivacyRequests = (status?: string) =>
  useQuery({ queryKey: ["sec", "privacy", "requests", status], queryFn: () => api.listPrivacyRequests(status), ...opts });

// Scans & findings
export const useScans = () =>
  useQuery({ queryKey: ["sec", "scans"], queryFn: api.listScans, ...opts });
export const useFindings = (status?: string) =>
  useQuery({ queryKey: ["sec", "findings", status], queryFn: () => api.listFindings(status), ...opts });
export const useRunScan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scanType: string) => api.runScan(scanType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sec", "scans"] });
      qc.invalidateQueries({ queryKey: ["sec", "findings"] });
      qc.invalidateQueries({ queryKey: ["sec", "dashboard"] });
    },
  });
};
export const useUpdateFinding = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; status: string }) => api.updateFinding(v.id, v.status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sec", "findings"] });
      qc.invalidateQueries({ queryKey: ["sec", "dashboard"] });
    },
  });
};

// Risk register
export const useRisks = (status?: string) =>
  useQuery({ queryKey: ["sec", "risk", status], queryFn: () => api.listRisks(status), ...opts });
export const useCreateRisk = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: api.Json) => api.createRisk(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sec", "risk"] }),
  });
};
