import { createFileRoute } from "@tanstack/react-router";

import {
  Bar,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  titleCase,
  useComplianceMatrix,
  useRunScan,
  useSecurityDashboard,
} from "@/features/security-compliance";

export const Route = createFileRoute("/security-dashboard")({ component: SecurityDashboardPage });

// -- small typed accessors over the loosely-typed API payloads --------------
type Json = Record<string, unknown>;
const obj = (v: unknown): Json => (v && typeof v === "object" ? (v as Json) : {});
const num = (v: unknown): number => (typeof v === "number" ? v : 0);
const str = (v: unknown): string => (typeof v === "string" ? v : "");
const arr = (v: unknown): Json[] => (Array.isArray(v) ? (v as Json[]) : []);

const GRADE_TONE: Record<string, string> = {
  "A+": "text-emerald-500", A: "text-emerald-500", "A-": "text-emerald-500",
  "B+": "text-lime-500", B: "text-lime-500", "B-": "text-lime-500",
  "C+": "text-amber-500", C: "text-amber-500", D: "text-orange-500", F: "text-red-500",
};

const SEV_TONE: Record<string, string> = {
  critical: "text-red-500", high: "text-orange-500", medium: "text-amber-500",
  low: "text-lime-500", info: "text-muted-foreground",
};

function scoreTone(score: number): string {
  if (score >= 90) return "bg-emerald-500";
  if (score >= 75) return "bg-lime-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-red-500";
}

