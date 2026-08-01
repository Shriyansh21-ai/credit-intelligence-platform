import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, useCrossHoldings, useUbo,
} from "@/features/banking-os";

export const Route = createFileRoute("/graph-analytics")({ component: GraphAnalyticsPage });

function GraphAnalyticsPage() {
  const cross = useCrossHoldings();
  const ubo = useUbo();
  const [ref, setRef] = useState("");

  const c = cross.data as any;
  const u = ubo.data as any;

  return (
    <OpsLayout
      title="Knowledge Graph Analytics"
      description="Ultimate beneficial owners, connected-lending detection, cross-holding cycles and entity timelines — the regulated-lending analytics over the enterprise knowledge graph."
    >
      <div className="space-y-6">
        <StateWrap loading={cross.isLoading} error={(cross.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Cross-holding cycles" value={String(c?.count ?? 0)} tone={(c?.count ?? 0) > 0 ? "text-amber-500" : "text-foreground"} />
            <MetricCard label="UBOs found" value={String((u?.ubos ?? []).length)} />
          </div>

          <SectionCard title="Ultimate Beneficial Owner lookup" description="Resolve UBOs by walking ownership edges with effective ownership percentages.">
            <div className="flex gap-2">
              <input
                value={ref}
                onChange={(e) => setRef(e.target.value)}
                placeholder="Company ref (e.g. Acme)"
                className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
              <button
                onClick={() => ref && ubo.mutate(ref)}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                {ubo.isPending ? "Resolving…" : "Resolve UBOs"}
              </button>
            </div>
            {ubo.error && <p className="mt-2 text-sm text-red-500">{(ubo.error as Error).message}</p>}
            {u && (
              <div className="mt-3 space-y-1 text-sm">
                {(u.ubos ?? []).length === 0 && <p className="text-muted-foreground">No UBOs above threshold.</p>}
                {(u.ubos ?? []).map((o: any) => (
                  <div key={o.id} className="flex justify-between border-b border-border/50 py-1">
                    <span className="text-foreground">{o.name} <span className="text-xs text-muted-foreground">{o.entity_type}</span></span>
                    <span className="font-mono text-muted-foreground">{Math.round(o.effective_ownership * 100)}%</span>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard title="Cross-holding cycles">
            <div className="space-y-2 text-sm">
              {(c?.cross_holdings ?? []).length === 0 && <p className="text-muted-foreground">No circular cross-holdings detected.</p>}
              {(c?.cross_holdings ?? []).map((cycle: string[], i: number) => (
                <div key={i} className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 font-mono text-xs text-amber-600">
                  {cycle.join(" → ")} → {cycle[0]}
                </div>
              ))}
            </div>
          </SectionCard>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
