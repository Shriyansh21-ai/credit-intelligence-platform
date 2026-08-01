import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, usePipelines, useSavePipeline, useRunPipeline } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-integration")({ component: IntegrationPage });

const SAMPLE_GRAPH = {
  nodes: [{ id: "s1", type: "source" }, { id: "t1", type: "transform", config: { multiply: 2 } }, { id: "k1", type: "sink" }],
  edges: [{ from: "s1", to: "t1" }, { from: "t1", to: "k1" }],
};

function IntegrationPage() {
  const pipelines = usePipelines();
  const save = useSavePipeline();
  const run = useRunPipeline();
  const [name, setName] = useState("");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Integration Studio" description="A visual integration builder: connector configuration, API/data mapping, transformation rules, event routing, retry policies, scheduling and run monitoring. Pipelines are node/edge graphs executed deterministically with per-node logs.">
      <div className="space-y-4">
        <SectionCard title="Create pipeline (sample source→transform→sink)">
          <div className="flex gap-2">
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="pipeline name" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!name || save.isPending}
              onClick={() => save.mutate({ name, graph: SAMPLE_GRAPH }, { onSuccess: () => setName("") })}>Create</button>
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Pipelines">
            <StateWrap loading={pipelines.isLoading} empty={!(pipelines.data?.pipelines?.length)}>
              <ul className="space-y-1 text-sm">{pipelines.data?.pipelines?.map((p: any) => (
                <li key={p.pipeline_id} className="flex items-center justify-between border-b border-border/50 py-1">
                  <span>{p.name} <span className="text-xs text-muted-foreground">{p.node_count} nodes · {p.status}</span></span>
                  <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => run.mutate({ pipeline_id: p.pipeline_id, sample_input: { id: 1, value: 50 } }, { onSuccess: (r) => setOut(r) })}>Run</button>
                </li>))}</ul>
            </StateWrap>
          </SectionCard>
          <SectionCard title="Run result"><StateWrap loading={run.isPending} empty={!out}><pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1200)}</pre></StateWrap></SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
