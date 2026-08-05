import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Topbar } from "@/components/dashboard/Topbar";
import { DashboardSkeleton, ErrorState } from "@/components/common";
import { Hero } from "@/components/dashboard/Hero";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { RiskDonut, VolumeArea, ApprovalBar } from "@/components/dashboard/Charts";
import { AssessmentsTable } from "@/components/dashboard/AssessmentsTable";
import { FraudCenter } from "@/components/dashboard/FraudCenter";
import { AiInsights } from "@/components/dashboard/AiInsights";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { getDashboard, type DashboardData } from "@/lib/api";
import { kpiSparklines, KPI_COMPARE_LABEL } from "@/lib/dashboard-data";

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

  const load = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Real-time updates: listen for new predictions via websocket
  useEffect(() => {
    if (typeof window === "undefined") return;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket("ws://127.0.0.1:8000/ws/predictions");
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg?.type === "prediction") {
            setDashboardData((prev) => {
              if (!prev) return prev;
              const updated = { ...prev } as any;
              updated.recent_predictions = [msg.data, ...(updated.recent_predictions || [])].slice(0, 10);
              // update summary counts if present
              if (updated.portfolio_summary && typeof updated.portfolio_summary.total_predictions === "number") {
                updated.portfolio_summary.total_predictions = (updated.portfolio_summary.total_predictions || 0) + 1;
              }
              return updated;
            });
          }
        } catch (e) {
          console.error("Failed to handle WS message:", e);
        }
      };
    } catch (e) {
      console.warn("Realtime websocket failed to connect:", e);
    }
    return () => {
      try {
        ws?.close();
      } catch (e) {}
    };
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
      key: "enterprise_score",
      label: "Average Enterprise Score",
      value: dashboardData ? String(Math.round(dashboardData.enterprise_summary.average_enterprise_score)) : "—",
      delta: 3.1,
      trend: "up" as const,
      icon: "Gauge",
    },
    {
      key: "enterprise_assessments",
      label: "Enterprise Assessments",
      value: dashboardData ? dashboardData.enterprise_summary.total_enterprise_assessments.toLocaleString() : "—",
      delta: 8.3,
      trend: "up" as const,
      icon: "Briefcase",
    },
    {
      key: "high_risk_accounts",
      label: "High Risk Accounts",
      value: dashboardData ? dashboardData.enterprise_summary.high_risk_accounts.toLocaleString() : "—",
      delta: -4.2,
      trend: "down" as const,
      icon: "AlertTriangle",
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

        <main className="mx-auto w-full max-w-7xl flex-1 space-y-5 p-4 md:p-6 lg:p-8">
          {loading ? (
            <DashboardSkeleton metrics={6} rows={5} />
          ) : error ? (
            <ErrorState error={error} onRetry={load} />
          ) : (
            <>
              <Hero />

              <section>
                <div className="mb-3 flex items-baseline justify-between">
                  <h2 className="text-sm font-semibold tracking-tight text-foreground">
                    Executive overview
                  </h2>
                  <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="h-1.5 w-1.5 rounded-full bg-success" />
                    Real-time · {KPI_COMPARE_LABEL}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                  {kpis.map((k, i) => (
                    <KpiCard
                      key={k.key}
                      index={i}
                      label={k.label}
                      value={k.value}
                      delta={k.delta}
                      trend={k.trend}
                      icon={k.icon}
                      spark={kpiSparklines[k.key]}
                      compareLabel={KPI_COMPARE_LABEL}
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

              {/* Live activity alongside the weekly decision trend. */}
              <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <ApprovalBar />
                </div>
                <ActivityFeed />
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
