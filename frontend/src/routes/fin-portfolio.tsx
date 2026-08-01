import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useCreatePortfolio, usePortfolios, useSyncPortfolio, usePortfolioSummary, usePortfolioConcentration, usePortfolioInsights } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-portfolio")({ component: PortfolioPage });

function PortfolioPage() {
  const portfolios = usePortfolios();
  const create = useCreatePortfolio();
  const sync = useSyncPortfolio();
  const summary = usePortfolioSummary();
  const concentration = usePortfolioConcentration();
  const insights = usePortfolioInsights();
  const [key, setKey] = useState("");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Enterprise Portfolio Intelligence" description="Build commercial/SME/corporate loan portfolios, then run concentration (HHI/Gini), expected & unexpected loss, RAROC, Monte-Carlo loss VaR, rating migration and early-warning analytics.">
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Create portfolio">
            <div className="flex gap-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!key || create.isPending}
                onClick={() => create.mutate({ key, name: key }, { onSuccess: () => setKey("") })}>Create</button>
            </div>
          </SectionCard>
          <SectionCard title="Result">
            {out ? <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1200)}</pre> : <p className="text-sm text-muted-foreground">Run an analysis on a portfolio.</p>}
          </SectionCard>
        </div>
        <SectionCard title="Portfolios">
          <StateWrap loading={portfolios.isLoading} empty={!(portfolios.data as any)?.length}>
            <ul className="space-y-2 text-sm">
              {(portfolios.data as any)?.map((p: any) => (
                <li key={p.id} className="rounded border border-border/50 p-2">
                  <div className="flex justify-between"><span className="font-medium">{p.name}</span><span className="text-xs text-muted-foreground">{p.portfolio_type}</span></div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => sync.mutate(p.id, { onSuccess: (r) => setOut(r) })}>Sync live</button>
                    <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => summary.mutate(p.id, { onSuccess: (r) => setOut(r) })}>Summary</button>
                    <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => concentration.mutate(p.id, { onSuccess: (r) => setOut(r) })}>Concentration</button>
                    <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => insights.mutate(p.id, { onSuccess: (r) => setOut(r) })}>AI insights</button>
                  </div>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
