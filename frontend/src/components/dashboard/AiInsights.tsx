import { motion } from "framer-motion";
import { Sparkles, TrendingUp, AlertTriangle, Info } from "lucide-react";
import { insights } from "@/lib/dashboard-data";
import { cn } from "@/lib/utils";

const ICONS = {
  positive: TrendingUp,
  neutral: Info,
  warning: AlertTriangle,
};

const TONES = {
  positive: "border-success/20 bg-success/5 text-success",
  neutral: "border-info/20 bg-info/5 text-info",
  warning: "border-warning/20 bg-warning/5 text-warning",
};

export function AiInsights() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold tracking-tight text-foreground">AI Insights</h3>
        </div>
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
          Updated 2m ago
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {insights.map((i, idx) => {
          const Icon = ICONS[i.tone];
          return (
            <motion.div
              key={i.title}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="group relative overflow-hidden rounded-xl border border-border bg-secondary/30 p-4 transition-colors hover:border-ring/30"
            >
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
                    TONES[i.tone],
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-sm font-medium text-foreground">{i.title}</div>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{i.body}</p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
