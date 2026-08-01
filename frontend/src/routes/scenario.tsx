import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { Plus, Play, X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import {
  MetricCard,
  RiskLayout,
  SectionCard,
  StateWrap,
  money,
  pct,
  riApi,
  scoreTone,
  useAssessmentId,
  useScenarioFactors,
  type ScenarioResult,
  type Snapshot,
} from "@/features/risk-intelligence";

interface Search {
  assessment_id?: number;
}

export const Route = createFileRoute("/scenario")({
  validateSearch: (search: Record<string, unknown>): Search => {
    const raw = search.assessment_id;
    const id = typeof raw === "string" ? Number(raw) : typeof raw === "number" ? raw : undefined;
    return id !== undefined && Number.isFinite(id) ? { assessment_id: id } : {};
  },
  component: ScenarioPage,
});

function ScenarioPage() {
  const { assessment_id } = Route.useSearch();
  const { assessmentId, loading: idLoading, error: idError } = useAssessmentId(assessment_id);
  const factors = useScenarioFactors();

  const [selected, setSelected] = useState("");
  const [value, setValue] = useState<number>(0);
  const [adjustments, setAdjustments] = useState<Array<{ factor: string; value: number }>>([]);

  const mutation = useMutation<ScenarioResult, Error>({
    mutationFn: () =>
      riApi.runScenario({ assessment_id: assessmentId as number, adjustments }),
  });

  function addAdjustment() {
    if (!selected) return;
    setAdjustments((a) => [...a, { factor: selected, value: Number(value) || 0 }]);
  }

  const result = mutation.data;

  return (
    <RiskLayout
      title="Scenario Simulator"
      description="Ask 'what happens if…'. Apply business shocks and instantly recompute the full risk picture — score, PD, expected loss, health and recommendation — with no page refresh."
    >
      <StateWrap loading={idLoading} error={idError} empty={!assessmentId && !idLoading}>
        <div className="space-y-6">
          <SectionCard title="Build a scenario"
            description="Combine one or more adjustments, then run the simulation.">
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                Factor
                <select
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                  className="w-64 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Select a factor…</option>
                  {(factors.data?.factors ?? []).map((f) => (
                    <option key={f.factor} value={f.factor}>
                      {f.label} ({f.value_unit})
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                Value
                <input
                  type="number"
                  value={value}
                  onChange={(e) => setValue(Number(e.target.value))}
                  className="w-32 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </label>
              <button
                onClick={addAdjustment}
                className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-accent/10"
              >
                <Plus className="h-4 w-4" /> Add
              </button>
              <button
                onClick={() => mutation.mutate()}
                disabled={adjustments.length === 0 || mutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                <Play className="h-4 w-4" /> {mutation.isPending ? "Running…" : "Run scenario"}
              </button>
            </div>

            {adjustments.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {adjustments.map((a, i) => (
                  <span key={i} className="inline-flex items-center gap-2 rounded-full border border-border bg-muted px-3 py-1 text-xs text-foreground">
                    {a.factor} = {a.value}
                    <button onClick={() => setAdjustments((prev) => prev.filter((_, idx) => idx !== i))}>
                      <X className="h-3 w-3 text-muted-foreground" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            {mutation.isError && (
              <p className="mt-3 text-sm text-red-500">{mutation.error.message}</p>
            )}
          </SectionCard>

          {result && <ScenarioComparison result={result} />}
        </div>
      </StateWrap>
    </RiskLayout>
  );
}

function Row({ label, base, scen, fmt, invert }: {
  label: string; base: number; scen: number; fmt: (n: number) => string; invert?: boolean;
}) {
  const d = scen - base;
  const good = invert ? d < 0 : d > 0;
  return (
    <tr className="border-t border-border">
      <td className="py-2 text-sm text-foreground">{label}</td>
      <td className="py-2 text-right font-mono text-sm text-muted-foreground">{fmt(base)}</td>
      <td className="py-2 text-right font-mono text-sm text-foreground">{fmt(scen)}</td>
      <td className={cn("py-2 text-right font-mono text-sm", d === 0 ? "text-muted-foreground" : good ? "text-emerald-500" : "text-red-500")}>
        {d > 0 ? "+" : ""}{fmt(d)}
      </td>
    </tr>
  );
}

function ScenarioComparison({ result }: { result: ScenarioResult }) {
  const b: Snapshot = result.baseline;
  const s: Snapshot = result.scenario;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Score (scenario)" value={s.enterprise_credit_score}
          tone={scoreTone(s.enterprise_credit_score)}
          sub={`was ${b.enterprise_credit_score}`} />
        <MetricCard label="PD (scenario)" value={pct(s.probability_of_default, 2)}
          sub={`was ${pct(b.probability_of_default, 2)}`} />
        <MetricCard label="Expected loss" value={pct(s.expected_loss, 2)}
          sub={`was ${pct(b.expected_loss, 2)}`} />
        <MetricCard label="Decision" value={s.decision}
          tone={s.decision === b.decision ? "text-foreground" : "text-amber-500"}
          sub={s.decision === b.decision ? "unchanged" : `was ${b.decision}`} />
      </div>

      <SectionCard title="Baseline vs scenario">
        <div className="overflow-x-auto"><table className="w-full">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
              <th className="text-left font-medium">Metric</th>
              <th className="text-right font-medium">Baseline</th>
              <th className="text-right font-medium">Scenario</th>
              <th className="text-right font-medium">Δ</th>
            </tr>
          </thead>
          <tbody>
            <Row label="Credit score" base={b.enterprise_credit_score} scen={s.enterprise_credit_score} fmt={(n) => n.toFixed(0)} />
            <Row label="Probability of default" base={b.probability_of_default} scen={s.probability_of_default} fmt={(n) => pct(n, 2)} invert />
            <Row label="Loss given default" base={b.loss_given_default} scen={s.loss_given_default} fmt={(n) => pct(n, 1)} invert />
            <Row label="Expected loss" base={b.expected_loss} scen={s.expected_loss} fmt={(n) => pct(n, 2)} invert />
            <Row label="Recommended loan" base={b.recommended_loan_amount} scen={s.recommended_loan_amount} fmt={money} />
            <Row label="Interest rate" base={b.recommended_interest_rate} scen={s.recommended_interest_rate} fmt={(n) => `${n.toFixed(1)}%`} invert />
          </tbody>
        </table></div>
      </SectionCard>
    </div>
  );
}
