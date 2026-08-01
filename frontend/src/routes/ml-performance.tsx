import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  num,
  pct,
  useEvaluatePerformance,
  useModels,
  usePerformanceTrend,
} from "@/features/ml-platform";
import { fmtCurrency, titleCase } from "@/features/operations";

export const Route = createFileRoute("/ml-performance")({ component: MLPerformancePage });

function MLPerformancePage() {
  const { data: modelsData, isLoading, error } = useModels();
  const models = modelsData?.models ?? [];
  const [modelId, setModelId] = useState<number | null>(null);

  useEffect(() => {
    if (modelId == null && models.length) {
      const prod = models.find((m) => m.production_status === "production");
      setModelId((prod ?? models[0]).id);
    }
  }, [models, modelId]);

  const trend = usePerformanceTrend(modelId);
  const evaluate = useEvaluatePerformance();
  const records = trend.data?.trend ?? [];
  const latest = records[records.length - 1];

  return (
    <OpsLayout
      title="Performance Dashboard"
      description="Model quality against realised outcomes — discrimination, calibration and business KPIs, tracked over time."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}
        empty={!isLoading && !models.length} emptyMessage="No models to evaluate yet.">
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={modelId ?? ""}
              onChange={(e) => setModelId(Number(e.target.value))}
              className="rounded-md border border-border bg-card px-3 py-2 text-sm"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.model_key} v{m.version} ({m.production_status})
                </option>
              ))}
            </select>
            <button
              onClick={() => modelId != null && evaluate.mutate(modelId)}
              disabled={evaluate.isPending || modelId == null}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {evaluate.isPending ? "Evaluating…" : "Run out-of-sample evaluation"}
            </button>
          </div>

          {latest && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="ROC-AUC" value={pct(latest.metrics.roc_auc as number, 1)} tone="text-emerald-500" />
                <MetricCard label="KS" value={num(latest.metrics.ks_statistic as number, 3)} />
                <MetricCard label="Gini" value={num(latest.metrics.gini as number, 3)} />
                <MetricCard label="Brier" value={num(latest.metrics.brier_score as number, 4)} />
                <MetricCard label="Precision" value={pct(latest.metrics.precision as number, 1)} />
                <MetricCard label="Recall" value={pct(latest.metrics.recall as number, 1)} />
                <MetricCard label="F1" value={pct(latest.metrics.f1 as number, 1)} />
                <MetricCard label="Accuracy" value={pct(latest.metrics.accuracy as number, 1)} />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <SectionCard title="Business KPIs (latest evaluation)">
                  <dl className="space-y-2 text-sm">
                    <Row k="Approval rate" v={pct(latest.business_kpis.approval_rate)} />
                    <Row k="Observed default rate" v={pct(latest.business_kpis.observed_default_rate)} />
                    <Row k="Bad rate in approved" v={pct(latest.business_kpis.bad_rate_in_approved)} />
                    <Row k="Expected loss" v={fmtCurrency(latest.business_kpis.expected_loss)} />
                    <Row k="EL per obligor" v={fmtCurrency(latest.business_kpis.expected_loss_per_obligor)} />
                    <Row k="Evaluation size" v={String(latest.n_samples)} />
                  </dl>
                </SectionCard>
                <SectionCard title="ROC-AUC trend">
                  {records.length < 2 ? (
                    <p className="text-sm text-muted-foreground">
                      Run more evaluations to build a trend.
                    </p>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {records.map((r) => (
                        <li key={r.id} className="flex items-center justify-between">
                          <span className="text-muted-foreground">
                            {r.note ? titleCase(r.note.slice(0, 32)) : `#${r.id}`}
                          </span>
                          <span className="font-mono text-foreground">{pct(r.metrics.roc_auc as number, 1)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>
              </div>
            </>
          )}
          {!latest && (
            <p className="text-sm text-muted-foreground">
              No evaluations recorded for this model yet — run one above.
            </p>
          )}
        </div>
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
