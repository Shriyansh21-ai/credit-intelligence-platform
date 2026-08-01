import { createFileRoute } from "@tanstack/react-router";
import { Clock } from "lucide-react";

import {
  MetricCard,
  RiskLayout,
  SectionCard,
  SeverityBadge,
  StateWrap,
  useUserAlerts,
} from "@/features/risk-intelligence";

export const Route = createFileRoute("/alerts")({
  component: AlertsPage,
});

const SEVERITY_ORDER = ["critical", "high", "medium", "low"];

function AlertsPage() {
  const q = useUserAlerts();
  const alerts = q.data?.alerts ?? [];

  const counts = SEVERITY_ORDER.reduce<Record<string, number>>((acc, s) => {
    acc[s] = alerts.filter((a) => a.severity === s).length;
    return acc;
  }, {});

  return (
    <RiskLayout
      title="Risk Alerts"
      description="Proactive early-warning alerts across your portfolio — deterioration signals, conduct red flags and covenant risks, each with a suggested analyst action and timeline."
    >
      <StateWrap
        loading={q.isLoading}
        error={(q.error as Error)?.message || null}
        empty={!q.isLoading && alerts.length === 0}
        emptyMessage="No active alerts across your portfolio."
      >
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {SEVERITY_ORDER.map((s) => (
              <MetricCard
                key={s}
                label={`${s[0].toUpperCase()}${s.slice(1)}`}
                value={counts[s]}
                tone={
                  s === "critical" ? "text-red-500"
                    : s === "high" ? "text-orange-500"
                    : s === "medium" ? "text-amber-500"
                    : "text-sky-500"
                }
              />
            ))}
          </div>

          <SectionCard title="Active alerts" description={`${alerts.length} alert(s), highest priority first.`}>
            <ul className="space-y-3">
              {alerts.map((a, i) => (
                <li key={i} className="rounded-lg border border-border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{a.title}</div>
                      <div className="mt-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                        {a.category.replace(/_/g, " ")}
                      </div>
                    </div>
                    <SeverityBadge severity={a.severity} />
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{a.business_impact}</p>
                  <div className="mt-3 rounded-md bg-muted/50 p-2.5 text-xs text-foreground">
                    <span className="font-medium">Suggested action:</span> {a.suggested_action}
                  </div>
                  <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" /> {a.timeline}
                  </div>
                </li>
              ))}
            </ul>
          </SectionCard>
        </div>
      </StateWrap>
    </RiskLayout>
  );
}
