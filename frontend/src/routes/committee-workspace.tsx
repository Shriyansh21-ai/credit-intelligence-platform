import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useCommitteeAnalytics, useCommittees, useMeetings,
} from "@/features/banking-os";

export const Route = createFileRoute("/committee-workspace")({ component: CommitteeWorkspacePage });

function CommitteeWorkspacePage() {
  const committees = useCommittees();
  const meetings = useMeetings();
  const analytics = useCommitteeAnalytics();

  const cs = (committees.data as any)?.committees ?? [];
  const ms = (meetings.data as any)?.meetings ?? [];
  const a = analytics.data as any;

  const statusTone = (s: string) =>
    s === "closed" ? "text-muted-foreground" : s === "in_session" ? "text-emerald-500" : "text-amber-500";

  return (
    <OpsLayout
      title="Loan Committee Workspace"
      description="Collaborative committee review — committees, meetings, agendas, weighted voting with digital signatures, minutes and decision analytics."
    >
      <div className="space-y-6">
        <StateWrap loading={analytics.isLoading} error={(analytics.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Committees" value={String(a?.committees ?? 0)} />
            <MetricCard label="Meetings" value={String(a?.meetings ?? 0)} />
            <MetricCard label="Decisions" value={String(a?.decided ?? 0)} />
            <MetricCard
              label="Approval rate"
              value={a?.approval_rate != null ? `${Math.round(a.approval_rate * 100)}%` : "—"}
              tone="text-emerald-500"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Committees">
              <div className="space-y-2 text-sm">
                {cs.length === 0 && <p className="text-muted-foreground">No committees yet.</p>}
                {cs.map((c: any) => (
                  <div key={c.id} className="flex justify-between rounded-md border border-border/60 p-2">
                    <span className="font-medium text-foreground">{c.name}</span>
                    <span className="text-xs text-muted-foreground">quorum {c.quorum} · {(c.members ?? []).length} members</span>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Meetings">
              <div className="space-y-2 text-sm">
                {ms.length === 0 && <p className="text-muted-foreground">No meetings scheduled.</p>}
                {ms.map((m: any) => (
                  <div key={m.id} className="flex justify-between rounded-md border border-border/60 p-2">
                    <span className="font-medium text-foreground">{m.title}</span>
                    <span className={`text-xs ${statusTone(m.status)}`}>{titleCase(m.status.replace(/_/g, " "))}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
