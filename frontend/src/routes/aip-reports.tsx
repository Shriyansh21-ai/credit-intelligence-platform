import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useGenerateReport, useReportTypes, useReports } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-reports")({ component: ReportsPage });

function ReportsPage() {
  const types = useReportTypes();
  const list = useReports();
  const gen = useGenerateReport();
  const [rt, setRt] = useState("credit_memo");
  const [company, setCompany] = useState("");
  const [report, setReport] = useState<any>(null);

  return (
    <OpsLayout
      title="AI Report Generation"
      description="Generate board-quality reports (credit memo, investment memo, risk, fraud, portfolio review, committee brief, executive summary, regulatory, due diligence, financial analysis, board deck) with reasoning, evidence, citations, charts, confidence and recommendations."
    >
      <div className="space-y-4">
        <SectionCard title="Generate report">
          <div className="flex flex-wrap gap-2">
            <select className="rounded border bg-background px-3 py-2 text-sm" value={rt} onChange={(e) => setRt(e.target.value)}>
              {((types.data as any)?.report_types ?? []).map((t: string) => <option key={t}>{t}</option>)}
            </select>
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="company ref" value={company} onChange={(e) => setCompany(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!company || gen.isPending}
              onClick={() => gen.mutate({ report_type: rt, company_ref: company }, { onSuccess: (r) => setReport(r) })}>Generate</button>
          </div>
          {report && (
            <div className="mt-3 space-y-3 text-sm">
              <div className="text-xs text-muted-foreground">{report.title} · decision {report.decision ?? "—"} · confidence {report.confidence}</div>
              {(report.sections ?? []).map((s: any, i: number) => (
                <div key={i} className="rounded border border-border p-3">
                  <div className="mb-1 font-semibold">{s.heading}</div>
                  <div className="whitespace-pre-wrap text-xs">{s.body}</div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
        <SectionCard title="Generated reports">
          <StateWrap loading={list.isLoading} empty={!(list.data as any)?.reports?.length}>
            <ul className="space-y-1 text-sm">
              {((list.data as any)?.reports ?? []).map((r: any) => (
                <li key={r.report_id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{r.title}</span><span className="text-xs text-muted-foreground">conf {r.confidence}</span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
