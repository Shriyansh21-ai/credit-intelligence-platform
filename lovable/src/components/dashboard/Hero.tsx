import { motion } from "framer-motion";
import { ArrowUpRight, Sparkles } from "lucide-react";

const stats = [
  { label: "Total Portfolio Exposure", value: "$1.84B", delta: "+3.2%" },
  { label: "Approval Rate", value: "68.4%", delta: "+4.1%" },
  { label: "Fraud Detection Accuracy", value: "99.31%", delta: "+0.4%" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden rounded-2xl border border-border bg-gradient-hero p-6 shadow-card md:p-8">
      <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
      <div className="absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />

      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Explainable AI · Real-time scoring
          </div>
          <motion.h2
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mt-4 text-3xl font-semibold tracking-tight text-foreground md:text-4xl lg:text-[40px] lg:leading-[1.1]"
          >
            AI Credit Intelligence <span className="gradient-text">Platform</span>
          </motion.h2>
          <p className="mt-3 max-w-xl text-sm text-muted-foreground md:text-base">
            Monitor credit risk, detect fraud, and analyze portfolio performance with explainable AI
            — built for risk teams that move fast.
          </p>
        </div>

        <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-3 lg:w-auto">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.08 }}
              className="glass rounded-xl p-4 lg:min-w-[180px]"
            >
              <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {s.label}
              </div>
              <div className="mt-1.5 text-xl font-semibold tracking-tight text-foreground">
                {s.value}
              </div>
              <div className="mt-1 inline-flex items-center gap-1 text-xs text-primary">
                <ArrowUpRight className="h-3 w-3" />
                {s.delta} vs last quarter
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
