import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useAlerts, useAlertSummary, useRunMonitoring, useSignals, useUpdateAlert,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/risk-monitoring")({ component: RiskMonitoringPage });

const SEV_TONE: Record<string, string> = {
  critical: "text-red-500", high: "text-orange-500", medium: "text-amber-500",
  low: "text-sky-500", info: "text-muted-foreground",
};

function RiskMonitoringPage() {
  const [company, setCompany] = useState("");
  const summary = useAlertSummary();
  const alerts = useAlerts("?status=open");
  const signals = useSignals();
  const run = useRunMonitoring();
  const update = useUpdateAlert();
  const sum = summary.data as Record<string, any> | undefined;

  const demo = () => run.mutate({
    company_ref: company || "DemoCo",
    observations: {
      financial: { current: { revenue: 70, net_margin: 0.05 }, previous: { revenue: 100, net_margin: 0.12 } },
      mca: { director_changes: 2 }, payment: { dpd: 45 },
    },
  });

  return (
    <OpsLayout
      title="Real-Time Risk Monitoring"
      description="A continuous monitoring engine over financial, connector, payment, GST, MCA, bureau, portfolio, news, document and market signals — generating prioritized alerts, reassessments and escalations."
    >
      <div className="space-y-6">
        <SectionCard title="Run monitoring">
          <div className="flex items-end gap-3">
            <label className="text-sm flex-1 max-w-md">
              <span className="mb-1 block text-muted-foreground">Company reference</span>
              <input value={company} onChange={(e) => setCompany(e.target.value)}
                placeholder="DemoCo"
                className="w-full rounded-md border border-border bg-background px-3 py-2" />
            </label>
            <button onClick={demo}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
              {run.isPending ? "Running…" : "Run sample observation"}
            </button>
          </div>
          {run.data && (
            <p className="mt-3 text-sm text-muted-foreground">
              {(run.data as any).signal_count} signal(s), {(run.data as any).alerts?.length ?? 0} alert(s),
              escalation: <span className="font-medium">{(run.data as any).escalation}</span>
            </p>
          )}
        </SectionCard>

        <StateWrap loading={summary.isLoading} error={(summary.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Open alerts" value={String(sum?.open ?? 0)} tone="text-amber-500" />
            <MetricCard label="Total alerts" value={String(sum?.total ?? 0)} />
            <MetricCard label="Critical" value={String(sum?.by_severity?.critical ?? 0)} tone="text-red-500" />
            <MetricCard label="High" value={String(sum?.by_severity?.high ?? 0)} tone="text-orange-500" />
          </div>
        </StateWrap>

        <SectionCard title="Open alerts">
          <StateWrap loading={alerts.isLoading} error={(alerts.error as Error)?.message ?? null}>
            <ul className="space-y-2">
              {(alerts.data?.alerts ?? []).map((a) => (
                <li key={a.id} className="flex items-start justify-between rounded-lg border border-border/60 p-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold uppercase ${SEV_TONE[a.severity]}`}>{a.severity}</span>
                      <span className="font-medium">{a.title}</span>
                    </div>
                    <div className="text-sm text-muted-foreground">{a.company_ref} · {a.recommended_action}</div>
                  </div>
                  <button onClick={() => update.mutate({ id: a.id, status: "resolved" })}
                    className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">Resolve</button>
                </li>
              ))}
              {(alerts.data?.alerts ?? []).length === 0 && (
                <li className="text-sm text-muted-foreground">No open alerts.</li>
              )}
            </ul>
          </StateWrap>
        </SectionCard>

        <SectionCard title="Recent signals">
          <ul className="space-y-1 text-sm">
            {(signals.data?.signals ?? []).slice(0, 15).map((s) => (
              <li key={s.id} className="flex items-center gap-3 border-b border-border/50 pb-1">
                <span className="rounded bg-muted px-2 py-0.5 text-xs">{s.source}</span>
                <span className={SEV_TONE[s.severity]}>{titleCase(s.signal_type)}</span>
                <span className="text-muted-foreground">{s.detail}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
