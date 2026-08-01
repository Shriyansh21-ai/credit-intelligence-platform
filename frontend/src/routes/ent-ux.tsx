import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, usePreferences, useSavePreferences, useCommandCatalog } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-ux")({ component: UxPage });

function UxPage() {
  const prefs = usePreferences();
  const save = useSavePreferences();
  const commands = useCommandCatalog();

  return (
    <OpsLayout title="Enterprise UX Platform" description="A polished, enterprise-grade experience: a global ⌘K command palette, personalization (theme, density, accent), saved layouts and keyboard-driven navigation across every module. Press ⌘K anywhere to search and navigate.">
      <div className="space-y-4">
        <SectionCard title="Personalization">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-muted-foreground">Theme:</span>
            {["light", "dark", "system"].map((t) => (
              <button key={t} className={`rounded px-3 py-1.5 text-sm ${prefs.data?.theme === t ? "bg-primary text-primary-foreground" : "bg-secondary"}`}
                onClick={() => save.mutate({ theme: t })}>{t}</button>
            ))}
            <span className="ml-4 text-sm text-muted-foreground">Density:</span>
            {["comfortable", "compact", "spacious"].map((d) => (
              <button key={d} className={`rounded px-3 py-1.5 text-sm ${prefs.data?.density === d ? "bg-primary text-primary-foreground" : "bg-secondary"}`}
                onClick={() => save.mutate({ density: d })}>{d}</button>
            ))}
          </div>
        </SectionCard>
        <SectionCard title="Command palette (⌘K)">
          <StateWrap loading={commands.isLoading} empty={!(commands.data?.commands?.length)}>
            <div className="grid gap-1 sm:grid-cols-2">
              {commands.data?.commands?.map((c: any) => (
                <a key={c.id} href={c.href || undefined} className="flex items-center justify-between rounded border border-border/50 px-3 py-2 text-sm hover:bg-accent">
                  <span>{c.label}</span>
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{c.group}</span>
                </a>
              ))}
            </div>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
