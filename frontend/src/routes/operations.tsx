import { createFileRoute } from "@tanstack/react-router";

import {
  ApplicationsTable,
  CountBarChart,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  fmtCurrency,
  titleCase,
  useOperations,
} from "@/features/operations";

export const Route = createFileRoute("/operations")({ component: OperationsPage });

function OperationsPage() {
  const { data, isLoading, error } = useOperations();

  return (
    <OpsLayout
      title="Credit Operations"
      description="Live operational view of the credit book — application pipeline, workload and open risk signals across the platform."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}>
        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <MetricCard label="Applications" value={data.totals.applications} />
              <MetricCard label="Pending Approvals" value={data.totals.pending_approvals}
                tone="text-amber-500" />
              <MetricCard label="Open Tasks" value={data.totals.open_tasks} />
              <MetricCard label="Open Alerts" value={data.totals.open_alerts}
                tone={data.totals.open_alerts ? "text-red-500" : undefined} />
              <MetricCard label="Total Exposure" value={fmtCurrency(data.totals.total_exposure)} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Pipeline by status" description="Applications in each lifecycle stage.">
                <CountBarChart
                  data={data.status_breakdown.map((s) => ({ label: titleCase(s.status), value: s.count }))}
                />
              </SectionCard>
              <SectionCard title="Recently updated" description="Latest activity across applications.">
                <ApplicationsTable rows={data.recent_applications} />
              </SectionCard>
            </div>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
