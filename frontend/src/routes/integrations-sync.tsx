import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  useRunSync,
  useSyncJobs,
} from "@/features/integrations";

export const Route = createFileRoute("/integrations-sync")({ component: SyncPage });

const STATUS_TONE: Record<string, string> = {
  completed: "text-emerald-500",
  partial: "text-amber-500",
  failed: "text-red-500",
  running: "text-sky-500",
};

function SyncPage() {
  const [entityRefs, setEntityRefs] = useState("27ABCDE1234F1Z5, AAAAA1111A");
  const [syncType, setSyncType] = useState("full");
  const jobs = useSyncJobs();
  const run = useRunSync();

  return (
    <OpsLayout
      title="Portfolio Synchronization"
      description="Full and incremental sync across connectors with conflict detection, versioning, a retry queue and a dead-letter queue. Incremental sync skips snapshots that are not yet due for refresh."
    >
      <div className="space-y-6">
        <SectionCard title="Run synchronization">
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Sync type</span>
              <select value={syncType} onChange={(e) => setSyncType(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2">
                <option value="full">Full</option>
                <option value="incremental">Incremental</option>
              </select>
            </label>
            <label className="text-sm md:col-span-3">
              <span className="mb-1 block text-muted-foreground">Entity references (comma-separated)</span>
              <input value={entityRefs} onChange={(e) => setEntityRefs(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono" />
            </label>
          </div>
          <button
            onClick={() =>
              run.mutate({
                sync_type: syncType,
                connectors: ["gst", "mca", "bureau", "erp", "payments"],
                entity_refs: entityRefs.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
            disabled={run.isPending}
            className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
            {run.isPending ? "Syncing…" : "Run sync"}
          </button>
          {run.data && (
            <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Processed" value={String(run.data.stats?.processed ?? 0)} tone="text-emerald-500" />
              <MetricCard label="Skipped" value={String(run.data.stats?.skipped ?? 0)} />
              <MetricCard label="Conflicts" value={String(run.data.stats?.conflicts ?? 0)} tone="text-amber-500" />
              <MetricCard label="Failed" value={String(run.data.stats?.failed ?? 0)}
                tone={run.data.stats?.failed ? "text-red-500" : undefined} />
            </div>
          )}
        </SectionCard>

        <SectionCard title="Recent sync jobs">
          <StateWrap loading={jobs.isLoading} error={(jobs.error as Error)?.message ?? null}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4">#</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Processed</th>
                    <th className="py-2 pr-4">Conflicts</th>
                    <th className="py-2 pr-4">Failed</th>
                  </tr>
                </thead>
                <tbody>
                  {(jobs.data?.jobs ?? []).map((j) => (
                    <tr key={j.id} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-mono">{j.id}</td>
                      <td className="py-2 pr-4">{j.sync_type}</td>
                      <td className={`py-2 pr-4 ${STATUS_TONE[j.status] ?? ""}`}>{j.status}</td>
                      <td className="py-2 pr-4">{j.processed}</td>
                      <td className="py-2 pr-4">{j.conflicts?.length ?? 0}</td>
                      <td className="py-2 pr-4">{j.failed}</td>
                    </tr>
                  ))}
                  {(jobs.data?.jobs ?? []).length === 0 && (
                    <tr><td colSpan={6} className="py-4 text-center text-muted-foreground">No sync jobs yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
