import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useOpsDashboard, useIncidents, useOpenIncident, useSeedRunbooks, useRunbooks } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-operations")({ component: OperationsPage });

const STATUS_TONE: Record<string, string> = {
  healthy: "text-emerald-500", warning: "text-amber-500", degraded: "text-orange-500",
  critical: "text-red-500", down: "text-red-600", unknown: "text-muted-foreground",
};

function OperationsPage() {
  const dash = useOpsDashboard();
  const incidents = useIncidents();
  const open = useOpenIncident();
  const seed = useSeedRunbooks();
  const runbooks = useRunbooks();

  return (
    <OpsLayout title="Operations Center" description="A single operations console rolling up platform / AI / ML / connector / storage / queue / job health, with incident management, runbooks and deterministic root-cause analysis. Health is computed live from real platform signals.">
      <div className="space-y-4">
        <SectionCard title={`Overall status: ${dash.data?.overall_status ?? "…"}`}>
          <StateWrap loading={dash.isLoading} empty={!dash.data?.components}>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(dash.data?.components ?? {}).map(([k, v]: any) => (
                <div key={k} className="rounded border bg-card p-3">
                  <div className="text-xs text-muted-foreground">{k}</div>
                  <div className={`text-sm font-semibold ${STATUS_TONE[v.status] ?? ""}`}>{v.status} · {v.score}</div>
                </div>
              ))}
            </div>
          </StateWrap>
        </SectionCard>
        <div className="flex gap-2">
          <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => seed.mutate()}>Seed runbooks</button>
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => open.mutate({ title: "AI latency spike", component: "ai", severity: "sev2" })}>Open sample incident</button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Incidents">
            <StateWrap loading={incidents.isLoading} empty={!(incidents.data?.incidents?.length)}>
              <ul className="space-y-1 text-sm">{incidents.data?.incidents?.map((i: any) => (
                <li key={i.incident_id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{i.title} <span className="text-xs text-muted-foreground">{i.component}</span></span>
                  <span className="text-xs text-muted-foreground">{i.severity} · {i.status}</span>
                </li>))}</ul>
            </StateWrap>
          </SectionCard>
          <SectionCard title="Runbooks">
            <StateWrap loading={runbooks.isLoading} empty={!(runbooks.data?.runbooks?.length)}>
              <ul className="space-y-1 text-sm">{runbooks.data?.runbooks?.map((r: any) => (
                <li key={r.runbook_id} className="flex justify-between border-b border-border/50 py-1"><span>{r.title}</span><span className="text-xs text-muted-foreground">{r.category}</span></li>))}</ul>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
