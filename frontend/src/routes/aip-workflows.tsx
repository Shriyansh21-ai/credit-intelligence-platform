import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useNodeTypes, useRunWorkflow, useSaveWorkflow, useWorkflows } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-workflows")({ component: WorkflowsPage });

const SAMPLE = JSON.stringify({
  start: "n_start",
  nodes: [
    { id: "n_start", type: "start", next: "n_agent" },
    { id: "n_agent", type: "agent", config: { goal: "Assess for a term loan", company_ref: "$input.company_ref" }, next: "n_report" },
    { id: "n_report", type: "report", config: { report_type: "credit_memo", company_ref: "$input.company_ref" }, next: "n_end" },
    { id: "n_end", type: "end" },
  ],
}, null, 2);

function WorkflowsPage() {
  const list = useWorkflows();
  const nodeTypes = useNodeTypes();
  const save = useSaveWorkflow();
  const run = useRunWorkflow();
  const [key, setKey] = useState("credit-flow");
  const [graph, setGraph] = useState(SAMPLE);
  const [company, setCompany] = useState("");
  const [runResult, setRunResult] = useState<any>(null);

  return (
    <OpsLayout
      title="AI Workflow Builder"
      description="Design node/edge workflows (agent, RAG, API, connector, approval, memory, condition, report nodes) and execute them deterministically with branching, an approval gate and full per-node result capture."
    >
      <div className="space-y-4">
        <div className="text-xs text-muted-foreground">Node types: {((nodeTypes.data as any)?.node_types ?? []).join(", ")}</div>
        <SectionCard title="Design & save workflow">
          <div className="space-y-2">
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} />
            <textarea className="h-56 w-full rounded border bg-background px-3 py-2 font-mono text-xs" value={graph} onChange={(e) => setGraph(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={save.isPending}
              onClick={() => { try { save.mutate({ key, name: key, graph: JSON.parse(graph) }); } catch { /* ignore */ } }}>Save</button>
          </div>
        </SectionCard>
        <SectionCard title="Run workflow">
          <div className="flex gap-2">
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="company ref (input)" value={company} onChange={(e) => setCompany(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={run.isPending}
              onClick={() => run.mutate({ key, input: { company_ref: company } }, { onSuccess: (r) => setRunResult(r) })}>Run</button>
          </div>
          {runResult && (
            <div className="mt-2 text-xs">
              <div>Status: <span className="font-semibold">{runResult.status}</span> · {runResult.steps} steps</div>
              <ul className="mt-1 space-y-0.5">
                {(runResult.node_results ?? []).map((n: any, i: number) => <li key={i} className="rounded bg-muted px-2 py-1">{n.node_id} ({n.type}) → {n.output?.status}</li>)}
              </ul>
            </div>
          )}
        </SectionCard>
        <SectionCard title="Workflows">
          <StateWrap loading={list.isLoading} empty={!(list.data as any)?.length}>
            <ul className="space-y-1 text-sm">
              {(list.data as any)?.map((w: any) => (
                <li key={w.id} className="flex justify-between border-b border-border/50 py-1"><span>{w.key}</span><span className="text-xs text-muted-foreground">v{w.version} · {w.node_count} nodes</span></li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
