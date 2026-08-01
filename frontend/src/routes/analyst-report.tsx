import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, AlertOctagon } from "lucide-react";

import {
  RiskLayout,
  SectionCard,
  SeverityBadge,
  StateWrap,
  money,
  titleCase,
  useAssessmentId,
  useReport,
  type RiskItem,
} from "@/features/risk-intelligence";

interface Search {
  assessment_id?: number;
}

export const Route = createFileRoute("/analyst-report")({
  validateSearch: (search: Record<string, unknown>): Search => {
    const raw = search.assessment_id;
    const id = typeof raw === "string" ? Number(raw) : typeof raw === "number" ? raw : undefined;
    return id !== undefined && Number.isFinite(id) ? { assessment_id: id } : {};
  },
  component: AnalystReportPage,
});

function RiskGroup({ title, items }: { title: string; items: RiskItem[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <ul className="space-y-2">
        {items.map((r, i) => (
          <li key={i} className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
            <div>
              <div className="text-sm font-medium text-foreground">{r.title}</div>
              <div className="text-xs text-muted-foreground">{r.impact}</div>
              <div className="mt-1 text-xs text-foreground/80">→ {r.action}</div>
            </div>
            <SeverityBadge severity={r.severity} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function AnalystReportPage() {
  const { assessment_id } = Route.useSearch();
  const { assessmentId, loading: idLoading, error: idError } = useAssessmentId(assessment_id);
  const q = useReport(assessmentId);
  const m = q.data;

  return (
    <RiskLayout
      title="Analyst Report"
      description="A deterministic, bank-grade credit memo composed from the scoring engine, financial analysis, explainability and early-warning layers. Every statement is traceable to a signal."
    >
      <StateWrap
        loading={idLoading || q.isLoading}
        error={idError || (q.error as Error)?.message || null}
        empty={!assessmentId && !idLoading}
      >
        {m && (
          <div className="space-y-6">
            <SectionCard title="Executive summary">
              <p className="text-sm leading-6 text-foreground">{m.executive_summary}</p>
            </SectionCard>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Business overview">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {Object.entries(m.business_overview).map(([k, v]) => (
                    <div key={k} className="flex flex-col">
                      <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{titleCase(k)}</dt>
                      <dd className="text-foreground">{v ?? "—"}</dd>
                    </div>
                  ))}
                </dl>
              </SectionCard>

              <SectionCard title="Recommendation">
                <dl className="space-y-2 text-sm">
                  <Line label="Decision" value={m.recommendation.decision} />
                  <Line label="Loan amount" value={money(m.recommendation.recommended_loan_amount)} />
                  <Line label="Interest rate" value={m.recommendation.recommended_interest_rate} />
                  <Line label="Tenure" value={m.recommendation.recommended_tenure} />
                  <Line label="Collateral" value={m.recommendation.collateral} />
                  <Line label="Monitoring" value={m.recommendation.monitoring_frequency} />
                </dl>
              </SectionCard>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Credit strengths">
                <ul className="space-y-2">
                  {m.credit_strengths.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> {s}
                    </li>
                  ))}
                  {m.credit_strengths.length === 0 && <li className="text-xs text-muted-foreground">None identified.</li>}
                </ul>
              </SectionCard>
              <SectionCard title="Weaknesses">
                <ul className="space-y-2">
                  {m.weaknesses.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                      <AlertOctagon className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" /> {s}
                    </li>
                  ))}
                  {m.weaknesses.length === 0 && <li className="text-xs text-muted-foreground">None identified.</li>}
                </ul>
              </SectionCard>
            </div>

            <SectionCard title="Risk assessment">
              <div className="space-y-5">
                <RiskGroup title="Business risks" items={m.business_risks} />
                <RiskGroup title="Industry risks" items={m.industry_risks} />
                <RiskGroup title="Financial risks" items={m.financial_risks} />
                <RiskGroup title="Management risks" items={m.management_risks} />
                {m.business_risks.length + m.industry_risks.length + m.financial_risks.length + m.management_risks.length === 0 && (
                  <p className="text-sm text-muted-foreground">No material risks flagged.</p>
                )}
              </div>
            </SectionCard>

            <SectionCard title="Analyst notes">
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {m.analyst_notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </SectionCard>

            <div className="rounded-xl border border-primary/30 bg-primary/5 p-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-primary">Final recommendation</div>
              <p className="mt-1 text-sm font-medium text-foreground">{m.final_recommendation}</p>
            </div>
          </div>
        )}
      </StateWrap>
    </RiskLayout>
  );
}

function Line({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium text-foreground">{value}</dd>
    </div>
  );
}
