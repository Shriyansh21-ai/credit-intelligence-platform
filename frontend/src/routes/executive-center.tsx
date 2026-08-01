import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, useExecDashboard, titleCase,
} from "@/features/banking-os";

export const Route = createFileRoute("/executive-center")({ component: ExecutiveCenterPage });

const PERSONAS = [
  "ceo", "chief_risk_officer", "chief_credit_officer", "chief_compliance_officer",
  "portfolio", "regulatory", "treasury",
];

function ExecutiveCenterPage() {
  const [persona, setPersona] = useState("ceo");
  const dash = useExecDashboard(persona);
  const d = dash.data as Record<string, any> | undefined;
  const cards: any[] = d?.cards ?? [];
  const charts: Record<string, any> = d?.charts ?? {};

  const tone = (intent: string) =>
    intent === "good" ? "text-emerald-500" : intent === "bad" ? "text-red-500" : "text-foreground";

  return (
    <OpsLayout
      title="Executive Intelligence Center"
      description="Real-time, role-specific executive dashboards — CEO, CRO, CCO, Compliance, Portfolio, Regulatory and Treasury — built by deterministic aggregation across the platform."
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-2">
          {PERSONAS.map((p) => (
            <button
              key={p}
              onClick={() => setPersona(p)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                persona === p ? "bg-primary text-primary-foreground" : "border border-border bg-card"
              }`}
            >
              {titleCase(p.replace(/_/g, " "))}
            </button>
          ))}
        </div>

        <StateWrap loading={dash.isLoading} error={(dash.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {cards.map((c, i) => (
              <MetricCard
                key={i}
                label={c.title}
                value={`${c.unit === "₹" ? "₹" : ""}${typeof c.value === "number" ? c.value.toLocaleString() : c.value}${c.unit && c.unit !== "₹" ? c.unit : ""}`}
                tone={tone(c.intent)}
              />
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {Object.entries(charts).map(([name, series]) => (
              <SectionCard key={name} title={titleCase(name.replace(/_/g, " "))}>
                <div className="space-y-1.5 text-sm">
                  {Object.entries(series as Record<string, any>).map(([k, v]) => (
                    <div key={k} className="flex justify-between border-b border-border/50 py-1">
                      <span className="text-foreground">{titleCase(k)}</span>
                      <span className="font-mono text-muted-foreground">
                        {typeof v === "object" ? `₹${(v.exposure ?? 0).toLocaleString()} · ${v.count}` : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            ))}
          </div>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
