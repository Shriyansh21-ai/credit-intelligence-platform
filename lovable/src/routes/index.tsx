import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { Hero } from "@/components/dashboard/Hero";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { RiskDonut, VolumeArea, ApprovalBar } from "@/components/dashboard/Charts";
import { AssessmentsTable } from "@/components/dashboard/AssessmentsTable";
import { FraudCenter } from "@/components/dashboard/FraudCenter";
import { AiInsights } from "@/components/dashboard/AiInsights";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { getDashboard, type DashboardData } from "@/lib/api";

export const Route = createFileRoute('/')({
  head: () => ({
    meta: [
      { title: "Dashboard · AI Credit Intelligence" },
      {
        name: "description",
        content:
          "Monitor credit risk, detect fraud, and analyze portfolio performance with explainable AI.",
      },
      { property: "og:title", content: "AI Credit Intelligence Platform" },
      {
        property: "og:description",
        content: "Real-time credit scoring and fraud intelligence for modern risk teams.",
      },
    ],
  }),
  component: DashboardPage,
});

function DashboardPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem("token")) {
      window.location.href = "/login";
      return;
    }
  }, []);

  useEffect(() => {
    async function fetchDashboard() {
      try {
        setLoading(true);
        const data = await getDashboard();
        setDashboardData(data);
        setError(null);
      } catch (err) {
        console.error("Failed to fetch dashboard:", err);
        setError("Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    }

    fetchDashboard();
  }, []);

  if (typeof window !== "undefined" && !localStorage.getItem("token")) {
    return null;
  }

  const kpis = [
    {
      key: "score",
      label: "Average Credit Score",
      value: dashboardData ? String(Math.round(dashboardData.portfolio_summary.average_credit_score)) : "—",
      delta: 2.4,
      trend: "up" as const,
      icon: "Gauge",
    },
    {
      key: "approval",
      label: "Approval Rate",
      value: dashboardData ? `${(dashboardData.portfolio_summary.approval_rate * 100).toFixed(1)}%` : "—",
      delta: 4.1,
      trend: "up" as const,
      icon: "CheckCircle2",
    },
    {
      key: "predictions",
      label: "Total Predictions",
      value: dashboardData ? dashboardData.portfolio_summary.total_predictions.toLocaleString() : "—",
      delta: 12.7,
      trend: "up" as const,
      icon: "Activity",
    },
    {
      key: "fraud",
      label: "Fraud Rate",
      value: dashboardData ? `${(dashboardData.fraud_summary.fraud_rate).toFixed(2)}%` : "—",
      delta: -0.08,
      trend: "down" as const,
      icon: "ShieldAlert",
    },
    {
      key: "fraud_checks",
      label: "Total Fraud Checks",
      value: dashboardData ? dashboardData.fraud_summary.total_checks.toLocaleString() : "—",
      delta: 6.2,
      trend: "up" as const,
      icon: "Users",
    },
    {
      key: "fraud_detected",
      label: "Fraud Detected",
      value: dashboardData ? dashboardData.fraud_summary.fraud_detected.toLocaleString() : "—",
      delta: -14.0,
      trend: "down" as const,
      icon: "AlertTriangle",
    },
  ];

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title="Dashboard" onMenu={() => setMenuOpen(true)} />

        <main className="mx-auto w-full max-w-[1500px] flex-1 space-y-6 p-4 md:p-6 lg:p-8">
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              {error}
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-foreground"></div>
            </div>
          )}

          {!loading && !error && (
            <>
              <Hero />

              <section>
                <div className="mb-3 flex items-baseline justify-between">
                  <h2 className="text-sm font-semibold tracking-tight text-foreground">
                    Executive overview
                  </h2>
                  <span className="text-xs text-muted-foreground">Real-time data</span>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                  {kpis.map((k, i) => (
                    <KpiCard
                      key={k.key}
                      index={i}
                      label={k.label}
                      value={k.value}
                      delta={k.delta}
                      trend={k.trend}
                      icon={k.icon}
                    />
                  ))}
                </div>
              </section>

              <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <RiskDonut />
                <div className="lg:col-span-2">
                  <VolumeArea />
                </div>
              </section>

              <section>
                <ApprovalBar />
              </section>

              <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                <div className="xl:col-span-2">
                  <AssessmentsTable riskData={dashboardData?.recent_predictions} />
                </div>
                <FraudCenter fraudData={dashboardData?.recent_fraud_checks} />
              </section>

              <AiInsights />

              <QuickActions />

              <footer className="pt-2 text-center text-xs text-muted-foreground">
                AI Credit Intelligence · Real-time data · © 2026
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
