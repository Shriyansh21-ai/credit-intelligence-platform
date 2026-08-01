import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useWorkflowRuns, useWorkflows,
} from "@/features/banking-os";

export const Route = createFileRoute("/workflow-studio")({ component: WorkflowStudioPage });

function WorkflowStudioPage() {
  const defs = useWorkflows();
  const runs = useWorkflowRuns();

  const definitions = (defs.data as any)?.definitions ?? [];
  const runList = (runs.data as any)?.runs ?? [];

  const statusTone = (s: string) =>
    s === "completed" ? "text-emerald-500" : s === "failed" ? "text-red-500" : s === "waiting" ? "text-amber-500" : "text-foreground";

  return (
    <OpsLayout
      title="Enterprise Workflow Studio"
      description="Visual, versioned BPMN-like workflows with a deterministic execution engine — start, task, decision, approval, automation, notification and end nodes with conditional routing."
    >
      <div className="space-y-6">
        <StateWrap loading={defs.isLoading} error={(defs.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Definitions" value={String(definitions.length)} />
            <MetricCard label="Active" value={String(definitions.filter((d: any) => d.status === "active").length)} />
            <MetricCard label="Runs" value={String(runList.length)} />
            <MetricCard label="Waiting" value={String(runList.filter((r: any) => r.status === "waiting").length)} tone="text-amber-500" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Workflow definitions">
              <div className="space-y-2 text-sm">
                {definitions.length === 0 && <p className="text-muted-foreground">No workflows designed yet.</p>}
                {definitions.map((d: any) => (
                  <div key={d.id} className="flex items-center justify-between rounded-md border border-border/60 p-2">
                    <div>
                      <div className="font-medium text-foreground">{d.name} <span className="text-xs text-muted-foreground">v{d.version}</span></div>
                      <div className="text-xs text-muted-foreground">{d.node_count} nodes</div>
                    </div>
                    <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase">{d.status}</span>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Recent runs">
              <div className="space-y-2 text-sm">
                {runList.length === 0 && <p className="text-muted-foreground">No runs yet.</p>}
                {runList.map((r: any) => (
                  <div key={r.id} className="flex items-center justify-between rounded-md border border-border/60 p-2">
                    <span className="text-foreground">{r.definition_key} <span className="text-xs text-muted-foreground">{r.subject_ref ?? ""}</span></span>
                    <span className={`text-xs ${statusTone(r.status)}`}>{titleCase(r.status)}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
