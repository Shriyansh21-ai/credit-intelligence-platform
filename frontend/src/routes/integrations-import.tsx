import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";

import {
  OpsLayout,
  SectionCard,
  StateWrap,
  titleCase,
  useImportData,
} from "@/features/integrations";

export const Route = createFileRoute("/integrations-import")({ component: ImportPage });

const CONNECTORS: Record<string, { param: string; operations: string[] }> = {
  gst: { param: "gstin", operations: ["get_profile", "get_returns", "get_filing_delays", "get_tax_trends", "get_filing_status"] },
  mca: { param: "cin", operations: ["get_company_master", "get_directors", "get_charges", "get_financial_statements", "get_director_network"] },
  bureau: { param: "pan", operations: ["get_business_score", "get_full_report", "get_dpd_history", "get_outstanding"] },
  erp: { param: "entity_ref", operations: ["get_financial_statements", "get_receivables", "get_payables", "get_trial_balance"] },
  payments: { param: "entity_ref", operations: ["get_transaction_health", "get_payment_behaviour", "get_settlement_delays", "get_counterparty_risk"] },
};

const SAMPLE: Record<string, string> = {
  gst: "27ABCDE1234F1Z5",
  mca: "U72200MH2015PTC123456",
  bureau: "AAAAA1111A",
  erp: "ENT-001",
  payments: "ENT-001",
};

function ImportPage() {
  const [connector, setConnector] = useState("gst");
  const [entityRef, setEntityRef] = useState(SAMPLE.gst);
  const [operation, setOperation] = useState(CONNECTORS.gst.operations[0]);
  const importData = useImportData();

  const cfg = CONNECTORS[connector];

  return (
    <OpsLayout
      title="Government & Bureau Imports"
      description="Import external financial information (GST, MCA, credit bureau, ERP, payments) through the connector framework. Every import is stored as a versioned, content-hashed snapshot — identical content does not create a new version."
    >
      <div className="space-y-6">
        <SectionCard title="Import external data">
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Connector</span>
              <select
                value={connector}
                onChange={(e) => {
                  const c = e.target.value;
                  setConnector(c);
                  setEntityRef(SAMPLE[c]);
                  setOperation(CONNECTORS[c].operations[0]);
                }}
                className="w-full rounded-md border border-border bg-background px-3 py-2"
              >
                {Object.keys(CONNECTORS).map((c) => (
                  <option key={c} value={c}>{titleCase(c)}</option>
                ))}
              </select>
            </label>
            <label className="text-sm md:col-span-2">
              <span className="mb-1 block text-muted-foreground">Entity reference ({cfg.param})</span>
              <input
                value={entityRef}
                onChange={(e) => setEntityRef(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Operation</span>
              <select
                value={operation}
                onChange={(e) => setOperation(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2"
              >
                {cfg.operations.map((o) => (
                  <option key={o} value={o}>{titleCase(o)}</option>
                ))}
              </select>
            </label>
          </div>
          <button
            onClick={() =>
              importData.mutate({
                connectorKey: connector,
                body: { entity_ref: entityRef, operation, params: {} },
              })
            }
            disabled={importData.isPending}
            className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {importData.isPending ? "Importing…" : "Import & snapshot"}
          </button>
          {importData.error && (
            <span className="ml-3 text-sm text-red-500">{(importData.error as Error).message}</span>
          )}
        </SectionCard>

        <StateWrap loading={false} error={null}>
          {importData.data && (
            <SectionCard
              title={`Snapshot v${importData.data.snapshot?.version ?? "?"} · ${importData.data.snapshot?.provider ?? ""}`}
            >
              <pre className="max-h-[480px] overflow-auto rounded-lg bg-muted/50 p-4 text-xs text-foreground">
                {JSON.stringify(importData.data.snapshot?.payload ?? importData.data, null, 2)}
              </pre>
            </SectionCard>
          )}
        </StateWrap>
      </div>
    </OpsLayout>
  );
}
