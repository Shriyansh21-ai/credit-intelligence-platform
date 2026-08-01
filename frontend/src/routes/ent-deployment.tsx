import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useEnvironments, useVersionDashboard, useSeedEnvironments, useDeploy, useRollback } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-deployment")({ component: DeploymentPage });

function DeploymentPage() {
  const envs = useEnvironments();
  const versions = useVersionDashboard();
  const seed = useSeedEnvironments();
  const deploy = useDeploy();
  const rollback = useRollback();

  return (
    <OpsLayout title="Deployment Platform" description="Environment management (dev/test/staging/prod), blue-green & canary deployments, feature rollouts, rollback, release notes, a version dashboard and deployment history with environment health.">
      <div className="space-y-4">
        <div className="flex gap-2">
          <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => seed.mutate()}>Seed environments</button>
        </div>
        <SectionCard title="Environments">
          <StateWrap loading={envs.isLoading} empty={!(envs.data?.environments?.length)}>
            <ul className="space-y-1 text-sm">{envs.data?.environments?.map((e: any) => (
              <li key={e.environment_id} className="flex items-center justify-between border-b border-border/50 py-1">
                <span>{e.name} <span className="text-xs text-muted-foreground">{e.current_version ?? "no version"} · {e.status}</span></span>
                <span className="flex gap-1">
                  <button className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground" onClick={() => deploy.mutate({ environment_id: e.environment_id, version: "1.0.0", strategy: "blue_green", release_notes: "GA" })}>Deploy 1.0.0</button>
                  <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => deploy.mutate({ environment_id: e.environment_id, version: "1.1.0", strategy: "canary", canary_percent: 10 })}>Canary 1.1.0</button>
                  <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => rollback.mutate({ environment_id: e.environment_id })}>Rollback</button>
                </span>
              </li>))}</ul>
          </StateWrap>
        </SectionCard>
        <SectionCard title="Version dashboard">
          {versions.data && <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify({ environments: versions.data.environments, success_rate_pct: versions.data.success_rate_pct, total: versions.data.total_deployments }, null, 2)}</pre>}
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
