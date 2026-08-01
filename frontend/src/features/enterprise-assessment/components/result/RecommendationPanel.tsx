import { CalendarClock, Landmark, Percent, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Recommendation } from "../../types";

function Line({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-border/70 py-3 last:border-b-0">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-secondary/50 text-muted-foreground">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className="text-sm text-foreground">{value}</div>
      </div>
    </div>
  );
}

export function RecommendationPanel({ recommendation }: { recommendation: Recommendation }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <h3 className="text-sm font-semibold tracking-tight text-foreground">Credit Recommendation</h3>
      <div className="mt-2">
        <Line icon={Landmark} label="Facility guidance" value={recommendation.loan_recommendation} />
        <Line icon={Percent} label="Indicative pricing" value={recommendation.interest_rate_recommendation} />
        <Line icon={CalendarClock} label="Suggested tenure" value={recommendation.loan_tenure_recommendation} />
        <Line icon={ShieldCheck} label="Collateral posture" value={recommendation.collateral_recommendation} />
        <Line icon={ShieldCheck} label="Monitoring" value={recommendation.monitoring} />
      </div>
    </div>
  );
}
