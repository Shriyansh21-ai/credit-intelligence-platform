import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  usePolicies, usePolicyDomains, usePolicyPlayground,
} from "@/features/banking-os";

export const Route = createFileRoute("/policy-engine")({ component: PolicyEnginePage });

const SAMPLE_RULES = JSON.stringify(
  [
    {
      id: "high-pd",
      name: "Reject very high PD",
      when: [{ field: "pd", op: "gte", value: 0.25 }],
      then: { decision: "reject", message: "PD above risk appetite" },
      priority: 100,
      stop: true,
    },
    { id: "refer", name: "Refer mid PD", when: [{ field: "pd", op: "gte", value: 0.1 }], then: { decision: "refer" }, priority: 50 },
  ],
  null,
  2,
);

function PolicyEnginePage() {
  const domains = usePolicyDomains();
  const policies = usePolicies();
  const playground = usePolicyPlayground();
  const [rules, setRules] = useState(SAMPLE_RULES);
  const [input, setInput] = useState('{ "pd": 0.3 }');

  const list = (policies.data as any)?.policies ?? [];
  const dom = domains.data as any;
  const result = playground.data as any;

  const run = () => {
    try {
      playground.mutate({ rules: JSON.parse(rules), data: JSON.parse(input) });
    } catch {
      /* invalid json — surfaced by disabled state below */
    }
  };

  const decisionTone = (d: string) =>
    d === "reject" || d === "block" ? "text-red-500" : d === "refer" || d === "flag" ? "text-amber-500" : "text-emerald-500";

  return (
    <OpsLayout
      title="Enterprise Policy Engine"
      description="No-code, versioned, deterministic business rules across loan, AML, KYC, exposure, collateral, approval and risk-appetite domains — with a live rule playground."
    >
      <div className="space-y-6">
        <StateWrap loading={policies.isLoading} error={(policies.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Policies" value={String(list.length)} />
            <MetricCard label="Active" value={String(list.filter((p: any) => p.status === "active").length)} />
            <MetricCard label="Domains" value={String((dom?.domains ?? []).length)} />
            <MetricCard label="Operators" value={String((dom?.operators ?? []).length)} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Rule Playground" description="Dry-run a ruleset against an input subject — deterministic, no persistence.">
              <div className="space-y-3">
                <textarea
                  value={rules}
                  onChange={(e) => setRules(e.target.value)}
                  rows={10}
                  className="w-full rounded-md border border-border bg-background p-2 font-mono text-xs"
                />
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  className="w-full rounded-md border border-border bg-background p-2 font-mono text-xs"
                />
                <button
                  onClick={run}
                  className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
                >
                  {playground.isPending ? "Evaluating…" : "Evaluate"}
                </button>
                {result && (
                  <div className="rounded-md border border-border bg-background p-3 text-sm">
                    {result.valid === false ? (
                      <div className="text-red-500">Invalid: {(result.problems ?? []).join("; ")}</div>
                    ) : (
                      <>
                        <div className="font-semibold">
                          Decision: <span className={decisionTone(result.decision)}>{titleCase(result.decision)}</span>
                        </div>
                        <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
                          {(result.reasons ?? []).map((r: string, i: number) => <li key={i}>{r}</li>)}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </div>
            </SectionCard>

            <SectionCard title="Policies" description="Governed business policies by domain.">
              <div className="space-y-2 text-sm">
                {list.length === 0 && <p className="text-muted-foreground">No policies yet.</p>}
                {list.map((p: any) => (
                  <div key={p.id} className="flex items-center justify-between rounded-md border border-border/60 p-2">
                    <div>
                      <div className="font-medium text-foreground">{p.name}</div>
                      <div className="text-xs text-muted-foreground">{titleCase(p.domain)} · v{p.current_version}</div>
                    </div>
                    <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase">{p.status}</span>
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
