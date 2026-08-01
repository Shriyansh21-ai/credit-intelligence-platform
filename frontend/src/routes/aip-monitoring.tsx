import { createFileRoute } from "@tanstack/react-router";

import { MetricCard, OpsLayout, SectionCard, StateWrap, useIncidents, useMonitoringDashboard, useRunMonitoring } from "@/features/ai-platform";
import { Button } from "@/components/ui/button";
import { statusText } from "@/lib/status";

export const Route = createFileRoute("/aip-monitoring")({ component: MonitoringPage });

function MonitoringPage() {
  const dash = useMonitoringDashboard();
  const incidents = useIncidents();
  const run = useRunMonitoring();
  const m = (dash.data as any)?.metrics ?? {};

  return (
    <OpsLayout
      title="AI Monitoring"
      description="Monitors hallucination, prompt/embedding drift, retrieval quality, latency, cost, accuracy, feedback score and business-KPI impact from the platform's own evaluations, RAG queries and feedback — raising incidents on breach."
      actions={
        <Button disabled={run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? "Running…" : "Run monitoring"}
        </Button>
      }
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-sm">Health: <span className={`font-semibold ${statusText((dash.data as any)?.health)}`}>{(dash.data as any)?.health ?? "—"}</span></div>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Hallucination" value={m.hallucination ?? "—"} />
          <MetricCard label="Retrieval quality" value={m.retrieval_quality ?? "—"} />
          <MetricCard label="Accuracy" value={m.accuracy ?? "—"} />
          <MetricCard label="Latency (ms)" value={m.latency ?? "—"} />
          <MetricCard label="Cost (USD)" value={m.cost ?? "—"} />
          <MetricCard label="Feedback score" value={m.feedback_score ?? "—"} />
          <MetricCard label="Drift" value={m.drift ?? "—"} />
          <MetricCard label="Open incidents" value={(dash.data as any)?.open_incident_count ?? "—"} />
        </div>
        <SectionCard title="Incidents">
          <StateWrap loading={incidents.isLoading} empty={!(incidents.data as any)?.incidents?.length} emptyMessage="No AI incidents.">
            <ul className="space-y-1 text-sm">
              {((incidents.data as any)?.incidents ?? []).map((i: any) => (
                <li key={i.incident_id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{i.type} <span className="text-xs text-muted-foreground">{i.description}</span></span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[10px]">{i.severity} · {i.status}</span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
