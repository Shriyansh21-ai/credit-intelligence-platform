import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUpRight, CircleDot, Sparkles } from "lucide-react";

import { useProfile } from "@/lib/profile";

const stats = [
  { label: "Portfolio Exposure", value: "$1.84B", delta: "+3.2%" },
  { label: "Approval Rate", value: "68.4%", delta: "+4.1%" },
  { label: "Fraud Accuracy", value: "99.31%", delta: "+0.4%" },
];

function greeting(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/**
 * Compact, role-aware command hero. Trimmed ~25% in height vs. the previous
 * marketing-style block: a personalised greeting, a live date + system-status
 * strip, and denser inline stat chips — so KPIs sit closer to the fold.
 */
export function Hero() {
  const profile = useProfile();
  // Client-only clock to avoid SSR/first-render hydration mismatch.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const firstName = profile.displayName.split(" ")[0] || profile.username;
  const hello = now ? greeting(now.getHours()) : "Welcome back";
  const dateLabel = now
    ? now.toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
      })
    : "";

  return (
    <section className="relative overflow-hidden rounded-2xl border border-border bg-gradient-hero p-5 shadow-card md:p-6">
      <div className="absolute -right-24 -top-24 h-56 w-56 rounded-full bg-primary/10 blur-3xl" />
      <div className="absolute -bottom-28 left-1/3 h-56 w-56 rounded-full bg-accent/10 blur-3xl" />

      <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/50 px-2.5 py-1 text-[11px] text-muted-foreground backdrop-blur">
              <Sparkles className="h-3 w-3 text-primary" />
              Explainable AI
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-success/25 bg-success/10 px-2.5 py-1 text-[11px] font-medium text-success">
              <CircleDot className="h-3 w-3" />
              All systems operational
            </span>
          </div>

          <motion.h2
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mt-3 text-2xl font-semibold tracking-tight text-foreground md:text-[28px] md:leading-tight"
          >
            {hello}, <span className="gradient-text">{firstName}</span>
          </motion.h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {dateLabel ? `${dateLabel} · ` : ""}
            {profile.jobTitle
              ? `Here's your ${profile.jobTitle} overview.`
              : "Here's your risk & portfolio overview."}
          </p>
        </div>

        <div className="grid w-full grid-cols-3 gap-2.5 lg:w-auto">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 + i * 0.06 }}
              className="glass rounded-xl px-3 py-2.5 lg:min-w-[132px]"
            >
              <div className="truncate text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {s.label}
              </div>
              <div className="mt-1 text-lg font-semibold tracking-tight text-foreground tabular-nums">
                {s.value}
              </div>
              <div className="mt-0.5 inline-flex items-center gap-0.5 text-[11px] text-primary">
                <ArrowUpRight className="h-3 w-3" />
                {s.delta}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
