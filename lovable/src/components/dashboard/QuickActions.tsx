import { Brain, ShieldCheck, BarChart3, Download, ArrowRight } from "lucide-react";

const actions = [
  { label: "Run Credit Prediction", icon: Brain, primary: true },
  { label: "Perform Fraud Check", icon: ShieldCheck },
  { label: "View Analytics", icon: BarChart3 },
  { label: "Export Reports", icon: Download },
];

export function QuickActions() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">Quick Actions</h3>
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
          Shortcuts
        </span>
      </div>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
        {actions.map((a) => (
          <button
            key={a.label}
            className={
              a.primary
                ? "group inline-flex items-center justify-between gap-2 rounded-lg bg-gradient-primary px-4 py-3 text-sm font-medium text-primary-foreground shadow-glow transition-transform hover:-translate-y-0.5"
                : "group inline-flex items-center justify-between gap-2 rounded-lg border border-border bg-secondary/40 px-4 py-3 text-sm font-medium text-foreground transition-colors hover:border-ring/40 hover:bg-secondary"
            }
          >
            <span className="inline-flex items-center gap-2">
              <a.icon className="h-4 w-4" />
              {a.label}
            </span>
            <ArrowRight className="h-3.5 w-3.5 opacity-60 transition-transform group-hover:translate-x-0.5" />
          </button>
        ))}
      </div>
    </div>
  );
}
