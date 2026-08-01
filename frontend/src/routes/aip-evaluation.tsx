import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { MetricCard, OpsLayout, SectionCard, StateWrap, useEvalList, useEvalScore, useEvalSummary } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-evaluation")({ component: EvalPage });

function EvalPage() {
  const summary = useEvalSummary();
  const list = useEvalList();
  const score = useEvalScore();
  const [output, setOutput] = useState("");
  const [grounding, setGrounding] = useState("");
  const [card, setCard] = useState<any>(null);

  return (
    <OpsLayout
      title="AI Evaluation Framework"
      description="Automatic scorecards across factual accuracy, hallucination, groundedness, consistency, policy compliance, reasoning, latency, cost, token usage and business correctness. Deterministic and reproducible."
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          <MetricCard label="Evaluations" value={(summary.data as any)?.count ?? "—"} />
          <MetricCard label="Mean overall" value={(summary.data as any)?.mean_overall ?? "—"} />
          <MetricCard label="Pass rate" value={(summary.data as any)?.pass_rate ?? "—"} />
        </div>
        <SectionCard title="Score an output">
          <div className="space-y-2">
            <textarea className="h-20 w-full rounded border bg-background px-3 py-2 text-sm" placeholder="model output text" value={output} onChange={(e) => setOutput(e.target.value)} />
            <textarea className="h-20 w-full rounded border bg-background px-3 py-2 text-sm" placeholder="grounding text (what it should be based on)" value={grounding} onChange={(e) => setGrounding(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!output || score.isPending}
              onClick={() => score.mutate({ output_text: output, grounding_text: grounding }, { onSuccess: (r) => setCard(r) })}>Evaluate</button>
            {card && (
              <div className="mt-2">
                <div className="mb-2 text-sm">Grade <span className="font-semibold">{card.grade}</span> · overall {card.overall_score}</div>
                <div className="grid grid-cols-2 gap-1 text-xs md:grid-cols-5">
                  {Object.entries(card.scores).map(([k, v]) => (
                    <div key={k} className="rounded bg-muted px-2 py-1"><div className="text-muted-foreground">{k}</div><div className="font-mono">{String(v)}</div></div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </SectionCard>
        <SectionCard title="Recent evaluations">
          <StateWrap loading={list.isLoading} empty={!(list.data as any)?.evaluations?.length}>
            <ul className="space-y-1 text-xs">
              {((list.data as any)?.evaluations ?? []).map((e: any) => (
                <li key={e.id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{e.target_type} {e.target_ref}</span><span>{e.grade} · {e.overall_score}</span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
