import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";

import {
  CountBarChart,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  integrationsApi,
} from "@/features/integrations";

export const Route = createFileRoute("/account-aggregator")({ component: AccountAggregatorPage });

function AccountAggregatorPage() {
  const [entityRef, setEntityRef] = useState("ENT-001");
  const [months, setMonths] = useState(12);
  const [statementId, setStatementId] = useState<number | null>(null);

  const consent = useMutation({ mutationFn: () => integrationsApi.createConsent({ entity_ref: entityRef, months }) });
  const refresh = useMutation({ mutationFn: (id: number) => integrationsApi.refreshConsent(id) });
  const importStmt = useMutation({
    mutationFn: () => integrationsApi.importStatement({ entity_ref: entityRef, account_ref: `AC-${entityRef}`, months }),
    onSuccess: (s) => setStatementId(s.id),
  });
  const analyze = useMutation({
    mutationFn: (id: number) => integrationsApi.analyzeStatement(id),
  });

  const metrics = analyze.data as Record<string, any> | undefined;
  const cashFlow = metrics?.cash_flow as Record<string, any> | undefined;

  return (
    <OpsLayout
      title="Account Aggregator"
      description="Consent-driven bank data import with full statement analytics — cash flow, salary detection, cheque bounces, liquidity trend, working-capital cycle, cash burn and a composite bank-health score."
    >
      <div className="space-y-6">
        <SectionCard title="Consent & statement flow">
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm md:col-span-2">
              <span className="mb-1 block text-muted-foreground">Entity reference</span>
              <input value={entityRef} onChange={(e) => setEntityRef(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono" />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Months</span>
              <input type="number" value={months} onChange={(e) => setMonths(Number(e.target.value))}
                className="w-full rounded-md border border-border bg-background px-3 py-2" />
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button onClick={() => consent.mutate()} disabled={consent.isPending}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50">
              1. Create consent
            </button>
            {consent.data && (
              <button onClick={() => refresh.mutate(consent.data!.id)} disabled={refresh.isPending}
                className="rounded-md border border-border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50">
                2. Activate ({refresh.data?.status ?? consent.data.status})
              </button>
            )}
            <button onClick={() => importStmt.mutate()} disabled={importStmt.isPending}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50">
              3. Import statement
            </button>
            <button onClick={() => statementId && analyze.mutate(statementId)} disabled={!statementId || analyze.isPending}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
              4. Analyze
            </button>
          </div>
          {importStmt.data && (
            <p className="mt-3 text-sm text-muted-foreground">
              Imported statement #{importStmt.data.id} — {importStmt.data.txn_count} transactions from{" "}
              {importStmt.data.bank_name}. Closing balance ₹{(importStmt.data.closing_balance ?? 0).toLocaleString()}.
            </p>
          )}
        </SectionCard>

        {metrics && (
          <StateWrap loading={analyze.isPending} error={(analyze.error as Error)?.message ?? null}>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard label="Bank Health Score" value={String(metrics.bank_health_score)} tone="text-emerald-500" />
              <MetricCard label="Net Cash Flow" value={`₹${(cashFlow?.net_cash_flow ?? 0).toLocaleString()}`} />
              <MetricCard label="Cheque Bounces" value={String(metrics.cheque_bounce?.count ?? 0)}
                tone={metrics.cheque_bounce?.count ? "text-red-500" : undefined} />
              <MetricCard label="Liquidity Trend" value={String(metrics.liquidity_trend ?? "-")} />
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Monthly net cash flow">
                <CountBarChart
                  data={(cashFlow?.monthly ?? []).map((m: any) => ({ label: m.month, value: Math.round(m.net) }))}
                />
              </SectionCard>
              <SectionCard title="Signals">
                <dl className="space-y-2 text-sm">
                  <Row k="Total inflow" v={`₹${(cashFlow?.total_inflow ?? 0).toLocaleString()}`} />
                  <Row k="Total outflow" v={`₹${(cashFlow?.total_outflow ?? 0).toLocaleString()}`} />
                  <Row k="Salary detected" v={metrics.salary_detection?.detected ? `yes (${metrics.salary_detection.payouts})` : "no"} />
                  <Row k="Average balance" v={`₹${(metrics.average_balance ?? 0).toLocaleString()}`} />
                  <Row k="Working capital cycle" v={`${metrics.working_capital_cycle_days} days`} />
                  <Row k="Cash burn / month" v={`₹${(metrics.cash_burn?.avg_monthly_burn ?? 0).toLocaleString()}`} />
                  <Row k="Seasonality index" v={String(metrics.seasonality_index ?? 0)} />
                </dl>
              </SectionCard>
            </div>
          </StateWrap>
        )}
      </div>
    </OpsLayout>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 pb-1">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-mono text-foreground">{v}</dd>
    </div>
  );
}
