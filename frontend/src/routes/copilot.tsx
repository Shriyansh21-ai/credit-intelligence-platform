import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, useAskCopilot, useProviderStatus } from "@/features/autonomous-intelligence";

export const Route = createFileRoute("/copilot")({ component: CopilotPage });

interface Turn { role: string; content: string; intent?: string; provider?: string; }

function CopilotPage() {
  const [company, setCompany] = useState("");
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conv, setConv] = useState<number | undefined>();
  const ask = useAskCopilot();
  const provider = useProviderStatus();

  const send = () => {
    if (!q.trim()) return;
    const question = q;
    setTurns((t) => [...t, { role: "user", content: question }]);
    setQ("");
    ask.mutate({ question, company_ref: company || undefined, conversation_id: conv },
      { onSuccess: (r) => {
          setConv(r.conversation_id);
          setTurns((t) => [...t, { role: "assistant", content: r.answer, intent: r.intent, provider: r.provider }]);
        } });
  };

  return (
    <OpsLayout
      title="AI Credit Copilot"
      description="An assistant that explains assessments, decisions, ratios, SHAP and fraud, summarizes financials and recommends next actions — grounded strictly in deterministic platform data. The LLM only phrases the facts; it never fabricates numbers."
    >
      <div className="space-y-4">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>LLM provider:</span>
          <span className="rounded bg-muted px-2 py-0.5 font-mono">
            {(provider.data as any)?.active ?? "local"}
          </span>
          <span>(Claude available: {String((provider.data as any)?.claude_available ?? false)})</span>
        </div>

        <div className="flex items-end gap-3">
          <label className="text-sm w-56">
            <span className="mb-1 block text-muted-foreground">Bound company (optional)</span>
            <input value={company} onChange={(e) => setCompany(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2" />
          </label>
        </div>

        <SectionCard title="Conversation">
          <div className="max-h-[420px] space-y-3 overflow-auto">
            {turns.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Ask something like “Explain the assessment”, “Summarize the financials”, or
                “What should I do next?”.
              </p>
            )}
            {turns.map((t, i) => (
              <div key={i} className={t.role === "user" ? "text-right" : ""}>
                <div className={`inline-block max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                  t.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                  {t.content}
                  {t.intent && (
                    <div className="mt-1 text-[10px] uppercase opacity-60">{t.intent} · {t.provider}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <input value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Ask the copilot…"
              className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm" />
            <button onClick={send} disabled={ask.isPending}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
              {ask.isPending ? "…" : "Send"}
            </button>
          </div>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
