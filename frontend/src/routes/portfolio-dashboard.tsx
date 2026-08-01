import { createFileRoute } from "@tanstack/react-router";

import {
  CategoryPie,
  CountBarChart,
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  fmtCurrency,
  titleCase,
  usePortfolioOps,
} from "@/features/operations";

export const Route = createFileRoute("/portfolio-dashboard")({ component: PortfolioDashboardPage });

function PortfolioDashboardPage() {
  const { data, isLoading, error } = usePortfolioOps();

  return (
    <OpsLayout
      title="Portfolio Dashboard"
      description="Book composition and concentration — distribution of applications and exposure across status, industry and rating."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null}>
        {data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <MetricCard label="Applications" value={data.totals.applications} />
              <MetricCard label="Total Exposure" value={fmtCurrency(data.totals.total_exposure)} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="By status">
                <CategoryPie
                  data={data.by_status.map((g) => ({ label: titleCase(g.value), value: g.count }))}
                />
              </SectionCard>
              <SectionCard title="By rating">
                <CategoryPie
                  data={data.by_rating.map((g) => ({ label: titleCase(g.value), value: g.count }))}
                />
              </SectionCard>
            </div>

            <SectionCard title="Exposure by industry">
              <CountBarChart
                data={data.by_industry.map((g) => ({
                  label: titleCase(g.value),
                  value: Math.round(g.exposure),
                }))}
                color="#06b6d4"
              />
            </SectionCard>
          </div>
        )}
      </StateWrap>
    </OpsLayout>
  );
}
