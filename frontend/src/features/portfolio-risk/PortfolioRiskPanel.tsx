import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  acknowledgeCovenantEvaluation,
  acknowledgeExposureBreach,
  createCompanyCovenant,
  createExposureLimit,
  evaluateCompanyCovenant,
  evaluateExposureLimits,
  getCompanyCovenants,
  getExposureLimits,
  getPortfolioRiskCompanies,
  getPortfolioRiskOverview,
  updateExposureLimit,
  type ExposureLimit,
} from "./api";

const inputClass = "rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground";

function showAmount(value: number | null, currency: string) {
  if (value === null) return "Unavailable";
  return `${currency} ${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)}`;
}

function LimitEditor({ limit, onSaved }: { limit: ExposureLimit; onSaved: () => void }) {
  const [threshold, setThreshold] = useState(String(limit.threshold));
  const [approaching, setApproaching] = useState(
    limit.approaching_ratio === null ? "" : String(limit.approaching_ratio),
  );
  const [reason, setReason] = useState("");
  const save = useMutation({
    mutationFn: () =>
      updateExposureLimit(limit.id, {
        threshold: Number(threshold),
        ...(approaching
          ? { approaching_ratio: Number(approaching) }
          : { clear_approaching_ratio: true }),
        reason,
      }),
    onSuccess: onSaved,
  });
  const deactivate = useMutation({
    mutationFn: () => updateExposureLimit(limit.id, { is_active: false, reason }),
    onSuccess: onSaved,
  });

  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer text-primary">Edit limit configuration</summary>
      <form
        className="mt-3 grid gap-2 sm:grid-cols-4"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <label className="space-y-1 text-muted-foreground">
          <span>Threshold ({limit.currency})</span>
          <input
            className={`${inputClass} w-full`}
            type="number"
            min="0.01"
            step="any"
            required
            value={threshold}
            onChange={(event) => setThreshold(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-muted-foreground">
          <span>Approaching ratio (optional)</span>
          <input
            className={`${inputClass} w-full`}
            type="number"
            min="0.01"
            max="0.99"
            step="any"
            value={approaching}
            onChange={(event) => setApproaching(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-muted-foreground sm:col-span-2">
          <span>Reason for change</span>
          <input
            className={`${inputClass} w-full`}
            required
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <div className="flex gap-2 sm:col-span-4">
          <button className="rounded-md bg-primary px-3 py-2 font-medium text-primary-foreground">
            Save changes
          </button>
          {limit.is_active && (
            <button
              className="rounded-md border border-destructive px-3 py-2 text-destructive"
              type="button"
              disabled={!reason || deactivate.isPending}
              onClick={() => deactivate.mutate()}
            >
              Deactivate limit
            </button>
          )}
          {(save.error || deactivate.error) && (
            <span className="self-center text-destructive">
              {(save.error || deactivate.error)?.message}
            </span>
          )}
        </div>
      </form>
    </details>
  );
}

export function PortfolioRiskPanel() {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<"portfolio" | "company" | "sector">("portfolio");
  const [companyId, setCompanyId] = useState("");
  const [sector, setSector] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [threshold, setThreshold] = useState("");
  const [approachingRatio, setApproachingRatio] = useState("");
  const [breachReason, setBreachReason] = useState("");
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | undefined>();
  const [covenantMetric, setCovenantMetric] = useState<
    "current_ratio_min" | "debt_to_equity_max" | "debt_to_ebitda_max"
  >("current_ratio_min");
  const [covenantName, setCovenantName] = useState("");
  const [covenantThreshold, setCovenantThreshold] = useState("");
  const overview = useQuery({
    queryKey: ["portfolio-risk", "overview"],
    queryFn: getPortfolioRiskOverview,
  });
  const limits = useQuery({
    queryKey: ["portfolio-risk", "limits"],
    queryFn: getExposureLimits,
  });
  const companies = useQuery({
    queryKey: ["portfolio-risk", "companies"],
    queryFn: getPortfolioRiskCompanies,
  });
  const covenants = useQuery({
    queryKey: ["portfolio-risk", "covenants", selectedCompanyId],
    queryFn: () => getCompanyCovenants(selectedCompanyId as number),
    enabled: selectedCompanyId !== undefined,
  });
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["portfolio-risk", "overview"] }),
      queryClient.invalidateQueries({ queryKey: ["portfolio-risk", "limits"] }),
      queryClient.invalidateQueries({ queryKey: ["portfolio-risk", "covenants"] }),
    ]);
  const createLimit = useMutation({
    mutationFn: () =>
      createExposureLimit({
        scope,
        ...(scope === "company" ? { company_id: Number(companyId) } : {}),
        ...(scope === "sector" ? { sector } : {}),
        currency,
        threshold: Number(threshold),
        ...(approachingRatio ? { approaching_ratio: Number(approachingRatio) } : {}),
      }),
    onSuccess: () => {
      setThreshold("");
      setApproachingRatio("");
      void refresh();
    },
  });
  const evaluateLimits = useMutation({
    mutationFn: evaluateExposureLimits,
    onSuccess: () => void refresh(),
  });
  const acknowledgeBreach = useMutation({
    mutationFn: (id: number) => acknowledgeExposureBreach(id, breachReason),
    onSuccess: () => {
      setBreachReason("");
      void refresh();
    },
  });
  const createCovenant = useMutation({
    mutationFn: () =>
      createCompanyCovenant(selectedCompanyId as number, {
        metric_key: covenantMetric,
        name: covenantName,
        threshold: Number(covenantThreshold),
      }),
    onSuccess: () => {
      setCovenantName("");
      setCovenantThreshold("");
      void refresh();
    },
  });
  const evaluateCovenant = useMutation({
    mutationFn: evaluateCompanyCovenant,
    onSuccess: () => void refresh(),
  });
  const acknowledgeCovenant = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      acknowledgeCovenantEvaluation(id, reason),
    onSuccess: () => void refresh(),
  });
  const companyRows = companies.data?.companies ?? [];
  const canManageLimits = limits.data?.can_manage === true;
  const selectedCompany = companyRows.find((company) => company.id === selectedCompanyId);

  function submitLimit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createLimit.mutate();
  }

  return (
    <section className="mt-8 space-y-6">
      <header>
        <h2 className="text-lg font-semibold text-foreground">Exposure limits & covenants</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Tenant-scoped controls calculated only from persisted exposure and approved financial
          evidence. Currency totals remain separate; missing or incompatible data is shown as
          incomplete.
        </p>
      </header>

      {overview.isError && (
        <p
          role="alert"
          className="rounded-md border border-destructive/30 p-3 text-sm text-destructive"
        >
          {(overview.error as Error).message}
        </p>
      )}
      {overview.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading portfolio exposure data…</p>
      ) : overview.data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Companies in portfolio</p>
            <p className="mt-1 text-xl font-semibold text-foreground">
              {overview.data.company_count}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">Companies with positive exposure</p>
            <p className="mt-1 text-xl font-semibold text-foreground">
              {overview.data.companies_with_exposure}
            </p>
          </div>
          {overview.data.exposure_by_currency.map((item) => (
            <div key={item.currency} className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Recorded exposure ({item.currency})</p>
              <p className="mt-1 text-xl font-semibold text-foreground">
                {showAmount(item.total_exposure, item.currency)}
              </p>
            </div>
          ))}
        </div>
      ) : null}
      {overview.data && (
        <p className="text-xs text-muted-foreground">
          Data quality: {overview.data.data_quality.missing_or_invalid_exposure_records} missing or
          invalid exposure records; {overview.data.data_quality.exposure_records_without_currency}{" "}
          without currency.
        </p>
      )}

      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Exposure limits</h3>
            <p className="text-xs text-muted-foreground">
              Breach comparison is strictly greater than the configured threshold.
            </p>
          </div>
          {canManageLimits && (
            <button
              type="button"
              className="rounded-md border border-input px-3 py-2 text-xs text-foreground"
              disabled={evaluateLimits.isPending}
              onClick={() => evaluateLimits.mutate()}
            >
              {evaluateLimits.isPending ? "Evaluating…" : "Evaluate limits"}
            </button>
          )}
        </div>

        {limits.isLoading && <p className="text-sm text-muted-foreground">Loading limits…</p>}
        {limits.isError && (
          <p role="alert" className="text-sm text-destructive">
            {(limits.error as Error).message}
          </p>
        )}
        {(limits.data?.limits.length ?? 0) === 0 && !limits.isLoading && (
          <p className="text-sm text-muted-foreground">No limits are configured.</p>
        )}
        <div className="space-y-4">
          {limits.data?.limits.map((limit) => (
            <article key={limit.id} className="rounded-lg border border-border p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h4 className="text-sm font-medium text-foreground">
                    {limit.scope === "portfolio"
                      ? "Whole portfolio"
                      : limit.scope === "company"
                        ? `Company ${limit.scope_key}`
                        : `Sector: ${limit.scope_key}`}
                    {" · "}
                    {limit.currency}
                  </h4>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Limit {showAmount(limit.threshold, limit.currency)} · {limit.company_count}{" "}
                    companies · {limit.status.replaceAll("_", " ")}
                    {limit.utilization !== null &&
                      ` · ${(limit.utilization * 100).toFixed(1)}% utilized`}
                    {limit.remaining_headroom !== null &&
                      ` · ${showAmount(limit.remaining_headroom, limit.currency)} headroom`}
                  </p>
                  {limit.reason && <p className="mt-1 text-xs text-amber-600">{limit.reason}</p>}
                </div>
                {limit.breach && (
                  <span className="rounded-full border border-destructive/30 px-2 py-1 text-xs text-destructive">
                    {limit.breach.status} breach ·{" "}
                    {showAmount(limit.breach.observed_exposure, limit.currency)}
                  </span>
                )}
              </div>
              {canManageLimits && <LimitEditor limit={limit} onSaved={() => void refresh()} />}
              {canManageLimits &&
                limit.breach &&
                limit.breach.status !== "resolved" &&
                limit.breach.status !== "acknowledged" && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <input
                      className={`${inputClass} min-w-56 flex-1`}
                      aria-label="Breach acknowledgement reason"
                      placeholder="Reason for acknowledgement"
                      value={breachReason}
                      onChange={(event) => setBreachReason(event.target.value)}
                    />
                    <button
                      className="rounded-md border border-input px-3 py-2 text-xs"
                      disabled={!breachReason || acknowledgeBreach.isPending}
                      onClick={() => acknowledgeBreach.mutate(limit.breach!.id)}
                    >
                      Acknowledge (does not resolve)
                    </button>
                  </div>
                )}
            </article>
          ))}
        </div>

        {canManageLimits && (
          <form
            className="mt-5 grid gap-3 border-t border-border pt-5 sm:grid-cols-2 lg:grid-cols-4"
            onSubmit={submitLimit}
          >
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>Limit scope</span>
              <select
                className={`${inputClass} w-full`}
                value={scope}
                onChange={(event) => setScope(event.target.value as typeof scope)}
              >
                <option value="portfolio">Whole portfolio</option>
                <option value="company">Company</option>
                <option value="sector">Sector</option>
              </select>
            </label>
            {scope === "company" && (
              <label className="space-y-1 text-xs text-muted-foreground">
                <span>Company</span>
                <select
                  className={`${inputClass} w-full`}
                  required
                  value={companyId}
                  onChange={(event) => setCompanyId(event.target.value)}
                >
                  <option value="">Choose company</option>
                  {companyRows.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name} (ID {company.id})
                    </option>
                  ))}
                </select>
              </label>
            )}
            {scope === "sector" && (
              <label className="space-y-1 text-xs text-muted-foreground">
                <span>Sector</span>
                <select
                  className={`${inputClass} w-full`}
                  required
                  value={sector}
                  onChange={(event) => setSector(event.target.value)}
                >
                  <option value="">Choose sector</option>
                  {[...new Set(companyRows.map((company) => company.sector).filter(Boolean))].map(
                    (value) => (
                      <option key={value} value={value as string}>
                        {value}
                      </option>
                    ),
                  )}
                </select>
              </label>
            )}
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>Currency</span>
              <input
                className={`${inputClass} w-full uppercase`}
                minLength={3}
                maxLength={3}
                pattern="[A-Z]{3}"
                required
                value={currency}
                onChange={(event) => setCurrency(event.target.value.toUpperCase())}
              />
            </label>
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>Threshold</span>
              <input
                className={`${inputClass} w-full`}
                type="number"
                min="0.01"
                step="any"
                required
                value={threshold}
                onChange={(event) => setThreshold(event.target.value)}
              />
            </label>
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>Approaching ratio (optional)</span>
              <input
                className={`${inputClass} w-full`}
                type="number"
                min="0.01"
                max="0.99"
                step="any"
                value={approachingRatio}
                onChange={(event) => setApproachingRatio(event.target.value)}
              />
            </label>
            <button className="self-end rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground">
              Create limit
            </button>
          </form>
        )}
        {createLimit.error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {createLimit.error.message}
          </p>
        )}
        {evaluateLimits.error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {evaluateLimits.error.message}
          </p>
        )}
        {acknowledgeBreach.error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {acknowledgeBreach.error.message}
          </p>
        )}
      </div>

      <div className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-sm font-semibold text-foreground">Company covenants</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Current ratio, debt-to-equity, and debt-to-EBITDA use values from the latest approved
          financial statement only.
        </p>
        <label className="mt-4 block max-w-lg space-y-1 text-xs text-muted-foreground">
          <span>Company</span>
          <select
            className={`${inputClass} w-full`}
            value={selectedCompanyId ?? ""}
            onChange={(event) =>
              setSelectedCompanyId(event.target.value ? Number(event.target.value) : undefined)
            }
          >
            <option value="">Choose company</option>
            {companyRows.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name}
              </option>
            ))}
          </select>
        </label>
        {companies.isError && (
          <p role="alert" className="mt-2 text-sm text-destructive">
            {(companies.error as Error).message}
          </p>
        )}
        {selectedCompanyId !== undefined && (
          <>
            {covenants.isLoading && (
              <p className="mt-3 text-sm text-muted-foreground">Loading covenants…</p>
            )}
            {covenants.isError && (
              <p role="alert" className="mt-3 text-sm text-destructive">
                {(covenants.error as Error).message}
              </p>
            )}
            {covenants.data?.covenants.map((covenant) => (
              <article key={covenant.id} className="mt-3 rounded-lg border border-border p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">{covenant.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {covenant.operator} {covenant.threshold} {covenant.unit}
                    </p>
                  </div>
                  {covenants.data.can_manage && covenant.is_active === "active" && (
                    <button
                      className="rounded-md border border-input px-3 py-2 text-xs"
                      disabled={evaluateCovenant.isPending}
                      onClick={() => evaluateCovenant.mutate(covenant.id)}
                    >
                      Evaluate approved evidence
                    </button>
                  )}
                </div>
                {covenant.evaluations.map((evaluation) => (
                  <div key={evaluation.id} className="mt-3 border-t border-border pt-3 text-xs">
                    <p className="font-medium text-foreground">
                      {evaluation.status.replaceAll("_", " ")} ·{" "}
                      {evaluation.fiscal_year ?? "No reporting period"}
                      {evaluation.calculated_value !== null &&
                        ` · value ${evaluation.calculated_value}`}
                    </p>
                    <p className="mt-1 text-muted-foreground">
                      Evidence: {evaluation.evidence_status}
                      {evaluation.source_document_id !== null &&
                        ` · approved document ${evaluation.source_document_id}`}
                      {evaluation.acknowledgement_reason &&
                        ` · acknowledged: ${evaluation.acknowledgement_reason}`}
                    </p>
                    {covenants.data?.can_manage &&
                      evaluation.status === "breached" &&
                      !evaluation.acknowledged_at && (
                        <button
                          className="mt-2 rounded-md border border-input px-3 py-1.5"
                          onClick={() => {
                            const reason = window.prompt(
                              "Reason for acknowledging this covenant breach",
                            );
                            if (reason?.trim()) {
                              acknowledgeCovenant.mutate({
                                id: evaluation.id,
                                reason: reason.trim(),
                              });
                            }
                          }}
                        >
                          Acknowledge breach
                        </button>
                      )}
                  </div>
                ))}
              </article>
            ))}
            {covenants.data?.covenants.length === 0 && !covenants.isLoading && (
              <p className="mt-3 text-sm text-muted-foreground">
                No covenants are configured for this company.
              </p>
            )}
            {covenants.data?.can_manage && (
              <form
                className="mt-5 grid gap-3 border-t border-border pt-5 sm:grid-cols-2 lg:grid-cols-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  createCovenant.mutate();
                }}
              >
                <input
                  className={inputClass}
                  aria-label="Covenant name"
                  placeholder="Covenant name"
                  required
                  value={covenantName}
                  onChange={(event) => setCovenantName(event.target.value)}
                />
                <select
                  className={inputClass}
                  aria-label="Covenant metric"
                  value={covenantMetric}
                  onChange={(event) =>
                    setCovenantMetric(event.target.value as typeof covenantMetric)
                  }
                >
                  <option value="current_ratio_min">Minimum current ratio</option>
                  <option value="debt_to_equity_max">Maximum debt to equity</option>
                  <option value="debt_to_ebitda_max">Maximum debt to EBITDA</option>
                </select>
                <input
                  className={inputClass}
                  aria-label="Covenant threshold"
                  type="number"
                  min="0.01"
                  step="any"
                  placeholder="Threshold"
                  required
                  value={covenantThreshold}
                  onChange={(event) => setCovenantThreshold(event.target.value)}
                />
                <button className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground">
                  Add covenant
                </button>
              </form>
            )}
            {createCovenant.error && (
              <p role="alert" className="mt-3 text-sm text-destructive">
                {createCovenant.error.message}
              </p>
            )}
            {evaluateCovenant.error && (
              <p role="alert" className="mt-3 text-sm text-destructive">
                {evaluateCovenant.error.message}
              </p>
            )}
            {acknowledgeCovenant.error && (
              <p role="alert" className="mt-3 text-sm text-destructive">
                {acknowledgeCovenant.error.message}
              </p>
            )}
          </>
        )}
        {selectedCompany && selectedCompany.is_demo && (
          <p className="mt-3 text-xs text-amber-600">
            This is a demo company; covenant evaluations remain subject to approved source-document
            requirements.
          </p>
        )}
      </div>
    </section>
  );
}
