import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  num,
  useDriftHistory,
} from "@/features/ml-platform";
import { titleCase } from "@/features/operations";

export const Route = createFileRoute("/ml-drift")({ component: MLDriftPage });

function MLDriftPage() {
  const { data, isLoading, error } = useDriftHistory(60);
  const reports = data?.reports ?? [];
  const breached = reports.filter((r) => r.breached);

  return (
    <OpsLayout
      title="Drift Dashboard"
      description="Population Stability Index and feature-drift detection against each model's training reference. Breaches recommend retraining."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}
        empty={!isLoading && !reports.length}
        emptyMessage="No drift reports yet. Run drift detection against a model.">
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            <MetricCard label="Drift Runs" value={reports.length} />
            <MetricCard label="Breaches" value={breached.length}
              tone={breached.length ? "text-red-500" : "text-emerald-500"} />
            <MetricCard label="Models Monitored" value={new Set(reports.map((r) => r.model_key)).size} />
          </div>

          <SectionCard title="Drift reports" description="Most recent first.">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3">Model</th>
                    <th className="py-2 pr-3">Type</th>
                    <th className="py-2 pr-3">Overall PSI</th>
                    <th className="py-2 pr-3">Drifted</th>
                    <th className="py-2 pr-3">Missing</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Top drifted features</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((r) => (
                    <tr key={r.id} className="border-b border-border/60">
                      <td className="py-2 pr-3 text-foreground">{r.model_key ?? "-"}</td>
                      <td className="py-2 pr-3">{r.report_type}</td>
                      <td className="py-2 pr-3 font-mono">{num(r.psi_overall, 3)}</td>
                      <td className="py-2 pr-3">{r.n_drifted}/{r.n_features}</td>
                      <td className="py-2 pr-3">{num((r.missing_feature_rate ?? 0) * 100, 1)}%</td>
                      <td className="py-2 pr-3">
                        <span className={r.breached ? "text-red-500" : "text-emerald-500"}>
                          {r.breached ? "Breached" : "Stable"}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {r.drifted_features.slice(0, 4).map(titleCase).join(", ") || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      </StateWrap>
    </OpsLayout>
  );
}
