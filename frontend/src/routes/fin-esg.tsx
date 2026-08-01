import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useEsgPortfolio, useEsgList, useEsgAssess, useEsgClimate } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-esg")({ component: EsgPage });

function EsgPage() {
  const portfolio = useEsgPortfolio();
  const list = useEsgList();
  const assess = useEsgAssess();
  const climate = useEsgClimate();
  const [subject, setSubject] = useState("");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Climate & ESG Intelligence" description="Environmental / social / governance scoring, carbon exposure & industry emissions, transition and physical climate risk, green-financing eligibility, climate stress testing and portfolio ESG analytics.">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="company ref" value={subject} onChange={(e) => setSubject(e.target.value)} />
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!subject} onClick={() => assess.mutate({ subject_ref: subject }, { onSuccess: (r) => setOut(r) })}>Assess ESG</button>
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!subject} onClick={() => climate.mutate({ subject_ref: subject }, { onSuccess: (r) => setOut(r) })}>Climate stress</button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Portfolio ESG">
            <StateWrap loading={portfolio.isLoading} empty={!portfolio.data}>
              <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(portfolio.data, null, 2)}</pre>
            </StateWrap>
          </SectionCard>
          <SectionCard title="Result">{out ? <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1200)}</pre> : <p className="text-sm text-muted-foreground">Assess a company.</p>}</SectionCard>
        </div>
        <SectionCard title="Assessments">
          <StateWrap loading={list.isLoading} empty={!(list.data?.assessments?.length)}>
            <ul className="space-y-1 text-sm">{list.data?.assessments?.map((a: any) => <li key={a.esg_id} className="flex justify-between border-b border-border/50 py-1"><span>{a.subject_ref} <span className="text-xs text-muted-foreground">({a.industry})</span></span><span className="text-xs text-muted-foreground">ESG {a.esg_score}</span></li>)}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
