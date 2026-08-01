import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const KEY = "ai-platform";

// M1 RAG
export const useSources = () => useQuery({ queryKey: [KEY, "sources"], queryFn: api.listSources });
export const useDocuments = () => useQuery({ queryKey: [KEY, "documents"], queryFn: api.listDocuments });
export const useRagStats = () => useQuery({ queryKey: [KEY, "rag-stats"], queryFn: api.ragStats });
export const useCreateSource = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createSource,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "sources"] }) });
};
export const useIngestDocument = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.ingestDocument,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "documents"] });
                       qc.invalidateQueries({ queryKey: [KEY, "rag-stats"] }); } });
};
export const useRagAnswer = () => useMutation({ mutationFn: api.ragAnswer });
export const useRagSearch = () => useMutation({ mutationFn: api.ragSearch });

// M2 Agents
export const useAgentRoster = () => useQuery({ queryKey: [KEY, "roster"], queryFn: api.agentRoster });
export const useAgentRuns = () => useQuery({ queryKey: [KEY, "agent-runs"], queryFn: api.listAgentRuns });
export const useRunAgents = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.runAgents,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "agent-runs"] }) });
};

// M3 Memory
export const useMemoryStats = () => useQuery({ queryKey: [KEY, "memory-stats"], queryFn: api.memoryStats });
export const useMemoryWrite = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.memoryWrite,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "memory-stats"] }) });
};
export const useMemoryRecall = () => useMutation({ mutationFn: api.memoryRecall });

// M4 Prompts
export const usePrompts = () => useQuery({ queryKey: [KEY, "prompts"], queryFn: api.listPrompts });
export const useSeedPrompts = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.seedPrompts,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "prompts"] }) });
};
export const useCreatePrompt = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createPrompt,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "prompts"] }) });
};
export const useRenderPrompt = () => useMutation({ mutationFn: api.renderPrompt });

// M5 Eval
export const useEvalSummary = () => useQuery({ queryKey: [KEY, "eval-summary"], queryFn: api.evalSummary });
export const useEvalList = () => useQuery({ queryKey: [KEY, "eval-list"], queryFn: api.evalList });
export const useEvalScore = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.evalScore,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "eval-summary"] });
                       qc.invalidateQueries({ queryKey: [KEY, "eval-list"] }); } });
};

// M6 Investigation
export const useInvestigations = () => useQuery({ queryKey: [KEY, "investigations"], queryFn: api.listInvestigations });
export const useRunInvestigation = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.runInvestigation,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "investigations"] }) });
};

// M7 Reports
export const useReportTypes = () => useQuery({ queryKey: [KEY, "report-types"], queryFn: api.reportTypes });
export const useReports = () => useQuery({ queryKey: [KEY, "reports"], queryFn: api.listReports });
export const useGenerateReport = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.generateReport,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "reports"] }) });
};

// M8 Workflows
export const useWorkflows = () => useQuery({ queryKey: [KEY, "workflows"], queryFn: api.listWorkflows });
export const useNodeTypes = () => useQuery({ queryKey: [KEY, "node-types"], queryFn: api.nodeTypes });
export const useSaveWorkflow = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.saveWorkflow,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "workflows"] }) });
};
export const useRunWorkflow = () => useMutation({ mutationFn: api.runWorkflow });

// M9 Chat
export const useConversations = () => useQuery({ queryKey: [KEY, "conversations"], queryFn: api.listConversations });
export const useCreateConversation = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createConversation,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "conversations"] }) });
};
export const useChatAsk = () => useMutation({ mutationFn: api.chatAsk });

// M10 Research
export const useResearchTypes = () => useQuery({ queryKey: [KEY, "research-types"], queryFn: api.researchTypes });
export const useResearch = () => useQuery({ queryKey: [KEY, "research"], queryFn: api.listResearch });
export const useRunResearch = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.runResearch,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "research"] }) });
};

// M11 Learning
export const useLearningStats = () => useQuery({ queryKey: [KEY, "learning-stats"], queryFn: api.learningStats });
export const useTrainingEvents = () => useQuery({ queryKey: [KEY, "training-events"], queryFn: api.listTrainingEvents });
export const useSubmitFeedback = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.submitFeedback,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "learning-stats"] }) });
};
export const useEvaluateTriggers = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.evaluateTriggers,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "training-events"] }) });
};

// M12 Governance
export const useAssets = () => useQuery({ queryKey: [KEY, "assets"], queryFn: api.listAssets });
export const useGovernanceSummary = () => useQuery({ queryKey: [KEY, "gov-summary"], queryFn: api.governanceSummary });
export const useRegisterAsset = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.registerAsset,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "assets"] });
                       qc.invalidateQueries({ queryKey: [KEY, "gov-summary"] }); } });
};
export const useTransitionAsset = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.transitionAsset,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "assets"] }) });
};

// M13 Explain
export const useExplanations = () => useQuery({ queryKey: [KEY, "explanations"], queryFn: api.listExplanations });
export const useExplainDecision = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.explainDecision,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "explanations"] }) });
};

// M14 Monitoring
export const useMonitoringDashboard = () => useQuery({ queryKey: [KEY, "monitoring"], queryFn: api.monitoringDashboard });
export const useIncidents = () => useQuery({ queryKey: [KEY, "incidents"], queryFn: api.listIncidents });
export const useRunMonitoring = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.runMonitoring,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "monitoring"] });
                       qc.invalidateQueries({ queryKey: [KEY, "incidents"] }); } });
};
