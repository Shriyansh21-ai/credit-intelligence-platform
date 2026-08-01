import { createFileRoute } from "@tanstack/react-router";

import {
  CategoryPie,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  ms,
  pct,
  useMonitoringSummary,
  useServingHistory,
} from "@/features/ml-platform";
import { titleCase } from "@/features/operations";

export const Route = createFileRoute("/ml-inference")({ component: MLInferencePage });

function MLInferencePage() {
  const summary = useMonitoringSummary();
  const history = useServingHistory(40);

  const s = summary.data;
  const preds = history.data?.predictions ?? [];

  return (
    <OpsLayout
      title="Inference Dashboard"
      description="Live serving operations — prediction volume, latency, success rate and recent inferences across all served models."
    >
      <StateWrap loading={summary.isLoading} error={(summary.error as Error)?.message ?? null}>
        {s && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Predictions" value={s.prediction_volume.total} />
              <MetricCard label="Success Rate" value={pct(s.success_rate, 1)}
                tone={s.success_rate === 1 ? "text-emerald-500" : "text-amber-500"} />
              <MetricCard label="Latency p95" value={ms(s.latency_ms.p95)} />
              <MetricCard label="Approval Rate" value={pct(s.class_distribution.approval_rate, 1)} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="By inference type">
                <CategoryPie
                  data={Object.entries(s.prediction_volume.by_type).map(([label, value]) => ({
                    label: titleCase(label),
                    value,
                  }))}
                />
              </SectionCard>
              <SectionCard title="Latency profile">
                <dl className="space-y-2 text-sm">
                  <Row k="Average" v={ms(s.latency_ms.avg)} />
                  <Row k="p50" v={ms(s.latency_ms.p50)} />
                  <Row k="p95" v={ms(s.latency_ms.p95)} />
                  <Row k="p99" v={ms(s.latency_ms.p99)} />
                  <Row k="Max" v={ms(s.latency_ms.max)} />
                  <Row k="Cached responses" v={String(s.prediction_volume.cached)} />
                  <Row k="Data completeness" v={pct(s.data_quality.populated_rate)} />
                </dl>
              </SectionCard>
            </div>

            <SectionCard title="Recent predictions">
              {preds.length === 0 ? (
                <p className="text-sm text-muted-foreground">No predictions logged yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-3">Model</th>
                        <th className="py-2 pr-3">Type</th>
                        <th className="py-2 pr-3">PD</th>
                        <th className="py-2 pr-3">Score</th>
                        <th className="py-2 pr-3">Grade</th>
                        <th className="py-2 pr-3">Latency</th>
                        <th className="py-2 pr-3">Mode</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preds.map((p) => (
                        <tr key={p.id} className="border-b border-border/60">
                          <td className="py-2 pr-3 text-foreground">{p.model_key ?? "-"}</td>
                          <td className="py-2 pr-3">{p.inference_type}</td>
                          <td className="py-2 pr-3">{pct(p.probability_of_default, 1)}</td>
                          <td className="py-2 pr-3 font-mono">{p.risk_score ?? "-"}</td>
                          <td className="py-2 pr-3">{p.risk_grade ?? "-"}</td>
                          <td className="py-2 pr-3">{ms(p.latency_ms)}</td>
                          <td className="py-2 pr-3 text-xs text-muted-foreground">{p.inference_mode}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 pb-1">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-mono text-foreground">{v}</dd>
    </div>
  );
}
