import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useQuantList, useQuantVar, useQuantMonteCarlo, useQuantStress } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-quant")({ component: QuantPage });

function QuantPage() {
  const list = useQuantList();
  const varm = useQuantVar();
  const mc = useQuantMonteCarlo();
  const stress = useQuantStress();
  const [vol, setVol] = useState("0.02");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Quantitative Risk Platform" description="Monte-Carlo simulation (correlated factors via Cholesky), Value-at-Risk, Expected Shortfall, stress testing, sensitivity, scenario trees, risk attribution, correlation matrices, EWMA volatility and tail risk. Deterministic and reproducible.">
      <div className="space-y-4">
        <SectionCard title="Run model">
          <div className="flex flex-wrap gap-2">
            <input className="w-28 rounded border bg-background px-3 py-2 text-sm" placeholder="volatility" value={vol} onChange={(e) => setVol(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => varm.mutate({ volatility: Number(vol), portfolio_value: 1000000, confidence: 0.99 }, { onSuccess: (r) => setOut(r) })}>Parametric VaR</button>
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => mc.mutate({ positions: [{ name: "a", mean: 0, vol: Number(vol), exposure: 1 }, { name: "b", mean: 0, vol: 0.15, exposure: 1 }], iterations: 2000, seed: 7 }, { onSuccess: (r) => setOut(r) })}>Monte Carlo</button>
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => stress.mutate({ base_value: 1000000, factors: { rates: -5000000, equity: 200000 } }, { onSuccess: (r) => setOut(r) })}>Stress test</button>
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Result"><StateWrap loading={varm.isPending || mc.isPending || stress.isPending} empty={!out}><pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1400)}</pre></StateWrap></SectionCard>
          <SectionCard title="Recent simulations">
            <StateWrap loading={list.isLoading} empty={!(list.data?.simulations?.length)}>
              <ul className="space-y-1 text-sm">{list.data?.simulations?.map((s: any) => <li key={s.simulation_id} className="flex justify-between border-b border-border/50 py-1"><span>{s.sim_type}</span><span className="text-xs text-muted-foreground">#{s.simulation_id}</span></li>)}</ul>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
