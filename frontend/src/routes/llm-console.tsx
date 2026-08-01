import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useLLMAnalytics, useProviders, useRouteLLM,
} from "@/features/banking-os";

export const Route = createFileRoute("/llm-console")({ component: LLMConsolePage });

function LLMConsolePage() {
  const providers = useProviders();
  const analytics = useLLMAnalytics();
  const route = useRouteLLM();
  const [strategy, setStrategy] = useState("balanced");

  const p = providers.data as any;
  const a = analytics.data as any;
  const r = route.data as any;

  return (
    <OpsLayout
      title="Multi-LLM Intelligence Layer"
      description="Provider registry across OpenAI, Anthropic, Gemini, Llama, Mistral, Azure and Ollama — deterministic routing by cost, latency, quality or a balanced blend, with fallback and analytics."
    >
      <div className="space-y-6">
        <StateWrap loading={providers.isLoading} error={(providers.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Providers" value={String((p?.providers ?? []).length)} />
            <MetricCard label="Provider kinds" value={String((p?.kinds ?? []).length)} />
            <MetricCard label="Invocations" value={String(a?.total_invocations ?? 0)} />
            <MetricCard label="Total cost" value={`$${a?.total_cost ?? 0}`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Router" description="Choose a strategy and see the winning provider + fallbacks.">
              <div className="space-y-3">
                <div className="flex gap-2">
                  {["balanced", "cost", "latency", "quality", "priority"].map((s) => (
                    <button
                      key={s}
                      onClick={() => setStrategy(s)}
                      className={`rounded-md px-3 py-1 text-xs ${strategy === s ? "bg-primary text-primary-foreground" : "border border-border"}`}
                    >
                      {titleCase(s)}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => route.mutate({ strategy })}
                  className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
                >
                  {route.isPending ? "Routing…" : "Route request"}
                </button>
                {r && (
                  <div className="rounded-md border border-border bg-background p-3 text-sm">
                    <div className="font-semibold text-foreground">→ {r.chosen?.name} <span className="text-xs text-muted-foreground">({r.chosen?.kind})</span></div>
                    <div className="text-xs text-muted-foreground">{r.routed_reason}</div>
                    <div className="mt-1 text-[11px] font-mono text-muted-foreground">
                      cost ${r.chosen?.est_cost} · {r.chosen?.avg_latency_ms}ms · q{r.chosen?.quality_score}
                    </div>
                  </div>
                )}
              </div>
            </SectionCard>

            <SectionCard title="Registered providers">
              <div className="space-y-2 text-sm">
                {(p?.providers ?? []).length === 0 && <p className="text-muted-foreground">No providers registered.</p>}
                {(p?.providers ?? []).map((pr: any) => (
                  <div key={pr.id} className="flex justify-between rounded-md border border-border/60 p-2">
                    <span className="font-medium text-foreground">{pr.name} <span className="text-xs text-muted-foreground">{pr.kind}</span></span>
                    <span className="text-[11px] font-mono text-muted-foreground">q{pr.quality_score} · {pr.avg_latency_ms}ms {pr.enabled ? "" : "· off"}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
