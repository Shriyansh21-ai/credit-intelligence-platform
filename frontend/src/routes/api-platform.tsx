import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  useApiKeys,
  useApiUsage,
  useCreateApiKey,
  useRevokeApiKey,
  useWebhooks,
} from "@/features/integrations";

export const Route = createFileRoute("/api-platform")({ component: ApiPlatformPage });

function ApiPlatformPage() {
  const keys = useApiKeys();
  const usage = useApiUsage();
  const webhooks = useWebhooks();
  const create = useCreateApiKey();
  const revoke = useRevokeApiKey();

  const [name, setName] = useState("Partner Integration");
  const [newKey, setNewKey] = useState<string | null>(null);

  return (
    <OpsLayout
      title="Open API Platform"
      description="Issue scoped API keys (shown once, stored hashed), manage webhook subscriptions, and monitor usage analytics and rate limits. SDK-ready and OAuth2-adjacent for external consumers."
    >
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard label="API Keys" value={String(keys.data?.keys.length ?? 0)} />
          <MetricCard label="Webhooks" value={String(webhooks.data?.subscriptions.length ?? 0)} />
          <MetricCard label="Total API Calls" value={String(usage.data?.total_calls ?? 0)} />
          <MetricCard label="Avg Latency" value={`${(usage.data?.avg_latency_ms ?? 0).toFixed(1)} ms`} />
        </div>

        <SectionCard title="Issue an API key">
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Name</span>
              <input value={name} onChange={(e) => setName(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2" />
            </label>
            <button
              onClick={() =>
                create.mutate({ name, scopes: ["read", "write"] }, { onSuccess: (k) => setNewKey(k.api_key ?? null) })
              }
              disabled={create.isPending}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
              {create.isPending ? "Creating…" : "Create key"}
            </button>
          </div>
          {newKey && (
            <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
              <p className="mb-1 font-medium text-amber-600 dark:text-amber-400">Copy this key now — it will not be shown again:</p>
              <code className="break-all font-mono text-foreground">{newKey}</code>
            </div>
          )}
        </SectionCard>

        <SectionCard title="API keys">
          <StateWrap loading={keys.isLoading} error={(keys.error as Error)?.message ?? null}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Prefix</th>
                    <th className="py-2 pr-4">Scopes</th>
                    <th className="py-2 pr-4">Rate / min</th>
                    <th className="py-2 pr-4">Active</th>
                    <th className="py-2 pr-4"></th>
                  </tr>
                </thead>
                <tbody>
                  {(keys.data?.keys ?? []).map((k) => (
                    <tr key={k.id} className="border-b border-border/50">
                      <td className="py-2 pr-4 text-foreground">{k.name}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{k.key_prefix}</td>
                      <td className="py-2 pr-4">{k.scopes.join(", ")}</td>
                      <td className="py-2 pr-4">{k.rate_limit_per_min}</td>
                      <td className={`py-2 pr-4 ${k.active ? "text-emerald-500" : "text-muted-foreground"}`}>
                        {k.active ? "active" : "revoked"}
                      </td>
                      <td className="py-2 pr-4">
                        {k.active && (
                          <button onClick={() => revoke.mutate(k.id)}
                            className="rounded-md border border-border px-2 py-1 text-xs text-red-500 hover:bg-muted">
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {(keys.data?.keys ?? []).length === 0 && (
                    <tr><td colSpan={6} className="py-4 text-center text-muted-foreground">No API keys issued.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </StateWrap>
        </SectionCard>

        <SectionCard title="Webhook subscriptions">
          <StateWrap loading={webhooks.isLoading} error={(webhooks.error as Error)?.message ?? null}>
            <ul className="space-y-2 text-sm">
              {(webhooks.data?.subscriptions ?? []).map((s) => (
                <li key={s.id} className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2">
                  <span className="font-mono text-foreground">{s.url}</span>
                  <span className="text-xs text-muted-foreground">{s.events.join(", ")}</span>
                </li>
              ))}
              {(webhooks.data?.subscriptions ?? []).length === 0 && (
                <li className="text-muted-foreground">No webhook subscriptions.</li>
              )}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
