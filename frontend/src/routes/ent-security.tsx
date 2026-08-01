import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useSecurityDashboard, useSecurityEvents, useAnalyzeSession } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-security")({ component: SecurityPage });

function SecurityPage() {
  const dash = useSecurityDashboard();
  const events = useSecurityEvents();
  const analyze = useAnalyzeSession();
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Security Center" description="Zero-trust console: session monitoring, threat & anomaly detection, device trust, behaviour analytics, privilege-escalation detection, access reviews, key rotation and a compliance dashboard.">
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          {dash.data && ["posture", "security_score", "open_events", "critical_events"].map((k) => (
            <div key={k} className="rounded border bg-card p-3"><div className="text-xs text-muted-foreground">{k.replace(/_/g, " ")}</div><div className="text-lg font-semibold">{String(dash.data[k])}</div></div>
          ))}
        </div>
        <SectionCard title="Analyze a session (zero-trust)">
          <div className="flex flex-wrap gap-2">
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => analyze.mutate({ subject_ref: "user@x.com", failed_logins: 6, new_device: true, impossible_travel: true }, { onSuccess: (r) => setOut(r) })}>Simulate suspicious login</button>
            <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => analyze.mutate({ subject_ref: "user@x.com", failed_logins: 0 }, { onSuccess: (r) => setOut(r) })}>Simulate normal login</button>
          </div>
          {out && <pre className="mt-2 rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2)}</pre>}
        </SectionCard>
        <SectionCard title="Security events">
          <StateWrap loading={events.isLoading} empty={!(events.data?.events?.length)}>
            <ul className="space-y-1 text-sm">{events.data?.events?.map((e: any) => (
              <li key={e.event_id} className="flex justify-between border-b border-border/50 py-1">
                <span>{e.event_type} <span className="text-xs text-muted-foreground">{e.subject_ref}</span></span>
                <span className="text-xs text-muted-foreground">{e.severity} · {e.status}</span>
              </li>))}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
