import { createFileRoute } from "@tanstack/react-router";

import {
  ApplicationsTable,
  CountList,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  useAnalyst,
} from "@/features/operations";

export const Route = createFileRoute("/analyst-dashboard")({ component: AnalystDashboardPage });

function AnalystDashboardPage() {
  const { data, isLoading, error } = useAnalyst();

  return (
    <OpsLayout
      title="Analyst Dashboard"
      description="Your personal workspace — assigned applications, your open tasks and unread notifications."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}>
        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
              <MetricCard label="My Open Tasks" value={data.totals.my_open_tasks}
                tone={data.totals.my_open_tasks ? "text-amber-500" : undefined} />
              <MetricCard label="My Applications" value={data.totals.my_applications} />
              <MetricCard label="Unread Notifications" value={data.totals.unread_notifications} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="My tasks by status">
                <CountList
                  data={data.my_tasks_by_status.map((t) => ({ label: t.status, value: t.count }))}
                />
              </SectionCard>
              <SectionCard title="My applications">
                <ApplicationsTable rows={data.my_applications} />
              </SectionCard>
            </div>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
