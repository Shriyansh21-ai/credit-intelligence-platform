import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard, OpsLayout, SectionCard, StateWrap,
  useCreateSource, useDocuments, useIngestDocument, useRagAnswer, useRagStats, useSources,
} from "@/features/ai-platform";

export const Route = createFileRoute("/aip-rag")({ component: RagPage });

function RagPage() {
  const sources = useSources();
  const docs = useDocuments();
  const stats = useRagStats();
  const createSource = useCreateSource();
  const ingest = useIngestDocument();
  const answer = useRagAnswer();

  const [sKey, setSKey] = useState("");
  const [sType, setSType] = useState("credit_policy");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [srcKey, setSrcKey] = useState("");
  const [q, setQ] = useState("");
  const [result, setResult] = useState<any>(null);

  return (
    <OpsLayout
      title="Enterprise RAG Platform"
      description="Ingest policies, circulars, statements and reports; retrieve with hybrid semantic + lexical search; answer with citations and confidence. Offline embeddings + pluggable vector store (pgvector-ready)."
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Sources" value={(stats.data as any)?.sources ?? "—"} />
          <MetricCard label="Documents" value={(stats.data as any)?.documents ?? "—"} />
          <MetricCard label="Chunks" value={(stats.data as any)?.chunks ?? "—"} />
          <MetricCard label="Vectors" value={(stats.data as any)?.vectors ?? "—"} />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Register knowledge source">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="key (e.g. credit-policies)" value={sKey} onChange={(e) => setSKey(e.target.value)} />
              <select className="w-full rounded border bg-background px-3 py-2 text-sm" value={sType} onChange={(e) => setSType(e.target.value)}>
                {["credit_policy", "rbi_circular", "basel_guideline", "financial_statement", "annual_report", "loan_agreement", "committee_note", "audit_report", "ocr_document", "customer_interaction", "email", "external_manual"].map((t) => <option key={t}>{t}</option>)}
              </select>
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!sKey || createSource.isPending}
                onClick={() => createSource.mutate({ key: sKey, name: sKey, source_type: sType }, { onSuccess: () => setSKey("") })}>Register</button>
            </div>
          </SectionCard>

          <SectionCard title="Ingest document">
            <div className="space-y-2">
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="source key" value={srcKey} onChange={(e) => setSrcKey(e.target.value)} />
              <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="title" value={title} onChange={(e) => setTitle(e.target.value)} />
              <textarea className="h-24 w-full rounded border bg-background px-3 py-2 text-sm" placeholder="document text" value={text} onChange={(e) => setText(e.target.value)} />
              <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!srcKey || !text || ingest.isPending}
                onClick={() => ingest.mutate({ source_key: srcKey, title: title || "Untitled", text }, { onSuccess: () => setText("") })}>Ingest</button>
            </div>
          </SectionCard>
        </div>

        <SectionCard title="Ask (grounded answer with citations)">
          <div className="flex gap-2">
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="Ask a question about the indexed knowledge…" value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!q || answer.isPending}
              onClick={() => answer.mutate({ question: q }, { onSuccess: (r) => setResult(r) })}>Ask</button>
          </div>
          {result && (
            <div className="mt-3 space-y-2 text-sm">
              <div className="rounded bg-muted p-3 whitespace-pre-wrap">{result.answer}</div>
              <div className="text-xs text-muted-foreground">Confidence: {result.confidence}</div>
              <ul className="space-y-1 text-xs">
                {(result.citations ?? []).map((c: any) => <li key={c.index}>[{c.index}] {c.label}</li>)}
              </ul>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Documents">
          <StateWrap loading={docs.isLoading} empty={!(docs.data as any)?.length}>
            <ul className="space-y-1 text-sm">
              {(docs.data as any)?.map((d: any) => (
                <li key={d.id} className="flex justify-between border-b border-border/50 py-1">
                  <span>{d.title} <span className="text-xs text-muted-foreground">({d.doc_type})</span></span>
                  <span className="text-xs text-muted-foreground">v{d.version} · {d.chunk_count} chunks</span>
                </li>
              ))}
            </ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
