import { useMemo } from "react";

import { titleCase } from "../format";
import { useFinancialAnalysis } from "../hooks/useFinancialAnalysis";
import type { Ratio } from "../types";
import { AnalysisSummary } from "./AnalysisSummary";
import { FinancialOverview } from "./FinancialOverview";
import { InsightCard } from "./InsightCard";
import { RatioCard } from "./RatioCard";
import { RecommendationCard } from "./RecommendationCard";
import { RiskFlagCard } from "./RiskFlagCard";
import { TrendChart } from "./TrendChart";

const CATEGORY_ORDER = ["liquidity", "profitability", "leverage", "efficiency", "cash_flow"];

/**
 * Financial Analysis dashboard. Loads the analysis for a specific assessment
 * (or the user's latest) and renders the full financial-intelligence report.
 */
export function FinancialAnalysis({ assessmentId }: { assessmentId?: number }) {
  const { analysis, trends, loading, error } = useFinancialAnalysis(assessmentId);

  const ratiosByCategory = useMemo(() => {
    const grouped: Record<string, Ratio[]> = {};
    for (const ratio of analysis?.ratios ?? []) {
      (grouped[ratio.category] ??= []).push(ratio);
    }
    return grouped;
  }, [analysis]);

  if (loading) {
    return <CenteredNote>Loading financial analysis…</CenteredNote>;
  }

  if (error || !analysis) {
    return (
      <CenteredNote>
        <p className="text-sm font-medium text-foreground">No analysis available</p>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          {error ?? "Run an enterprise assessment to generate a financial analysis."}
        </p>
        <a
          href="/enterprise"
          className="mt-4 inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Run an assessment
        </a>
      </CenteredNote>
    );
  }

  const categories = [
    ...CATEGORY_ORDER.filter((c) => ratiosByCategory[c]),
    ...Object.keys(ratiosByCategory).filter((c) => !CATEGORY_ORDER.includes(c)),
  ];

  return (
    <div className="space-y-8">
      <AnalysisSummary analysis={analysis} />

      <Section title="Financial Health Overview">
        <FinancialOverview health={analysis.health_scores} />
      </Section>

      {analysis.risk_flags.length > 0 && (
        <Section title="Risk Flags" caption={`${analysis.risk_flags.length} detected`}>
          <div className="grid gap-3 md:grid-cols-2">
            {analysis.risk_flags.map((flag) => (
              <RiskFlagCard key={flag.code} flag={flag} />
            ))}
          </div>
        </Section>
      )}

      {analysis.insights.length > 0 && (
        <Section title="Key Insights">
          <div className="grid gap-3 md:grid-cols-2">
            {analysis.insights.map((insight) => (
              <InsightCard key={insight.key} insight={insight} />
            ))}
          </div>
        </Section>
      )}

      <Section title="Financial Ratios" caption="20 commercial-lending ratios">
        <div className="space-y-6">
          {categories.map((category) => (
            <div key={category}>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {titleCase(category)}
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {ratiosByCategory[category].map((ratio) => (
                  <RatioCard key={ratio.key} ratio={ratio} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {analysis.recommendations.length > 0 && (
        <Section title="Recommendations">
          <div className="grid gap-3 md:grid-cols-2">
            {analysis.recommendations.map((rec) => (
              <RecommendationCard key={rec.key} recommendation={rec} />
            ))}
          </div>
        </Section>
      )}

      {trends && (
        <Section title="Trends">
          <TrendChart trends={trends} />
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  caption,
  children,
}: {
  title: string;
  caption?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight text-foreground">{title}</h2>
        {caption && <span className="text-xs text-muted-foreground">{caption}</span>}
      </div>
      {children}
    </section>
  );
}

function CenteredNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      {children}
    </div>
  );
}
