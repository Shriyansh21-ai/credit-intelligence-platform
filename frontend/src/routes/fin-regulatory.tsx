import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useRegDashboard, useRegEcl, useRegRwa } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-regulatory")({ component: RegulatoryPage });

function RegulatoryPage() {
  const dash = useRegDashboard();
  const ecl = useRegEcl();
  const rwa = useRegRwa();
  const [pd, setPd] = useState("0.05");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Basel III / IFRS 9 Platform" description="Explainable regulatory calculations: PD/LGD/EAD, 12-month & lifetime ECL, staging, provisioning, IRB & standardized RWA, capital adequacy, leverage and a consolidated dashboard. Every result carries its formula.">
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-3">
          {(dash.data?.results ? Object.entries(dash.data.results).filter(([, v]) => typeof v !== "object") : []).map(([k, v]: any) => (
            <div key={k} className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">{k.replace(/_/g, " ")}</div><div className="text-lg font-semibold">{String(v)}</div></div>
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Run calculation">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="PD (e.g. 0.05)" value={pd} onChange={(e) => setPd(e.target.value)} />
              <div className="flex gap-2">
                <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => ecl.mutate({ pd: Number(pd), lgd: 0.45, ead: 1000000 }, { onSuccess: (r) => setOut(r) })}>ECL</button>
                <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => rwa.mutate({ pd: Number(pd), lgd: 0.45, ead: 1000000 }, { onSuccess: (r) => setOut(r) })}>RWA (IRB)</button>
              </div>
            </div>
          </SectionCard>
          <SectionCard title="Result">
            <StateWrap loading={ecl.isPending || rwa.isPending} empty={!out}>
              <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1400)}</pre>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
