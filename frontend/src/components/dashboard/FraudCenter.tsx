import { ShieldAlert, Radio } from "lucide-react";
import { cn } from "@/lib/utils";

type Severity = "Low" | "Medium" | "High" | "Critical";

interface FraudAlertData {
  id: string | number;
  fraud_detected?: boolean;
  fraud_score?: number;
  anomaly_score?: number;
  amount?: number;
  created_at?: string;
  ai_analysis?: string;
  type?: string;
}

const SEV: Record<Severity, string> = {
  Low: "bg-info/10 text-info border-info/20",
  Medium: "bg-warning/10 text-warning border-warning/20",
  High: "bg-destructive/10 text-destructive border-destructive/20",
  Critical: "bg-destructive/20 text-destructive border-destructive/30",
};

function getSeverity(score: number): Severity {
  if (score >= 0.8) return "Critical";
  if (score >= 0.6) return "High";
  if (score >= 0.4) return "Medium";
  return "Low";
}

export function FraudCenter({ fraudData }: { fraudData?: FraudAlertData[] }) {
  const data = fraudData ? fraudData.map((item, idx) => ({
    id: item.id || `fraud-${idx}`,
    customer: `Account ${item.id || idx}`,
    type: item.type || "Anomaly Detection",
    severity: getSeverity(item.fraud_score ?? item.anomaly_score ?? 0),
    anomaly: (item.fraud_score ?? item.anomaly_score ?? 0) / 100,
    detectedAt: item.created_at ? new Date(item.created_at).toLocaleString() : new Date().toLocaleString(),
  })) : [];

  return (
    <div className="rounded-xl border border-border bg-card shadow-card">
      <div className="flex items-center justify-between border-b border-border p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-destructive/20 bg-destructive/10 text-destructive">
            <ShieldAlert className="h-4.5 w-4.5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold tracking-tight text-foreground">
              Fraud Intelligence Center
            </h3>
            <p className="text-xs text-muted-foreground">Live anomaly detection feed</p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-success/20 bg-success/10 px-2.5 py-1 text-[11px] font-medium text-success">
          <Radio className="h-3 w-3 animate-pulse" />
          Monitoring
        </span>
      </div>

      <ul className="divide-y divide-border">
        {data.length === 0 ? (
          <li className="flex items-center justify-center py-8 text-xs text-muted-foreground">
            No fraud checks available
          </li>
        ) : (
          data.map((a) => (
            <li
              key={a.id}
              className="flex items-center gap-4 p-4 transition-colors hover:bg-secondary/30"
            >
              <div className="relative">
                <div
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-full border text-[11px] font-semibold",
                    SEV[a.severity],
                  )}
                >
                  {Math.round(a.anomaly * 100)}
                </div>
                {a.severity === "Critical" && (
                  <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 animate-ping rounded-full bg-destructive" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className="truncate font-medium text-foreground">{a.customer}</span>
                  <span className="text-muted-foreground">·</span>
                  <span className="truncate text-muted-foreground">{a.type}</span>
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {a.id} · {a.detectedAt}
                </div>
              </div>
              <span
                className={cn(
                  "hidden rounded-md border px-2 py-0.5 text-xs font-medium sm:inline-flex",
                  SEV[a.severity],
                )}
              >
                {a.severity}
              </span>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
