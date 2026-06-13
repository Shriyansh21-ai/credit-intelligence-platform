import { Menu, Search, Bell, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";

interface TopbarProps {
  title?: string;
  onMenu?: () => void;
}

export function Topbar({ title = "", onMenu }: TopbarProps) {
  function handleLogout() {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }

  return (
    <header className="border-b border-border bg-background">
      <div className="mx-auto flex max-w-[1500px] items-center gap-4 p-4 md:p-6 lg:p-8">
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
          <div className="relative">
            <input
              placeholder="Search"
              className={cn(
                "w-64 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground",
              )}
            />
            <Search className="absolute right-2 top-2 h-4 w-4 text-muted-foreground" />
          </div>

          <button className="rounded-md p-2 text-muted-foreground hover:bg-accent/10">
            <Bell className="h-5 w-5" />
          </button>

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
