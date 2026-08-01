import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  usePlugins, useRunMarketplace, useSeedPlugins,
} from "@/features/banking-os";

export const Route = createFileRoute("/recommendation-marketplace")({ component: MarketplacePage });

function MarketplacePage() {
  const plugins = usePlugins();
  const seed = useSeedPlugins();
  const run = useRunMarketplace();
  const [pd, setPd] = useState("0.3");

  const list = (plugins.data as any)?.plugins ?? [];
  const result = run.data as any;

  const prioTone = (p: string) => (p === "high" ? "text-red-500" : p === "medium" ? "text-amber-500" : "text-muted-foreground");

  return (
    <OpsLayout
      title="AI Recommendation Marketplace"
      description="Plugin architecture for credit-action recommendations — restructure, collateral, exposure, pricing, covenants, guarantees and more. Install, curate and run against a subject."
    >
      <div className="space-y-6">
        <StateWrap loading={plugins.isLoading} error={(plugins.error as Error)?.message ?? null}>
          <div className="flex flex-wrap items-center gap-3">
            <MetricCard label="Plugins" value={String(list.length)} />
            <MetricCard label="Installed" value={String(list.filter((p: any) => p.installed).length)} />
            <button onClick={() => seed.mutate()} className="rounded-md border border-border px-4 py-2 text-sm">
              {seed.isPending ? "Installing…" : "Install built-in plugins"}
            </button>
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground">PD</label>
              <input value={pd} onChange={(e) => setPd(e.target.value)} className="w-20 rounded-md border border-border bg-background px-2 py-1 text-sm" />
              <button
                onClick={() => run.mutate({ subject_ref: "Demo", context: { pd: Number(pd), debt_to_equity: 2.5, collateral_coverage: 0.6, exposure: 30000000 } })}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                {run.isPending ? "Running…" : "Run marketplace"}
              </button>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Available plugins">
              <div className="space-y-2 text-sm">
                {list.length === 0 && <p className="text-muted-foreground">No plugins — install the built-in set.</p>}
                {list.map((p: any) => (
                  <div key={p.id} className="flex items-center justify-between rounded-md border border-border/60 p-2">
                    <div>
                      <div className="font-medium text-foreground">{p.name}</div>
                      <div className="text-xs text-muted-foreground">{titleCase(p.category ?? "")}</div>
                    </div>
                    <span className={`text-[10px] uppercase ${p.installed ? "text-emerald-500" : "text-muted-foreground"}`}>
                      {p.installed ? "installed" : "available"}
                    </span>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Recommendations" description={result ? `${result.count} generated` : "Run the marketplace to generate."}>
              <div className="space-y-2 text-sm">
                {(result?.recommendations ?? []).map((r: any, i: number) => (
                  <div key={i} className="rounded-md border border-border/60 p-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-foreground">{r.title}</span>
                      <span className={`text-[10px] uppercase ${prioTone(r.priority)}`}>{r.priority}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{r.rationale}</p>
                    <div className="text-[10px] font-mono text-muted-foreground">confidence {r.confidence}</div>
                  </div>
                ))}
                {!result && <p className="text-muted-foreground">No recommendations yet.</p>}
              </div>
            </SectionCard>
          </div>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
