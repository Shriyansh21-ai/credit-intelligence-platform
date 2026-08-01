import { createFileRoute } from "@tanstack/react-router";

import { cn } from "@/lib/utils";
import {
  Bar,
  RiskLayout,
  SectionCard,
  StateWrap,
  pct,
  titleCase,
  useAssessmentId,
  useModels,
  usePrediction,
} from "@/features/risk-intelligence";

interface Search {
  assessment_id?: number;
}

export const Route = createFileRoute("/feature-importance")({
  validateSearch: (search: Record<string, unknown>): Search => {
    const raw = search.assessment_id;
    const id = typeof raw === "string" ? Number(raw) : typeof raw === "number" ? raw : undefined;
    return id !== undefined && Number.isFinite(id) ? { assessment_id: id } : {};
  },
  component: FeatureImportancePage,
});

function FeatureImportancePage() {
  const { assessment_id } = Route.useSearch();
  const { assessmentId, loading: idLoading, error: idError } = useAssessmentId(assessment_id);
  const models = useModels();
  const prediction = usePrediction(assessmentId);

  const importance = prediction.data?.feature_importance ?? {};
  const ranked = Object.entries(importance)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20);
  const max = Math.max(1e-9, ...ranked.map(([, v]) => v));

  return (
    <RiskLayout
      title="Feature Importance"
      description="The model's global feature importances and the configurable model registry. No model is trained yet — every model runs a deterministic, explainable estimator until real ML is plugged in."
    >
      <div className="space-y-6">
        <SectionCard title="Model registry"
          description="Selectable risk models. Business logic depends only on the interface, so new algorithms drop in without code changes.">
          <StateWrap loading={models.isLoading} error={(models.error as Error)?.message || null}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(models.data?.models ?? []).map((m) => (
                <div key={m.model_type} className="rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground">{m.algorithm}</span>
                    {m.is_default && (
                      <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-primary">
                        Default
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex gap-2 text-[11px]">
                    <span className={cn("rounded px-1.5 py-0.5", m.trained ? "bg-emerald-500/15 text-emerald-500" : "bg-muted text-muted-foreground")}>
                      {m.trained ? "Trained" : "Deterministic"}
                    </span>
                    <span className={cn("rounded px-1.5 py-0.5", m.backend_available ? "bg-sky-500/15 text-sky-500" : "bg-muted text-muted-foreground")}>
                      backend {m.backend_available ? "available" : "absent"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </StateWrap>
        </SectionCard>

        <SectionCard title="Global feature importance"
          description="Relative influence of each driver on the risk model.">
          <StateWrap
            loading={idLoading || prediction.isLoading}
            error={idError || (prediction.error as Error)?.message || null}
            empty={!assessmentId && !idLoading}
          >
            <div className="space-y-3">
              {ranked.map(([feature, v]) => (
                <Bar key={feature} label={titleCase(feature)} display={pct(v, 1)} fraction={v / max} />
              ))}
            </div>
          </StateWrap>
        </SectionCard>
      </div>
    </RiskLayout>
  );
}
