import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Brain,
  History,
  ShieldAlert,
  ShieldCheck,
  BarChart3,
  Settings,
  LogOut,
  Sparkles,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { label: "Credit Prediction", icon: Brain, href: "/predict" },
  { label: "Prediction History", icon: History, href: "/predict" },
  { label: "Fraud Detection", icon: ShieldAlert, href: "/fraud" },
  { label: "Fraud History", icon: ShieldCheck, href: "/fraud" },
  { label: "Analytics", icon: BarChart3, href: "/" },
  { label: "Settings", icon: Settings, href: "/" },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-background/70 backdrop-blur-sm lg:hidden"
          aria-hidden
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 transform border-r border-sidebar-border bg-sidebar transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between px-5 py-5">
            <a href="#" className="flex items-center gap-2.5">
              <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-primary shadow-glow">
                <Sparkles className="h-4.5 w-4.5 text-primary-foreground" strokeWidth={2.5} />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold tracking-tight text-sidebar-foreground">
                  AI Credit
                </div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                  Intelligence
                </div>
              </div>
            </a>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground lg:hidden"
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <nav className="flex-1 space-y-1 px-3">
            <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Workspace
            </div>
            {nav.map((item) => {
              const isActive =
                typeof window !== "undefined" &&
                (window.location.pathname === item.href || window.location.pathname.startsWith(item.href));

              return (
                <a
                  key={item.label}
                  href={item.href}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                  )}
                >
                  {isActive && (
                    <motion.span
                      layoutId="sidebar-active"
                      className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r-full bg-gradient-primary"
                    />
                  )}
                  <item.icon className="h-4 w-4 opacity-90" />
                  <span>{item.label}</span>
                </a>
              );
            })}
          </nav>

          <div className="m-3 rounded-xl border border-sidebar-border bg-sidebar-accent/40 p-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-accent text-sm font-semibold text-accent-foreground">
                SD
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-sidebar-foreground">
                  Shriyansh Dev
                </div>
                <div className="truncate text-xs text-muted-foreground">Head of Risk</div>
              </div>
              <button
                className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
                aria-label="Log out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
