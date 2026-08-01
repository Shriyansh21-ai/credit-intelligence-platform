import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { AppShell } from "@/components/dashboard/AppShell";

interface Props {
  title: string;
  description?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  children: ReactNode;
}

/** Shared page shell for the Credit Operations dashboards. Delegates to {@link AppShell}. */
export function OpsLayout({ title, description, icon, actions, children }: Props) {
  return (
    <AppShell title={title} description={description} icon={icon} actions={actions}>
      {children}
    </AppShell>
  );
}
