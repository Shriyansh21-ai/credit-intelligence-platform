/**
 * Enterprise navigation sidebar.
 *
 * Generated entirely from the navigation registry (no hardcoded links). Features:
 *  - Expanded / collapsed (icon-rail) modes, hover-to-expand when collapsed, and
 *    a drag-to-resize handle. All persisted per-user via NavigationProvider.
 *  - Smart single-open accordion: only the active module is expanded.
 *  - Favourites and Recent pages pinned to the top; pinnable modules.
 *  - Workspace filtering (e.g. the ML workspace hides Treasury pages) — nothing
 *    is removed, only filtered.
 *  - Search launcher (opens the ⌘K command palette).
 *
 * The same {open, onClose} contract as before is preserved, so every call-site
 * (AppShell, the operations/risk layouts and the handful of pages that mount the
 * sidebar directly) keeps working untouched.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  ChevronDown,
  LogOut,
  Pin,
  PinOff,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sparkles,
  Star,
  X,
  type LucideIcon,
} from "lucide-react";

import {
  moduleInWorkspace,
  NAV_MODULES,
  resolvePathToItem,
  useNavigation,
  type NavItem,
  type NavModule,
} from "@/navigation";
import { WorkspaceSwitcher } from "@/components/navigation/WorkspaceSwitcher";
import { useProfile } from "@/lib/profile";
import { cn } from "@/lib/utils";

const RAIL_WIDTH = 68;

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const { collapsed, hidden, width, setWidth, hydrated } = useNavigation();
  const [hovered, setHovered] = useState(false);
  const resizingRef = useRef(false);

  // Before hydration, always render expanded defaults so SSR and the first client
  // render agree (avoids collapsed/expanded flicker mismatch).
  const effectiveCollapsed = hydrated ? collapsed && !hovered : false;
  const flowWidth = hydrated && collapsed ? RAIL_WIDTH : width;
  const panelWidth = effectiveCollapsed ? RAIL_WIDTH : width;

  // Drag-to-resize (expanded mode only).
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!resizingRef.current) return;
      setWidth(e.clientX);
    }
    function onUp() {
      if (resizingRef.current) {
        resizingRef.current = false;
        document.body.style.userSelect = "";
        document.body.style.cursor = "";
      }
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [setWidth]);

  function startResize(e: React.MouseEvent) {
    e.preventDefault();
    resizingRef.current = true;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  }

  return (
    <>
      {/* Mobile drawer overlay */}
      {open && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-background/70 backdrop-blur-sm lg:hidden"
          aria-hidden
        />
      )}

      {/* Mobile drawer (always full width, never collapsed) */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 transform border-r border-sidebar-border bg-sidebar transition-transform duration-300 lg:hidden",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <SidebarBody collapsed={false} onNavigate={onClose} onClose={onClose} mobile />
      </aside>

      {/* Desktop sidebar: a flow spacer of `flowWidth`, with a fixed panel that can
          hover-expand over the content without shifting layout. In full-screen
          (focus) mode the entire desktop sidebar is removed so the content spans
          the full width; the mobile drawer and the top-bar restore button remain. */}
      {!(hydrated && hidden) && (
        <aside
          className="relative hidden shrink-0 lg:block"
          style={{ width: flowWidth }}
          aria-label="Primary navigation"
        >
          <div
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            className={cn(
              "fixed inset-y-0 left-0 z-30 flex h-screen flex-col border-r border-sidebar-border bg-sidebar",
              !resizingRef.current && "transition-[width] duration-200 ease-out",
            )}
            style={{ width: panelWidth }}
          >
            <SidebarBody collapsed={effectiveCollapsed} />
            {/* Resize handle (expanded only) */}
            {!effectiveCollapsed && (
              <div
                onMouseDown={startResize}
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize sidebar"
                className="absolute inset-y-0 right-0 z-40 w-1 cursor-col-resize hover:bg-primary/40"
              />
            )}
          </div>
        </aside>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------

function SidebarBody({
  collapsed,
  onNavigate,
  onClose,
  mobile,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
  onClose?: () => void;
  mobile?: boolean;
}) {
  const {
    toggleCollapsed,
    openPalette,
    workspace,
    favoriteItems,
    recentItems,
    isFavorite,
    toggleFavorite,
    pinned,
    togglePinned,
  } = useNavigation();

  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const activeItem = useMemo(() => resolvePathToItem(pathname), [pathname]);
  const activeModuleId = activeItem?.moduleId;

  // Single-open accordion: only the active module is expanded; user can switch.
  const [openModule, setOpenModule] = useState<string | undefined>(activeModuleId);
  useEffect(() => {
    if (activeModuleId) setOpenModule(activeModuleId);
  }, [activeModuleId]);

  const visibleModules = useMemo(
    () => NAV_MODULES.filter((m) => moduleInWorkspace(m, workspace)),
    [workspace],
  );
  const pinnedModules = useMemo(() => NAV_MODULES.filter((m) => pinned.includes(m.id)), [pinned]);
  const unpinnedVisible = visibleModules.filter((m) => !pinned.includes(m.id));

  function handleNavigate() {
    onNavigate?.();
  }

  // ---- Collapsed icon rail --------------------------------------------------
  if (collapsed) {
    return (
      <div className="flex h-full flex-col">
        <RailHeader />
        <div className="hide-scrollbar flex flex-1 flex-col items-center gap-1 overflow-y-auto px-2 py-2">
          <RailButton icon={Search} label="Search (⌘K)" onClick={openPalette} />
          {favoriteItems.length > 0 && <RailDivider />}
          {favoriteItems.map((item) => (
            <RailLink key={item.id} item={item} active={item.id === activeItem?.id} onNavigate={handleNavigate} />
          ))}
          <RailDivider />
          {visibleModules.map((m) => (
            <RailLink
              key={m.id}
              item={m.items[0]}
              icon={m.icon}
              label={m.title}
              active={m.id === activeModuleId}
              onNavigate={handleNavigate}
            />
          ))}
        </div>
        <RailFooter />
      </div>
    );
  }

  // ---- Expanded body --------------------------------------------------------
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4">
        <Link to="/" onClick={handleNavigate} className="flex items-center gap-2.5">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-primary shadow-glow">
            <Sparkles className="h-[1.125rem] w-[1.125rem] text-primary-foreground" strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight text-sidebar-foreground">AI Credit</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Intelligence</div>
          </div>
        </Link>
        {mobile ? (
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
            aria-label="Close menu"
          >
            <X className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={toggleCollapsed}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
            aria-label="Collapse sidebar"
            title="Collapse sidebar (Ctrl+B)"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Search launcher + workspace switcher */}
      <div className="space-y-2 px-3 pb-2">
        <button
          onClick={openPalette}
          className="flex w-full items-center gap-2 rounded-lg border border-sidebar-border bg-sidebar-accent/30 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <Search className="h-4 w-4" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-sidebar-border bg-sidebar px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            ⌘K
          </kbd>
        </button>
        <WorkspaceSwitcher />
      </div>

      {/* Scrollable navigation */}
      <nav aria-label="Primary" className="hide-scrollbar flex-1 space-y-1 overflow-y-auto px-3 pb-3">
        {favoriteItems.length > 0 && (
          <Section label="Favorites">
            {favoriteItems.map((item) => (
              <NavItemLink
                key={item.id}
                item={item}
                active={item.id === activeItem?.id}
                favorite={isFavorite(item.id)}
                onToggleFavorite={toggleFavorite}
                onNavigate={handleNavigate}
              />
            ))}
          </Section>
        )}

        {recentItems.length > 0 && (
          <Section label="Recent">
            {recentItems.slice(0, 5).map((item) => (
              <NavItemLink
                key={item.id}
                item={item}
                active={item.id === activeItem?.id}
                favorite={isFavorite(item.id)}
                onToggleFavorite={toggleFavorite}
                onNavigate={handleNavigate}
              />
            ))}
          </Section>
        )}

        {pinnedModules.length > 0 && (
          <Section label="Pinned">
            {pinnedModules.map((m) => (
              <ModuleGroup
                key={m.id}
                module={m}
                isOpen={openModule === m.id}
                onToggleOpen={() => setOpenModule((o) => (o === m.id ? undefined : m.id))}
                activeItemId={activeItem?.id}
                pinned
                onTogglePin={togglePinned}
                isFavorite={isFavorite}
                onToggleFavorite={toggleFavorite}
                onNavigate={handleNavigate}
              />
            ))}
          </Section>
        )}

        <Section label={pinnedModules.length > 0 ? "Modules" : undefined}>
          {unpinnedVisible.map((m) => (
            <ModuleGroup
              key={m.id}
              module={m}
              isOpen={openModule === m.id}
              onToggleOpen={() => setOpenModule((o) => (o === m.id ? undefined : m.id))}
              activeItemId={activeItem?.id}
              pinned={false}
              onTogglePin={togglePinned}
              isFavorite={isFavorite}
              onToggleFavorite={toggleFavorite}
              onNavigate={handleNavigate}
            />
          ))}
        </Section>
      </nav>

      <UserFooter />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expanded building blocks.
// ---------------------------------------------------------------------------

function Section({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <div className="pt-1">
      {label && (
        <div className="px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </div>
      )}
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function ModuleGroup({
  module,
  isOpen,
  onToggleOpen,
  activeItemId,
  pinned,
  onTogglePin,
  isFavorite,
  onToggleFavorite,
  onNavigate,
}: {
  module: NavModule;
  isOpen: boolean;
  onToggleOpen: () => void;
  activeItemId?: string;
  pinned: boolean;
  onTogglePin: (id: string) => void;
  isFavorite: (id: string) => boolean;
  onToggleFavorite: (id: string) => void;
  onNavigate: () => void;
}) {
  const Icon = module.icon;
  const hasActive = module.items.some((it) => it.id === activeItemId);

  return (
    <div>
      <div
        className={cn(
          "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          hasActive ? "text-sidebar-foreground" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/50",
        )}
      >
        <button onClick={onToggleOpen} className="flex min-w-0 flex-1 items-center gap-2.5 text-left">
          <Icon className="h-4 w-4 shrink-0 opacity-90" />
          <span className="truncate">{module.title}</span>
        </button>
        <button
          onClick={() => onTogglePin(module.id)}
          aria-label={pinned ? "Unpin module" : "Pin module"}
          title={pinned ? "Unpin module" : "Pin module"}
          className={cn(
            "shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-sidebar-foreground group-hover:opacity-100",
            pinned && "opacity-100 text-primary",
          )}
        >
          {pinned ? <PinOff className="h-3.5 w-3.5" /> : <Pin className="h-3.5 w-3.5" />}
        </button>
        <button onClick={onToggleOpen} aria-label={isOpen ? "Collapse" : "Expand"} className="shrink-0">
          <ChevronDown
            className={cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180")}
          />
        </button>
      </div>

      {isOpen && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="overflow-hidden pl-3"
        >
          <div className="space-y-0.5 border-l border-sidebar-border/70 pl-2 pt-0.5">
            {module.items.map((item) => (
              <NavItemLink
                key={item.id}
                item={item}
                active={item.id === activeItemId}
                favorite={isFavorite(item.id)}
                onToggleFavorite={onToggleFavorite}
                onNavigate={onNavigate}
                nested
              />
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}

function NavItemLink({
  item,
  active,
  favorite,
  onToggleFavorite,
  onNavigate,
  nested,
}: {
  item: NavItem;
  active: boolean;
  favorite: boolean;
  onToggleFavorite: (id: string) => void;
  onNavigate: () => void;
  nested?: boolean;
}) {
  const Icon = item.icon;
  return (
    <div
      className={cn(
        "group relative flex items-center gap-2 rounded-lg pr-2 text-sm font-medium transition-colors",
        nested ? "pl-2" : "pl-3",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r-full bg-gradient-primary" />
      )}
      <Link to={item.href} onClick={onNavigate} className="flex min-w-0 flex-1 items-center gap-2.5 py-2">
        <Icon className="h-4 w-4 shrink-0 opacity-90" />
        <span className="truncate">{item.title}</span>
      </Link>
      <button
        onClick={() => onToggleFavorite(item.id)}
        aria-label={favorite ? "Remove favourite" : "Add favourite"}
        title={favorite ? "Remove favourite" : "Add favourite"}
        className={cn(
          "shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-sidebar-foreground group-hover:opacity-100",
          favorite && "opacity-100",
        )}
      >
        <Star className={cn("h-3.5 w-3.5", favorite && "fill-yellow-400 text-yellow-400")} />
      </button>
    </div>
  );
}

function UserFooter() {
  const profile = useProfile();
  function handleLogout() {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  return (
    <div className="m-3 rounded-xl border border-sidebar-border bg-sidebar-accent/40 p-3">
      <div className="flex items-center gap-3">
        <Link
          to="/settings"
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg -m-1 p-1 transition-colors hover:bg-sidebar-accent/60"
          title="Profile & settings"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-accent text-sm font-semibold text-accent-foreground">
            {profile.initials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-sidebar-foreground">
              {profile.displayName}
            </div>
            <div className="truncate text-xs text-muted-foreground">
              {profile.email ?? profile.jobTitle}
            </div>
          </div>
        </Link>
        <button
          onClick={handleLogout}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Collapsed rail building blocks.
// ---------------------------------------------------------------------------

function RailHeader() {
  const { toggleCollapsed } = useNavigation();
  return (
    <div className="flex flex-col items-center gap-2 px-2 py-4">
      <Link
        to="/"
        className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-primary shadow-glow"
        title="AI Credit Intelligence"
      >
        <Sparkles className="h-[1.125rem] w-[1.125rem] text-primary-foreground" strokeWidth={2.5} />
      </Link>
      <button
        onClick={toggleCollapsed}
        className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
        aria-label="Expand sidebar"
        title="Expand sidebar (Ctrl+B)"
      >
        <PanelLeftOpen className="h-4 w-4" />
      </button>
    </div>
  );
}

function RailDivider() {
  return <div className="my-1 h-px w-8 bg-sidebar-border" />;
}

function RailButton({ icon: Icon, label, onClick }: { icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="flex h-10 w-10 items-center justify-center rounded-lg text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
    >
      <Icon className="h-[1.15rem] w-[1.15rem]" />
    </button>
  );
}

function RailLink({
  item,
  icon,
  label,
  active,
  onNavigate,
}: {
  item?: NavItem;
  icon?: LucideIcon;
  label?: string;
  active: boolean;
  onNavigate: () => void;
}) {
  if (!item) return null;
  const Icon = icon ?? item.icon;
  return (
    <Link
      to={item.href}
      onClick={onNavigate}
      title={label ?? item.title}
      aria-label={label ?? item.title}
      className={cn(
        "relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r-full bg-gradient-primary" />
      )}
      <Icon className="h-[1.15rem] w-[1.15rem]" />
    </Link>
  );
}

function RailFooter() {
  const profile = useProfile();
  function handleLogout() {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  return (
    <div className="flex flex-col items-center gap-2 py-3">
      <Link
        to="/settings"
        className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-accent text-sm font-semibold text-accent-foreground"
        title={`${profile.displayName}${profile.email ? ` · ${profile.email}` : ""} — profile & settings`}
      >
        {profile.initials}
      </Link>
      <button
        onClick={handleLogout}
        className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
        aria-label="Log out"
        title="Log out"
      >
        <LogOut className="h-4 w-4" />
      </button>
    </div>
  );
}
