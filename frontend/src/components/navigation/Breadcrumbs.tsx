/**
 * Breadcrumb trail (Dashboard › Module › Page), generated from the navigation
 * registry for the current route. Every crumb except the last is a clickable
 * link. Rendered by AppShell above the page header.
 */

import { Link, useRouterState } from "@tanstack/react-router";
import { ChevronRight, Home } from "lucide-react";

import { breadcrumbsFor } from "@/navigation";
import { cn } from "@/lib/utils";

export function Breadcrumbs({ className }: { className?: string }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const crumbs = breadcrumbsFor(pathname);

  // Nothing useful to show on the dashboard itself.
  if (crumbs.length <= 1) return null;

  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0", className)}>
      <ol className="flex items-center gap-1 text-xs text-muted-foreground">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <li key={`${crumb.label}-${i}`} className="flex min-w-0 items-center gap-1">
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-60" aria-hidden />}
              {i === 0 && <Home className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />}
              {crumb.href && !isLast ? (
                <Link
                  to={crumb.href}
                  className="truncate rounded px-1 py-0.5 transition-colors hover:text-foreground"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span
                  className={cn("truncate px-1 py-0.5", isLast && "font-medium text-foreground")}
                  aria-current={isLast ? "page" : undefined}
                >
                  {crumb.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
