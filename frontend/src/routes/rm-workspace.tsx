import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase, useRmWorkspace,
} from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/rm-workspace")({ component: RmWorkspacePage });

function RmWorkspacePage() {
  const [input, setInput] = useState("");
  const [ref, setRef] = useState<string | null>(null);
  const q = useRmWorkspace(ref);
  const w = q.data as Record<string, any> | undefined;

  return (
    <OpsLayout
      title="Relationship Manager Workspace"
      description="A single cockpit per customer: timeline, communications, loan history, cross-sell opportunities, AI recommendations, customer health, open alerts and the next best action."
    >
      <div className="space-y-6">
        <SectionCard title="Load customer">
          <div className="flex items-end gap-3">
            <input value={input} onChange={(e) => setInput(e.target.value)}
              placeholder="Company reference"
              className="w-full max-w-md rounded-md border border-border bg-background px-3 py-2" />
            <button onClick={() => setRef(input)}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
              Load
            </button>
          </div>
        </SectionCard>

        <StateWrap loading={q.isLoading} error={(q.error as Error)?.message ?? null}>
          {w && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <MetricCard label="Customer health" value={String(w.health?.health_score ?? "—")}
                  sub={w.health?.band} tone="text-emerald-500" />
                <MetricCard label="Open alerts" value={String(w.open_alerts?.length ?? 0)} tone="text-amber-500" />
                <MetricCard label="Opportunities" value={String(w.opportunities?.length ?? 0)} />
                <MetricCard label="EWS band" value={titleCase(w.ews?.ews_band ?? "—")} />
              </div>

              <SectionCard title="Next best action">
                <div className="rounded-lg bg-primary/10 p-3 text-sm">
                  <span className="font-medium">{titleCase(w.next_best_action?.action ?? "")}</span>
                  {" — "}{w.next_best_action?.detail}
                  <span className="ml-2 text-xs text-muted-foreground">({w.next_best_action?.source})</span>
                </div>
              </SectionCard>

              <div className="grid gap-6 lg:grid-cols-2">
                <SectionCard title="Timeline">
                  <ul className="space-y-1 text-sm">
                    {(w.timeline ?? []).slice(0, 12).map((e: any, i: number) => (
                      <li key={i} className="flex gap-2 border-b border-border/50 pb-1">
                        <span className="rounded bg-muted px-2 py-0.5 text-xs">{e.type}</span>
                        <span className="text-muted-foreground">{e.detail}</span>
                      </li>
                    ))}
                    {(w.timeline ?? []).length === 0 && <li className="text-muted-foreground">No events.</li>}
                  </ul>
                </SectionCard>
                <SectionCard title="Cross-sell opportunities">
                  <ul className="space-y-1 text-sm">
                    {(w.opportunities ?? []).map((o: any, i: number) => (
                      <li key={i} className="flex justify-between rounded-md border border-border/60 px-3 py-1.5">
                        <span>{o.name}</span>
                        <span className="text-xs text-muted-foreground">{Math.round((o.confidence ?? 0) * 100)}%</span>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              </div>

              <SectionCard title="AI recommendations">
                <ul className="space-y-1 text-sm">
                  {(w.recommendations ?? []).map((r: any, i: number) => (
                    <li key={i}>• <b>{titleCase(r.action)}</b> — {r.title}</li>
                  ))}
                </ul>
              </SectionCard>
            </>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
