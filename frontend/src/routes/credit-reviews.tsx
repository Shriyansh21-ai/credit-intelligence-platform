import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { Link } from "@tanstack/react-router";

import { OpsLayout } from "@/features/operations/components/OpsLayout";
import {
  useCreateReviewCase,
  useReviewCases,
  useReviewCompanies,
  useReviewDashboard,
} from "@/features/credit-reviews";
import type { ReviewFilters } from "@/features/credit-reviews";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const Route = createFileRoute("/credit-reviews")({
  component: CreditReviewsPage,
});

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  in_review: "In review",
  pending_approval: "Pending approval",
  approved: "Approved",
  declined: "Declined",
  deferred: "Deferred",
  returned_for_revision: "Returned",
};

function CreditReviewsPage() {
  const dashboard = useReviewDashboard();
  const navigate = useNavigate();
  const [filters, setFilters] = useState<ReviewFilters>({ assigned_to: "all" });
  const cases = useReviewCases(filters);
  const companies = useReviewCompanies(dashboard.data !== undefined);
  const createCase = useCreateReviewCase();
  const [companyId, setCompanyId] = useState("");
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState("");
  const [reviewType, setReviewType] = useState("initial_assessment");
  const [dueDate, setDueDate] = useState("");

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!companyId || !title.trim()) return;
    try {
      const result = await createCase.mutateAsync({
        company_id: Number(companyId),
        review_type: reviewType,
        title: title.trim(),
        purpose: purpose.trim() || undefined,
        due_date: dueDate || undefined,
      });
      await navigate({
        to: "/credit-reviews/$caseId",
        params: { caseId: String(result.id) },
      });
    } catch {
      return;
    }
  }

  const counts = dashboard.data?.counts;

  return (
    <OpsLayout
      title="Credit Reviews"
      description="Tenant-scoped credit review cases, analyst assessments, authorized decisions, and follow-ups."
    >
      {dashboard.isLoading && (
        <p className="text-sm text-muted-foreground">Loading review dashboard…</p>
      )}
      {(dashboard.error || cases.error || companies.error) && (
        <Card>
          <CardContent className="pt-6 text-sm text-destructive">
            {(dashboard.error ?? cases.error ?? companies.error)?.message ||
              "The review data could not be loaded."}
          </CardContent>
        </Card>
      )}

      {counts && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {[
            ["Draft", counts.draft],
            ["In review", counts.in_review],
            ["Pending approvals", counts.pending_approval],
            ["Approved", counts.approved],
            ["Declined", counts.declined],
            ["Deferred / returned", counts.deferred_or_returned],
          ].map(([label, count]) => (
            <Card key={label}>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="mt-1 text-2xl font-semibold">{count}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {(dashboard.data?.approval_queue ?? []).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>My approval queue</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(dashboard.data?.approval_queue ?? []).map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 border-b pb-3 last:border-0"
              >
                <div>
                  <p className="font-medium">
                    {item.company_name ?? "Company"} — {item.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {item.reference} · Assigned reviewer {item.reviewer_id ?? "not assigned"}
                  </p>
                </div>
                <Link
                  to="/credit-reviews/$caseId"
                  params={{ caseId: String(item.id) }}
                  className="text-sm text-primary hover:underline"
                >
                  Review evidence and decision
                </Link>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {dashboard.data?.can_create && (
        <Card>
          <CardHeader>
            <CardTitle>Create review case</CardTitle>
          </CardHeader>
          <CardContent>
            {companies.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading tenant companies…</p>
            ) : companies.data?.length ? (
              <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCreate}>
                <div className="space-y-2">
                  <Label htmlFor="review-company">Company</Label>
                  <select
                    id="review-company"
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    value={companyId}
                    onChange={(event) => setCompanyId(event.target.value)}
                    required
                  >
                    <option value="">Select a tenant company</option>
                    {companies.data.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name} · {company.industry}
                        {company.is_demo ? " · demo data" : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="review-title">Case title</Label>
                  <Input
                    id="review-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    maxLength={200}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="review-type">Review type</Label>
                  <select
                    id="review-type"
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    value={reviewType}
                    onChange={(event) => setReviewType(event.target.value)}
                  >
                    <option value="initial_assessment">Initial assessment</option>
                    <option value="periodic_review">Periodic review</option>
                    <option value="renewal">Renewal</option>
                    <option value="material_change">Material change</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="review-due-date">Due date (optional)</Label>
                  <Input
                    id="review-due-date"
                    type="date"
                    value={dueDate}
                    onChange={(event) => setDueDate(event.target.value)}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="review-purpose">Purpose (optional)</Label>
                  <Textarea
                    id="review-purpose"
                    value={purpose}
                    onChange={(event) => setPurpose(event.target.value)}
                    maxLength={4000}
                    rows={2}
                  />
                </div>
                {createCase.error && (
                  <p className="text-sm text-destructive md:col-span-2">
                    {createCase.error.message}
                  </p>
                )}
                <div className="md:col-span-2">
                  <Button
                    type="submit"
                    disabled={createCase.isPending || !companyId || !title.trim()}
                  >
                    {createCase.isPending ? "Creating…" : "Create draft case"}
                  </Button>
                </div>
              </form>
            ) : (
              <p className="text-sm text-muted-foreground">
                No companies are available in this tenant. Add a company to the portfolio before
                creating a review.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Review queue</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <Label htmlFor="filter-status">Status</Label>
              <select
                id="filter-status"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={filters.status ?? ""}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, status: event.target.value || undefined }))
                }
              >
                <option value="">All statuses</option>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="filter-type">Review type</Label>
              <select
                id="filter-type"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={filters.review_type ?? ""}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    review_type: event.target.value || undefined,
                  }))
                }
              >
                <option value="">All types</option>
                <option value="initial_assessment">Initial assessment</option>
                <option value="periodic_review">Periodic review</option>
                <option value="renewal">Renewal</option>
                <option value="material_change">Material change</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="filter-company">Company</Label>
              <select
                id="filter-company"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={filters.company_id ?? ""}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    company_id: event.target.value ? Number(event.target.value) : undefined,
                  }))
                }
              >
                <option value="">All companies</option>
                {(companies.data ?? []).map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="filter-assignment">Assignment</Label>
              <select
                id="filter-assignment"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={filters.assigned_to ?? "all"}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    assigned_to: event.target.value as "mine" | "all",
                  }))
                }
              >
                <option value="all">All tenant cases</option>
                <option value="mine">Assigned to me</option>
              </select>
            </div>
          </div>

          {cases.isLoading && <p className="text-sm text-muted-foreground">Loading cases…</p>}
          {cases.data?.items.length === 0 && (
            <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
              No credit review cases match these filters.
            </p>
          )}
          <div className="divide-y">
            {(cases.data?.items ?? []).map((item) => (
              <div
                key={item.id}
                className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <Link
                    to="/credit-reviews/$caseId"
                    params={{ caseId: String(item.id) }}
                    className="font-medium text-primary hover:underline"
                  >
                    {item.company_name ?? "Company"} — {item.title}
                  </Link>
                  <p className="text-xs text-muted-foreground">
                    {item.reference} · {item.review_type.replaceAll("_", " ")} · Analyst{" "}
                    {item.analyst_id}
                    {item.reviewer_id ? ` · Reviewer ${item.reviewer_id}` : ""}
                  </p>
                </div>
                <div className="text-sm">
                  <span className="rounded-full border px-2.5 py-1">
                    {STATUS_LABELS[item.status] ?? item.status}
                  </span>
                  {item.reporting_periods.length > 0 && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      FY {item.reporting_periods.join(", ")}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </OpsLayout>
  );
}
