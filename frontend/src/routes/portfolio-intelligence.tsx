import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import {
  Bar,
  MetricCard,
  RiskLayout,
  SectionCard,
  StateWrap,
  money,
  pct,
  titleCase,
  usePortfolio,
  type DistributionRow,
} from "@/features/risk-intelligence";

export const Route = createFileRoute("/portfolio-intelligence")({
  component: PortfolioPage,
});

function DistributionList({ rows }: { rows: DistributionRow[] }) {
  const max = Math.max(1e-9, ...rows.map((r) => r.exposure_share));
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <Bar
          key={r.key}
          label={`${r.key} (${r.client_count})`}
          display={pct(r.exposure_share, 1)}
          fraction={r.exposure_share / max}
        />
      ))}
      {rows.length === 0 && <p className="text-xs text-muted-foreground">No exposures.</p>}
    </div>
  );
}

function PortfolioPage() {
  const [industry, setIndustry] = useState<string | undefined>();
  const q = usePortfolio(industry ? { industry } : undefined);
  const p = q.data;

  return (
    <RiskLayout
      title="Portfolio Intelligence"
      description="Portfolio-level risk: aggregate exposure, expected and unexpected loss, concentration and the distribution of risk across industries, ratings and regions."
    >
      <StateWrap
        loading={q.isLoading}
        error={(q.error as Error)?.message || null}
        empty={!!p && p.summary.client_count === 0}
        emptyMessage="No portfolio exposures yet."
      >
        {p && p.summary.client_count > 0 && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Clients" value={p.summary.client_count} />
              <MetricCard label="Total exposure" value={money(p.summary.total_exposure)} />
              <MetricCard label="Expected loss" value={money(p.summary.expected_loss)}
                sub={`${pct(p.summary.expected_loss_rate, 2)} of exposure`} />
              <MetricCard label="Unexpected loss" value={money(p.summary.unexpected_loss)} />
              <MetricCard label="Portfolio PD"
                value={pct(p.summary.portfolio_default_probability, 2)} />
              <MetricCard label="Weighted score" value={p.summary.weighted_average_score}
                sub={p.summary.portfolio_health.status} />
              <MetricCard label="Industry HHI" value={p.concentration.industry_hhi.toFixed(3)}
                sub={titleCase(p.concentration.assessment)} />
              <MetricCard label="Top industry"
                value={pct(p.concentration.top_industry_share, 0)} sub="of exposure" />
            </div>

            {industry && (
              <button onClick={() => setIndustry(undefined)}
                className="rounded-md border border-input bg-background px-3 py-1.5 text-xs text-foreground hover:bg-accent/10">
                Clear filter: {industry} ✕
              </button>
            )}

            <div className="grid gap-6 lg:grid-cols-3">
              <SectionCard title="Exposure by industry">
                <DistributionList rows={p.distributions.by_industry} />
              </SectionCard>
              <SectionCard title="Exposure by rating">
                <DistributionList rows={p.distributions.by_rating} />
              </SectionCard>
              <SectionCard title="Exposure by region">
                <DistributionList rows={p.distributions.by_region} />
              </SectionCard>
            </div>

            <SectionCard title="Top risk clients"
              description="Largest contributors to portfolio expected loss.">
              <div className="overflow-x-auto"><table className="w-full">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="text-left font-medium">Client</th>
                    <th className="text-left font-medium">Industry</th>
                    <th className="text-right font-medium">Rating</th>
                    <th className="text-right font-medium">PD</th>
                    <th className="text-right font-medium">Exposure</th>
                    <th className="text-right font-medium">Expected loss</th>
                  </tr>
                </thead>
                <tbody>
                  {p.top_risk_clients.map((c) => (
                    <tr key={c.client_id} className="border-t border-border">
                      <td className="py-2 text-sm text-foreground">{c.company_name}</td>
                      <td className="py-2 text-sm text-muted-foreground">{c.industry}</td>
                      <td className="py-2 text-right font-mono text-sm text-muted-foreground">{c.rating}</td>
                      <td className="py-2 text-right font-mono text-sm text-muted-foreground">{pct(c.probability_of_default, 2)}</td>
                      <td className="py-2 text-right font-mono text-sm text-muted-foreground">{money(c.exposure)}</td>
                      <td className="py-2 text-right font-mono text-sm text-red-500">{money(c.expected_loss)}</td>
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
