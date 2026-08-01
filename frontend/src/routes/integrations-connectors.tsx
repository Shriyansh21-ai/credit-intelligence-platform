import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  titleCase,
  useConnectors,
  useHealth,
  useOverview,
  useSetMode,
} from "@/features/integrations";

export const Route = createFileRoute("/integrations-connectors")({ component: ConnectorsPage });

const MODE_TONE: Record<string, string> = {
  mock: "text-sky-500",
  sandbox: "text-amber-500",
  production: "text-emerald-500",
};
const STATUS_TONE: Record<string, string> = {
  healthy: "text-emerald-500",
  degraded: "text-amber-500",
  unavailable: "text-red-500",
  unknown: "text-muted-foreground",
};

function ConnectorsPage() {
  const connectors = useConnectors();
  const overview = useOverview();
  const health = useHealth();
  const setMode = useSetMode();

  const totals = overview.data?.totals ?? {};
  const healthByKey = new Map((health.data?.health ?? []).map((h) => [h.category + ":" + h.provider, h]));

  return (
    <OpsLayout
      title="Connector Framework"
      description="Every external system is reached through one common connector interface with authentication, retries, rate limiting, timeouts, a circuit breaker, caching, audit logging and health checks. Switch mock → sandbox → production per connector — no code changes."
    >
      <StateWrap loading={connectors.isLoading} error={(connectors.error as Error)?.message ?? null}>
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Connectors" value={String(connectors.data?.connectors.length ?? 0)} />
            <MetricCard label="Total Calls" value={String(totals.calls ?? 0)} />
            <MetricCard label="Success Rate" value={`${((totals.success_rate ?? 0) * 100).toFixed(1)}%`} tone="text-emerald-500" />
            <MetricCard label="Cache Hits" value={String(totals.cache_hits ?? 0)} />
          </div>

          <SectionCard title="Registered connectors">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4">Connector</th>
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4">Active mode</th>
                    <th className="py-2 pr-4">Health</th>
                    <th className="py-2 pr-4">Switch mode</th>
                  </tr>
                </thead>
                <tbody>
                  {(connectors.data?.connectors ?? []).map((c) => {
                    const cfg = connectors.data?.configs.find((x) => x.connector_key === c.key);
                    const mode = cfg?.provider_mode ?? "mock";
                    const h = healthByKey.get((c.category ?? "") + ":" + `${mode}_${c.key.split("_")[0]}`);
                    const hStatus =
                      (health.data?.health ?? []).find((x) => x.provider.includes(c.key.split("_")[0]))?.status ??
                      "unknown";
                    return (
                      <tr key={c.key} className="border-b border-border/50">
                        <td className="py-2.5 pr-4 font-medium text-foreground">{titleCase(c.key)}</td>
                        <td className="py-2.5 pr-4 text-muted-foreground">{titleCase(c.category ?? "")}</td>
                        <td className={`py-2.5 pr-4 font-mono ${MODE_TONE[mode] ?? ""}`}>{mode}</td>
                        <td className={`py-2.5 pr-4 ${STATUS_TONE[hStatus] ?? ""}`}>{hStatus}</td>
                        <td className="py-2.5 pr-4">
                          <div className="flex gap-1.5">
                            {c.modes.map((m) => (
                              <button
                                key={m}
                                onClick={() => setMode.mutate({ key: c.key, mode: m })}
                                disabled={setMode.isPending || m === mode}
                                className={`rounded-md border px-2 py-1 text-xs transition-colors ${
                                  m === mode
                                    ? "border-primary bg-primary/10 text-foreground"
                                    : "border-border text-muted-foreground hover:bg-muted"
                                }`}
                              >
                                {m}
                              </button>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>

          <SectionCard title="Live provider metrics (observability)">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4">Provider</th>
                    <th className="py-2 pr-4">Calls</th>
                    <th className="py-2 pr-4">Success %</th>
                    <th className="py-2 pr-4">Retries</th>
                    <th className="py-2 pr-4">Avg ms</th>
                    <th className="py-2 pr-4">p95 ms</th>
                  </tr>
                </thead>
                <tbody>
                  {(overview.data?.live_metrics ?? []).map((m) => (
                    <tr key={m.provider} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-mono text-foreground">{m.provider}</td>
                      <td className="py-2 pr-4">{m.calls}</td>
                      <td className="py-2 pr-4 text-emerald-500">{(m.success_rate * 100).toFixed(1)}%</td>
                      <td className="py-2 pr-4">{m.retries}</td>
                      <td className="py-2 pr-4">{m.avg_latency_ms.toFixed(2)}</td>
                      <td className="py-2 pr-4">{m.p95_latency_ms.toFixed(2)}</td>
                    </tr>
                  ))}
                  {(overview.data?.live_metrics ?? []).length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-4 text-center text-muted-foreground">
                        No calls recorded yet — import data to populate metrics.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      </StateWrap>
    </OpsLayout>
  );
}
