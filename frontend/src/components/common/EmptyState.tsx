import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Polished, reusable empty state: an illustration, a title, an explanatory
 * description, an optional CTA row (primary action + doc/demo shortcuts) and an
 * optional footer tip. Replaces bare "no data" placeholders across the app.
 */
export function EmptyState({
  icon: Icon = Inbox,
  title = "Nothing here yet",
  description,
  action,
  footer,
  className,
}: {
  icon?: LucideIcon;
  title?: ReactNode;
  description?: ReactNode;
  /** CTA row — e.g. a primary button plus a "View docs" / "Load demo data" link. */
  action?: ReactNode;
  /** Optional smaller helper/tip line under the actions. */
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-card p-10 text-center",
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-border bg-secondary/50 text-muted-foreground">
        <Icon className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description && (
          <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && (
        <div className="mt-1 flex flex-wrap items-center justify-center gap-2">{action}</div>
      )}
      {footer && <div className="max-w-md text-xs text-muted-foreground">{footer}</div>}
    </div>
  );
}
