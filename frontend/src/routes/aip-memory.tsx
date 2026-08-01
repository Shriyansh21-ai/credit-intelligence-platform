import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { MetricCard, OpsLayout, SectionCard, useMemoryRecall, useMemoryStats, useMemoryWrite } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-memory")({ component: MemoryPage });

function MemoryPage() {
  const stats = useMemoryStats();
  const write = useMemoryWrite();
  const recall = useMemoryRecall();
  const [content, setContent] = useState("");
  const [scope, setScope] = useState("organization");
  const [scopeRef, setScopeRef] = useState("");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);

  return (
    <OpsLayout
      title="Long-Term Memory"
      description="Enterprise memory across semantic, episodic, procedural, org, tenant, user, conversation, case, committee and customer scopes. Vector + graph + SQL, with retrieval scoring, summaries and a decay-based forgetting strategy."
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Total" value={(stats.data as any)?.total ?? "—"} />
          <MetricCard label="Active" value={(stats.data as any)?.active ?? "—"} />
          <MetricCard label="Summaries" value={(stats.data as any)?.summaries ?? "—"} />
          <MetricCard label="Types" value={Object.keys((stats.data as any)?.by_type ?? {}).length} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Write memory">
            <div className="space-y-2">
              <textarea className="h-20 w-full rounded border bg-background px-3 py-2 text-sm" placeholder="memory content" value={content} onChange={(e) => setContent(e.target.value)} />
              <div className="flex gap-2">
                <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="scope" value={scope} onChange={(e) => setScope(e.target.value)} />
                <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="scope ref" value={scopeRef} onChange={(e) => setScopeRef(e.target.value)} />
              </div>
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!content || write.isPending}
                onClick={() => write.mutate({ content, scope, scope_ref: scopeRef || undefined }, { onSuccess: () => setContent("") })}>Store</button>
            </div>
          </SectionCard>
          <SectionCard title="Recall">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="query" value={q} onChange={(e) => setQ(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!q || recall.isPending}
                onClick={() => recall.mutate({ query: q, scope, scope_ref: scopeRef || undefined }, { onSuccess: (r) => setHits(r.memories) })}>Recall</button>
              <ul className="space-y-1 text-xs">
                {hits.map((m) => <li key={m.memory_id} className="rounded bg-muted px-2 py-1">{m.content} <span className="text-muted-foreground">({m.score})</span></li>)}
              </ul>
            </div>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
