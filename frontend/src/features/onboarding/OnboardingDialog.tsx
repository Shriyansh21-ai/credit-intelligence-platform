import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  BookOpen,
  Bot,
  Briefcase,
  LayoutDashboard,
  ShieldAlert,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useOnboarding } from "./useOnboarding";

interface Step {
  icon: LucideIcon;
  title: string;
  body: string;
  bullets?: { icon: LucideIcon; label: string }[];
}

const STEPS: Step[] = [
  {
    icon: Sparkles,
    title: "Welcome to AI Credit Intelligence",
    body: "The AI-native platform for enterprise credit, risk and lending — assess borrowers, detect fraud, and make explainable decisions in seconds. Here's a quick tour of what you can do.",
  },
  {
    icon: Briefcase,
    title: "Underwrite in seconds",
    body: "Run an Enterprise Assessment to score creditworthiness with machine learning, complete with risk banding, a recommendation and a confidence score — every number explainable and auditable.",
  },
  {
    icon: ShieldAlert,
    title: "Monitor risk continuously",
    body: "Track portfolio health, early-warning signals and fraud alerts across your book — and simulate what-if and stress scenarios before they hit the balance sheet.",
  },
  {
    icon: Bot,
    title: "Ask the AI Copilot",
    body: "Ask questions in plain language and get grounded, cited answers from your own platform data. The AI phrases the facts — it never invents the numbers.",
    bullets: [
      { icon: Briefcase, label: "Enterprise Assessment" },
      { icon: ShieldAlert, label: "Risk Intelligence" },
      { icon: Bot, label: "AI Copilot" },
      { icon: LayoutDashboard, label: "Executive Command Center" },
    ],
  },
];

/**
 * First-run onboarding overlay. Additive and self-contained: mounted once at the
 * app root, auto-opens on first visit, and is re-openable via `openOnboarding()`.
 */
export function OnboardingDialog() {
  const { open, setOpen, dismiss } = useOnboarding();
  const [index, setIndex] = useState(0);

  const step = STEPS[index];
  const isLast = index === STEPS.length - 1;
  const Icon = step.icon;

  function close() {
    dismiss();
    setIndex(0);
  }

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : close())}>
      <DialogContent className="max-w-lg overflow-hidden p-0" aria-describedby={undefined}>
        {/* Banner */}
        <div className="bg-gradient-hero px-6 pb-5 pt-7">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-primary shadow-glow">
            <Icon className="h-5 w-5 text-primary-foreground" strokeWidth={2.25} />
          </div>
        </div>

        <div className="px-6 pb-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={index}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.2 }}
            >
              <h2 className="text-lg font-semibold tracking-tight text-foreground">{step.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>

              {step.bullets && (
                <div className="mt-4 grid grid-cols-2 gap-2">
                  {step.bullets.map((b) => (
                    <div
                      key={b.label}
                      className="flex items-center gap-2 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-xs font-medium text-foreground"
                    >
                      <b.icon className="h-4 w-4 text-primary" />
                      {b.label}
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Step dots */}
          <div className="mt-6 flex items-center gap-1.5" aria-hidden>
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={
                  "h-1.5 rounded-full transition-all " +
                  (i === index ? "w-6 bg-primary" : "w-1.5 bg-border")
                }
              />
            ))}
          </div>

          {/* Actions */}
          <div className="mt-5 flex items-center justify-between gap-2">
            <Button variant="ghost" size="sm" onClick={close}>
              {isLast ? "Close" : "Skip tour"}
            </Button>
            <div className="flex items-center gap-2">
              {index > 0 && (
                <Button variant="outline" size="sm" onClick={() => setIndex((i) => i - 1)}>
                  Back
                </Button>
              )}
              {isLast ? (
                <>
                  <Button variant="outline" size="sm" asChild onClick={close}>
                    <Link to="/copilot">
                      <Bot className="mr-1.5 h-3.5 w-3.5" /> Open Copilot
                    </Link>
                  </Button>
                  <Button size="sm" asChild onClick={close}>
                    <Link to="/enterprise">
                      Run first assessment <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </>
              ) : (
                <Button size="sm" onClick={() => setIndex((i) => i + 1)}>
                  Next <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>

          <div className="mt-4 border-t border-border pt-3 text-center">
            <a
              href="https://github.com/Shriyansh21-ai/ai_credit_system/blob/main/docs/index.md"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              <BookOpen className="h-3.5 w-3.5" /> Read the documentation
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
