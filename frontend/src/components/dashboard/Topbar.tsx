import { useEffect, useState } from "react";
import { Menu, Search, LogOut, FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";
import { isDemoMode, toggleDemoMode } from "@/lib/demo";
import { useNavigation } from "@/navigation";
import { NotificationsMenu } from "@/components/dashboard/NotificationsMenu";

interface TopbarProps {
  title?: string;
  onMenu?: () => void;
}

export function Topbar({ title = "", onMenu }: TopbarProps) {
  const [demo, setDemo] = useState(false);
  const { openPalette } = useNavigation();
  useEffect(() => setDemo(isDemoMode()), []);

  function handleLogout() {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }

  function handleToggleDemo() {
    const next = toggleDemoMode();
    setDemo(next);
    // Reload so all queries refetch with (or without) demo data.
    window.location.reload();
  }

  return (
    <header className="border-b border-border bg-background">
      <div className="mx-auto flex w-full max-w-7xl items-center gap-4 p-4 md:p-6 lg:p-8">
        <button
          onClick={onMenu}
          aria-label="Open menu"
          className="rounded-md p-2 text-muted-foreground hover:bg-accent/10 lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold tracking-tight text-foreground">{title}</div>
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <button
            type="button"
            onClick={openPalette}
            aria-label="Search everything"
            title="Search everything (Ctrl+K)"
            className={cn(
              "group flex w-64 items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm text-muted-foreground transition-colors hover:border-ring hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            <Search className="h-4 w-4" />
            <span className="flex-1 text-left">Search everything…</span>
            <kbd className="rounded border border-border bg-secondary/60 px-1.5 py-0.5 text-[10px] font-medium">
              ⌘K
            </kbd>
          </button>

          <button
            onClick={handleToggleDemo}
            aria-pressed={demo}
            title={demo ? "Demo mode is on — showing sample data" : "Turn on demo mode (sample data)"}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              demo
                ? "border-primary/40 bg-primary/15 text-primary"
                : "border-border text-muted-foreground hover:bg-accent/10 hover:text-foreground",
            )}
          >
            <FlaskConical className="h-3.5 w-3.5" />
            <span className="hidden lg:inline">Demo</span>
          </button>

          <NotificationsMenu />

          <button 
            onClick={handleLogout}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent/10 hover:text-foreground transition-colors"
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </div>
    </header>
  );
}
