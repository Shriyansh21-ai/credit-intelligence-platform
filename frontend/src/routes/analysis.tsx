import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { FinancialAnalysis } from "@/features/financial-analysis";

interface AnalysisSearch {
  assessment_id?: number;
}

export const Route = createFileRoute("/analysis")({
  validateSearch: (search: Record<string, unknown>): AnalysisSearch => {
    const raw = search.assessment_id;
    const id = typeof raw === "string" ? Number(raw) : typeof raw === "number" ? raw : undefined;
    return id !== undefined && Number.isFinite(id) ? { assessment_id: id } : {};
  },
  component: AnalysisPage,
});

function AnalysisPage() {
  const { assessment_id } = Route.useSearch();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title="Financial Analysis" onMenu={() => setMenuOpen(true)} />

        <main className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-6 lg:p-8">
          <FinancialAnalysis assessmentId={assessment_id} />
        </main>
      </div>
    </div>
  );
}
