import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useResearch, useResearchTypes, useRunResearch } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-research")({ component: ResearchPage });

function ResearchPage() {
  const types = useResearchTypes();
  const list = useResearch();
  const run = useRunResearch();
  const [topic, setTopic] = useState("");
  const [rt, setRt] = useState("sector_analysis");
  const [subject, setSubject] = useState("");
  const [result, setResult] = useState<any>(null);

  return (
    <OpsLayout
      title="AI Research Assistant"
      description="Autonomous research: industry benchmarking, peer comparison, sector analysis, economic indicators, regulatory updates, macro/supply-chain/geopolitical/ESG — grounded in the internal portfolio and indexed knowledge."
    >
      <div className="space-y-4">
        <SectionCard title="Run research">
          <div className="flex flex-wrap gap-2">
            <select className="rounded border bg-background px-3 py-2 text-sm" value={rt} onChange={(e) => setRt(e.target.value)}>
              {((types.data as any)?.research_types ?? []).map((t: string) => <option key={t}>{t}</option>)}
            </select>
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="topic" value={topic} onChange={(e) => setTopic(e.target.value)} />
            <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="subject ref (optional)" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!topic || run.isPending}
              onClick={() => run.mutate({ topic, research_type: rt, subject_ref: subject || undefined }, { onSuccess: (r) => setResult(r) })}>Research</button>
          </div>
          {result && (
            <div className="mt-3 space-y-2 text-sm">
              <div className="text-xs text-muted-foreground">confidence {result.confidence} · {result.sources?.length ?? 0} source(s)</div>
              {(result.sections ?? []).map((s: any, i: number) => (
                <div key={i} className="rounded border border-border p-3">
                  <div className="mb-1 font-semibold">{s.heading}</div>
                  <div className="whitespace-pre-wrap text-xs">{s.body}</div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
        <SectionCard title="Research history">
          <StateWrap loading={list.isLoading} empty={!(list.data as any)?.research?.length}>
            <ul className="space-y-1 text-sm">
              {((list.data as any)?.research ?? []).map((r: any) => (
                <li key={r.research_id} className="flex justify-between border-b border-border/50 py-1"><span>{r.topic}</span><span className="text-xs text-muted-foreground">{r.research_type}</span></li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
