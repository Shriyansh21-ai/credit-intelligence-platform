import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, usePlugins, useMarketplaceAnalytics, usePublishPlugin } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-marketplace")({ component: MarketplacePage });

function MarketplacePage() {
  const plugins = usePlugins();
  const analytics = useMarketplaceAnalytics();
  const publish = usePublishPlugin();
  const [key, setKey] = useState("");

  return (
    <OpsLayout title="Plugin Marketplace" description="Full plugin lifecycle: publishing, approval workflow, semantic versioning, dependencies, compatibility, permissions, health, install analytics and billing readiness.">
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          {analytics.data && ["total_plugins", "published", "total_installs", "revenue_ready"].map((k) => (
            <div key={k} className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">{k.replace(/_/g, " ")}</div><div className="text-lg font-semibold">{analytics.data[k]}</div></div>
          ))}
        </div>
        <SectionCard title="Publish plugin">
          <div className="flex gap-2">
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="plugin key" value={key} onChange={(e) => setKey(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!key || publish.isPending}
              onClick={() => publish.mutate({ key, name: key, category: "integration" }, { onSuccess: () => setKey("") })}>Publish</button>
          </div>
        </SectionCard>
        <SectionCard title="Plugins">
          <StateWrap loading={plugins.isLoading} empty={!(plugins.data?.plugins?.length)}>
            <ul className="space-y-1 text-sm">{plugins.data?.plugins?.map((p: any) => (
              <li key={p.plugin_id} className="flex justify-between border-b border-border/50 py-1">
                <span>{p.name} <span className="text-xs text-muted-foreground">v{p.latest_version} · {p.category}</span></span>
                <span className="text-xs text-muted-foreground">{p.status} · {p.install_count} installs</span>
              </li>))}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
