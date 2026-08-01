import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { EnterpriseAssessment } from "@/features/enterprise-assessment";

export const Route = createFileRoute("/enterprise")({
  component: EnterprisePage,
});

function EnterprisePage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title="Enterprise Assessment" onMenu={() => setMenuOpen(true)} />

        <main className="mx-auto w-full max-w-6xl flex-1 p-4 md:p-6 lg:p-8">
          <EnterpriseAssessment />
        </main>
      </div>
    </div>
  );
}
