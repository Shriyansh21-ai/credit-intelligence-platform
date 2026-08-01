import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { runFraudCheck, type FraudCheckRequest, type FraudCheckResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute('/fraud')({
  component: FraudDetectionPage,
});

function FraudDetectionPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FraudCheckResponse | null>(null);

  const [formData, setFormData] = useState<FraudCheckRequest>({
    amount: 5000,
    frequency: 1,
    account_age: 12,
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);
      const data = await runFraudCheck(formData);
      setResult(data);
    } catch (err) {
      console.error("Fraud check failed:", err);
      setError("Failed to run fraud detection");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title="Fraud Detection" onMenu={() => setMenuOpen(true)} />

        <main className="mx-auto w-full max-w-2xl flex-1 space-y-6 p-4 md:p-6 lg:p-8">
          <div className="rounded-xl border border-border bg-card shadow-card p-6">
            <h2 className="text-lg font-semibold tracking-tight text-foreground mb-6">
              Run Fraud Detection
            </h2>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-foreground">Transaction Amount</label>
                  <input
                    type="number"
                    min="0"
                    max="100000"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: Number(e.target.value) })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground">Transaction Frequency</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={formData.frequency}
                    onChange={(e) => setFormData({ ...formData, frequency: Number(e.target.value) })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground">Account Age (months)</label>
                  <input
                    type="number"
                    min="0"
                    max="240"
                    value={formData.account_age}
                    onChange={(e) => setFormData({ ...formData, account_age: Number(e.target.value) })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>

              {error && (
                <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {loading ? "Running Detection..." : "Run Fraud Detection"}
              </button>
            </form>
          </div>

          {result && (
            <div className="rounded-xl border border-border bg-card shadow-card p-6 space-y-4">
              <h3 className="text-lg font-semibold tracking-tight text-foreground">Detection Result</h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Fraud Detected</div>
                  <div className={cn(
                    "text-lg font-semibold",
                    result.fraud_detected ? "text-destructive" : "text-success"
                  )}>
                    {result.fraud_detected ? "⚠️ Yes" : "✓ No"}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Fraud Score</div>
                  <div className="text-2xl font-bold text-foreground">{(result.fraud_score * 100).toFixed(1)}%</div>
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Anomaly Score</div>
                  <div className="text-2xl font-bold text-foreground">{(result.anomaly_score * 100).toFixed(1)}%</div>
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Risk Level</div>
                  <div className={cn(
                    "inline-flex rounded-md border px-3 py-1 text-sm font-medium",
                    {
                      "bg-success/10 text-success border-success/20": result.fraud_score < 0.3,
                      "bg-warning/10 text-warning border-warning/20": result.fraud_score >= 0.3 && result.fraud_score < 0.7,
                      "bg-destructive/10 text-destructive border-destructive/20": result.fraud_score >= 0.7,
                    }
                  )}>
                    {result.fraud_score < 0.3 ? "Low" : result.fraud_score < 0.7 ? "Medium" : "High"}
                  </div>
                </div>
              </div>

              {result.ai_analysis && (
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-2">AI Analysis</div>
                  <p className="text-sm text-foreground bg-secondary/30 rounded-md p-3">
                    {result.ai_analysis}
                  </p>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
