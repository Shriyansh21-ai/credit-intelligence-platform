import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  CountBarChart,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  num,
  pct,
  useAlgorithms,
  useTrainModel,
  type TrainingReport,
} from "@/features/ml-platform";
import { titleCase } from "@/features/operations";

export const Route = createFileRoute("/ml-training")({ component: MLTrainingPage });

function MLTrainingPage() {
  const { data, isLoading, error } = useAlgorithms();
  const train = useTrainModel();
  const [algorithm, setAlgorithm] = useState("logistic_regression");
  const [tune, setTune] = useState(false);
  const report: TrainingReport | undefined = train.data?.training_report;

  const algorithms = data?.algorithms ?? [];

  return (
    <OpsLayout
      title="Training Dashboard"
      description="Train a new risk model on the enterprise feature set. Supported algorithms degrade gracefully when their backend is unavailable."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}>
        <div className="space-y-6">
          <SectionCard title="Available algorithms">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
              {algorithms.map((a) => (
                <button
                  key={a.algorithm}
                  onClick={() => a.backend_available && setAlgorithm(a.algorithm)}
                  disabled={!a.backend_available}
                  className={`rounded-lg border p-3 text-left text-sm transition-colors ${
                    algorithm === a.algorithm
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-muted"
                  } ${a.backend_available ? "" : "opacity-40"}`}
                >
                  <div className="font-medium text-foreground">{titleCase(a.algorithm)}</div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    {a.backend_available ? "backend ready" : "backend unavailable"}
                  </div>
                </button>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input type="checkbox" checked={tune} onChange={(e) => setTune(e.target.checked)} />
                Hyperparameter tuning
              </label>
              <button
                onClick={() => train.mutate({ algorithm, tune })}
                disabled={train.isPending}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90 disabled:opacity-50"
              >
                {train.isPending ? "Training…" : `Train ${titleCase(algorithm)}`}
              </button>
              {train.error && (
                <span className="text-sm text-red-500">{(train.error as Error).message}</span>
              )}
            </div>
          </SectionCard>

          {report && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="ROC-AUC" value={pct(report.metrics.roc_auc as number, 1)} tone="text-emerald-500" />
                <MetricCard label="KS Statistic" value={num(report.metrics.ks_statistic as number, 3)} />
                <MetricCard label="Gini" value={num(report.metrics.gini as number, 3)} />
                <MetricCard label="CV Mean (AUC)" value={pct(report.cross_validation.mean, 1)}
                  sub={`±${num(report.cross_validation.std, 3)}`} />
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <SectionCard title="Top feature importances">
                  <CountBarChart
                    data={Object.entries(report.feature_importances)
                      .slice(0, 10)
                      .map(([label, value]) => ({ label: titleCase(label), value: Number((value * 100).toFixed(2)) }))}
                  />
                </SectionCard>
                <SectionCard title="Training summary">
                  <dl className="space-y-2 text-sm">
                    <Row k="Algorithm" v={titleCase(report.algorithm)} />
                    <Row k="Training rows" v={String(report.n_train)} />
                    <Row k="Test rows" v={String(report.n_test)} />
                    <Row k="Dataset" v={`${report.dataset.name} · ${report.dataset.content_hash}`} />
                    <Row k="Positive rate" v={pct(report.dataset.positive_rate)} />
                    <Row k="Brier score" v={num(report.metrics.brier_score as number, 4)} />
                    <Row k="Training time" v={`${report.training_time_seconds.toFixed(2)} s`} />
                  </dl>
                </SectionCard>
              </div>
            </>
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
