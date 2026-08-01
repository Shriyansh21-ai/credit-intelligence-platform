import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useFabricCatalog, useFabricStats,
} from "@/features/banking-os";

export const Route = createFileRoute("/data-fabric")({ component: DataFabricPage });

function DataFabricPage() {
  const catalog = useFabricCatalog();
  const stats = useFabricStats();

  const datasets = (catalog.data as any)?.datasets ?? [];
  const s = stats.data as any;

  const classTone: Record<string, string> = {
    restricted: "text-red-500",
    confidential: "text-amber-500",
    internal: "text-foreground",
    public: "text-emerald-500",
  };

  return (
    <OpsLayout
      title="Enterprise Data Fabric"
      description="Unified data catalog with lineage, impact analysis, versioned data contracts and deterministic quality scoring across completeness, validity and consistency."
    >
      <div className="space-y-6">
        <StateWrap loading={stats.isLoading} error={(stats.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Datasets" value={String(s?.datasets ?? 0)} />
            <MetricCard label="Lineage edges" value={String(s?.lineage_edges ?? 0)} />
            <MetricCard label="Contracts" value={String(s?.contracts ?? 0)} />
            <MetricCard label="Avg quality" value={s?.avg_quality != null ? `${Math.round(s.avg_quality * 100)}%` : "—"} tone="text-emerald-500" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Catalog">
              <div className="space-y-2 text-sm">
                {datasets.length === 0 && <p className="text-muted-foreground">No datasets registered.</p>}
                {datasets.map((d: any) => (
                  <div key={d.id} className="flex items-center justify-between rounded-md border border-border/60 p-2">
                    <div>
                      <div className="font-medium text-foreground">{d.name}</div>
                      <div className="text-xs text-muted-foreground">{titleCase(d.domain ?? "—")} · {d.owner ?? "unowned"}</div>
                    </div>
                    <span className={`text-[11px] uppercase ${classTone[d.classification] ?? ""}`}>{d.classification}</span>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="By classification">
              <div className="space-y-1.5 text-sm">
                {Object.entries(s?.by_classification ?? {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-border/50 py-1">
                    <span className={classTone[k] ?? "text-foreground"}>{titleCase(k)}</span>
                    <span className="font-mono text-muted-foreground">{String(v)}</span>
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
