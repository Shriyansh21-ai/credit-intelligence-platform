import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap, titleCase,
  useReindex, useSearch, useSearchFacets,
} from "@/features/banking-os";

export const Route = createFileRoute("/enterprise-search")({ component: EnterpriseSearchPage });

function EnterpriseSearchPage() {
  const facets = useSearchFacets();
  const doSearch = useSearch();
  const reindex = useReindex();
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("hybrid");

  const f = facets.data as any;
  const res = doSearch.data as any;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch.mutate({ query: q, mode, limit: 20 });
  };

  return (
    <OpsLayout
      title="Enterprise Search"
      description="Universal search across companies, applications, documents, reports, alerts, tasks, policies and models — with keyword, semantic and hybrid ranking."
    >
      <div className="space-y-6">
        <form onSubmit={submit} className="flex flex-wrap gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search the platform…"
            className="min-w-[280px] flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <select value={mode} onChange={(e) => setMode(e.target.value)} className="rounded-md border border-border bg-background px-3 py-2 text-sm">
            <option value="hybrid">Hybrid</option>
            <option value="keyword">Keyword</option>
            <option value="semantic">Semantic</option>
          </select>
          <button type="submit" className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
            {doSearch.isPending ? "Searching…" : "Search"}
          </button>
          <button type="button" onClick={() => reindex.mutate()} className="rounded-md border border-border px-4 py-2 text-sm">
            {reindex.isPending ? "Reindexing…" : "Reindex"}
          </button>
        </form>

        <StateWrap loading={facets.isLoading} error={(facets.error as Error)?.message ?? null}>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Indexed documents" value={String(f?.total ?? 0)} />
            <MetricCard label="Doc types" value={String(Object.keys(f?.by_doc_type ?? {}).length)} />
            <MetricCard label="Results" value={String(res?.count ?? 0)} />
            <MetricCard label="Mode" value={titleCase(mode)} />
          </div>
        </StateWrap>

        {res && (
          <SectionCard title={`Results for “${res.query}”`} description={`${res.count} hits, ${res.mode} ranking`}>
            <div className="space-y-2">
              {(res.results ?? []).map((r: any, i: number) => (
                <div key={i} className="rounded-md border border-border/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-foreground">{r.title}</span>
                    <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase">{r.doc_type}</span>
                  </div>
                  {r.snippet && <p className="mt-1 text-xs text-muted-foreground">{r.snippet}</p>}
                  <div className="mt-1 flex gap-3 text-[10px] font-mono text-muted-foreground">
                    <span>score {r.score}</span>
                    <span>kw {r.signals?.keyword}</span>
                    <span>sem {r.signals?.semantic}</span>
                  </div>
                </div>
              ))}
              {(res.results ?? []).length === 0 && <p className="text-sm text-muted-foreground">No matches.</p>}
            </div>
          </SectionCard>
        )}
      </div>
    </OpsLayout>
  );
}
