/**
 * Global command palette (⌘K / Ctrl+K, or Ctrl+Shift+P).
 *
 * Fuzzy-searches every page in the navigation registry (title, module, keywords)
 * so typing "fraud", "portfolio", "policy" or "rag" instantly surfaces the right
 * pages. When the query is empty it shows the user's favourites and recent pages.
 * Full keyboard control: ↑/↓ to move, ↵ to open, ⌘↵ / ★ to toggle favourite,
 * Esc to close. Open/close state lives in NavigationProvider so the shortcut, the
 * top-bar search button and this component all stay in sync.
 *
 * Registry-driven and self-contained: no backend round-trip, so search is instant
 * and never points at a dead route.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { CornerDownLeft, Search, Star } from "lucide-react";

import { searchNavigation, useNavigation, type NavItem } from "@/navigation";
import { cn } from "@/lib/utils";

interface Row {
  item: NavItem;
  section: "Favorites" | "Recent" | "Results" | "All Pages";
}

export function CommandPalette() {
  const navigate = useNavigate();
  const { paletteOpen, setPaletteOpen, closePalette, favoriteItems, recentItems, isFavorite, toggleFavorite } =
    useNavigation();

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Reset + focus each time the palette opens.
  useEffect(() => {
    if (paletteOpen) {
      setQuery("");
      setActive(0);
      const t = setTimeout(() => inputRef.current?.focus(), 20);
      return () => clearTimeout(t);
    }
  }, [paletteOpen]);

  // Build the flat, ordered row list (with section grouping) for the current query.
  const rows = useMemo<Row[]>(() => {
    const q = query.trim();
    if (q) {
      return searchNavigation(q, 40).map((item) => ({ item, section: "Results" as const }));
    }
    const out: Row[] = [];
    const seen = new Set<string>();
    for (const item of favoriteItems) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      out.push({ item, section: "Favorites" });
    }
    for (const item of recentItems) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      out.push({ item, section: "Recent" });
    }
    // Fall back to a starter set so the palette is never empty on first use.
    if (out.length === 0) {
      for (const item of searchNavigation("", 8)) {
        out.push({ item, section: "All Pages" });
      }
    }
    return out;
  }, [query, favoriteItems, recentItems]);

  // Keep the active index in range and scrolled into view.
  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, rows.length - 1)));
  }, [rows.length]);
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-row="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function open(item: NavItem) {
    closePalette();
    if (/^https?:\/\//i.test(item.href)) window.location.href = item.href;
    else navigate({ to: item.href });
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (rows.length ? (a + 1) % rows.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (rows.length ? (a - 1 + rows.length) % rows.length : 0));
    } else if (e.key === "Enter" && rows[active]) {
      e.preventDefault();
      if (e.metaKey || e.ctrlKey) toggleFavorite(rows[active].item.id);
      else open(rows[active].item);
    } else if (e.key === "Escape") {
      e.preventDefault();
      closePalette();
    }
  }

  if (!paletteOpen) return null;

  let lastSection = "";

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center bg-black/40 px-4 pt-[12vh] backdrop-blur-sm duration-150 animate-in fade-in-0"
      onClick={() => setPaletteOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-xl border border-border bg-popover shadow-2xl duration-150 animate-in fade-in-0 zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 border-b border-border px-4">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search pages, modules, settings…"
            className="w-full bg-transparent py-3.5 text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>

        <ul ref={listRef} className="max-h-[22rem] overflow-y-auto py-1">
          {rows.length === 0 && (
            <li className="px-4 py-8 text-center text-sm text-muted-foreground">
              No pages match “{query}”.
            </li>
          )}
          {rows.map((row, i) => {
            const showHeader = row.section !== lastSection;
            lastSection = row.section;
            const Icon = row.item.icon;
            const fav = isFavorite(row.item.id);
            return (
              <li key={row.item.id}>
                {showHeader && (
                  <div className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    {row.section}
                  </div>
                )}
                <div
                  data-row={i}
                  onMouseEnter={() => setActive(i)}
                  className={cn(
                    "mx-1 flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm",
                    i === active ? "bg-accent text-accent-foreground" : "text-foreground",
                  )}
                  onClick={() => open(row.item)}
                >
                  <Icon className="h-4 w-4 shrink-0 opacity-80" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{row.item.title}</span>
                    <span className="block truncate text-[11px] text-muted-foreground">
                      {row.item.moduleTitle}
                      {row.item.description ? ` · ${row.item.description}` : ""}
                    </span>
                  </span>
                  <button
                    type="button"
                    aria-label={fav ? "Remove favourite" : "Add favourite"}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleFavorite(row.item.id);
                    }}
                    className="shrink-0 rounded p-1 text-muted-foreground hover:text-foreground"
                  >
                    <Star className={cn("h-3.5 w-3.5", fav && "fill-yellow-400 text-yellow-400")} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>

        <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-2 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <CornerDownLeft className="h-3 w-3" /> open · ↑↓ navigate · ⌘↵ favourite · esc close
          </span>
          <span>⌘K</span>
        </div>
      </div>
    </div>
  );
}
