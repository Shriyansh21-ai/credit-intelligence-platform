import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useReadiness, useChecklists, useGenerateAllChecklists } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-launch")({ component: LaunchPage });

function LaunchPage() {
  const readiness = useReadiness();
  const checklists = useChecklists();
  const generate = useGenerateAllChecklists();

  return (
    <OpsLayout title="Launch Readiness" description="Commercial-release gating: production, deployment, security, operational, release, disaster-recovery, business-continuity, scaling, performance and monitoring checklists — each scored and rolled up into an overall launch-readiness grade.">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => generate.mutate()}>Generate all checklists</button>
          {readiness.data?.overall_readiness_score != null && (
            <span className="text-sm">Overall readiness: <b>{readiness.data.overall_readiness_score}%</b> ({readiness.data.grade}) · {readiness.data.commercial_ready ? "commercial-ready" : "in progress"}</span>
          )}
        </div>
        <SectionCard title="Readiness by area">
          <StateWrap loading={readiness.isLoading} empty={!readiness.data?.by_type}>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(readiness.data?.by_type ?? {}).map(([k, v]: any) => (
                <div key={k} className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">{k}</div><div className="text-lg font-semibold">{v}%</div></div>
              ))}
            </div>
          </StateWrap>
        </SectionCard>
        <SectionCard title="Checklists">
          <StateWrap loading={checklists.isLoading} empty={!(checklists.data?.checklists?.length)}>
            <ul className="space-y-1 text-sm">{checklists.data?.checklists?.map((c: any) => (
              <li key={c.checklist_id} className="flex justify-between border-b border-border/50 py-1">
                <span>{c.title}</span><span className="text-xs text-muted-foreground">{c.completed}/{c.total} · {c.readiness_score}%</span>
              </li>))}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
