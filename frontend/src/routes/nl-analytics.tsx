import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useNlQuery } from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/nl-analytics")({ component: NlAnalyticsPage });

const EXAMPLES = [
  "Show high-risk textile companies.",
  "Which customers deteriorated this month?",
  "Top borrowers by exposure.",
  "Show covenant breaches.",
  "Which companies have improving cash flow?",
];

function NlAnalyticsPage() {
  const [q, setQ] = useState("");
  const run = useNlQuery();
  const r = run.data as Record<string, any> | undefined;

  const ask = (question: string) => { setQ(question); run.mutate(question); };

  return (
    <OpsLayout
      title="Natural Language Analytics"
      description="Ask questions in plain English. They are translated into a transparent, structured platform query and executed deterministically against your book."
    >
      <div className="space-y-6">
        <SectionCard title="Ask a question">
          <div className="flex gap-2">
            <input value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run.mutate(q)}
              placeholder="e.g. Top borrowers by exposure"
              className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm" />
            <button onClick={() => run.mutate(q)}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
              {run.isPending ? "…" : "Ask"}
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => ask(ex)}
                className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted">{ex}</button>
            ))}
          </div>
        </SectionCard>

        <StateWrap loading={run.isPending} error={(run.error as Error)?.message ?? null}>
          {r && (
            <>
              <div className="text-sm text-muted-foreground">
                Intent: <span className="font-mono">{r.intent}</span> · confidence{" "}
                {Math.round((r.confidence ?? 0) * 100)}% · {r.count} result(s)
              </div>
              <SectionCard title="Results">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="text-left text-muted-foreground">
                      {(r.columns as string[]).map((c) => <th key={c} className="pb-2 pr-4">{c}</th>)}
                    </tr></thead>
                    <tbody>
                      {(r.rows as Array<Record<string, any>>).map((row, i) => (
                        <tr key={i} className="border-t border-border/50">
                          {(r.columns as string[]).map((c) => (
                            <td key={c} className="py-1.5 pr-4 font-mono">{String(row[c] ?? "—")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
              <SectionCard title="Structured query">
                <pre className="rounded-lg bg-muted/50 p-3 text-[11px]">
                  {JSON.stringify(r.structured_query, null, 2)}
                </pre>
              </SectionCard>
            </>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
