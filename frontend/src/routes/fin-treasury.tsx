import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useCreateFundingSource, useFundingSources, useTreasuryDashboard, useLcr, useNsfr } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-treasury")({ component: TreasuryPage });

function TreasuryPage() {
  const sources = useFundingSources();
  const dash = useTreasuryDashboard();
  const create = useCreateFundingSource();
  const lcr = useLcr();
  const nsfr = useNsfr();
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("1000000");
  const [rate, setRate] = useState("0.05");
  const [hqla, setHqla] = useState("5000000");
  const [rsf, setRsf] = useState("8000000");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Treasury Intelligence Platform" description="Cash position, liquidity buckets, funding-gap analysis, net interest margin, ALM, Basel LCR & NSFR, cash forecasting, funding optimization and treasury KPIs — all grounded in the funding-source registry.">
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-3">
          {(dash.data?.kpis ? Object.entries(dash.data.kpis) : []).map(([k, v]: any) => (
            <div key={k} className="rounded border bg-card p-3">
              <div className="text-xs text-muted-foreground">{k.replace(/_/g, " ")}</div>
              <div className="text-lg font-semibold">{String(v)}</div>
            </div>
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Register funding source">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="rate" value={rate} onChange={(e) => setRate(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!name || create.isPending}
                onClick={() => create.mutate({ name, source_type: "deposit", amount: Number(amount), rate: Number(rate) }, { onSuccess: () => setName("") })}>Add deposit source</button>
            </div>
          </SectionCard>
          <SectionCard title="Liquidity ratios">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="HQLA" value={hqla} onChange={(e) => setHqla(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => lcr.mutate({ hqla: Number(hqla) }, { onSuccess: (r) => setOut(r) })}>Compute LCR</button>
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="Required stable funding" value={rsf} onChange={(e) => setRsf(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => nsfr.mutate({ required_stable_funding: Number(rsf) }, { onSuccess: (r) => setOut(r) })}>Compute NSFR</button>
              {out && <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 900)}</pre>}
            </div>
          </SectionCard>
        </div>
        <SectionCard title="Funding sources">
          <StateWrap loading={sources.isLoading} empty={!(sources.data as any)?.length}>
            <ul className="space-y-1 text-sm">
              {(sources.data as any)?.map((s: any) => (
                <li key={s.id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{s.name} <span className="text-xs text-muted-foreground">({s.source_type})</span></span>
                  <span className="text-xs text-muted-foreground">{s.amount?.toLocaleString()} @ {(s.rate * 100).toFixed(2)}%</span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
