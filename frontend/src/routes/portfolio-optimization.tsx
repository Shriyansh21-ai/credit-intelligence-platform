import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase, usePortfolioAnalysis,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/portfolio-optimization")({ component: PortfolioOptimizationPage });

function fmt(v: unknown) {
  return typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";
}
function pct(v: unknown) {
  return typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—";
}

function PortfolioOptimizationPage() {
  const q = usePortfolioAnalysis();
  const r = q.data as Record<string, any> | undefined;

  return (
    <OpsLayout
      title="Portfolio Optimization AI"
      description="Diversification, sector & geographic exposure, concentration limits, expected return, RAROC, capital allocation and risk-adjusted rebalancing suggestions across the live book."
    >
      <StateWrap loading={q.isLoading} error={(q.error as Error)?.message ?? null}>
        {r && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Positions" value={String(r.position_count)} />
              <MetricCard label="Total exposure" value={fmt(r.total_exposure)} />
              <MetricCard label="Net return" value={fmt(r.net_return)} tone="text-emerald-500" />
              <MetricCard label="Portfolio RAROC" value={pct(r.portfolio_raroc)} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Sector exposure">
                <div className="space-y-1 text-sm">
                  {Object.entries(r.sector_exposure ?? {}).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground">{titleCase(k)}</span>
                      <span className="font-mono">{pct(v)}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
              <SectionCard title="Concentration">
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">HHI</span>
                    <span className="font-mono">{r.concentration?.hhi}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Top-name share</span>
                    <span className="font-mono">{pct(r.concentration?.top_name_share)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Effective names</span>
                    <span className="font-mono">{r.concentration?.effective_names}</span></div>
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Limit breaches">
              {(r.limit_breaches ?? []).length === 0 ? (
                <p className="text-sm text-emerald-500">Within all concentration limits.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {(r.limit_breaches as Array<Record<string, any>>).map((b, i) => (
                    <li key={i} className="flex justify-between rounded-md border border-red-500/30 px-3 py-1.5">
                      <span>{titleCase(b.type)}: {b.entity}</span>
                      <span className="font-mono text-red-500">{pct(b.share)} / {pct(b.limit)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard title="Recommendations">
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {(r.recommendations as string[]).map((rec, i) => <li key={i}>{rec}</li>)}
              </ul>
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
