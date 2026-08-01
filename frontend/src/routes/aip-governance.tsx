import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { MetricCard, OpsLayout, SectionCard, StateWrap, useAssets, useGovernanceSummary, useRegisterAsset, useTransitionAsset } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-governance")({ component: GovernancePage });

const NEXT: Record<string, string> = { registered: "validate", validated: "approve", approved: "deploy", deployed: "retire" };

function GovernancePage() {
  const summary = useGovernanceSummary();
  const assets = useAssets();
  const register = useRegisterAsset();
  const transition = useTransitionAsset();
  const [type, setType] = useState("prompt");
  const [ref, setRef] = useState("");

  return (
    <OpsLayout
      title="AI Governance"
      description="Register every AI asset (prompts, models, datasets, agents, workflows, RAG indexes, reports) with a version, checksum and lineage; drive it through registered → validated → approved → deployed → retired. Every AI decision is reproducible."
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          <MetricCard label="Assets" value={(summary.data as any)?.total ?? "—"} />
          <MetricCard label="Reproducible" value={(summary.data as any)?.reproducible ?? "—"} />
          <MetricCard label="Types" value={Object.keys((summary.data as any)?.by_type ?? {}).length} />
        </div>
        <SectionCard title="Register asset">
          <div className="flex flex-wrap gap-2">
            <select className="rounded border bg-background px-3 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
              {["prompt", "model", "dataset", "agent", "workflow", "rag_index", "report"].map((t) => <option key={t}>{t}</option>)}
            </select>
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="asset ref" value={ref} onChange={(e) => setRef(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!ref || register.isPending}
              onClick={() => register.mutate({ asset_type: type, asset_ref: ref, name: ref }, { onSuccess: () => setRef("") })}>Register</button>
          </div>
        </SectionCard>
        <SectionCard title="Asset registry">
          <StateWrap loading={assets.isLoading} empty={!(assets.data as any)?.assets?.length}>
            <ul className="space-y-1 text-sm">
              {((assets.data as any)?.assets ?? []).map((a: any) => (
                <li key={a.id} className="flex items-center justify-between border-b border-border/50 py-1">
                  <span>{a.asset_type}:{a.asset_ref} <span className="text-xs text-muted-foreground">v{a.version}</span></span>
                  <span className="flex items-center gap-2">
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[10px]">{a.state}</span>
                    {NEXT[a.state] && (
                      <button className="rounded border px-2 py-0.5 text-[10px]"
                        onClick={() => transition.mutate({ asset_id: a.id, action: NEXT[a.state] })}>{NEXT[a.state]}</button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
