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

/** Shared page shell for all AI Risk Intelligence pages. Delegates to {@link AppShell}. */
export function RiskLayout({ title, description, icon, actions, children }: Props) {
  return (
    <AppShell title={title} description={description} icon={icon} actions={actions}>
      {children}
    </AppShell>
  );
}
