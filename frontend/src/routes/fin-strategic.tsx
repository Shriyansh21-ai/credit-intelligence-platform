import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useStrategicList, useStrategicGenerate } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-strategic")({ component: StrategicPage });

function StrategicPage() {
  const list = useStrategicList();
  const generate = useStrategicGenerate();
  const [type, setType] = useState("executive_briefing");
  const [subject, setSubject] = useState("");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Strategic Intelligence Platform" description="Executive briefings, market/industry/competitor/economic/regulatory/portfolio/investment reports and long-term outlooks — combining deterministic analytics with AI reasoning while preserving citations and evidence per section.">
      <div className="space-y-4">
        <SectionCard title="Generate report">
          <div className="flex flex-wrap gap-2">
            <select className="rounded border bg-background px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
              {["executive_briefing", "market", "industry", "competitor", "economic", "regulatory", "portfolio", "investment", "outlook"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="subject (optional)" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={generate.isPending} onClick={() => generate.mutate({ report_type: type, subject_ref: subject || undefined }, { onSuccess: (r) => setOut(r) })}>Generate</button>
          </div>
        </SectionCard>
        {out && (
          <SectionCard title={out.title}>
            <div className="space-y-3">
              {out.sections?.map((s: any, i: number) => (
                <div key={i} className="rounded border border-border/50 p-3">
                  <div className="text-sm font-medium">{s.title}</div>
                  <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
                  <div className="mt-1 text-[10px] text-muted-foreground">source: {s.evidence?.source} · checksum {String(s.evidence?.checksum).slice(0, 10)}</div>
                </div>
              ))}
              <ul className="list-disc space-y-1 pl-5 text-sm">{out.recommendations?.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
            </div>
          </SectionCard>
        )}
        <SectionCard title="Reports">
          <StateWrap loading={list.isLoading} empty={!(list.data?.reports?.length)}>
            <ul className="space-y-1 text-sm">{list.data?.reports?.map((r: any) => <li key={r.report_id} className="flex justify-between border-b border-border/50 py-1"><span>{r.title}</span><span className="text-xs text-muted-foreground">{r.report_type}</span></li>)}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
