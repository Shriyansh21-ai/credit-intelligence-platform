import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useCreatePrompt, usePrompts, useRenderPrompt, useSeedPrompts } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-prompts")({ component: PromptsPage });

function PromptsPage() {
  const prompts = usePrompts();
  const seed = useSeedPrompts();
  const create = useCreatePrompt();
  const render = useRenderPrompt();
  const [key, setKey] = useState("");
  const [rk, setRk] = useState("");
  const [vars, setVars] = useState("{}");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout
      title="Prompt Engineering Platform"
      description="A governed prompt registry: parameterised templates, versioning, evaluation, approval workflow, deployment, rollback and A/B testing. No prompt is hardcoded in application logic."
    >
      <div className="space-y-4">
        <div className="flex gap-2">
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={seed.isPending} onClick={() => seed.mutate()}>Seed default prompts</button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Create prompt">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!key || create.isPending}
                onClick={() => create.mutate({ key, name: key }, { onSuccess: () => setKey("") })}>Create</button>
            </div>
          </SectionCard>
          <SectionCard title="Render deployed prompt">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="prompt key" value={rk} onChange={(e) => setRk(e.target.value)} />
              <textarea className="h-16 w-full rounded border bg-background px-3 py-2 font-mono text-xs" placeholder='variables json e.g. {"company":"Acme"}' value={vars} onChange={(e) => setVars(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!rk || render.isPending}
                onClick={() => { try { render.mutate({ key: rk, variables: JSON.parse(vars || "{}") }, { onSuccess: (r) => setOut(r) }); } catch { setOut({ text: "invalid JSON" }); } }}>Render</button>
              {out && <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{out.text}</pre>}
            </div>
          </SectionCard>
        </div>
        <SectionCard title="Prompt registry">
          <StateWrap loading={prompts.isLoading} empty={!(prompts.data as any)?.length}>
            <ul className="space-y-1 text-sm">
              {(prompts.data as any)?.map((p: any) => (
                <li key={p.id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{p.key} <span className="text-xs text-muted-foreground">({p.task ?? "general"})</span></span>
                  <span className="text-xs text-muted-foreground">v{p.current_version} · deployed {p.deployed_version ?? "—"}</span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
