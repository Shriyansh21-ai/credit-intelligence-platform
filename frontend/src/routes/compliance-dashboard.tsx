import { createFileRoute } from "@tanstack/react-router";

import {
  CountBarChart,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  titleCase,
  useCompliance,
} from "@/features/operations";

export const Route = createFileRoute("/compliance-dashboard")({ component: ComplianceDashboardPage });

function ComplianceDashboardPage() {
  const { data, isLoading, error } = useCompliance();

  return (
    <OpsLayout
      title="Compliance Dashboard"
      description="Governance view — open covenant and monitoring alerts and recent audit activity for compliance oversight."
    >
      <StateWrap
        loading={isLoading}
        error={(error as Error)?.message ?? null}
        empty={!data && !isLoading}
        emptyMessage="Audit visibility permission is required to view this dashboard."
      >
        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
              <MetricCard label="Open Covenant Alerts" value={data.totals.open_covenant_alerts}
                tone={data.totals.open_covenant_alerts ? "text-red-500" : undefined} />
              <MetricCard label="Open Monitoring Alerts" value={data.totals.open_monitoring_alerts}
                tone={data.totals.open_monitoring_alerts ? "text-amber-500" : undefined} />
              <MetricCard label="Audit Events" value={data.totals.audit_events} />
            </div>

            <SectionCard title="Top audit actions">
              <CountBarChart
                data={data.audit.by_action
                  .slice(0, 10)
                  .map((a) => ({ label: titleCase(a.action), value: a.count }))}
                color="#a855f7"
              />
            </SectionCard>

            <SectionCard title="Recent audit trail" description="Latest 15 audited events.">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">When</th>
                      <th className="py-2 pr-3 font-medium">User</th>
                      <th className="py-2 pr-3 font-medium">Action</th>
                      <th className="py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_audit.map((r, i) => (
                      <tr key={i} className="border-b border-border/60 last:border-0">
                        <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">
                          {r.timestamp ? new Date(r.timestamp).toLocaleString() : "-"}
                        </td>
                        <td className="py-2 pr-3">{r.user ?? "-"}</td>
                        <td className="py-2 pr-3">{titleCase(r.action)}</td>
                        <td className="py-2">
                          <span
                            className={
                              r.status === "failure"
                                ? "text-red-500"
                                : "text-emerald-500"
                            }
                          >
                            {titleCase(r.status)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
