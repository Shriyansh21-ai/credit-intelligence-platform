import { Banknote, CircleGauge, Gavel, Percent, ShieldCheck, TrendingDown } from "lucide-react";
import { MetricCard } from "./MetricCard";
import { HealthMetrics } from "./HealthMetrics";
import { RecommendationPanel } from "./RecommendationPanel";
import { decisionTone, formatCurrency, formatPercent, gradeTone } from "../../format";
import type { EnterpriseAssessmentResult } from "../../types";

const RATIO_LABELS: Record<string, string> = {
  dscr: "DSCR",
  current_ratio: "Current Ratio",
  quick_ratio: "Quick Ratio",
  debt_to_ebitda: "Debt / EBITDA",
  interest_coverage: "Interest Coverage",
  gross_margin: "Gross Margin",
  net_margin: "Net Margin",
  operating_cash_flow_margin: "OCF Margin",
};

const PERCENT_RATIOS = new Set(["gross_margin", "net_margin", "operating_cash_flow_margin"]);

export function AssessmentResult({ result }: { result: EnterpriseAssessmentResult }) {
  const { summary, risk_metrics, recommendation, health_metrics, narrative, key_ratios } = result;

  return (
    <div id="assessment-result" className="space-y-5">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-success" />
        <h2 className="text-base font-semibold tracking-tight text-foreground">Assessment Result</h2>
      </div>

      {/* KPI header */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard
          label="Enterprise Credit Score"
          value={String(summary.enterprise_credit_score)}
          sub="Scale 300–900"
          badge={summary.risk_grade}
          tone={gradeTone(summary.risk_grade)}
          icon={CircleGauge}
        />
        <MetricCard
          label="Risk Grade"
          value={summary.risk_grade}
          sub="Internal rating"
          tone={gradeTone(summary.risk_grade)}
          icon={ShieldCheck}
        />
        <MetricCard
          label="Probability of Default"
          value={formatPercent(summary.probability_of_default)}
          sub={`Expected loss ${formatPercent(risk_metrics.expected_loss)}`}
          icon={TrendingDown}
        />
        <MetricCard
          label="Recommended Loan Amount"
          value={formatCurrency(summary.recommended_loan_amount)}
          sub="Debt-capacity headroom"
          icon={Banknote}
        />
        <MetricCard
          label="Recommended Interest Rate"
          value={`${summary.recommended_interest_rate.toFixed(1)}%`}
          sub="Risk-based indicative"
          icon={Percent}
        />
        <MetricCard
          label="Overall Recommendation"
          value={recommendation.decision}
          sub={recommendation.monitoring}
          badge={recommendation.decision}
          tone={decisionTone(recommendation.decision)}
          icon={Gavel}
        />
      </div>

      {/* Health + recommendation */}
      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <HealthMetrics health={health_metrics} />
        <RecommendationPanel recommendation={recommendation} />
      </div>

      {/* Narrative + ratios */}
      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-5">
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Analyst Summary</h3>
          <p className="mt-2 text-sm leading-7 text-muted-foreground">{narrative}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Key Ratios</h3>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2.5">
            {Object.entries(RATIO_LABELS).map(([key, label]) => {
              const value = key_ratios[key];
              if (value === undefined) return null;
              const display = PERCENT_RATIOS.has(key) ? formatPercent(value, 1) : `${value.toFixed(2)}x`;
              return (
                <div key={key} className="flex items-center justify-between border-b border-border/60 pb-2 text-sm">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="font-semibold text-foreground">{display}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      </div>

      {/* Deep-dive link into the Phase 3 financial analysis dashboard. */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-5 shadow-card">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Full Financial Analysis</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            20 ratios, seven health dimensions, insights, risk flags and recommendations.
          </p>
        </div>
        <a
          href="/analysis"
          className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          View financial analysis
        </a>
      </div>
    </div>
  );
}
