import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, useExplainDecision } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-explainability")({ component: ExplainPage });

function ExplainPage() {
  const explain = useExplainDecision();
  const [company, setCompany] = useState("");
  const [r, setR] = useState<any>(null);

  return (
    <OpsLayout
      title="Explainable Enterprise AI"
      description="SHAP-style additive contributions, a LIME-style local view, counterfactuals, a decision-tree/rule path, feature importance, a natural-language explanation, an evidence trace, a confidence interval and a reasoning chain — reproducible by construction."
    >
      <div className="space-y-4">
        <SectionCard title="Explain a decision">
          <div className="flex gap-2">
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="company ref" value={company} onChange={(e) => setCompany(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!company || explain.isPending}
              onClick={() => explain.mutate({ company_ref: company }, { onSuccess: (res) => setR(res) })}>Explain</button>
          </div>
        </SectionCard>
        {r && (
          <>
            <SectionCard title={`Decision: ${r.decision} (P favourable ${r.p_favorable})`}>
              <div className="space-y-2">
                {(r.shap ?? []).map((c: any) => (
                  <div key={c.feature} className="text-xs">
                    <div className="flex justify-between"><span>{c.feature} = {String(c.value)}</span><span className={c.contribution >= 0 ? "text-green-500" : "text-red-500"}>{c.contribution >= 0 ? "+" : ""}{c.contribution}</span></div>
                    <div className="h-1.5 w-full rounded bg-muted"><div className={`h-full rounded ${c.contribution >= 0 ? "bg-green-500" : "bg-red-500"}`} style={{ width: `${Math.min(100, Math.abs(c.contribution) * 40)}%` }} /></div>
                  </div>
                ))}
              </div>
            </SectionCard>
            <div className="grid gap-4 lg:grid-cols-2">
              <SectionCard title="Counterfactuals">
                <ul className="space-y-1 text-xs">
                  {(r.counterfactuals ?? []).map((c: any, i: number) => <li key={i} className="rounded bg-muted px-2 py-1">{c.effect}</li>)}
                  {!(r.counterfactuals ?? []).length && <li className="text-muted-foreground">None — decision is well supported.</li>}
                </ul>
              </SectionCard>
              <SectionCard title="Reasoning chain">
                <ol className="list-decimal space-y-0.5 pl-5 text-xs">
                  {(r.reasoning_chain ?? []).map((s: string, i: number) => <li key={i}>{s}</li>)}
                </ol>
              </SectionCard>
            </div>
            <SectionCard title="Natural-language explanation">
              <div className="whitespace-pre-wrap text-sm">{r.nl_explanation}</div>
            </SectionCard>
          </>
        )}
      </div>
    </OpsLayout>
  );
}
