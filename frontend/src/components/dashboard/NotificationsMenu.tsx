/**
 * Top-bar notifications dropdown. In Demo Mode it surfaces a realistic activity
 * feed (covenant breaches, exposure moves, model drift, treasury, ESG, committee,
 * fraud) coherent with the demo book; otherwise it shows an empty "all caught up"
 * state. Presentation only — no backend calls.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  ShieldAlert,
  TrendingUp,
  Waves,
  Wallet,
  FileText,
  Leaf,
  CheckCircle2,
  Gavel,
  type LucideIcon,
} from "lucide-react";

import { isDemoMode } from "@/lib/demo";
import { NOTIFICATIONS, type NotificationSeverity } from "@/lib/demo/enterprise-data";
import { cn } from "@/lib/utils";

const CATEGORY_ICON: Record<string, LucideIcon> = {
  Covenant: ShieldAlert,
  Fraud: ShieldAlert,
  Exposure: TrendingUp,
  Treasury: Wallet,
  "Model Risk": Waves,
  Committee: Gavel,
  Documents: FileText,
  ESG: Leaf,
  Portfolio: CheckCircle2,
};

const SEVERITY_STYLE: Record<NotificationSeverity, string> = {
  critical: "bg-destructive/10 text-destructive",
  warning: "bg-warning/10 text-warning",
  info: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
};

function timeAgo(iso: string): string {
  const diff = Date.parse("2026-07-28T09:30:00Z") - Date.parse(iso);
  const days = Math.round(diff / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

export function NotificationsMenu() {
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [demo, setDemo] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => setDemo(isDemoMode()), []);

  const items = useMemo(() => (demo ? NOTIFICATIONS : []), [demo]);
  const unread = items.filter((n) => n.unread && !dismissed.has(n.id)).length;

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        aria-expanded={open}
        className="relative rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-[calc(100%+8px)] z-50 w-[22rem] overflow-hidden rounded-xl border border-border bg-popover shadow-2xl duration-150 animate-in fade-in-0 zoom-in-95">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="text-sm font-semibold text-foreground">Notifications</div>
            {unread > 0 && (
              <button
                onClick={() => setDismissed(new Set(items.map((n) => n.id)))}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-[24rem] overflow-y-auto">
            {items.length === 0 && (
              <li className="px-4 py-10 text-center text-sm text-muted-foreground">
                You’re all caught up.
              </li>
            )}
            {items.map((n) => {
              const Icon = CATEGORY_ICON[n.category] ?? Bell;
              const isUnread = n.unread && !dismissed.has(n.id);
              return (
                <li
                  key={n.id}
                  className={cn(
                    "flex gap-3 border-b border-border/60 px-4 py-3 last:border-0",
                    isUnread && "bg-accent/30",
                  )}
                >
                  <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", SEVERITY_STYLE[n.severity])}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-foreground">{n.title}</span>
                      <span className="shrink-0 text-[10px] text-muted-foreground">{timeAgo(n.created_at)}</span>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{n.detail}</p>
                  </div>
                  {isUnread && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />}
                </li>
              );
            })}
          </ul>
          <div className="border-t border-border px-4 py-2 text-center text-[11px] text-muted-foreground">
            {items.length} recent {items.length === 1 ? "event" : "events"}
          </div>
        </div>
      )}
    </div>
  );
}
