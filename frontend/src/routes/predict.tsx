import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { generateAnalystReport, runPrediction, type PredictionRequest, type PredictionResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute('/predict')({
  component: PredictPage,
});

function PredictPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [report, setReport] = useState<Awaited<ReturnType<typeof generateAnalystReport>> | null>(null);

  const [formData, setFormData] = useState<PredictionRequest>({
    age: 25,
    sex: "male",
    job: 0,
    housing: "own",
    saving_account: "little",
    checking_account: "moderate",
    credit_amount: 5000,
    duration: 24,
    purpose: "car",
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);
      const data = await runPrediction(formData);
      setResult(data);
      const reportData = await generateAnalystReport(formData);
      setReport(reportData);
    } catch (err) {
      console.error("Prediction failed:", err);
      setError("Failed to run prediction");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title="Credit Prediction" onMenu={() => setMenuOpen(true)} />

        <main className="mx-auto w-full max-w-2xl flex-1 space-y-6 p-4 md:p-6 lg:p-8">
          <div className="rounded-xl border border-border bg-card shadow-card p-6">
            <h2 className="text-lg font-semibold tracking-tight text-foreground mb-6">
              Run Credit Prediction
            </h2>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-foreground">Age</label>
                  <input
                    type="number"
                    min="18"
                    max="100"
                    value={formData.age}
                    onChange={(e) => setFormData({ ...formData, age: Number(e.target.value) })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground">Sex</label>
                  <select
                    value={formData.sex}
                    onChange={(e) => setFormData({ ...formData, sex: e.target.value })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground">Credit Amount</label>
                  <input
                    type="number"
                    min="1000"
                    max="100000"
                    value={formData.credit_amount}
                    onChange={(e) => setFormData({ ...formData, credit_amount: Number(e.target.value) })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground">Duration (months)</label>
                  <input
                    type="number"
                    min="1"
                    max="72"
                    value={formData.duration}
                    onChange={(e) => setFormData({ ...formData, duration: Number(e.target.value) })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground">Housing</label>
                  <select
                    value={formData.housing}
                    onChange={(e) => setFormData({ ...formData, housing: e.target.value })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="own">Own</option>
                    <option value="rent">Rent</option>
                    <option value="free">Free</option>
                  </select>
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground">Purpose</label>
                  <select
                    value={formData.purpose}
                    onChange={(e) => setFormData({ ...formData, purpose: e.target.value })}
                    className="w-full mt-1.5 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="car">Car</option>
                    <option value="furniture">Furniture</option>
                    <option value="education">Education</option>
                    <option value="business">Business</option>
                    <option value="domestic">Domestic</option>
                  </select>
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
                {loading ? "Running Prediction..." : "Run Prediction"}
              </button>
            </form>
          </div>

          {result && (
            <div className="rounded-xl border border-border bg-card shadow-card p-6 space-y-4">
              <h3 className="text-lg font-semibold tracking-tight text-foreground">Prediction Result</h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Credit Score</div>
                  <div className="text-2xl font-bold text-foreground">{Math.round(result.credit_score)}</div>
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Risk Level</div>
                  <div className={cn(
                    "inline-flex rounded-md border px-3 py-1 text-sm font-medium",
                    {
                      "bg-success/10 text-success border-success/20": result.risk_level === "Low",
                      "bg-warning/10 text-warning border-warning/20": result.risk_level === "Medium",
                      "bg-destructive/10 text-destructive border-destructive/20": result.risk_level === "High",
                    }
                  )}>
                    {result.risk_level}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Approval</div>
                  <div className="text-lg font-semibold text-foreground">
                    {result.approval ? "✓ Approved" : "✗ Rejected"}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Probability</div>
                  <div className="text-2xl font-bold text-foreground">{(result.probability * 100).toFixed(1)}%</div>
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

              {report && (
                <div className="rounded-lg border border-border bg-secondary/20 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-foreground">AI Credit Analyst Report</h4>
                    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">{report.status}</span>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-md bg-background/70 p-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Summary</p>
                      <p className="mt-2 text-sm text-foreground">Score: {report.summary.score}</p>
                      <p className="text-sm text-foreground">Risk: {report.summary.risk_level}</p>
                    </div>
                    <div className="rounded-md bg-background/70 p-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Decision</p>
                      <p className="mt-2 text-sm text-foreground">{report.recommendations.decision}</p>
                      <p className="text-sm text-foreground">{report.recommendations.monitoring}</p>
                    </div>
                  </div>

                  {report.top_factors && report.top_factors.length > 0 && (
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Key factors</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {report.top_factors.map((factor) => (
                          <span key={factor} className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-foreground">{factor}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Analyst note</p>
                    <p className="mt-2 text-sm leading-7 text-foreground">{report.ai_analysis}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
