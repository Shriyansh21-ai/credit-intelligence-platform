import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useMonitoringDashboard } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-monitoring")({ component: MonitoringPage });

function MonitoringPage() {
  const dash = useMonitoringDashboard();
  const d = dash.data;

  return (
    <OpsLayout title="Monitoring Platform" description="Distributed tracing, service dependency graph, latency (p50/p95/p99) analysis, capacity planning, SLA tracking and AI/ML/infra cost monitoring in one executive observability dashboard.">
      <StateWrap loading={dash.isLoading} empty={!d}>
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">p99 latency</div><div className="text-lg font-semibold">{d?.latency?.p99_ms ?? "—"} ms</div></div>
            <div className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">error rate</div><div className="text-lg font-semibold">{d?.latency?.error_rate_pct ?? 0}%</div></div>
            <div className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">SLA compliance</div><div className="text-lg font-semibold">{d?.sla?.compliance_pct ?? "—"}%</div></div>
            <div className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">monthly cost</div><div className="text-lg font-semibold">${d?.cost?.total_usd ?? "—"}</div></div>
          </div>
          <SectionCard title="Service dependency graph">
            <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(d?.dependency_graph, null, 2).slice(0, 900)}</pre>
          </SectionCard>
          <SectionCard title="Cost breakdown">
            <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(d?.cost, null, 2)}</pre>
          </SectionCard>
        </div>
      </StateWrap>
    </OpsLayout>
  );
}
