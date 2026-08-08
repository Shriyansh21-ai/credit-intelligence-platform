/**
 * Demo-portfolio API client.
 *
 * Talks to the tenant-isolated backend endpoints under `/api/demo-portfolio`.
 * These deliberately bypass the client-side Demo Mode fixtures (via `authFetch`)
 * because the whole point of this feature is *persisted* data: the numbers the
 * UI shows are the real database counts returned by the backend, scoped to the
 * authenticated user's organization.
 */

import { authFetch } from "@/lib/http";

export interface LoadResult {
  status: string;
  already_loaded: boolean;
  data_source: string;
  is_demo: boolean;
  companies_loaded: number;
  financial_records_loaded: number;
  credit_profiles_loaded: number;
  portfolio_records_loaded: number;
  skipped_existing: number;
}

export interface PortfolioSummary {
  loaded: boolean;
  is_demo: boolean;
  data_source?: string;
  total_companies: number;
  total_exposure: number;
  total_outstanding: number;
  approval_rate: number;
  approved_count: number;
  high_risk_accounts: number;
  delinquent_accounts: number;
  active_borrowers: number;
  average_credit_score: number;
  average_pd: number;
  expected_loss: number;
  risk_distribution: Record<string, number>;
  sector_distribution: Record<string, number>;
  industry_distribution: Record<string, number>;
  financial_trend: { fiscal_year: number; revenue: number; net_income: number; ebitda: number }[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* non-JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function loadDemoPortfolio(count = 50): Promise<LoadResult> {
  const res = await authFetch("/api/demo-portfolio/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count }),
  });
  return json<LoadResult>(res);
}

export async function getDemoPortfolioSummary(): Promise<PortfolioSummary> {
  const res = await authFetch("/api/demo-portfolio/summary");
  return json<PortfolioSummary>(res);
}

export async function resetDemoPortfolio(): Promise<{ status: string; companies_removed: number }> {
  const res = await authFetch("/api/demo-portfolio/reset", { method: "DELETE" });
  return json(res);
}

/** Format rupees as an abbreviated ₹ crore string (1 crore = 1e7). */
export function formatCrore(rupees: number): string {
  const cr = rupees / 1e7;
  if (cr >= 1000) return `₹${(cr / 1000).toFixed(2)} K Cr`;
  return `₹${cr.toLocaleString(undefined, { maximumFractionDigits: 0 })} Cr`;
}
