import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useEvaluateFairness, useFairnessHistory,
} from "@/features/banking-os";

export const Route = createFileRoute("/fairness-governance")({ component: FairnessGovernancePage });

const DEMO_RECORDS = [
  ...Array.from({ length: 8 }, () => ({ group: "A", approved: true })),
  ...Array.from({ length: 2 }, () => ({ group: "A", approved: false })),
  ...Array.from({ length: 3 }, () => ({ group: "B", approved: true })),
  ...Array.from({ length: 7 }, () => ({ group: "B", approved: false })),
];

function FairnessGovernancePage() {
  const history = useFairnessHistory();
  const evaluate = useEvaluateFairness();

  const runs = (history.data as any)?.history ?? [];
  const res = evaluate.data as any;

  return (
    <OpsLayout
      title="Model Fairness & Drift Governance"
      description="Deterministic bias/fairness diagnostics (demographic parity, disparate-impact 80% rule, equal opportunity) and PSI drift — extending the model governance platform."
    >
      <div className="space-y-6">
        <StateWrap loading={history.isLoading} error={(history.error as Error)?.message ?? null}>
          <div className="flex items-center gap-3">
            <MetricCard label="Fairness runs" value={String(runs.length)} />
            <button
              onClick={() => evaluate.mutate({ model_key: "pd_model", records: DEMO_RECORDS, protected_attribute: "group" })}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              {evaluate.isPending ? "Evaluating…" : "Evaluate demo cohort"}
            </button>
          </div>

          {res && (
            <SectionCard title="Fairness result" description={res.summary}>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="Disparate impact" value={String(res.metrics?.disparate_impact_ratio ?? "—")} tone={res.passed ? "text-emerald-500" : "text-red-500"} />
                <MetricCard label="Parity diff" value={String(res.metrics?.demographic_parity_diff ?? "—")} />
                <MetricCard label="Verdict" value={res.passed ? "Pass" : "Fail"} tone={res.passed ? "text-emerald-500" : "text-red-500"} />
                <MetricCard label="Groups" value={String((res.groups ?? []).length)} />
              </div>
              <div className="mt-4 space-y-1 text-sm">
                {(res.groups ?? []).map((g: any) => (
                  <div key={g.group} className="flex justify-between border-b border-border/50 py-1">
                    <span className="text-foreground">Group {g.group} <span className="text-xs text-muted-foreground">n={g.n}</span></span>
                    <span className="font-mono text-muted-foreground">approval {Math.round(g.approval_rate * 100)}%</span>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          <SectionCard title="History">
            <div className="space-y-2 text-sm">
              {runs.length === 0 && <p className="text-muted-foreground">No fairness/drift runs yet.</p>}
              {runs.map((r: any) => (
                <div key={r.id} className="flex justify-between rounded-md border border-border/60 p-2">
                  <span className="text-foreground">{r.model_key} <span className="text-xs text-muted-foreground">{titleCase(r.kind)}</span></span>
                  <span className={`text-xs ${r.passed ? "text-emerald-500" : "text-red-500"}`}>{r.passed ? "Pass" : "Fail"}</span>
                </div>
              ))}
            </div>
          </SectionCard>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
