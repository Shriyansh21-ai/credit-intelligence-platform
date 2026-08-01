import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useDataCatalog, useUpsertGolden, useDetectDuplicates } from "@/features/enterprise-platform";

export const Route = createFileRoute("/ent-data")({ component: DataPage });

function DataPage() {
  const catalog = useDataCatalog();
  const upsert = useUpsertGolden();
  const dupes = useDetectDuplicates();
  const [name, setName] = useState("");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Data Management (MDM)" description="Master Data Management: golden records, reference data, data-quality rules, deterministic duplicate detection & entity resolution, stewardship, bulk import/export and a data catalog.">
      <div className="space-y-4">
        <SectionCard title="Add golden customer record">
          <div className="flex gap-2">
            <input className="w-full rounded border bg-background px-3 py-2 text-sm" placeholder="customer name" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" disabled={!name}
              onClick={() => upsert.mutate({ entity_type: "customer", natural_key: name, record: { name } }, { onSuccess: () => setName("") })}>Add</button>
            <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => dupes.mutate({ entity_type: "customer", threshold: 0.6 }, { onSuccess: (r) => setOut(r) })}>Detect duplicates</button>
          </div>
          {out && <pre className="mt-2 rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 900)}</pre>}
        </SectionCard>
        <SectionCard title="Data catalog">
          <StateWrap loading={catalog.isLoading} empty={!catalog.data?.entities}>
            <ul className="space-y-1 text-sm">{Object.entries(catalog.data?.entities ?? {}).map(([k, v]: any) => (
              <li key={k} className="flex justify-between border-b border-border/50 py-1">
                <span>{k}</span><span className="text-xs text-muted-foreground">{v.records} records · quality {v.avg_quality ?? "—"}</span>
              </li>))}</ul>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
