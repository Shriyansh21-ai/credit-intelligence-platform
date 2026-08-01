import { createFileRoute } from "@tanstack/react-router";

import {
  Bar,
  RiskLayout,
  SectionCard,
  StateWrap,
  pct,
  useAssessmentId,
  useExplanation,
} from "@/features/risk-intelligence";

interface Search {
  assessment_id?: number;
}

export const Route = createFileRoute("/explainability")({
  validateSearch: (search: Record<string, unknown>): Search => {
    const raw = search.assessment_id;
    const id = typeof raw === "string" ? Number(raw) : typeof raw === "number" ? raw : undefined;
    return id !== undefined && Number.isFinite(id) ? { assessment_id: id } : {};
  },
  component: ExplainabilityPage,
});

function ExplainabilityPage() {
  const { assessment_id } = Route.useSearch();
  const { assessmentId, loading: idLoading, error: idError } = useAssessmentId(assessment_id);
  const q = useExplanation(assessmentId);
  const e = q.data;

  const maxImportance = Math.max(1e-9, ...(e?.global_importance ?? []).map((g) => g.importance));

  return (
    <RiskLayout
      title="Explainability"
      description="Every prediction is decomposed into transparent, auditable feature contributions — the SHAP/LIME-style attribution that lets an analyst defend the decision."
    >
      <StateWrap
        loading={idLoading || q.isLoading}
        error={idError || (q.error as Error)?.message || null}
        empty={!assessmentId && !idLoading}
      >
        {e && (
          <div className="space-y-6">
            <SectionCard title="Summary" description={`Method: ${e.method}`}>
              <p className="text-sm text-foreground">{e.summary}</p>
              <div className="mt-3 flex gap-6 text-xs text-muted-foreground">
                <span>Base rate: <b className="text-foreground">{pct(e.base_probability, 2)}</b></span>
                <span>This borrower: <b className="text-foreground">{pct(e.probability_of_default, 2)}</b></span>
                <span>Grade: <b className="text-foreground">{e.risk_grade}</b></span>
              </div>
            </SectionCard>

            <SectionCard title="Risk waterfall"
              description="How each driver moves the probability of default from the base rate to the final estimate.">
              <ul className="space-y-2">
                {e.waterfall.map((step, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-foreground">{step.label}</span>
                    <div className="flex items-center gap-4">
                      <span className={`font-mono text-xs ${step.impact_pp > 0 ? "text-red-500" : step.impact_pp < 0 ? "text-emerald-500" : "text-muted-foreground"}`}>
                        {step.impact_pp > 0 ? "+" : ""}{step.impact_pp.toFixed(2)}%
                      </span>
                      <span className="w-16 text-right font-mono text-muted-foreground">
                        {pct(step.cumulative_pd, 2)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </SectionCard>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Top positive contributors" description="Increase risk">
                <div className="space-y-3">
                  {e.top_positive_contributors.map((c) => (
                    <Bar key={c.feature} label={c.label} display={`+${Math.abs(c.impact_pp).toFixed(1)}%`}
                      fraction={Math.min(1, Math.abs(c.impact_pp) / 20)} tone="bg-red-500" />
                  ))}
                </div>
              </SectionCard>
              <SectionCard title="Top negative contributors" description="Reduce risk">
                <div className="space-y-3">
                  {e.top_negative_contributors.map((c) => (
                    <Bar key={c.feature} label={c.label} display={`−${Math.abs(c.impact_pp).toFixed(1)}%`}
                      fraction={Math.min(1, Math.abs(c.impact_pp) / 20)} tone="bg-emerald-500" />
                  ))}
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Global feature importance"
              description="Model-level influence of each driver, independent of this borrower.">
              <div className="space-y-3">
                {e.global_importance.map((g) => (
                  <Bar key={g.feature} label={g.label} display={pct(g.importance, 1)}
                    fraction={g.importance / maxImportance} />
                ))}
              </div>
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </RiskLayout>
  );
}
