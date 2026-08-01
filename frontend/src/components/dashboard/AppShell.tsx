import { useState, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { PageHeader } from "@/components/common/PageHeader";

export interface AppShellProps {
  title: string;
  description?: string;
  /** Optional leading icon shown beside the page title. */
  icon?: LucideIcon;
  /** Right-aligned page actions (buttons, filters). Rendered in the header. */
  actions?: ReactNode;
  children: ReactNode;
}

/**
 * Canonical authenticated page shell: sidebar + top bar + a content column with
 * a standardised {@link PageHeader}. Used by every dashboard so page heading,
 * spacing and max-width are identical app-wide. `OpsLayout` and `RiskLayout`
 * delegate here.
 */
export function AppShell({ title, description, icon, actions, children }: AppShellProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to main content
      </a>
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} onMenu={() => setMenuOpen(true)} />
        <main
          id="main-content"
          className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 duration-300 animate-in fade-in md:p-6 lg:p-8"
        >
          <PageHeader title={title} description={description} icon={icon} actions={actions} />
          {children}
        </main>
      </div>
    </div>
  );
}