function SecurityDashboardPage() {
  const { data, isLoading, error } = useSecurityDashboard();
  const { data: matrix } = useComplianceMatrix();
  const runScan = useRunScan();

  const dash = obj(data);
  const posture = obj(dash.posture);
  const dimensions = obj(posture.dimensions);
  const findings = obj(dash.findings);
  const bySeverity = obj(findings.by_severity);
  const risk = obj(dash.risk_register);
  const topRisks = arr(risk.top);
  const privacy = obj(dash.privacy);
  const secrets = obj(dash.secrets);
  const sessions = obj(dash.sessions);
  const recentScans = arr(dash.recent_scans);
  const overall = num(posture.overall_score);
  const grade = str(posture.grade) || "F";

  const frameworks = arr(obj(matrix).frameworks);

  return (
    <OpsLayout
      title="Security & Compliance Center"
      description="Enterprise security posture, compliance readiness, findings, risk register and privacy operations — Stage 4."
    >
      <StateWrap
        loading={isLoading}
        error={(error as Error)?.message ?? null}
        empty={!data && !isLoading}
        emptyMessage="Security dashboard permission (sec.dashboard.view) is required to view this page."
      >
        <div className="space-y-6">
          {/* Posture headline */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <MetricCard
              label="Security Posture"
              value={`${overall.toFixed(1)}`}
              sub={<span className={GRADE_TONE[grade] ?? "text-muted-foreground"}>Grade {grade}</span>}
              tone={GRADE_TONE[grade]}
            />
            <MetricCard
              label="Open Findings"
              value={num(findings.open_total)}
              tone={num(findings.open_total) ? "text-amber-500" : "text-emerald-500"}
            />
            <MetricCard
              label="Critical Findings"
              value={num(bySeverity.critical)}
              tone={num(bySeverity.critical) ? "text-red-500" : "text-emerald-500"}
            />
            <MetricCard
              label="Open Risks"
              value={num(risk.open_total)}
              tone={num(risk.open_total) ? "text-amber-500" : undefined}
            />
            <MetricCard
              label="Compliance Readiness"
              value={`${num(obj(matrix).overall_readiness_score).toFixed(0)}%`}
              sub={titleCase(str(obj(matrix).overall_readiness))}
            />
          </div>

          {/* Action bar */}
          <div className="flex flex-wrap items-center gap-2">
            {["full", "owasp", "authz", "tenant", "secrets", "supply_chain", "container", "ai_security", "ml_security"].map((t) => (
              <button
                key={t}
                onClick={() => runScan.mutate(t)}
                disabled={runScan.isPending}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
              >
                Run {titleCase(t.replace("_", " "))} scan
              </button>
            ))}
            {runScan.isPending && <span className="text-xs text-muted-foreground">Running…</span>}
          </div>

          {/* Posture dimensions */}
          <SectionCard title="Posture by dimension" description="Weighted contribution of each security domain to the overall score.">
            <div className="grid gap-3 md:grid-cols-2">
              {Object.entries(dimensions).map(([name, value]) => {
                const v = num(value);
                return (
                  <Bar
                    key={name}
                    label={titleCase(name.replace(/_/g, " "))}
                    display={v.toFixed(0)}
                    fraction={v / 100}
                    tone={scoreTone(v)}
                  />
                );
              })}
            </div>
          </SectionCard>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Findings by severity */}
            <SectionCard title="Open findings by severity">
              <div className="space-y-2">
                {(["critical", "high", "medium", "low", "info"] as const).map((sev) => (
                  <div key={sev} className="flex items-center justify-between text-sm">
                    <span className={SEV_TONE[sev]}>{titleCase(sev)}</span>
                    <span className="font-mono">{num(bySeverity[sev])}</span>
                  </div>
                ))}
              </div>
            </SectionCard>

            {/* Top risks */}
            <SectionCard title="Top risk register entries" description="Highest inherent-risk items.">
              {topRisks.length === 0 ? (
                <p className="text-sm text-muted-foreground">No open risks recorded.</p>
              ) : (
                <div className="space-y-2">
                  {topRisks.map((r, i) => (
                    <div key={i} className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate">{str(r.title)}</span>
                      <span className="shrink-0 font-mono text-muted-foreground">
                        {num(r.inherent_score)} · {titleCase(str(r.inherent_level))}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>

          {/* Compliance matrix */}
          <SectionCard title="Compliance readiness" description="Readiness across mapped frameworks (SOC 2, ISO 27001, GDPR, PCI DSS, RBI, NIST CSF).">
            <div className="grid gap-3 md:grid-cols-2">
              {frameworks.map((f, i) => {
                const v = num(f.score);
                return (
                  <Bar
                    key={i}
                    label={str(f.name)}
                    display={`${v.toFixed(0)}%`}
                    fraction={v / 100}
                    tone={scoreTone(v)}
                  />
                );
              })}
            </div>
          </SectionCard>

          {/* Operational counters */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Open Privacy Requests" value={num(privacy.open_requests)} />
            <MetricCard
              label="Insecure Critical Secrets"
              value={num(secrets.insecure_critical)}
              tone={num(secrets.insecure_critical) ? "text-red-500" : "text-emerald-500"}
            />
            <MetricCard label="Active Sessions" value={num(sessions.active_sessions)} />
            <MetricCard label="Registered Devices" value={num(sessions.devices)} />
          </div>

          {/* Recent scans */}
          <SectionCard title="Recent security scans">
            {recentScans.length === 0 ? (
              <p className="text-sm text-muted-foreground">No scans run yet. Use the actions above to run one.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">When</th>
                      <th className="py-2 pr-3 font-medium">Type</th>
                      <th className="py-2 pr-3 font-medium">Score</th>
                      <th className="py-2 pr-3 font-medium">Grade</th>
                      <th className="py-2 font-medium">Findings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentScans.map((s, i) => (
                      <tr key={i} className="border-b border-border/60 last:border-0">
                        <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">
                          {str(s.created_at) ? new Date(str(s.created_at)).toLocaleString() : "-"}
                        </td>
                        <td className="py-2 pr-3">{titleCase(str(s.scan_type).replace("_", " "))}</td>
                        <td className="py-2 pr-3 font-mono">{num(s.score).toFixed(0)}</td>
                        <td className="py-2 pr-3">{str(s.grade)}</td>
                        <td className="py-2">
                          {num(s.findings_count)}
                          {num(s.critical_count) > 0 && (
                            <span className="ml-1 text-red-500">({num(s.critical_count)} crit)</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>
        </div>
      </StateWrap>
    </OpsLayout>
  );
}
