import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useBenchmarkList, useBenchmarkRun } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-benchmark")({ component: BenchmarkPage });

function BenchmarkPage() {
  const list = useBenchmarkList();
  const run = useBenchmarkRun();
  const [subject, setSubject] = useState("");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Corporate Benchmarking Platform" description="Compare a company against its industry peer set: financial, growth, profitability, liquidity, leverage, ESG, risk and credit rankings with percentile positioning and a synthesized competitive position.">
      <div className="space-y-4">
        <SectionCard title="Run benchmark">
          <div className="flex gap-2">
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="company ref" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!subject || run.isPending} onClick={() => run.mutate({ subject_ref: subject }, { onSuccess: (r) => setOut(r) })}>Benchmark</button>
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Result"><StateWrap loading={run.isPending} empty={!out}><pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out?.rankings ?? out, null, 2).slice(0, 1400)}</pre></StateWrap></SectionCard>
          <SectionCard title="Benchmarks">
            <StateWrap loading={list.isLoading} empty={!(list.data?.benchmarks?.length)}>
              <ul className="space-y-1 text-sm">{list.data?.benchmarks?.map((b: any) => <li key={b.benchmark_id} className="flex justify-between border-b border-border/50 py-1"><span>{b.subject_ref}</span><span className="text-xs text-muted-foreground">{b.competitive_position}</span></li>)}</ul>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
