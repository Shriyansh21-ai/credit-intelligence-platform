import { createFileRoute } from "@tanstack/react-router";

import {
  CategoryPie,
  CountList,
  MetricCard,
  OpsLayout,
  SectionCard,
  SeverityBadge,
  StateWrap,
  titleCase,
  useMonitoringOps,
} from "@/features/operations";

export const Route = createFileRoute("/monitoring-dashboard")({ component: MonitoringDashboardPage });

function MonitoringDashboardPage() {
  const { data, isLoading, error } = useMonitoringOps();

  return (
    <OpsLayout
      title="Monitoring Dashboard"
      description="Post-disbursement health — deterioration alerts across the live book by category and severity."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}>
        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <MetricCard label="Open Alerts" value={data.totals.open_alerts}
                tone={data.totals.open_alerts ? "text-red-500" : undefined} />
              <MetricCard label="Alert Categories" value={data.by_category.length} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="By category">
                <CategoryPie
                  data={data.by_category.map((c) => ({ label: titleCase(c.category), value: c.count }))}
                />
              </SectionCard>
              <SectionCard title="By severity">
                <CountList
                  data={data.by_severity.map((s) => ({ label: s.severity, value: s.count }))}
                />
              </SectionCard>
            </div>

            <SectionCard title="Recent deterioration alerts">
              {data.recent_alerts.length === 0 ? (
                <p className="text-sm text-muted-foreground">No monitoring alerts.</p>
              ) : (
                <ul className="space-y-2">
                  {data.recent_alerts.map((a, i) => (
                    <li
                      key={i}
                      className="flex items-start justify-between gap-3 rounded-lg border border-border p-3"
                    >
                      <div>
                        <div className="text-sm font-medium text-foreground">
                          {titleCase(a.category)} · Application #{a.application_id}
                        </div>
                        <div className="text-xs text-muted-foreground">{a.message}</div>
                      </div>
                      <SeverityBadge severity={a.severity} />
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
