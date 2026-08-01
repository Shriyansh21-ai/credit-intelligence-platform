import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, useChatAsk, useCreateConversation } from "@/features/ai-platform";

export const Route = createFileRoute("/aip-assistant")({ component: AssistantPage });

interface Turn { role: string; content: string; intent?: string; citations?: any[]; }

function AssistantPage() {
  const createConv = useCreateConversation();
  const ask = useChatAsk();
  const [company, setCompany] = useState("");
  const [conv, setConv] = useState<number | undefined>();
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  const ensureConv = (cb: (id: number) => void) => {
    if (conv) return cb(conv);
    createConv.mutate({ title: "Chat", bindings: company ? { company_ref: company } : {} },
      { onSuccess: (r) => { setConv(r.conversation_id); cb(r.conversation_id); } });
  };

  const send = () => {
    if (!q.trim()) return;
    const question = q;
    setTurns((t) => [...t, { role: "user", content: question }]);
    setQ("");
    ensureConv((id) => ask.mutate({ conversation_id: id, message: question },
      { onSuccess: (r) => setTurns((t) => [...t, { role: "assistant", content: r.answer, intent: r.intent, citations: r.citations }]) }));
  };

  return (
    <OpsLayout
      title="Enterprise Conversational AI"
      description="A ChatGPT-style assistant over customers, portfolios, loans, documents, compliance, fraud, policies, regulations and committee history. Every answer is grounded and carries evidence — the LLM never fabricates numbers."
    >
      <div className="space-y-4">
        <SectionCard title="Bind a company (optional)">
          <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="company ref" value={company} onChange={(e) => setCompany(e.target.value)} disabled={!!conv} />
        </SectionCard>
        <SectionCard title="Conversation">
          <div className="mb-3 max-h-96 space-y-2 overflow-y-auto">
            {turns.map((t, i) => (
              <div key={i} className={t.role === "user" ? "text-right" : ""}>
                <div className={`inline-block max-w-[85%] rounded-lg px-3 py-2 text-sm ${t.role === "user" ? "bg-primary/20" : "bg-muted"}`}>
                  <div className="whitespace-pre-wrap">{t.content}</div>
                  {t.intent && <div className="mt-1 text-[10px] text-muted-foreground">intent: {t.intent}{t.citations?.length ? ` · ${t.citations.length} citation(s)` : ""}</div>}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <input className="flex-1 rounded border bg-background px-3 py-2 text-sm" placeholder="Ask anything…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={ask.isPending} onClick={send}>Send</button>
          </div>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
