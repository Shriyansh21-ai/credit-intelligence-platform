import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  useCollateralTypes,
  useCreateCollateral,
  useEntityCollateral,
} from "@/features/integrations";
import type { CollateralItem, CoverageSummary } from "@/features/integrations";

export const Route = createFileRoute("/collateral")({ component: CollateralPage });

function CollateralPage() {
  const [entityRef, setEntityRef] = useState("ENT-001");
  const types = useCollateralTypes();
  const list = useEntityCollateral(entityRef);
  const create = useCreateCollateral();

  const [form, setForm] = useState({
    collateral_type: "real_estate",
    description: "",
    market_value: 10000000,
    loan_amount: 6000000,
  });

  const data = list.data as { summary?: CoverageSummary; items?: CollateralItem[] } | undefined;
  const summary = data?.summary;
  const items = data?.items ?? [];

  return (
    <OpsLayout
      title="Collateral Management"
      description="Track collateral with valuation, haircut, realizable value, LTV and coverage. Supports real estate, machinery, vehicles, inventory, receivables, fixed deposits, guarantees and insurance."
    >
      <div className="space-y-6">
        <SectionCard title="Entity">
          <div className="flex items-end gap-3">
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Entity reference</span>
              <input value={entityRef} onChange={(e) => setEntityRef(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 font-mono" />
            </label>
          </div>
        </SectionCard>

        {summary && (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Items" value={String(summary.item_count)} />
            <MetricCard label="Realizable Value" value={`₹${summary.total_realizable_value.toLocaleString()}`} />
            <MetricCard label="Total Exposure" value={`₹${summary.total_exposure.toLocaleString()}`} />
            <MetricCard label="Coverage"
              value={summary.coverage_ratio != null ? `${(summary.coverage_ratio * 100).toFixed(0)}%` : "—"}
              tone={summary.secured ? "text-emerald-500" : "text-amber-500"} />
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          <SectionCard title="Add collateral">
            <div className="space-y-3 text-sm">
              <label className="block">
                <span className="mb-1 block text-muted-foreground">Type</span>
                <select value={form.collateral_type} onChange={(e) => setForm({ ...form, collateral_type: e.target.value })}
                  className="w-full rounded-md border border-border bg-background px-3 py-2">
                  {(types.data?.types ?? []).map((t) => (
                    <option key={t.type} value={t.type}>{t.display} · {(t.default_haircut * 100).toFixed(0)}% haircut</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-muted-foreground">Description</span>
                <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full rounded-md border border-border bg-background px-3 py-2" />
              </label>
              <label className="block">
                <span className="mb-1 block text-muted-foreground">Market value</span>
                <input type="number" value={form.market_value} onChange={(e) => setForm({ ...form, market_value: Number(e.target.value) })}
                  className="w-full rounded-md border border-border bg-background px-3 py-2" />
              </label>
              <label className="block">
                <span className="mb-1 block text-muted-foreground">Loan amount secured</span>
                <input type="number" value={form.loan_amount} onChange={(e) => setForm({ ...form, loan_amount: Number(e.target.value) })}
                  className="w-full rounded-md border border-border bg-background px-3 py-2" />
              </label>
              <button
                onClick={() => create.mutate({ ...form, entity_ref: entityRef, description: form.description || "Collateral" })}
                disabled={create.isPending}
                className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
                {create.isPending ? "Adding…" : "Add collateral"}
              </button>
              {create.error && <p className="text-sm text-red-500">{(create.error as Error).message}</p>}
            </div>
          </SectionCard>

          <div className="lg:col-span-2">
            <SectionCard title="Collateral register">
              <StateWrap loading={list.isLoading} error={(list.error as Error)?.message ?? null}>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-4">Type</th>
                        <th className="py-2 pr-4">Market ₹</th>
                        <th className="py-2 pr-4">Haircut</th>
                        <th className="py-2 pr-4">Realizable ₹</th>
                        <th className="py-2 pr-4">LTV</th>
                        <th className="py-2 pr-4">Coverage</th>
                        <th className="py-2 pr-4">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((i) => (
                        <tr key={i.id} className="border-b border-border/50">
                          <td className="py-2 pr-4 text-foreground">{i.display}</td>
                          <td className="py-2 pr-4">{i.market_value.toLocaleString()}</td>
                          <td className="py-2 pr-4">{(i.haircut_pct * 100).toFixed(0)}%</td>
                          <td className="py-2 pr-4">{i.realizable_value.toLocaleString()}</td>
                          <td className="py-2 pr-4">{i.ltv != null ? `${(i.ltv * 100).toFixed(0)}%` : "—"}</td>
                          <td className="py-2 pr-4">{i.coverage_ratio != null ? `${(i.coverage_ratio * 100).toFixed(0)}%` : "—"}</td>
                          <td className="py-2 pr-4">{i.status}</td>
                        </tr>
                      ))}
                      {items.length === 0 && (
                        <tr><td colSpan={7} className="py-4 text-center text-muted-foreground">No collateral for this entity.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </StateWrap>
            </SectionCard>
          </div>
        </div>
      </div>
    </OpsLayout>
  );
}
