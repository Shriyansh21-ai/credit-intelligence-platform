import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { MetricCard, OpsLayout, SectionCard, StateWrap, useEvaluateTriggers, useLearningStats, useSubmitFeedback, useTrainingEvents } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-learning")({ component: LearningPage });

function LearningPage() {
  const stats = useLearningStats();
  const events = useTrainingEvents();
  const feedback = useSubmitFeedback();
  const triggers = useEvaluateTriggers();
  const [target, setTarget] = useState("prediction");
  const [rating, setRating] = useState("0.5");
  const [fired, setFired] = useState<any>(null);

  return (
    <OpsLayout
      title="Continuous Learning"
      description="Capture human feedback, corrections, approval outcomes and repayment/default signals; evaluate retraining triggers; record versioned training events that flow into the model registry."
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Feedback" value={(stats.data as any)?.feedback ?? "—"} />
          <MetricCard label="Mean rating" value={(stats.data as any)?.mean_rating ?? "—"} />
          <MetricCard label="Signals" value={(stats.data as any)?.signals ?? "—"} />
          <MetricCard label="Training events" value={(stats.data as any)?.training_events ?? "—"} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Submit feedback">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="target type" value={target} onChange={(e) => setTarget(e.target.value)} />
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="rating 0..1" value={rating} onChange={(e) => setRating(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={feedback.isPending}
                onClick={() => feedback.mutate({ target_type: target, rating: parseFloat(rating) })}>Submit</button>
            </div>
          </SectionCard>
          <SectionCard title="Evaluate retraining triggers">
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={triggers.isPending}
              onClick={() => triggers.mutate({}, { onSuccess: (r) => setFired(r) })}>Evaluate</button>
            {fired && (
              <div className="mt-2 text-xs">
                <div>Fired: {(fired.fired ?? []).map((f: any) => f.trigger).join(", ") || "none"}</div>
                <div className="text-muted-foreground">Training events created: {fired.training_events?.length ?? 0}</div>
              </div>
            )}
          </SectionCard>
        </div>
        <SectionCard title="Training events">
          <StateWrap loading={events.isLoading} empty={!(events.data as any)?.training_events?.length}>
            <ul className="space-y-1 text-sm">
              {((events.data as any)?.training_events ?? []).map((e: any) => (
                <li key={e.id} className="flex justify-between border-b border-border/50 py-1"><span>{e.trigger} <span className="text-xs text-muted-foreground">{e.version}</span></span><span className="text-xs">{e.status}</span></li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
