import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase, useGovernanceDashboard,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/model-governance")({ component: ModelGovernancePage });

function ModelGovernancePage() {
  const q = useGovernanceDashboard();
  const d = q.data as Record<string, any> | undefined;

  return (
    <OpsLayout
      title="Model Governance Platform"
      description="Enterprise ML governance over the model registry: versions, validation gates, approval workflow, deployment history, champion/challenger, rollback and full model lineage."
    >
      <StateWrap loading={q.isLoading} error={(q.error as Error)?.message ?? null}>
        {d && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Model keys" value={String(d.model_keys?.length ?? 0)} />
              <MetricCard label="Versions" value={String(d.total_versions ?? 0)} />
              <MetricCard label="Validations" value={String(d.validations?.total ?? 0)} />
              <MetricCard label="In production"
                value={String(d.by_production_status?.production ?? 0)} tone="text-emerald-500" />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="By approval status">
                <div className="space-y-1 text-sm">
                  {Object.entries(d.by_approval_status ?? {}).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground">{titleCase(k)}</span>
                      <span className="font-mono">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
              <SectionCard title="Validations by status">
                <div className="space-y-1 text-sm">
                  {Object.entries(d.validations?.by_status ?? {}).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground">{titleCase(k)}</span>
                      <span className="font-mono">{String(v)}</span>
                    </div>
                  ))}
                  {Object.keys(d.validations?.by_status ?? {}).length === 0 && (
                    <p className="text-muted-foreground">No validations recorded yet.</p>
                  )}
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Recent governance events">
              <ul className="space-y-1 text-sm">
                {(d.recent_events ?? []).map((e: any, i: number) => (
                  <li key={i} className="flex gap-2 border-b border-border/50 pb-1">
                    <span className="rounded bg-muted px-2 py-0.5 text-xs">{e.event_type}</span>
                    <span className="text-muted-foreground">{e.model_key} v{e.version} — {e.detail}</span>
                  </li>
                ))}
                {(d.recent_events ?? []).length === 0 && (
                  <li className="text-muted-foreground">No governance events yet. Train + register a model,
                    then validate it here.</li>
                )}
              </ul>
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
