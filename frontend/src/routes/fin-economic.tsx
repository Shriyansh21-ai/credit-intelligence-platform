import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useEconIndicators, useEconScenarios, useEconSeed, useEconGenerate, useEconPropagate } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-economic")({ component: EconomicPage });

function EconomicPage() {
  const indicators = useEconIndicators();
  const scenarios = useEconScenarios();
  const seed = useEconSeed();
  const generate = useEconGenerate();
  const propagate = useEconPropagate();
  const [type, setType] = useState("adverse");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Economic Scenario Engine" description="Macroeconomic indicators (GDP, inflation, rates, FX, unemployment, country risk) and optimistic / baseline / adverse / severely-adverse / custom scenarios that propagate through the live exposure set into stressed PD and expected loss.">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => seed.mutate()}>Seed indicators</button>
          <select className="rounded border bg-background px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
            {["optimistic", "baseline", "adverse", "severely_adverse"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => generate.mutate({ name: `${type} scenario`, scenario_type: type }, { onSuccess: (r) => setOut(r) })}>Generate</button>
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => propagate.mutate({ scenario_type: type }, { onSuccess: (r) => setOut(r) })}>Propagate</button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Indicators">
            <StateWrap loading={indicators.isLoading} empty={!(indicators.data?.indicators?.length)}>
              <ul className="space-y-1 text-sm">{indicators.data?.indicators?.map((i: any) => <li key={i.id} className="flex justify-between border-b border-border/50 py-1"><span>{i.name}</span><span className="text-xs text-muted-foreground">{i.value}</span></li>)}</ul>
            </StateWrap>
          </SectionCard>
          <SectionCard title="Result">{out ? <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1200)}</pre> : <p className="text-sm text-muted-foreground">Generate or propagate a scenario.</p>}</SectionCard>
        </div>
        <SectionCard title="Scenarios">
          <StateWrap loading={scenarios.isLoading} empty={!(scenarios.data?.scenarios?.length)}>
            <ul className="space-y-1 text-sm">{scenarios.data?.scenarios?.map((s: any) => <li key={s.scenario_id} className="flex justify-between border-b border-border/50 py-1"><span>{s.name}</span><span className="text-xs text-muted-foreground">{s.scenario_type}</span></li>)}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
