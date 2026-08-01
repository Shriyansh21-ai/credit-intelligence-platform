import { createFileRoute } from "@tanstack/react-router";
import { Activity } from "lucide-react";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  useStressScenarios,
} from "@/features/ml-platform";

export const Route = createFileRoute("/ml-stress")({ component: MLStressPage });

function MLStressPage() {
  const { data, isLoading, error } = useStressScenarios();
  const scenarios = data?.scenarios ?? [];

  return (
    <OpsLayout
      title="Stress Testing Dashboard"
      description="Macroeconomic scenarios applied directly to model features and re-scored through the production model to project portfolio impact."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}>
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            <MetricCard label="Macro Scenarios" value={scenarios.length} />
            <MetricCard label="Severity Bands" value={3} sub="optimistic · expected · worst" />
            <MetricCard label="Method" value="ML re-scoring" />
          </div>

          <SectionCard
            title="Available macro scenarios"
            description="Each scenario shocks the relevant features (additively or multiplicatively), scaled by severity, then re-scores the book."
          >
            <div className="grid gap-4 md:grid-cols-2">
              {scenarios.map((sc) => (
                <div key={sc.name} className="rounded-lg border border-border p-4">
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold text-foreground">{sc.label}</h3>
                  </div>
                  <p className="mt-1.5 text-xs text-muted-foreground">{sc.description}</p>
                  <code className="mt-2 inline-block rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                    {sc.name}
                  </code>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="How to run a stress test">
            <p className="text-sm text-muted-foreground">
              Stress tests run over a portfolio of positions via{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">POST /api/ml/stress-ml/run</code> (single
              scenario across severities) or{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">POST /api/ml/stress-ml/run-all</code>{" "}
              (every scenario, ranked by projected expected-loss impact). Each returns the baseline
              portfolio default rate and expected loss alongside the stressed cases.
            </p>
          </SectionCard>
        </div>
      </StateWrap>
    </OpsLayout>
  );
}
