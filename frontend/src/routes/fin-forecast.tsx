import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import { OpsLayout, SectionCard, StateWrap, useForecastTypes, useForecastList, useForecastRun } from "@/features/financial-intelligence";

export const Route = createFileRoute("/fin-forecast")({ component: ForecastPage });

function ForecastPage() {
  const types = useForecastTypes();
  const list = useForecastList();
  const run = useForecastRun();
  const [type, setType] = useState("revenue");
  const [history, setHistory] = useState("100,110,121,133,146");
  const [out, setOut] = useState<any>(null);

  return (
    <OpsLayout title="Enterprise Forecasting Platform" description="Multi-horizon forecasting for revenue, cash flow, working capital, profit, growth, risk, default and recovery — with 95% confidence intervals from a deterministic ensemble (linear + damped trend + drift).">
      <div className="space-y-4">
        <SectionCard title="Run forecast">
          <div className="flex flex-wrap gap-2">
            <select className="rounded border bg-background px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
              {(types.data?.forecast_types ?? ["revenue"]).map((t: string) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input className="w-72 rounded border bg-background px-3 py-2 text-sm" placeholder="history csv" value={history} onChange={(e) => setHistory(e.target.value)} />
            <button className="rounded bg-primary px-3 py-2 text-sm text-primary-foreground" onClick={() => run.mutate({ forecast_type: type, history: history.split(",").map(Number), horizon: 12 }, { onSuccess: (r) => setOut(r) })}>Forecast 12m</button>
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Result">
            <StateWrap loading={run.isPending} empty={!out}>
              <pre className="rounded bg-muted p-2 text-xs whitespace-pre-wrap">{JSON.stringify(out?.metrics ?? out, null, 2)}</pre>
            </StateWrap>
          </SectionCard>
          <SectionCard title="Recent forecasts">
            <StateWrap loading={list.isLoading} empty={!(list.data?.forecasts?.length)}>
              <ul className="space-y-1 text-sm">{list.data?.forecasts?.map((f: any) => <li key={f.forecast_id} className="flex justify-between border-b border-border/50 py-1"><span>{f.forecast_type}</span><span className="text-xs text-muted-foreground">{f.horizon}m</span></li>)}</ul>
            </StateWrap>
          </SectionCard>
        </div>
      </div>
    </OpsLayout>
  );
}
