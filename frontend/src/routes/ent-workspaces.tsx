import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useWorkspaces, useCreateWorkspace } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-workspaces")({ component: WorkspacesPage });

function WorkspacesPage() {
  const workspaces = useWorkspaces();
  const create = useCreateWorkspace();
  const [name, setName] = useState("");
  const [type, setType] = useState("team");

  return (
    <OpsLayout title="Enterprise Workspaces" description="Personal, team, department, organization and shared workspaces holding pinned dashboards, saved reports, shared views, collections, bookmarks and templates, with members and per-workspace analytics.">
      <div className="space-y-4">
        <SectionCard title="Create workspace">
          <div className="flex flex-wrap gap-2">
            <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
            <select className="rounded border bg-background px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
              {["personal", "team", "department", "organization", "shared"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!name || create.isPending}
              onClick={() => create.mutate({ name, workspace_type: type }, { onSuccess: () => setName("") })}>Create</button>
          </div>
        </SectionCard>
        <SectionCard title="Workspaces">
          <StateWrap loading={workspaces.isLoading} empty={!(workspaces.data?.workspaces?.length)}>
            <ul className="space-y-1 text-sm">{workspaces.data?.workspaces?.map((w: any) => (
              <li key={w.workspace_id} className="flex justify-between border-b border-border/50 py-1">
                <span>{w.name}</span><span className="text-xs text-muted-foreground">{w.workspace_type}</span>
              </li>))}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
