import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { DocumentIntelligence } from "@/features/documents";

export const Route = createFileRoute("/documents")({
  component: DocumentsPage,
});

function DocumentsPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title="Document Intelligence" onMenu={() => setMenuOpen(true)} />

        <main className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-6 lg:p-8">
          <DocumentIntelligence />
        </main>
      </div>
    </div>
  );
}
