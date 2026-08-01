import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useApiKeys, useApiExplorer, useCreateApiKey, useWebhooks, useSandboxRequest } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-developer")({ component: DeveloperPage });

function DeveloperPage() {
  const keys = useApiKeys();
  const explorer = useApiExplorer();
  const createKey = useCreateApiKey();
  const webhooks = useWebhooks();
  const sandbox = useSandboxRequest();
  const [name, setName] = useState("");
  const [secret, setSecret] = useState<string | null>(null);
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Developer Platform" description="An internal developer platform: API-key management (secrets shown once, stored as hashes), webhook testing & replay, a sandbox request runner, rate-limit testing, request history and an OpenAPI-backed API explorer.">
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-3">
          {explorer.data && (
            <div className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">API paths</div><div className="text-lg font-semibold">{explorer.data.total_paths}</div></div>
          )}
          <div className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">API keys</div><div className="text-lg font-semibold">{keys.data?.api_keys?.length ?? 0}</div></div>
          <div className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">Webhooks</div><div className="text-lg font-semibold">{webhooks.data?.webhooks?.length ?? 0}</div></div>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Create API key">
            <div className="flex gap-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="key name" value={name} onChange={(e) => setName(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!name}
                onClick={() => createKey.mutate({ name }, { onSuccess: (r) => { setSecret(r.secret); setName(""); } })}>Create</button>
            </div>
            {secret && <pre className="mt-2 rounded bg-muted p-2 text-xs break-all">{secret}<br /><span className="text-muted-foreground">store now — shown once</span></pre>}
          </SectionCard>
          <SectionCard title="Sandbox request">
            <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => sandbox.mutate({ method: "GET", path: "/api/fin/treasury/kpis" }, { onSuccess: (r) => setOut(r) })}>Run GET /api/fin/treasury/kpis</button>
            {out && <pre className="mt-2 rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 700)}</pre>}
          </SectionCard>
        </div>
        <SectionCard title="API keys">
          <StateWrap loading={keys.isLoading} empty={!(keys.data?.api_keys?.length)}>
            <ul className="space-y-1 text-sm">{keys.data?.api_keys?.map((k: any) => (
              <li key={k.api_key_id} className="flex justify-between border-b border-border/50 py-1">
                <span>{k.name} <span className="text-xs text-muted-foreground">{k.prefix}…</span></span>
                <span className="text-xs text-muted-foreground">{k.environment} · {k.status}</span>
              </li>))}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
