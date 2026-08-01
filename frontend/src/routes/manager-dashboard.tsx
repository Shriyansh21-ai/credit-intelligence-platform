import { createFileRoute } from "@tanstack/react-router";

import {
  ApplicationsTable,
  CountBarChart,
  CountList,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  fmtCurrency,
  titleCase,
  useManager,
} from "@/features/operations";

export const Route = createFileRoute("/manager-dashboard")({ component: ManagerDashboardPage });

function ManagerDashboardPage() {
  const { data, isLoading, error } = useManager();

  return (
    <OpsLayout
      title="Manager Dashboard"
      description="Approvals oversight — what is awaiting decision, decision throughput, and exposure concentration by rating."
    >
      <StateWrap
        loading={isLoading}
        error={(error as Error)?.message ?? null}
        empty={!data && !isLoading}
        emptyMessage="Approval oversight permission is required to view this dashboard."
      >
        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-2">
              <MetricCard label="Pending Approvals" value={data.totals.pending_approvals}
                tone="text-amber-500" />
              <MetricCard label="Total Exposure" value={fmtCurrency(data.totals.total_exposure)} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Pending by stage">
                <CountList
                  data={data.pending_by_stage.map((s) => ({ label: s.stage, value: s.count }))}
                />
              </SectionCard>
              <SectionCard title="Exposure by rating">
                <CountBarChart
                  data={data.exposure_by_rating.map((r) => ({
                    label: titleCase(r.rating),
                    value: Math.round(r.exposure),
                  }))}
                  color="#22c55e"
                />
              </SectionCard>
            </div>

            <SectionCard title="Awaiting decision" description="Applications currently in an approval stage.">
              <ApplicationsTable rows={data.pending_applications} />
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
