import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Database,
  Loader2,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  formatCrore,
  getDemoPortfolioSummary,
  loadDemoPortfolio,
  resetDemoPortfolio,
  type PortfolioSummary,
} from "@/lib/demo-portfolio";

type Phase = "idle" | "loading" | "working" | "error";

/**
 * "Load Demo Portfolio" panel.
 *
 * Persists a coherent, tenant-isolated demo book via the backend and renders
 * the *actual* returned/DB metrics — never hardcoded numbers. Distinct loading,
 * success and error states; a clear "Demo Data" marker; and a reset action.
 * `onLoaded` lets the parent dashboard refresh once data is persisted.
 */
export function DemoPortfolioCard({ onLoaded }: { onLoaded?: () => void }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [justLoaded, setJustLoaded] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await getDemoPortfolioSummary();
      setSummary(s);
      setPhase("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load portfolio summary");
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleLoad = useCallback(async () => {
    setPhase("working");
    setError(null);
    setJustLoaded(null);
    try {
      const result = await loadDemoPortfolio(50);
      setJustLoaded(result.companies_loaded || result.skipped_existing);
      await refresh();
      onLoaded?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load demo portfolio");
      setPhase("error");
    }
  }, [refresh, onLoaded]);

  const handleReset = useCallback(async () => {
    setPhase("working");
    setError(null);
    try {
      await resetDemoPortfolio();
      setJustLoaded(null);
      await refresh();
      onLoaded?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset demo portfolio");
      setPhase("error");
    }
  }, [refresh, onLoaded]);

  const loaded = !!summary?.loaded;
  const busy = phase === "working";

  return (
    <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
      <CardContent className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
              <Database className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-foreground">Demo Portfolio</h3>
                <Badge variant="secondary" className="gap-1 text-[10px]">
                  <Sparkles className="h-3 w-3" /> Demo Data · Synthetic
                </Badge>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {loaded
                  ? "A synthetic, clearly-labelled book persisted to your organization."
                  : "Populate your organization with ~50 synthetic companies, financials, credit profiles and exposures."}
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {loaded && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleReset}
                disabled={busy}
                className="text-muted-foreground"
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" /> Reset
              </Button>
            )}
            <Button onClick={handleLoad} disabled={busy || phase === "loading"} size="sm">
              {busy ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Working…
                </>
              ) : loaded ? (
                <>
                  <RefreshCw className="mr-1.5 h-4 w-4" /> Reload
                </>
              ) : (
                <>
                  <Sparkles className="mr-1.5 h-4 w-4" /> Load Demo Portfolio
                </>
              )}
            </Button>
          </div>
        </div>

        {phase === "error" && error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
            <Button variant="ghost" size="sm" className="ml-auto h-6 text-xs" onClick={refresh}>
              Retry
            </Button>
          </div>
        )}

        {justLoaded !== null && loaded && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>Demo portfolio ready — {summary?.total_companies} companies persisted.</span>
          </div>
        )}

        {loaded && summary && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6"
          >
            <Metric
              label="Companies"
              value={summary.total_companies.toLocaleString()}
              icon={<Building2 className="h-3.5 w-3.5" />}
            />
            <Metric label="Portfolio Exposure" value={formatCrore(summary.total_exposure)} />
            <Metric label="Approval Rate" value={`${summary.approval_rate.toFixed(1)}%`} />
            <Metric
              label="High-Risk Accounts"
              value={summary.high_risk_accounts.toLocaleString()}
            />
            <Metric label="Avg Credit Score" value={String(summary.average_credit_score)} />
            <Metric label="Avg PD" value={`${(summary.average_pd * 100).toFixed(1)}%`} />
          </motion.div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/60 px-3 py-2">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold tabular-nums text-foreground">{value}</div>
    </div>
  );
}
