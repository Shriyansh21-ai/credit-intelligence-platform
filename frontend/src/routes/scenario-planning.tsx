import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useRunScenarios, useScenarioLibrary,
} from "@/features/banking-os";

export const Route = createFileRoute("/scenario-planning")({ component: ScenarioPlanningPage });

const DEMO_POSITIONS = [
  { ref: "TextileCo", exposure: 10000000, pd: 0.14, lgd: 0.5 },
  { ref: "SteelWorks", exposure: 20000000, pd: 0.06, lgd: 0.45 },
  { ref: "PharmaInc", exposure: 50000000, pd: 0.02, lgd: 0.4 },
];

function ScenarioPlanningPage() {
  const library = useScenarioLibrary();
  const run = useRunScenarios();

  const lib = library.data as any;
  const res = run.data as any;

  return (
    <OpsLayout
      title="Scenario Planning & Digital Twin"
      description="Best / base / worst / stress / black-swan scenarios with seeded Monte Carlo (VaR / expected-shortfall) and one-factor sensitivity over the portfolio."
    >
      <div className="space-y-6">
        <StateWrap loading={library.isLoading} error={(library.error as Error)?.message ?? null}>
          <div className="flex flex-wrap items-center gap-2">
            {(lib?.scenarios ?? []).map((s: string) => (
              <span key={s} className="rounded-full border border-border px-3 py-1 text-xs">{titleCase(s.replace(/_/g, " "))}</span>
            ))}
            <button
              onClick={() => run.mutate({ name: "Demo plan", positions: DEMO_POSITIONS, monte_carlo_draws: 1000, persist: false })}
              className="ml-auto rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              {run.isPending ? "Running…" : "Run scenario plan"}
            </button>
          </div>

          {res && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="Total exposure" value={`₹${(res.total_exposure ?? 0).toLocaleString()}`} />
                <MetricCard label="Baseline EL" value={`₹${(res.baseline_expected_loss ?? 0).toLocaleString()}`} />
                <MetricCard label="99% VaR" value={`₹${(res.monte_carlo?.var_99 ?? 0).toLocaleString()}`} tone="text-red-500" />
                <MetricCard label="Worst case" value={titleCase((res.worst_case?.scenario ?? "").replace(/_/g, " "))} tone="text-red-500" />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <SectionCard title="Scenario expected loss">
                  <div className="space-y-1.5 text-sm">
                    {(res.scenarios ?? []).map((s: any) => (
                      <div key={s.scenario} className="flex justify-between border-b border-border/50 py-1">
                        <span className="text-foreground">{titleCase(s.scenario.replace(/_/g, " "))}</span>
                        <span className="font-mono text-muted-foreground">₹{(s.expected_loss ?? 0).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </SectionCard>

                <SectionCard title="Monte Carlo distribution">
                  <div className="space-y-1.5 text-sm">
                    {[["Mean", res.monte_carlo?.mean], ["Median (p50)", res.monte_carlo?.p50], ["95% VaR", res.monte_carlo?.var_95], ["99% VaR", res.monte_carlo?.var_99], ["Expected shortfall", res.monte_carlo?.es_97_5]].map(([label, v]) => (
                      <div key={String(label)} className="flex justify-between border-b border-border/50 py-1">
                        <span className="text-foreground">{label}</span>
                        <span className="font-mono text-muted-foreground">₹{Number(v ?? 0).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              </div>

              {(res.recommendations ?? []).length > 0 && (
                <SectionCard title="Recommendations">
                  <ul className="list-inside list-disc text-sm text-muted-foreground">
                    {res.recommendations.map((r: string, i: number) => <li key={i}>{r}</li>)}
                  </ul>
                </SectionCard>
              )}
            </>
          )}
          {!res && <p className="text-sm text-muted-foreground">Run a scenario plan to see the loss distribution.</p>}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
