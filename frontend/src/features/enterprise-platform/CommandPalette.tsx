/**
 * Global command palette (M1 Enterprise UX).
 *
 * A ⌘K / Ctrl-K command palette + global search that navigates every module.
 * Self-contained and additive: mounted once at the app root. Commands are served
 * by `/api/ent/ux/commands` so the catalog stays in step with the backend and no
 * navigation target is ever a dead placeholder.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { useCommandCatalog } from "./hooks";

type Command = { id: string; label: string; group: string; href: string };

export function CommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const catalog = useCommandCatalog();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);

  const commands: Command[] = (catalog.data?.commands ?? []) as Command[];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.group.toLowerCase().includes(q),
    );
  }, [commands, query]);

  function run(cmd: Command) {
    setOpen(false);
    if (cmd.href) {
      // External links use a full navigation; internal routes use fast client-side nav.
      if (/^https?:\/\//i.test(cmd.href)) {
        window.location.href = cmd.href;
      } else {
        navigate({ to: cmd.href });
      }
    } else if (cmd.id === "action-toggle-theme") {
      const root = document.documentElement;
      root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center bg-black/40 pt-[12vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-xl border border-border bg-popover shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, filtered.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && filtered[active]) {
              run(filtered[active]);
            }
          }}
          placeholder="Search commands, pages, actions…"
          className="w-full border-b border-border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
        />
        <ul className="max-h-80 overflow-y-auto py-1">
          {filtered.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-muted-foreground">No results</li>
          )}
          {filtered.map((cmd, i) => (
            <li key={cmd.id}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={() => run(cmd)}
                className={`flex w-full items-center justify-between px-4 py-2 text-left text-sm ${
                  i === active ? "bg-accent text-accent-foreground" : "text-foreground"
                }`}
              >
                <span>{cmd.label}</span>
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  {cmd.group}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="flex items-center justify-between border-t border-border px-4 py-2 text-[10px] text-muted-foreground">
          <span>↑↓ navigate · ↵ open · esc close</span>
          <span>⌘K</span>
        </div>
      </div>
    </div>
  );
}
