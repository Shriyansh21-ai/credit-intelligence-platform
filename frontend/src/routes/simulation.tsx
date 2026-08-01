import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  OpsLayout, SectionCard, StateWrap, titleCase, useRunSimulation, useScenarios,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/simulation")({ component: SimulationPage });

function SimulationPage() {
  const [company, setCompany] = useState("");
  const [shocks, setShocks] = useState<Record<string, number>>({ revenue_drop: 0.2, interest_increase: 0.15 });
  const scenarios = useScenarios();
  const run = useRunSimulation();
  const r = run.data;

  return (
    <OpsLayout
      title="Scenario Simulation Engine"
      description="Simulate revenue drops, rate hikes, FX/commodity moves, customer default, supplier loss, recession, new loans and M&A — and see the new PD, rating, limit, expected loss and recommendations side-by-side."
    >
      <div className="space-y-6">
        <SectionCard title="Configure scenario">
          <label className="text-sm block max-w-md mb-3">
            <span className="mb-1 block text-muted-foreground">Company reference</span>
            <input value={company} onChange={(e) => setCompany(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2" />
          </label>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {(scenarios.data?.scenarios ?? []).map((sc) => (
              <label key={sc.key} className="flex items-center justify-between rounded-md border border-border/60 px-3 py-1.5 text-sm">
                <span>{sc.label}</span>
                <input type="number" step="0.05" value={shocks[sc.key] ?? ""}
                  onChange={(e) => setShocks((s) => ({ ...s, [sc.key]: parseFloat(e.target.value) || 0 }))}
                  className="w-20 rounded border border-border bg-background px-2 py-1 text-right" />
              </label>
            ))}
          </div>
          <button
            onClick={() => run.mutate({ shocks: Object.fromEntries(
              Object.entries(shocks).filter(([, v]) => v)), company_ref: company || undefined })}
            className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
            {run.isPending ? "Simulating…" : "Run simulation"}
          </button>
        </SectionCard>

        <StateWrap loading={run.isPending} error={(run.error as Error)?.message ?? null}>
          {r && (
            <>
              <SectionCard title="Baseline vs stressed">
                <div className="overflow-x-auto"><table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="pb-2">Metric</th><th className="pb-2">Baseline</th><th className="pb-2">Stressed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(r.comparison as Array<Record<string, any>>).map((row, i) => (
                      <tr key={i} className="border-t border-border/50">
                        <td className="py-1.5">{row.metric}</td>
                        <td className="py-1.5 font-mono">{String(row.baseline)}</td>
                        <td className="py-1.5 font-mono">{String(row.stressed)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              </SectionCard>
              <SectionCard title="Recommendations">
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {(r.recommendations as string[]).map((rec, i) => <li key={i}>{rec}</li>)}
                </ul>
              </SectionCard>
            </>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
