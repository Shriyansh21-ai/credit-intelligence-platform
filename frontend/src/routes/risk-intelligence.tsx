import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  RiskLayout,
  SectionCard,
  SeverityBadge,
  StateWrap,
  gradeTone,
  pct,
  scoreTone,
  useAssessmentAlerts,
  useAssessmentId,
  useExplanation,
  usePrediction,
} from "@/features/risk-intelligence";

interface Search {
  assessment_id?: number;
}

function parseSearch(search: Record<string, unknown>): Search {
  const raw = search.assessment_id;
  const id = typeof raw === "string" ? Number(raw) : typeof raw === "number" ? raw : undefined;
  return id !== undefined && Number.isFinite(id) ? { assessment_id: id } : {};
}

export const Route = createFileRoute("/risk-intelligence")({
  validateSearch: parseSearch,
  component: RiskIntelligencePage,
});

function RiskIntelligencePage() {
  const { assessment_id } = Route.useSearch();
  const { assessmentId, loading: idLoading, error: idError } = useAssessmentId(assessment_id);

  const prediction = usePrediction(assessmentId);
  const explanation = useExplanation(assessmentId);
  const alerts = useAssessmentAlerts(assessmentId);

  const loading = idLoading || prediction.isLoading;
  const error = idError || (prediction.error as Error)?.message || null;
  const p = prediction.data;

  return (
    <RiskLayout
      title="Risk Intelligence"
      description="An AI-assisted, fully explainable view of a single borrower's risk — model prediction, key drivers and live early-warning signals. AI supports the analyst; it does not replace credit judgement."
    >
      <StateWrap loading={loading} error={error} empty={!assessmentId && !loading}>
        {p && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Risk Score" value={p.risk_score} tone={scoreTone(p.risk_score)}
                sub={`Grade ${p.risk_grade}`} />
              <MetricCard label="Probability of Default" value={pct(p.probability_of_default, 2)}
                tone={gradeTone(p.risk_grade)} />
              <MetricCard label="Decision" value={p.approval ? "Approve" : "Refer / Decline"}
                tone={p.approval ? "text-emerald-500" : "text-red-500"} />
              <MetricCard label="Model" value={p.model_metadata.algorithm}
                sub={p.model_metadata.inference_mode.replace(/_/g, " ")} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Top risk drivers"
                description="Signals increasing this borrower's risk.">
                <ul className="space-y-3">
                  {(explanation.data?.top_positive_contributors ?? []).slice(0, 5).map((c) => (
                    <li key={c.feature} className="text-sm">
                      <div className="flex justify-between gap-2">
                        <span className="text-foreground">{c.label}</span>
                        <span className="font-mono text-red-500">+{Math.abs(c.impact_pp).toFixed(1)}%</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{c.narrative}</p>
                    </li>
                  ))}
                  {(explanation.data?.top_positive_contributors ?? []).length === 0 && (
                    <li className="text-xs text-muted-foreground">No material risk drivers.</li>
                  )}
                </ul>
              </SectionCard>

              <SectionCard title="Top mitigants"
                description="Signals reducing this borrower's risk.">
                <ul className="space-y-3">
                  {(explanation.data?.top_negative_contributors ?? []).slice(0, 5).map((c) => (
                    <li key={c.feature} className="text-sm">
                      <div className="flex justify-between gap-2">
                        <span className="text-foreground">{c.label}</span>
                        <span className="font-mono text-emerald-500">−{Math.abs(c.impact_pp).toFixed(1)}%</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{c.narrative}</p>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            </div>

            <SectionCard title="Early-warning alerts"
              description="Deterioration signals detected on this exposure.">
              {(alerts.data?.alerts ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">No active alerts.</p>
              ) : (
                <ul className="space-y-2">
                  {(alerts.data?.alerts ?? []).map((a, i) => (
                    <li key={i} className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
                      <div>
                        <div className="text-sm font-medium text-foreground">{a.title}</div>
                        <div className="text-xs text-muted-foreground">{a.business_impact}</div>
                      </div>
                      <SeverityBadge severity={a.severity} />
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </RiskLayout>
  );
}
