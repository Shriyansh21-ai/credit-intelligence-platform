import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useMarketDashboard, useMarketNews, useMarketSeed, useMarketAddNews } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-market")({ component: MarketPage });

function MarketPage() {
  const dash = useMarketDashboard();
  const news = useMarketNews();
  const seed = useMarketSeed();
  const addNews = useMarketAddNews();
  const [headline, setHeadline] = useState("");

  return (
    <OpsLayout title="Market Intelligence Platform" description="Interest curves, bond yields, equity indices, commodities, FX, credit spreads and volatility, plus corporate/industry/macro news with sentiment, summaries and impact analysis, and an economic calendar. Provider-agnostic.">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => seed.mutate()}>Seed market data</button>
          <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="news headline" value={headline} onChange={(e) => setHeadline(e.target.value)} />
          <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!headline} onClick={() => addNews.mutate({ headline, category: "macro" }, { onSuccess: () => setHeadline("") })}>Add news</button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Quotes & curve">
            <StateWrap loading={dash.isLoading} empty={!dash.data}>
              <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify({ quotes: dash.data?.quotes, yield_curve: dash.data?.yield_curve, sentiment: dash.data?.sentiment }, null, 2).slice(0, 1400)}</pre>
            </StateWrap>
          </SectionCard>
          <SectionCard title="News">
            <StateWrap loading={news.isLoading} empty={!(news.data?.news?.length)}>
              <ul className="space-y-1 text-sm">{news.data?.news?.map((n: any) => <li key={n.news_id} className="border-b border-border/50 py-1"><span>{n.headline}</span> <span className="text-xs text-muted-foreground">({n.sentiment})</span></li>)}</ul>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
