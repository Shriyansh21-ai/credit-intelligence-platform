import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, useRunStress,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/stress-testing-9")({ component: StressTesting9Page });

function StressTesting9Page() {
  const [scenario, setScenario] = useState("severe");
  const [scope, setScope] = useState("portfolio");
  const run = useRunStress();
  const r = run.data as any;

  return (
    <OpsLayout
      title="Stress Testing (Portfolio)"
      description="Banking-grade Base / Moderate / Severe / Custom stress across a company, the portfolio, an industry or a region — with loss projections, capital impact, PD & rating migration and heatmaps."
    >
      <div className="space-y-6">
        <SectionCard title="Run stress test">
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Scenario</span>
              <select value={scenario} onChange={(e) => setScenario(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2">
                {["base", "moderate", "severe"].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Scope</span>
              <select value={scope} onChange={(e) => setScope(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2">
                {["portfolio", "industry", "region"].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <button onClick={() => run.mutate({ scenario, scope })}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
              {run.isPending ? "Running…" : "Run"}
            </button>
          </div>
        </SectionCard>

        <StateWrap loading={run.isPending} error={(run.error as Error)?.message ?? null}>
          {r && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="Positions" value={String(r.position_count)} />
                <MetricCard label="Total exposure" value={fmt(r.total_exposure)} />
                <MetricCard label="Stressed EL" value={fmt(r.expected_loss?.stressed)} tone="text-orange-500" />
                <MetricCard label="Extra capital" value={fmt(r.capital_impact?.additional_required)} tone="text-red-500" />
              </div>
              <SectionCard title="Rating migration">
                <div className="flex gap-4 text-sm">
                  <span>Downgraded: <b className="text-red-500">{r.rating_migration_summary?.downgraded}</b></span>
                  <span>Stable: <b>{r.rating_migration_summary?.stable}</b></span>
                  <span>Upgraded: <b className="text-emerald-500">{r.rating_migration_summary?.upgraded}</b></span>
                </div>
              </SectionCard>
              <SectionCard title="Loss heatmap">
                <div className="overflow-x-auto"><table className="w-full text-sm">
                  <thead><tr className="text-left text-muted-foreground">
                    <th className="pb-2">Bucket</th><th className="pb-2">Exposure</th>
                    <th className="pb-2">Stress EL</th><th className="pb-2">Loss rate</th></tr></thead>
                  <tbody>
                    {(r.heatmap as Array<Record<string, any>>).map((h, i) => (
                      <tr key={i} className="border-t border-border/50">
                        <td className="py-1.5">{h.bucket}</td>
                        <td className="py-1.5 font-mono">{fmt(h.exposure)}</td>
                        <td className="py-1.5 font-mono">{fmt(h.stress_el)}</td>
                        <td className="py-1.5 font-mono">{(h.loss_rate * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              </SectionCard>
            </>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}

function fmt(v: unknown) {
  return typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";
}
