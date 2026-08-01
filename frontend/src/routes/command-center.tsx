import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase, useCommandDashboard,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/command-center")({ component: CommandCenterPage });

const PERSONAS = [
  { key: "ceo", label: "CEO" },
  { key: "chief_risk_officer", label: "Chief Risk Officer" },
  { key: "chief_credit_officer", label: "Chief Credit Officer" },
  { key: "board", label: "Board" },
  { key: "regional_head", label: "Regional Head" },
];

function fmt(v: unknown) {
  return typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";
}

function CommandCenterPage() {
  const [persona, setPersona] = useState("ceo");
  const q = useCommandDashboard(persona);
  const d = q.data as Record<string, any> | undefined;
  const k = d?.kpis;

  return (
    <OpsLayout
      title="Executive Command Center"
      description="Role-tailored CXO dashboards — KPIs, portfolio risk, capital usage, approvals pipeline, watchlist, industry & geographic exposure, fraud trends, ML drift and business growth."
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-2">
          {PERSONAS.map((p) => (
            <button key={p.key} onClick={() => setPersona(p.key)}
              className={`rounded-full px-4 py-1.5 text-sm ${persona === p.key
                ? "bg-primary text-primary-foreground" : "border border-border hover:bg-muted"}`}>
              {p.label}
            </button>
          ))}
        </div>

        <StateWrap loading={q.isLoading} error={(q.error as Error)?.message ?? null}>
          {d && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="Companies" value={String(k?.companies ?? 0)} />
                <MetricCard label="Total exposure" value={fmt(k?.total_exposure)} />
                <MetricCard label="Expected loss" value={fmt(k?.expected_loss)} tone="text-orange-500" />
                <MetricCard label="High-risk" value={String(k?.high_risk_count ?? 0)} tone="text-red-500" />
              </div>

              {d.watchlist && (
                <SectionCard title="Watchlist">
                  <ul className="space-y-1 text-sm">
                    {(d.watchlist as Array<Record<string, any>>).map((w, i) => (
                      <li key={i} className="flex justify-between rounded-md border border-border/60 px-3 py-1.5">
                        <span>{w.company_ref} · {titleCase(w.industry ?? "")}</span>
                        <span className="font-mono">{w.rating} · PD {((w.pd ?? 0) * 100).toFixed(1)}%</span>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              )}

              {d.industry_exposure && (
                <SectionCard title="Industry exposure">
                  <div className="space-y-1 text-sm">
                    {(d.industry_exposure as Array<Record<string, any>>).map((it, i) => (
                      <div key={i} className="flex justify-between">
                        <span className="text-muted-foreground">{titleCase(it.industry)}</span>
                        <span className="font-mono">{fmt(it.exposure)} ({(it.share * 100).toFixed(0)}%)</span>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              )}

              <SectionCard title="Alerts overview">
                <pre className="max-h-56 overflow-auto rounded-lg bg-muted/50 p-3 text-[11px]">
                  {JSON.stringify(d.alerts, null, 2)}
                </pre>
              </SectionCard>
            </>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
