import { useMemo, useState } from "react";
import { ArrowUpDown, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

type RiskLevel = "Low" | "Medium" | "High" | "Critical";
type ApprovalStatus = "Approved" | "Rejected" | "Review";

interface AssessmentData {
  id: string | number;
  credit_score?: number;
  score?: number;
  risk_level?: string;
  risk?: string;
  approval?: boolean;
  status?: ApprovalStatus;
  probability?: number;
  created_at?: string;
  date?: string;
  customer?: string;
  email?: string;
}

const RISK_STYLES: Record<string, string> = {
  Low: "bg-success/10 text-success border-success/20",
  Medium: "bg-warning/10 text-warning border-warning/20",
  High: "bg-destructive/10 text-destructive border-destructive/20",
  Critical: "bg-destructive/20 text-destructive border-destructive/30",
};

const STATUS_STYLES: Record<string, string> = {
  Approved: "bg-success/10 text-success",
  Rejected: "bg-destructive/10 text-destructive",
  Review: "bg-info/10 text-info",
};

const Th = ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
  <th
    onClick={onClick}
    className={cn("px-5 py-3 font-medium", onClick && "cursor-pointer hover:bg-secondary/30")}
  >
    <div className="flex items-center gap-1.5">
      {children}
      {onClick && <ArrowUpDown className="h-3 w-3 opacity-50" />}
    </div>
  </th>
);

export function AssessmentsTable({ riskData }: { riskData?: AssessmentData[] }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: "score" | "probability" | "date"; dir: "asc" | "desc" }>({
    key: "date",
    dir: "desc",
  });
  const [page, setPage] = useState(1);
  const pageSize = 6;

  const data = riskData ? riskData.map((item) => ({
    id: item.id || "—",
    customer: item.customer || "—",
    email: item.email || "—",
    score: item.credit_score ?? item.score ?? 0,
    risk: item.risk_level ?? item.risk ?? "Unknown",
    status: (item.approval ? "Approved" : "Rejected") as ApprovalStatus,
    probability: item.probability ?? 0,
    date: item.created_at ?? item.date ?? new Date().toISOString().split("T")[0],
  })) : [];

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    const list = data.filter(
      (a) =>
        String(a.customer).toLowerCase().includes(q) ||
        String(a.email).toLowerCase().includes(q) ||
        String(a.id).toLowerCase().includes(q),
    );
    const sorted = [...list].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (typeof av === "number" && typeof bv === "number") {
        return sort.dir === "asc" ? av - bv : bv - av;
      }
      if (av < bv) return sort.dir === "asc" ? -1 : 1;
      if (av > bv) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [query, sort, data]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const toggleSort = (key: "score" | "probability" | "date") =>
    setSort((s) => ({ key, dir: s.key === key && s.dir === "asc" ? "desc" : "asc" }));

  return (
    <div className="rounded-xl border border-border bg-card shadow-card">
      <div className="flex flex-col gap-3 border-b border-border p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">
            Recent Credit Assessments
          </h3>
          <p className="text-xs text-muted-foreground">Latest AI-scored applications</p>
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search customer…"
            className="h-9 w-full rounded-lg border border-border bg-secondary/40 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring sm:w-64"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        {data.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            No predictions available
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <Th onClick={() => toggleSort("date")}>Date</Th>
                <th className="px-5 py-3 font-medium">Credit Score</th>
                <th className="px-5 py-3 font-medium">Risk Level</th>
                <th className="px-5 py-3 font-medium">Approval</th>
                <Th onClick={() => toggleSort("probability")}>Probability</Th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-border last:border-0 transition-colors hover:bg-secondary/30"
                >
                  <td className="px-5 py-4 text-xs text-muted-foreground">{a.date}</td>
                  <td className="px-5 py-4 font-medium text-foreground">{a.score}</td>
                  <td className="px-5 py-4">
                    <span
                      className={cn(
                        "inline-flex rounded-md border px-2 py-0.5 text-xs font-medium",
                        RISK_STYLES[a.risk] || RISK_STYLES.Medium,
                      )}
                    >
                      {a.risk}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={cn(
                        "inline-flex rounded-md border px-2 py-0.5 text-xs font-medium",
                        STATUS_STYLES[a.status],
                      )}
                    >
                      {a.status}
                    </span>
                  </td>
                  <td className="px-5 py-4 font-medium text-foreground">
                    {(a.probability * 100).toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {data.length > 0 && totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border p-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground disabled:opacity-50"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>
          <span className="text-xs text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground disabled:opacity-50"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
