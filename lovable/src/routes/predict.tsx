import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { runPrediction, type PredictionRequest, type PredictionResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute('/predict')({
  component: PredictPage,
});

function PredictPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);

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
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
