import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  titleCase,
  useCustomer360,
} from "@/features/integrations";

export const Route = createFileRoute("/customer360")({ component: Customer360Page });

function Customer360Page() {
  const [input, setInput] = useState("27ABCDE1234F1Z5");
  const [entityRef, setEntityRef] = useState<string | null>("27ABCDE1234F1Z5");
  const profile = useCustomer360(entityRef);

  const p = profile.data;
  const completeness = p?.completeness;

  return (
    <OpsLayout
      title="Customer 360"
      description="A unified enterprise profile aggregating assessment, GST, MCA, bureau, ERP, payments, bank analytics, collateral, monitoring, approvals, audit, a relationship network and the full customer timeline."
    >
      <div className="space-y-6">
        <SectionCard title="Lookup">
          <div className="flex items-end gap-3">
            <label className="text-sm flex-1 max-w-md">
              <span className="mb-1 block text-muted-foreground">Entity reference (GSTIN / PAN / CIN)</span>
              <input value={input} onChange={(e) => setInput(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono" />
            </label>
            <button onClick={() => setEntityRef(input)}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
              Load profile
            </button>
          </div>
        </SectionCard>

        <StateWrap loading={profile.isLoading} error={(profile.error as Error)?.message ?? null}>
          {p && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="Data Completeness"
                  value={`${((completeness?.score ?? 0) * 100).toFixed(0)}%`}
                  sub={`${completeness?.sources_present}/${completeness?.sources_total} sources`}
                  tone="text-emerald-500" />
                <MetricCard label="Relationship Nodes" value={String(p.relationship_network?.node_count ?? 0)} />
                <MetricCard label="Timeline Events" value={String(p.timeline?.length ?? 0)} />
                <MetricCard label="Collateral Items" value={String(p.collateral?.items?.length ?? 0)} />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <SectionCard title="Data sources present">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {Object.entries(completeness?.detail ?? {}).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between rounded-md border border-border/60 px-3 py-1.5">
                        <span className="text-muted-foreground">{titleCase(k)}</span>
                        <span className={v ? "text-emerald-500" : "text-muted-foreground/60"}>{v ? "✓" : "—"}</span>
                      </div>
                    ))}
                  </div>
                </SectionCard>

                <SectionCard title="Customer timeline">
                  <ul className="space-y-2 text-sm">
                    {(p.timeline ?? []).slice(0, 12).map((e, i) => (
                      <li key={i} className="flex items-start gap-3 border-b border-border/50 pb-1.5">
                        <span className="font-mono text-xs text-muted-foreground">{(e.at ?? "").slice(0, 10)}</span>
                        <span className="rounded bg-muted px-2 py-0.5 text-xs">{titleCase(e.type)}</span>
                        <span className="text-foreground">{e.detail}</span>
                      </li>
                    ))}
                    {(p.timeline ?? []).length === 0 && (
                      <li className="text-muted-foreground">No events yet.</li>
                    )}
                  </ul>
                </SectionCard>
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {(["gst", "mca", "bureau", "erp", "payments", "bank_analytics"] as const).map((key) => (
                  <SectionCard key={key} title={titleCase(key)}>
                    {p[key] ? (
                      <pre className="max-h-56 overflow-auto rounded-lg bg-muted/50 p-3 text-[11px] text-foreground">
                        {JSON.stringify(p[key], null, 2)}
                      </pre>
                    ) : (
                      <p className="text-sm text-muted-foreground">No data imported.</p>
                    )}
                  </SectionCard>
                ))}
              </div>
            </>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
