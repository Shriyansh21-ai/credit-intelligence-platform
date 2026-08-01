import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useAgentRoster, useAgentRuns, useRunAgents } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-agents")({ component: AgentsPage });

function AgentsPage() {
  const roster = useAgentRoster();
  const runs = useAgentRuns();
  const run = useRunAgents();
  const [goal, setGoal] = useState("Assess creditworthiness for a term loan");
  const [company, setCompany] = useState("");
  const [result, setResult] = useState<any>(null);

  return (
    <OpsLayout
      title="Multi-Agent AI System"
      description="A planner decomposes the goal to a committee of 12 specialist agents; contributions are fused by confidence-weighted consensus with explicit conflict resolution and an executive synthesis. Grounded, offline by default."
    >
      <div className="space-y-4">
        <SectionCard title="Run a committee">
          <div className="space-y-2">
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="goal" value={goal} onChange={(e) => setGoal(e.target.value)} />
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="company ref (optional)" value={company} onChange={(e) => setCompany(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={run.isPending}
              onClick={() => run.mutate({ goal, company_ref: company || undefined }, { onSuccess: (r) => setResult(r) })}>Run agents</button>
          </div>
          {result && (
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-semibold">{result.decision}</span>
                <span className="text-xs text-muted-foreground">confidence {result.confidence}</span>
              </div>
              <div className="rounded bg-muted p-3 whitespace-pre-wrap">{result.executive_summary}</div>
              <div className="grid gap-2 md:grid-cols-2">
                {(result.contributions ?? []).map((c: any) => (
                  <div key={c.role} className="rounded border border-border p-2 text-xs">
                    <div className="font-semibold">{c.title} · <span className="text-muted-foreground">{c.signal}</span></div>
                    <div className="mt-1 whitespace-pre-wrap">{c.recommendation}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </SectionCard>

        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Agent roster">
            <StateWrap loading={roster.isLoading}>
              <ul className="grid grid-cols-2 gap-1 text-xs">
                {((roster.data as any)?.roles ?? []).map((a: any) => <li key={a.role} className="rounded bg-muted px-2 py-1">{a.title}</li>)}
              </ul>
            </StateWrap>
          </SectionCard>
          <SectionCard title="Recent runs">
            <StateWrap loading={runs.isLoading} empty={!(runs.data as any)?.runs?.length}>
              <ul className="space-y-1 text-xs">
                {((runs.data as any)?.runs ?? []).map((r: any) => (
                  <li key={r.run_id} className="flex justify-between border-b border-border/50 py-1">
                    <span className="truncate">{r.goal}</span><span>{r.decision}</span>
                  </li>
                ))}
              </ul>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
