import { fmtCurrency, titleCase } from "../format";
import type { ApplicationRow } from "../types";

/** Compact table of applications used across dashboards. */
export function ApplicationsTable({ rows }: { rows: ApplicationRow[] }) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">No applications.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="py-2 pr-3 font-medium">Reference</th>
            <th className="py-2 pr-3 font-medium">Company</th>
            <th className="py-2 pr-3 font-medium">Industry</th>
            <th className="py-2 pr-3 font-medium">Amount</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 font-medium">Rating</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-border/60 last:border-0">
              <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">{r.reference ?? `#${r.id}`}</td>
              <td className="py-2 pr-3 text-foreground">{r.company_name}</td>
              <td className="py-2 pr-3 text-muted-foreground">{r.industry ?? "-"}</td>
              <td className="py-2 pr-3 font-mono">{fmtCurrency(r.requested_amount)}</td>
              <td className="py-2 pr-3">
                <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-medium">
                  {r.status_label ?? titleCase(r.status)}
                </span>
              </td>
              <td className="py-2">{r.risk_rating ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
