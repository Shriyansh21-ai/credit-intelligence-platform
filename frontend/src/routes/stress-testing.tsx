import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  RiskLayout,
  SectionCard,
  StateWrap,
  pct,
  scoreTone,
  useAssessmentId,
  useStressTest,
  type StressCase,
} from "@/features/risk-intelligence";

interface Search {
  assessment_id?: number;
}

export const Route = createFileRoute("/stress-testing")({
  validateSearch: (search: Record<string, unknown>): Search => {
    const raw = search.assessment_id;
    const id = typeof raw === "string" ? Number(raw) : typeof raw === "number" ? raw : undefined;
    return id !== undefined && Number.isFinite(id) ? { assessment_id: id } : {};
  },
  component: StressTestingPage,
});

const CASE_META: Array<{ key: "base_case" | "optimistic_case" | "expected_case" | "worst_case"; label: string }> = [
  { key: "base_case", label: "Base Case" },
  { key: "optimistic_case", label: "Optimistic" },
  { key: "expected_case", label: "Expected" },
  { key: "worst_case", label: "Worst Case" },
];

function StressTestingPage() {
  const { assessment_id } = Route.useSearch();
  const { assessmentId, loading: idLoading, error: idError } = useAssessmentId(assessment_id);
  const q = useStressTest(assessmentId);
  const r = q.data;

  return (
    <RiskLayout
      title="Stress Testing"
      description="Banking-style stress testing across recession, inflation, rate-shock, pandemic and other macro scenarios — producing base, optimistic, expected and worst cases for the exposure."
    >
      <StateWrap
        loading={idLoading || q.isLoading}
        error={idError || (q.error as Error)?.message || null}
        empty={!assessmentId && !idLoading}
      >
        {r && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {CASE_META.map(({ key, label }) => {
                const c: StressCase = r[key];
                return (
                  <MetricCard
                    key={key}
                    label={label}
                    value={c.snapshot.enterprise_credit_score}
                    tone={scoreTone(c.snapshot.enterprise_credit_score)}
                    sub={`PD ${pct(c.snapshot.probability_of_default, 2)} · EL ${pct(c.snapshot.expected_loss, 2)}`}
                  />
                );
              })}
            </div>

            <SectionCard title="Case comparison">
              <div className="overflow-x-auto"><table className="w-full">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="text-left font-medium">Case</th>
                    <th className="text-right font-medium">Score</th>
                    <th className="text-right font-medium">Grade</th>
                    <th className="text-right font-medium">PD</th>
                    <th className="text-right font-medium">Expected loss</th>
                    <th className="text-right font-medium">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {CASE_META.map(({ key, label }) => {
                    const s = r[key].snapshot;
                    return (
                      <tr key={key} className="border-t border-border">
                        <td className="py-2 text-sm text-foreground">{label}</td>
                        <td className="py-2 text-right font-mono text-sm text-foreground">{s.enterprise_credit_score}</td>
                        <td className="py-2 text-right font-mono text-sm text-muted-foreground">{s.risk_grade}</td>
                        <td className="py-2 text-right font-mono text-sm text-muted-foreground">{pct(s.probability_of_default, 2)}</td>
                        <td className="py-2 text-right font-mono text-sm text-muted-foreground">{pct(s.expected_loss, 2)}</td>
                        <td className="py-2 text-right text-sm text-muted-foreground">{s.decision}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table></div>
            </SectionCard>

            <SectionCard title="Worst-case impact by scenario"
              description="Which macro shock hurts this borrower most (ranked by expected loss).">
              <div className="overflow-x-auto"><table className="w-full">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="text-left font-medium">Scenario</th>
                    <th className="text-right font-medium">Worst PD</th>
                    <th className="text-right font-medium">Worst EL</th>
                    <th className="text-right font-medium">Score impact</th>
                  </tr>
                </thead>
                <tbody>
                  {r.comparison.by_scenario.map((s) => (
                    <tr key={s.scenario} className="border-t border-border">
                      <td className="py-2 text-sm text-foreground">{s.label}</td>
                      <td className="py-2 text-right font-mono text-sm text-muted-foreground">{pct(s.worst_probability_of_default, 2)}</td>
                      <td className="py-2 text-right font-mono text-sm text-muted-foreground">{pct(s.worst_expected_loss, 2)}</td>
                      <td className="py-2 text-right font-mono text-sm text-red-500">{s.score_impact}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </RiskLayout>
  );
}
