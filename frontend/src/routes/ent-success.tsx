import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useSuccessDashboard, useCustomers, useCreateCustomer, enterprisePlatformApi } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-success")({ component: SuccessPage });

function SuccessPage() {
  const dash = useSuccessDashboard();
  const customers = useCustomers();
  const create = useCreateCustomer();
  const [name, setName] = useState("");
  const [rec, setRec] = useState<any>(null);

  return (
    <OpsLayout title="Customer Success" description="Customer lifecycle: onboarding, implementation tracking, health scoring, product adoption, milestones, support tickets, training, renewals and AI success recommendations with confidence, reasoning, citations and evidence.">
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          {dash.data && ["customers", "total_arr", "avg_health", "at_risk"].map((k) => (
            <div key={k} className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">{k.replace(/_/g, " ")}</div><div className="text-lg font-semibold">{String(dash.data[k] ?? "—")}</div></div>
          ))}
        </div>
        <SectionCard title="Onboard customer">
          <div className="flex gap-2">
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="customer name" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!name}
              onClick={() => create.mutate({ name, arr: 100000 }, { onSuccess: () => setName("") })}>Create</button>
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Customers">
            <StateWrap loading={customers.isLoading} empty={!(customers.data?.customers?.length)}>
              <ul className="space-y-1 text-sm">{customers.data?.customers?.map((c: any) => (
                <li key={c.customer_id} className="flex items-center justify-between border-b border-border/50 py-1">
                  <span>{c.name} <span className="text-xs text-muted-foreground">health {c.health_score}</span></span>
                  <button className="rounded bg-secondary px-2 py-1 text-xs" onClick={() => enterprisePlatformApi.customerRecommendations(c.customer_id).then(setRec)}>Recommendations</button>
                </li>))}</ul>
            </StateWrap>
          </SectionCard>
          <SectionCard title="AI recommendations">{rec ? <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(rec, null, 2).slice(0, 1200)}</pre> : <p className="text-sm text-muted-foreground">Select a customer.</p>}</SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
