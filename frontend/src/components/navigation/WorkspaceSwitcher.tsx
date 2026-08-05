/**
 * Workspace selector. Switching workspace filters which modules the sidebar
 * shows (e.g. "ML" hides Treasury pages) without deleting anything — "All
 * Workspaces" shows everything. Preference is persisted per-browser.
 */

import { useEffect, useRef, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { useNavigation, WORKSPACES } from "@/navigation";
import { cn } from "@/lib/utils";

export function WorkspaceSwitcher({ collapsed = false }: { collapsed?: boolean }) {
  const { workspace, setWorkspace } = useNavigation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = WORKSPACES.find((w) => w.id === workspace) ?? WORKSPACES[0];
  const Icon = current.icon;

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
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={collapsed ? `Workspace: ${current.label}` : undefined}
        className={cn(
          "flex w-full items-center gap-2 rounded-lg border border-sidebar-border bg-sidebar-accent/40 px-2.5 py-2 text-left text-sm transition-colors hover:bg-sidebar-accent",
          collapsed && "justify-center px-0",
        )}
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gradient-primary text-primary-foreground">
          <Icon className="h-3.5 w-3.5" />
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-medium text-sidebar-foreground">
                {current.label}
              </span>
              <span className="block text-[10px] text-muted-foreground">Workspace</span>
            </span>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          </>
        )}
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 overflow-hidden rounded-lg border border-border bg-popover shadow-xl duration-150 animate-in fade-in-0 zoom-in-95"
        >
          {WORKSPACES.map((w) => {
            const WIcon = w.icon;
            const active = w.id === workspace;
            return (
              <button
                key={w.id}
                role="option"
                aria-selected={active}
                onClick={() => {
                  setWorkspace(w.id);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-accent",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <WIcon className="h-4 w-4 shrink-0 opacity-80" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{w.label}</span>
                  <span className="block truncate text-[10px] text-muted-foreground">
                    {w.description}
                  </span>
                </span>
                {active && <Check className="h-4 w-4 shrink-0 text-primary" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
