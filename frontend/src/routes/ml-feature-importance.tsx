import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  CountBarChart,
  OpsLayout,
  SectionCard,
  StateWrap,
  useModel,
  useModels,
} from "@/features/ml-platform";
import { titleCase } from "@/features/operations";

export const Route = createFileRoute("/ml-feature-importance")({ component: MLFeatureImportancePage });

function MLFeatureImportancePage() {
  const { data: modelsData, isLoading, error } = useModels();
  const models = modelsData?.models ?? [];
  const [modelId, setModelId] = useState<number | null>(null);

  useEffect(() => {
    if (modelId == null && models.length) {
      const prod = models.find((m) => m.production_status === "production");
      setModelId((prod ?? models[0]).id);
    }
  }, [models, modelId]);

  const detail = useModel(modelId);
  const importances = detail.data?.report?.feature_importances ?? {};
  const rows = Object.entries(importances)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([label, value]) => ({ label: titleCase(label), value: Number((value * 100).toFixed(2)) }));

  return (
    <OpsLayout
      title="Feature Importance Dashboard"
      description="Global driver importances for a trained model. Tree models expose genuine SHAP importances; linear models expose coefficient magnitudes."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}
        empty={!isLoading && !models.length} emptyMessage="No models available.">
        <div className="space-y-6">
          <select
            value={modelId ?? ""}
            onChange={(e) => setModelId(Number(e.target.value))}
            className="rounded-md border border-border bg-card px-3 py-2 text-sm"
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.model_key} v{m.version} ({m.production_status})
              </option>
            ))}
          </select>

          <SectionCard title="Top 15 feature importances" description="Share of total model importance (%).">
            {rows.length ? (
              <CountBarChart data={rows} />
            ) : (
              <p className="text-sm text-muted-foreground">No importance data for this model.</p>
            )}
          </SectionCard>
        </div>
      </StateWrap>
    </OpsLayout>
  );
}
