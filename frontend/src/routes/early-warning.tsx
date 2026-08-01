import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useEvaluateEws } from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/early-warning")({ component: EarlyWarningPage });

const BAND: Record<string, string> = {
  red: "bg-red-500/15 text-red-500", amber: "bg-amber-500/15 text-amber-500",
  green: "bg-emerald-500/15 text-emerald-500",
};

function EarlyWarningPage() {
  const [company, setCompany] = useState("");
  const evaluate = useEvaluateEws();
  const r = evaluate.data;

  return (
    <OpsLayout
      title="Early Warning Signal Engine"
      description="Detects cash-flow deterioration, margin compression, working-capital stress, sales decline, leverage spikes, director changes, auditor resignation, tax defaults, covenant breaches and concentration risk — each with severity, confidence, business impact, action and evidence."
    >
      <div className="space-y-6">
        <SectionCard title="Evaluate a company">
          <div className="flex items-end gap-3">
            <label className="text-sm flex-1 max-w-md">
              <span className="mb-1 block text-muted-foreground">Company reference</span>
              <input value={company} onChange={(e) => setCompany(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2" />
            </label>
            <button
              onClick={() => evaluate.mutate({ company_ref: company, persist: true,
                context: { director_changes: 1, sector_index_change: -0.15 } })}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
              {evaluate.isPending ? "Evaluating…" : "Run EWS"}
            </button>
          </div>
        </SectionCard>

        <StateWrap loading={evaluate.isPending} error={(evaluate.error as Error)?.message ?? null}>
          {r && (
            <>
              <div className="flex items-center gap-4">
                <div className={`rounded-xl px-6 py-4 text-center ${BAND[r.ews_band]}`}>
                  <div className="text-3xl font-bold">{r.ews_score}</div>
                  <div className="text-xs uppercase tracking-wide">{r.ews_band} band</div>
                </div>
                <p className="text-sm text-muted-foreground">{r.summary}</p>
              </div>

              <SectionCard title={`Signals (${r.signal_count})`}>
                <ul className="space-y-2">
                  {(r.signals as Array<Record<string, any>>).map((s, i) => (
                    <li key={i} className="rounded-lg border border-border/60 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{s.name}</span>
                        <span className="text-xs uppercase text-muted-foreground">
                          {s.severity} · {Math.round((s.confidence ?? 0) * 100)}%
                        </span>
                      </div>
                      <div className="text-sm text-muted-foreground">{s.business_impact}</div>
                      <div className="mt-1 text-xs text-primary">→ {s.recommended_action}</div>
                    </li>
                  ))}
                  {r.signal_count === 0 && <li className="text-sm text-muted-foreground">No signals detected.</li>}
                </ul>
              </SectionCard>
            </>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
