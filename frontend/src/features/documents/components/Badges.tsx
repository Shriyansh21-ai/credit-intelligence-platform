import { cn } from "@/lib/utils";
import { CONFIDENCE_META, STATUS_META } from "../constants";
import type { ConfidenceLevel, DocumentStatus } from "../types";

type Tone = "neutral" | "positive" | "warning" | "negative";

const toneClass: Record<Tone, string> = {
  neutral: "bg-secondary/70 text-muted-foreground",
  positive: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  negative: "bg-destructive/10 text-destructive",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", toneClass[tone])}>
      {children}
    </span>
  );
}

export function ConfidenceBadge({ level, score }: { level: ConfidenceLevel; score?: number }) {
  const meta = CONFIDENCE_META[level];
  return (
    <Badge tone={meta.tone}>
      {meta.label}
      {typeof score === "number" ? ` · ${Math.round(score * 100)}%` : ""}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "neutral" as Tone };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}
