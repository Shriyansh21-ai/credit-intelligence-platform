import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase, usePrompts,
} from "@/features/banking-os";

export const Route = createFileRoute("/prompt-studio")({ component: PromptStudioPage });

function PromptStudioPage() {
  const prompts = usePrompts();
  const list = (prompts.data as any)?.prompts ?? [];

  return (
    <OpsLayout
      title="Prompt Management Studio"
      description="Versioned, governed LLM prompts — templates with a draft → approved → deployed lifecycle, declared variables, deterministic evaluation and a render playground."
    >
      <div className="space-y-6">
        <StateWrap loading={prompts.isLoading} error={(prompts.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Templates" value={String(list.length)} />
            <MetricCard label="Active" value={String(list.filter((p: any) => p.status === "active").length)} />
            <MetricCard label="Deployed" value={String(list.filter((p: any) => p.deployed_version).length)} />
            <MetricCard label="Categories" value={String(new Set(list.map((p: any) => p.category).filter(Boolean)).size)} />
          </div>

          <SectionCard title="Prompt templates">
            <div className="space-y-2 text-sm">
              {list.length === 0 && <p className="text-muted-foreground">No prompt templates yet.</p>}
              {list.map((p: any) => (
                <div key={p.id} className="flex items-center justify-between rounded-md border border-border/60 p-2">
                  <div>
                    <div className="font-medium text-foreground">{p.name}</div>
                    <div className="text-xs text-muted-foreground">{titleCase(p.category ?? "—")} · v{p.current_version}{p.deployed_version ? ` · deployed v${p.deployed_version}` : ""}</div>
                  </div>
                  <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase">{p.status}</span>
                </div>
              ))}
            </div>
          </SectionCard>
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
