/**
 * NavigationProvider — shared state for the whole navigation system.
 *
 * Holds user navigation preferences (favourites, recent pages, pinned modules,
 * sidebar collapsed/width, active workspace) and the command-palette open state,
 * persists everything to localStorage per-browser, records recently-visited
 * pages automatically, and installs the global keyboard shortcuts.
 *
 * SSR-safe: initial render uses deterministic defaults; stored values are loaded
 * in an effect after mount, so server and first client render agree (no hydration
 * mismatch). Mounted once at the app root, wrapping <Outlet/>.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouterState } from "@tanstack/react-router";

import { getItemById, resolvePathToItem, type NavItem, type WorkspaceId } from "./registry";

const STORAGE_KEY = "nav:prefs:v1";
const MAX_RECENTS = 15;
const DEFAULT_WIDTH = 288;
const MIN_WIDTH = 220;
const MAX_WIDTH = 420;

interface StoredPrefs {
  favorites: string[];
  recents: string[];
  pinned: string[];
  collapsed: boolean;
  /** Full-screen / focus mode — the sidebar is hidden entirely (not just collapsed). */
  hidden: boolean;
  width: number;
  workspace: WorkspaceId;
}

const DEFAULTS: StoredPrefs = {
  favorites: [],
  recents: [],
  pinned: [],
  collapsed: false,
  hidden: false,
  width: DEFAULT_WIDTH,
  workspace: "all",
};

interface NavigationContextValue {
  hydrated: boolean;

  // Favourites.
  favorites: string[];
  favoriteItems: NavItem[];
  isFavorite: (id: string) => boolean;
  toggleFavorite: (id: string) => void;

  // Recents.
  recentItems: NavItem[];

  // Pinned modules.
  pinned: string[];
  isPinned: (moduleId: string) => boolean;
  togglePinned: (moduleId: string) => void;

  // Sidebar layout.
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  toggleCollapsed: () => void;
  /** Full-screen mode: the sidebar is hidden entirely for a distraction-free view. */
  hidden: boolean;
  setHidden: (v: boolean) => void;
  toggleHidden: () => void;
  width: number;
  setWidth: (v: number) => void;

  // Workspace.
  workspace: WorkspaceId;
  setWorkspace: (w: WorkspaceId) => void;

  // Command palette.
  paletteOpen: boolean;
  openPalette: () => void;
  closePalette: () => void;
  setPaletteOpen: (v: boolean) => void;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

const clampWidth = (w: number) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(w)));

function isTypingTarget(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || node.isContentEditable;
}

