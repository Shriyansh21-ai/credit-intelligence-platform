import { useMemo } from "react";
import {
  AlertTriangle,
  Ban,
  PlugZap,
  RefreshCw,
  SearchX,
  ServerCrash,
  WifiOff,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { classifyError, makeErrorId, supportHref, type ErrorCategory } from "@/lib/errors";
import { Button } from "@/components/ui/button";

const ICONS: Record<ErrorCategory, LucideIcon> = {
  network: WifiOff,
  permission: Ban,
  notFound: SearchX,
  validation: AlertTriangle,
  server: ServerCrash,
  ai: AlertTriangle,
  connector: PlugZap,
  unknown: AlertTriangle,
};

/**
 * Enterprise error panel: friendly categorised message, a retry affordance, a
 * quotable error reference id and a support link. Drop-in replacement for raw
 * error text. Used by `StateWrap` and available standalone.
 */
export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const info = useMemo(() => classifyError(error), [error]);
  // A stable-per-mount reference id (permission errors don't need one).
  const ref = useMemo(
    () => (info.category === "permission" ? undefined : makeErrorId()),
    [info.category],
  );
  const Icon = ICONS[info.category];

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center",
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-destructive/30 bg-destructive/10 text-destructive">
        <Icon className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{info.title}</p>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">{info.message}</p>
      </div>
      <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
        {onRetry && (
          <Button size="sm" onClick={onRetry}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Try again
          </Button>
        )}
        <Button size="sm" variant="outline" asChild>
          <a href={supportHref(ref, `Support: ${info.title}`)}>Contact support</a>
        </Button>
      </div>
      {ref && (
        <p className="text-xs text-muted-foreground">
          Reference <span className="font-mono text-foreground">{ref}</span>
        </p>
      )}
    </div>
  );
}
