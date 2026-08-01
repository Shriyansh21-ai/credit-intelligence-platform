import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useExecPersonas, useExecDashboard } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-executive")({ component: ExecutivePage });

function ExecutivePage() {
  const personas = useExecPersonas();
  const build = useExecDashboard();
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Executive Intelligence Center" description="Persona-tailored dashboards (CEO, CFO, CRO, Treasurer, Portfolio Manager, Board, Credit Committee, Regulator, RM) with grounded KPIs, an AI executive summary and strategic recommendations.">
      <div className="space-y-4">
        <SectionCard title="Choose persona">
          <StateWrap loading={personas.isLoading} empty={!(personas.data?.personas?.length)}>
            <div className="flex flex-wrap gap-2">
              {personas.data?.personas?.map((p: string) => (
                <button key={p} className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => build.mutate({ persona: p }, { onSuccess: (r) => setOut(r) })}>{personas.data?.labels?.[p] ?? p}</button>
              ))}
            </div>
          </StateWrap>
        </SectionCard>
        {out && (
          <SectionCard title={out.title}>
            <p className="mb-3 text-sm text-muted-foreground">{out.summary}</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {out.kpis?.map((k: any, i: number) => <div key={i} className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">{k.label}</div><div className="text-lg font-semibold">{String(k.value)} {k.unit}</div></div>)}
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">{out.recommendations?.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
          </SectionCard>
        )}
      </div>
    </OpsLayout>
  );
}