export function NavigationProvider({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const [prefs, setPrefs] = useState<StoredPrefs>(DEFAULTS);
  const [hydrated, setHydrated] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Load stored prefs once, after mount (client only).
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<StoredPrefs>;
        setPrefs({
          favorites: parsed.favorites ?? [],
          recents: parsed.recents ?? [],
          pinned: parsed.pinned ?? [],
          collapsed: parsed.collapsed ?? false,
          hidden: parsed.hidden ?? false,
          width: clampWidth(parsed.width ?? DEFAULT_WIDTH),
          workspace: parsed.workspace ?? "all",
        });
      }
    } catch {
      /* ignore corrupt storage */
    }
    setHydrated(true);
  }, []);

  // Persist on every change once hydrated (never clobber storage with defaults
  // before the initial load has run).
  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      /* ignore quota / private-mode errors */
    }
  }, [prefs, hydrated]);

  // Record recently-visited pages. Only registry-known pages are tracked, so
  // /login, /signup and unknown routes are ignored automatically.
  useEffect(() => {
    if (!hydrated) return;
    const item = resolvePathToItem(pathname);
    if (!item) return;
    setPrefs((p) => {
      if (p.recents[0] === item.id) return p;
      const recents = [item.id, ...p.recents.filter((id) => id !== item.id)].slice(0, MAX_RECENTS);
      return { ...p, recents };
    });
  }, [pathname, hydrated]);

  // ---- Actions -----------------------------------------------------------
  const toggleFavorite = useCallback((id: string) => {
    setPrefs((p) => ({
      ...p,
      favorites: p.favorites.includes(id)
        ? p.favorites.filter((f) => f !== id)
        : [...p.favorites, id],
    }));
  }, []);

  const togglePinned = useCallback((moduleId: string) => {
    setPrefs((p) => ({
      ...p,
      pinned: p.pinned.includes(moduleId)
        ? p.pinned.filter((m) => m !== moduleId)
        : [...p.pinned, moduleId],
    }));
  }, []);

  const setCollapsed = useCallback((v: boolean) => setPrefs((p) => ({ ...p, collapsed: v })), []);
  const toggleCollapsed = useCallback(() => setPrefs((p) => ({ ...p, collapsed: !p.collapsed })), []);
  const setHidden = useCallback((v: boolean) => setPrefs((p) => ({ ...p, hidden: v })), []);
  const toggleHidden = useCallback(() => setPrefs((p) => ({ ...p, hidden: !p.hidden })), []);
  const setWidth = useCallback((v: number) => setPrefs((p) => ({ ...p, width: clampWidth(v) })), []);
  const setWorkspace = useCallback((w: WorkspaceId) => setPrefs((p) => ({ ...p, workspace: w })), []);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  // ---- Global keyboard shortcuts ----------------------------------------
  const paletteOpenRef = useRef(paletteOpen);
  paletteOpenRef.current = paletteOpen;
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      const key = e.key.toLowerCase();

      // ⌘K / Ctrl+K — toggle palette. Ctrl/⌘+Shift+P — open palette.
      if (mod && key === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      if (mod && e.shiftKey && key === "p") {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }
      // Ctrl/⌘+B — collapse/expand sidebar.
      if (mod && key === "b") {
        e.preventDefault();
        setPrefs((p) => ({ ...p, collapsed: !p.collapsed }));
        return;
      }
      // Ctrl/⌘+\ — hide/show the sidebar entirely (full-screen / focus mode).
      if (mod && key === "\\") {
        e.preventDefault();
        setPrefs((p) => ({ ...p, hidden: !p.hidden }));
        return;
      }
      // Alt+Left / Alt+Right — history back / forward.
      if (e.altKey && key === "arrowleft") {
        e.preventDefault();
        window.history.back();
        return;
      }
      if (e.altKey && key === "arrowright") {
        e.preventDefault();
        window.history.forward();
        return;
      }
      // "/" — focus search (open palette) when not already typing somewhere.
      if (key === "/" && !mod && !e.altKey && !isTypingTarget(e.target) && !paletteOpenRef.current) {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ---- Derived -----------------------------------------------------------
  const favoriteItems = useMemo(
    () => prefs.favorites.map((id) => getItemById(id)).filter((x): x is NavItem => Boolean(x)),
    [prefs.favorites],
  );
  const recentItems = useMemo(
    () => prefs.recents.map((id) => getItemById(id)).filter((x): x is NavItem => Boolean(x)),
    [prefs.recents],
  );

  const value = useMemo<NavigationContextValue>(
    () => ({
      hydrated,
      favorites: prefs.favorites,
      favoriteItems,
      isFavorite: (id) => prefs.favorites.includes(id),
      toggleFavorite,
      recentItems,
      pinned: prefs.pinned,
      isPinned: (id) => prefs.pinned.includes(id),
      togglePinned,
      collapsed: prefs.collapsed,
      setCollapsed,
      toggleCollapsed,
      hidden: prefs.hidden,
      setHidden,
      toggleHidden,
      width: prefs.width,
      setWidth,
      workspace: prefs.workspace,
      setWorkspace,
      paletteOpen,
      openPalette,
      closePalette,
      setPaletteOpen,
    }),
    [
      hydrated,
      prefs,
      favoriteItems,
      recentItems,
      toggleFavorite,
      togglePinned,
      setCollapsed,
      toggleCollapsed,
      setHidden,
      toggleHidden,
      setWidth,
      setWorkspace,
      paletteOpen,
      openPalette,
      closePalette,
    ],
  );

  return <NavigationContext.Provider value={value}>{children}</NavigationContext.Provider>;
}

export function useNavigation(): NavigationContextValue {
  const ctx = useContext(NavigationContext);
  if (!ctx) {
    throw new Error("useNavigation must be used within a <NavigationProvider>");
  }
  return ctx;
}
