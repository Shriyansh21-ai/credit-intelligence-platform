import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useInvestigations, useRunInvestigation } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-investigation")({ component: InvestigationPage });

function InvestigationPage() {
  const list = useInvestigations();
  const run = useRunInvestigation();
  const [company, setCompany] = useState("");
  const [result, setResult] = useState<any>(null);

  return (
    <OpsLayout
      title="Autonomous Investigation"
      description="Investigate a company end-to-end: collect documents, search knowledge, analyse statements, screen fraud, verify compliance, benchmark industry, compute risk, explain reasoning, recommend and produce an executive report. Every stage is traceable."
    >
      <div className="space-y-4">
        <SectionCard title="Run investigation">
          <div className="flex gap-2">
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="company ref" value={company} onChange={(e) => setCompany(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!company || run.isPending}
              onClick={() => run.mutate({ company_ref: company }, { onSuccess: (r) => setResult(r) })}>Investigate</button>
          </div>
          {result && (
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-semibold">{result.decision}</span>
                <span className="text-xs text-muted-foreground">confidence {result.confidence} · report #{result.report_id}</span>
              </div>
              <div className="rounded bg-muted p-3">{result.recommendation}</div>
              <ol className="list-decimal space-y-0.5 pl-5 text-xs">
                {(result.reasoning_chain ?? []).map((s: string, i: number) => <li key={i}>{s}</li>)}
              </ol>
            </div>
          )}
        </SectionCard>
        <SectionCard title="Investigations">
          <StateWrap loading={list.isLoading} empty={!(list.data as any)?.investigations?.length}>
            <ul className="space-y-1 text-sm">
              {((list.data as any)?.investigations ?? []).map((i: any) => (
                <li key={i.investigation_id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{i.company_ref}</span><span className="text-xs text-muted-foreground">{i.recommendation}</span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
