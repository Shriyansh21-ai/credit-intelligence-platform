import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useGraphStats, useNetwork, usePropagateRisk,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/knowledge-graph")({ component: KnowledgeGraphPage });

function KnowledgeGraphPage() {
  const stats = useGraphStats();
  const net = useNetwork(undefined, 2);
  const propagate = usePropagateRisk();
  const s = stats.data as Record<string, any> | undefined;
  const n = net.data;

  return (
    <OpsLayout
      title="Enterprise Knowledge Graph"
      description="Companies, directors, promoters, subsidiaries, suppliers, customers, lenders, guarantors and sectors as a directed, weighted graph — with traversal, connected exposure, similarity and risk propagation."
    >
      <div className="space-y-6">
        <div className="flex justify-end">
          <button onClick={() => propagate.mutate()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
            {propagate.isPending ? "Propagating…" : "Propagate risk across network"}
          </button>
        </div>

        <StateWrap loading={stats.isLoading} error={(stats.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Entities" value={String(s?.entities ?? 0)} />
            <MetricCard label="Relationships" value={String(s?.relationships ?? 0)} />
            <MetricCard label="Entity types" value={String(Object.keys(s?.by_entity_type ?? {}).length)} />
            <MetricCard label="Relationship types" value={String(Object.keys(s?.by_relationship_type ?? {}).length)} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="By entity type">
              <div className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(s?.by_entity_type ?? {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between rounded-md border border-border/60 px-3 py-1.5">
                    <span className="text-muted-foreground">{titleCase(k)}</span>
                    <span className="font-mono">{String(v)}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
            <SectionCard title="By relationship type">
              <div className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(s?.by_relationship_type ?? {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between rounded-md border border-border/60 px-3 py-1.5">
                    <span className="text-muted-foreground">{titleCase(k)}</span>
                    <span className="font-mono">{String(v)}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </StateWrap>

        <SectionCard title={`Network (${n?.node_count ?? 0} nodes / ${n?.edge_count ?? 0} edges)`}>
          <StateWrap loading={net.isLoading} error={(net.error as Error)?.message ?? null}>
            {n && n.nodes.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Graph is empty. Seed it from an assessment via <code>POST /api/ai/graph/seed</code> or
                ingest a relationship network.
              </p>
            )}
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {(n?.nodes ?? []).slice(0, 30).map((node) => (
                <div key={node.id} className="rounded-lg border border-border/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{node.name}</span>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs">{titleCase(node.entity_type)}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Risk {node.risk_score ?? "—"}
                    {node.propagated_risk != null && ` · propagated ${node.propagated_risk}`}
                  </div>
                </div>
              ))}
            </div>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
