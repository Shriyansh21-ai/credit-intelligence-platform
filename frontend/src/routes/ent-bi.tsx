import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useBiAnalytics, useBoardReport } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-bi")({ component: BiPage });

function BiPage() {
  const [category, setCategory] = useState("executive");
  const analytics = useBiAnalytics(category);
  const board = useBoardReport();

  return (
    <OpsLayout title="Business Intelligence" description="Executive analytics computed from live platform data: revenue, product, customer, risk, AI, adoption, operational, financial and growth analytics, plus a board report. No placeholder numbers — every metric is grounded.">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {["executive", "revenue", "customer", "product", "risk", "operational", "growth"].map((c) => (
            <button key={c} className={`rounded px-3 py-1.5 text-sm ${category === c ? "bg-primary text-primary-foreground" : "bg-secondary"}`} onClick={() => setCategory(c)}>{c}</button>
          ))}
        </div>
        <SectionCard title={`${category} analytics`}>
          <StateWrap loading={analytics.isLoading} empty={!analytics.data}>
            <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(analytics.data?.metrics ?? {}, null, 2).slice(0, 1400)}</pre>
          </StateWrap>
        </SectionCard>
        <SectionCard title="Board report">
          {board.data && <div><p className="mb-2 text-sm">{board.data.headline}</p><pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(board.data.sections ?? {}, null, 2).slice(0, 1200)}</pre></div>}
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
