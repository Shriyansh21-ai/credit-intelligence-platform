import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useTwins, useTwinCreate, useTwinSimulate } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-twin")({ component: TwinPage });

function TwinPage() {
  const twins = useTwins();
  const create = useTwinCreate();
  const simulate = useTwinSimulate();
  const [key, setKey] = useState("");
  const [type, setType] = useState("company");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Enterprise Financial Digital Twin" description="Driver-based models of a company, industry, portfolio, economy, bank, treasury, market, supply chain or counterparty. Simulate the twin's state forward under scenario shocks to project future outcomes.">
      <div className="space-y-4">
        <SectionCard title="Create twin">
          <div className="flex flex-wrap gap-2">
            <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} />
            <select className="rounded border bg-background px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
              {["company", "portfolio", "economy", "bank", "treasury", "market", "supply_chain", "counterparty"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!key || create.isPending} onClick={() => create.mutate({ key, name: key, twin_type: type }, { onSuccess: () => setKey("") })}>Create</button>
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Twins">
            <StateWrap loading={twins.isLoading} empty={!(twins.data?.twins?.length)}>
              <ul className="space-y-1 text-sm">{twins.data?.twins?.map((t: any) => (
                <li key={t.twin_id} className="flex items-center justify-between border-b border-border/50 py-1">
                  <span>{t.name} <span className="text-xs text-muted-foreground">({t.twin_type})</span></span>
                  <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => simulate.mutate({ id: t.twin_id, body: { horizon: 8 } }, { onSuccess: (r) => setOut(r) })}>Simulate</button>
                </li>))}</ul>
            </StateWrap>
          </SectionCard>
          <SectionCard title="Simulation"><StateWrap loading={simulate.isPending} empty={!out}><pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify({ terminal_state: out?.terminal_state, deltas: out?.deltas }, null, 2)}</pre></StateWrap></SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
