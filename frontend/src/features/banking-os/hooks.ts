/**
 * React Query hooks for the Phase 10 Banking OS. Queries are keyed by module so
 * mutations can invalidate precisely; every hook maps 1:1 to an api.ts function.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const opts = { staleTime: 30_000 } as const;

// M7 Policy
export const usePolicyDomains = () =>
  useQuery({ queryKey: ["os", "policy", "domains"], queryFn: api.getPolicyDomains, ...opts });
export const usePolicies = (domain?: string) =>
  useQuery({ queryKey: ["os", "policy", "list", domain], queryFn: () => api.listPolicies(domain), ...opts });
export const usePolicyPlayground = () =>
  useMutation({ mutationFn: (body: api.Json) => api.policyPlayground(body) });
export const useEvaluatePolicy = () =>
  useMutation({ mutationFn: (v: { key: string; body: api.Json }) => api.evaluatePolicy(v.key, v.body) });
export const useCreatePolicy = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: api.Json) => api.createPolicy(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["os", "policy", "list"] }),
  });
};

// M4 Committee
export const useCommittees = () =>
  useQuery({ queryKey: ["os", "committee", "list"], queryFn: api.listCommittees, ...opts });
export const useMeetings = () =>
  useQuery({ queryKey: ["os", "committee", "meetings"], queryFn: api.listMeetings, ...opts });
export const useCommitteeAnalytics = () =>
  useQuery({ queryKey: ["os", "committee", "analytics"], queryFn: api.committeeAnalytics, ...opts });

// M2 Search
export const useSearch = () => useMutation({ mutationFn: (body: api.Json) => api.search(body) });
export const useSearchFacets = () =>
  useQuery({ queryKey: ["os", "search", "facets"], queryFn: api.searchFacets, ...opts });
export const useReindex = () => useMutation({ mutationFn: api.reindex });

// M8 Prompt
export const usePrompts = () =>
  useQuery({ queryKey: ["os", "prompt", "list"], queryFn: api.listPrompts, ...opts });

// M9 LLM
export const useProviders = () =>
  useQuery({ queryKey: ["os", "llm", "providers"], queryFn: api.listProviders, ...opts });
export const useLLMAnalytics = () =>
  useQuery({ queryKey: ["os", "llm", "analytics"], queryFn: api.llmAnalytics, ...opts });
export const useRouteLLM = () => useMutation({ mutationFn: (body: api.Json) => api.routeLLM(body) });

// M14 Data Fabric
export const useFabricCatalog = () =>
  useQuery({ queryKey: ["os", "fabric", "catalog"], queryFn: api.fabricCatalog, ...opts });
export const useFabricStats = () =>
  useQuery({ queryKey: ["os", "fabric", "stats"], queryFn: api.fabricStats, ...opts });

// M11 Workflow
export const useWorkflows = () =>
  useQuery({ queryKey: ["os", "workflow", "defs"], queryFn: api.listWorkflows, ...opts });
export const useWorkflowRuns = () =>
  useQuery({ queryKey: ["os", "workflow", "runs"], queryFn: api.listWorkflowRuns, ...opts });
export const useValidateWorkflow = () =>
  useMutation({ mutationFn: (body: api.Json) => api.validateWorkflow(body) });

// M12 Marketplace
export const usePlugins = () =>
  useQuery({ queryKey: ["os", "marketplace", "plugins"], queryFn: api.listPlugins, ...opts });
export const useSeedPlugins = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.seedPlugins,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["os", "marketplace"] }),
  });
};
export const useRunMarketplace = () =>
  useMutation({ mutationFn: (body: api.Json) => api.runMarketplace(body) });

// M5/M6 Scenario
export const useScenarioLibrary = () =>
  useQuery({ queryKey: ["os", "scenario", "library"], queryFn: api.scenarioLibrary, ...opts });
export const useRunScenarios = () =>
  useMutation({ mutationFn: (body: api.Json) => api.runScenarios(body) });

// M13 Fairness
export const useFairnessHistory = () =>
  useQuery({ queryKey: ["os", "fairness", "history"], queryFn: api.fairnessHistory, ...opts });
export const useEvaluateFairness = () =>
  useMutation({ mutationFn: (body: api.Json) => api.evaluateFairness(body) });

// M1 Graph
export const useCrossHoldings = () =>
  useQuery({ queryKey: ["os", "graph", "cross"], queryFn: api.getCrossHoldings, ...opts });
export const useUbo = () => useMutation({ mutationFn: (ref: string) => api.getUbo(ref) });

// M10 Exec
export const useExecDashboard = (persona: string) =>
  useQuery({ queryKey: ["os", "exec", persona], queryFn: () => api.execDashboard(persona), ...opts });
