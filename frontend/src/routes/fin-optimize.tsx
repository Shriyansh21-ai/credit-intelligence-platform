import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useOptList, useOptLoanPricing, useOptCreditLimit } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-optimize")({ component: OptimizePage });

function OptimizePage() {
  const list = useOptList();
  const pricing = useOptLoanPricing();
  const limit = useOptCreditLimit();
  const [subject, setSubject] = useState("");
  const [pd, setPd] = useState("0.05");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Decision Optimization Engine" description="Explainable optimization for loan pricing, credit limits, collateral, portfolio & capital allocation, liquidity and recovery. Every solution names its objective, binding constraints and trade-off.">
      <div className="space-y-4">
        <SectionCard title="Optimize">
          <div className="flex flex-wrap gap-2">
            <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="company ref (optional)" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <input className="w-28 rounded border bg-background px-3 py-2 text-sm" placeholder="PD" value={pd} onChange={(e) => setPd(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => pricing.mutate({ subject_ref: subject || undefined, pd: Number(pd) }, { onSuccess: (r) => setOut(r) })}>Loan pricing</button>
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => limit.mutate({ subject_ref: subject || undefined, pd: Number(pd) }, { onSuccess: (r) => setOut(r) })}>Credit limit</button>
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Solution & explanation"><StateWrap loading={pricing.isPending || limit.isPending} empty={!out}><pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1400)}</pre></StateWrap></SectionCard>
          <SectionCard title="Recent optimizations">
            <StateWrap loading={list.isLoading} empty={!(list.data?.optimizations?.length)}>
              <ul className="space-y-1 text-sm">{list.data?.optimizations?.map((o: any) => <li key={o.optimization_id} className="flex justify-between border-b border-border/50 py-1"><span>{o.opt_type}</span><span className="text-xs text-muted-foreground">{o.objective}</span></li>)}</ul>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
