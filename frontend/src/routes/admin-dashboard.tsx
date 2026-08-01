import { createFileRoute } from "@tanstack/react-router";

import {
  CountBarChart,
  CountList,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  titleCase,
  useAdmin,
} from "@/features/operations";

export const Route = createFileRoute("/admin-dashboard")({ component: AdminDashboardPage });

function AdminDashboardPage() {
  const { data, isLoading, error } = useAdmin();

  return (
    <OpsLayout
      title="Administrator Dashboard"
      description="Platform administration overview — users, roles, configuration and audit activity."
    >
      <StateWrap
        loading={isLoading}
        error={(error as Error)?.message ?? null}
        empty={!data && !isLoading}
        emptyMessage="Administrator access is required to view this dashboard."
      >
        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Users" value={data.totals.users} />
              <MetricCard label="Roles" value={data.totals.roles} />
              <MetricCard label="Config Keys" value={data.totals.config_keys} />
              <MetricCard label="Applications" value={data.totals.applications} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Top audit actions" description="Most frequent audited events.">
                <CountBarChart
                  data={data.audit.by_action
                    .slice(0, 10)
                    .map((a) => ({ label: titleCase(a.action), value: a.count }))}
                />
              </SectionCard>
              <SectionCard title="Applications by status">
                <CountList
                  data={data.status_breakdown.map((s) => ({ label: s.status, value: s.count }))}
                />
              </SectionCard>
            </div>

            <SectionCard title="Audit outcomes" description={`${data.audit.total} total audited events.`}>
              <CountList data={data.audit.by_status.map((s) => ({ label: s.status, value: s.count }))} />
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
