import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useAltIngest, useAltComposite } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-altdata")({ component: AltDataPage });

function AltDataPage() {
  const ingest = useAltIngest();
  const composite = useAltComposite();
  const [subject, setSubject] = useState("Acme");
  const [type, setType] = useState("payments");
  const [value, setValue] = useState("80");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Alternative Data Intelligence" description="Turn non-traditional signals — satellite, shipping, web traffic, reviews, social, hiring, payments, footfall — into normalized enterprise risk signals (direction, magnitude, confidence) and a blended composite that can tilt PD.">
      <div className="space-y-4">
        <SectionCard title="Ingest signal">
          <div className="flex flex-wrap gap-2">
            <input className="rounded border bg-background px-3 py-2 text-sm" placeholder="subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <select className="rounded border bg-background px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
              {["payments", "hiring", "web_traffic", "reviews", "satellite", "shipping", "footfall"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input className="w-24 rounded border bg-background px-3 py-2 text-sm" placeholder="value 0-100" value={value} onChange={(e) => setValue(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => ingest.mutate({ subject_ref: subject, signal_type: type, raw: { value: Number(value) } }, { onSuccess: (r) => setOut(r) })}>Ingest</button>
            <button className="rounded bg-secondary px-3 py-2 text-sm" onClick={() => composite.mutate({ subject_ref: subject }, { onSuccess: (r) => setOut(r) })}>Composite risk</button>
          </div>
        </SectionCard>
        <SectionCard title="Result">
          <StateWrap loading={ingest.isPending || composite.isPending} empty={!out}>
            <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out, null, 2).slice(0, 1400)}</pre>
          </StateWrap>
        </SectionCard>
      </div>
    </OpsLayout>
  );
}
