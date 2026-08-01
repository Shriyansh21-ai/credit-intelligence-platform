import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

interface SectionCardProps {
  step: number;
  title: string;
  description: string;
  icon: LucideIcon;
  children: ReactNode;
}

/** A titled, numbered section wrapper used to structure the assessment form. */
export function SectionCard({ step, title, description, icon: Icon, children }: SectionCardProps) {
  return (
    <section className="rounded-xl border border-border bg-card shadow-card">
      <header className="flex items-start gap-3 border-b border-border px-5 py-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-secondary/60 text-foreground">
          <Icon className="h-4.5 w-4.5" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Section {step}
            </span>
          </div>
          <h2 className="text-sm font-semibold tracking-tight text-foreground">{title}</h2>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </header>
      <div className="grid gap-x-5 gap-y-4 p-5 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
    </section>
  );
}
