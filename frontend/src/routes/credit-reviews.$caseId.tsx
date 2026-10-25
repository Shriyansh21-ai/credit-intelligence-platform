import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";

import { OpsLayout } from "@/features/operations/components/OpsLayout";
import {
  useAssignReviewCase,
  useDecideReview,
  useReopenReview,
  useResumeReview,
  useReviewCase,
  useReviewAssignmentCandidates,
  useSaveReviewAssessment,
  useSubmitReviewForApproval,
  useUpdateReviewCondition,
} from "@/features/credit-reviews";
import type {
  CreditReviewDetail,
  DecisionOutcome,
  ReviewRecommendation,
} from "@/features/credit-reviews";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const Route = createFileRoute("/credit-reviews/$caseId")({
  component: CreditReviewCasePage,
});

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  in_review: "In review",
  pending_approval: "Pending approval",
  approved: "Approved",
  declined: "Declined",
  deferred: "Deferred",
  returned_for_revision: "Returned for revision",
};

const RECOMMENDATIONS: Array<{ value: ReviewRecommendation; label: string }> = [
  { value: "recommend_approval", label: "Recommend approval" },
  { value: "recommend_approval_with_conditions", label: "Recommend approval with conditions" },
  { value: "recommend_decline", label: "Recommend decline" },
  { value: "request_information", label: "Request additional information" },
  { value: "escalate", label: "Escalate for further review" },
];

const DECISIONS: Array<{ value: DecisionOutcome; label: string }> = [
  { value: "approved", label: "Approve" },
  { value: "approved_with_conditions", label: "Approve with conditions" },
  { value: "declined", label: "Decline" },
  { value: "deferred", label: "Defer" },
  { value: "returned_for_revision", label: "Return for revision" },
];

type AssessmentForm = {
  summary: string;
  strengths: string;
  weaknesses: string;
  risk_indicators: string;
  data_quality_concerns: string;
  mitigations: string;
  outstanding_questions: string;
  recommendation: ReviewRecommendation;
  recommendation_rationale: string;
};

const emptyAssessment: AssessmentForm = {
  summary: "",
  strengths: "",
  weaknesses: "",
  risk_indicators: "",
  data_quality_concerns: "",
  mitigations: "",
  outstanding_questions: "",
  recommendation: "request_information",
  recommendation_rationale: "",
};

function toLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function displayValue(value: number | string | null | undefined, currency?: string | null) {
  if (value === null || value === undefined || value === "") return "Not provided";
  if (typeof value === "number") {
    return `${currency ? `${currency} ` : ""}${value.toLocaleString()}`;
  }
  return value;
}

function ReviewField({
  label,
  value,
  currency,
}: {
  label: string;
  value: number | string | null | undefined;
  currency?: string | null;
}) {
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-medium">{displayValue(value, currency)}</p>
    </div>
  );
}

function CreditReviewCasePage() {
  const { caseId: rawCaseId } = Route.useParams();
  const caseId = Number(rawCaseId);
  const query = useReviewCase(caseId);
  const detail = query.data;
  const candidates = useReviewAssignmentCandidates(detail?.actions.can_assign ?? false);
  const assign = useAssignReviewCase(caseId);
  const saveAssessment = useSaveReviewAssessment(caseId);
  const submitApproval = useSubmitReviewForApproval(caseId);
  const decide = useDecideReview(caseId);
  const resume = useResumeReview(caseId);
  const reopen = useReopenReview(caseId);
  const [assessment, setAssessment] = useState<AssessmentForm>(emptyAssessment);
  const [loadedId, setLoadedId] = useState<number | null>(null);
  const [analystId, setAnalystId] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [outcome, setOutcome] = useState<DecisionOutcome | "">("");
  const [decisionRationale, setDecisionRationale] = useState("");
  const [conditionDescription, setConditionDescription] = useState("");
  const [actionReason, setActionReason] = useState("");
  const [conditionNotes, setConditionNotes] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    const latest = detail?.assessments.at(-1);
    if (!detail || loadedId === detail.id) return;
    setAssessment(
      latest
        ? {
            summary: latest.summary,
            strengths: latest.strengths.join("\n"),
            weaknesses: latest.weaknesses.join("\n"),
            risk_indicators: latest.risk_indicators.join("\n"),
            data_quality_concerns: latest.data_quality_concerns.join("\n"),
            mitigations: latest.mitigations.join("\n"),
            outstanding_questions: latest.outstanding_questions.join("\n"),
            recommendation: latest.recommendation,
            recommendation_rationale: latest.recommendation_rationale,
          }
        : emptyAssessment,
    );
    setLoadedId(detail.id);
    setAnalystId(String(detail.analyst_id));
    setReviewerId(detail.reviewer_id ? String(detail.reviewer_id) : "");
  }, [detail, loadedId]);

  async function runAction(action: () => Promise<unknown>) {
    setActionError("");
    try {
      await action();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "The operation failed.");
    }
  }

  async function submitAssessment(submit: boolean) {
    await runAction(() =>
      saveAssessment.mutateAsync({
        ...assessment,
        strengths: toLines(assessment.strengths),
        weaknesses: toLines(assessment.weaknesses),
        risk_indicators: toLines(assessment.risk_indicators),
        data_quality_concerns: toLines(assessment.data_quality_concerns),
        mitigations: toLines(assessment.mitigations),
        outstanding_questions: toLines(assessment.outstanding_questions),
        evidence_refs: {
          financial_ids: detail?.financials.map((row) => row.id) ?? [],
          document_ids: [],
        },
        submit,
      }),
    );
  }

  async function submitDecision() {
    if (!outcome) return;
    const conditions =
      outcome === "approved_with_conditions" && conditionDescription.trim()
        ? [{ description: conditionDescription.trim() }]
        : [];
    await runAction(() =>
      decide.mutateAsync({
        outcome,
        rationale: decisionRationale,
        conditions,
      }),
    );
  }

  async function submitAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!analystId) return;
    await runAction(() =>
      assign.mutateAsync({
        analyst_id: Number(analystId),
        reviewer_id: reviewerId ? Number(reviewerId) : null,
      }),
    );
  }

  if (query.isLoading) {
    return (
      <OpsLayout title="Credit Review" description="Loading case details…">
        <p className="text-sm text-muted-foreground">Loading case, evidence, and history…</p>
      </OpsLayout>
    );
  }

  if (query.error || !detail) {
    return (
      <OpsLayout title="Credit Review" description="Case details are unavailable.">
        <Card>
          <CardContent className="pt-6 text-sm text-destructive">
            {query.error?.message ?? "The case could not be loaded."}
          </CardContent>
        </Card>
      </OpsLayout>
    );
  }

  const latestAssessment = detail.assessments.at(-1);
  const timeline: Array<{
    key: string;
    kind: string;
    title: string;
    timestamp: string | null;
    actor: string;
    body?: string;
  }> = [
    ...detail.history.map((item, index) => ({
      key: `audit-${item.action}-${item.timestamp}-${index}`,
      kind: "Workflow",
      title: item.action.replace("credit_review.", "").replaceAll("_", " "),
      timestamp: item.timestamp,
      actor: item.actor_email ?? `User ${item.actor_id ?? "unknown"}`,
      body: item.reason ?? undefined,
    })),
    ...detail.assessments.map((item) => ({
      key: `assessment-${item.id}`,
      kind: "Analyst assessment",
      title: `Version ${item.version} · ${item.submitted_at ? "Submitted" : "Draft"}`,
      timestamp: item.created_at,
      actor: `User ${item.author_id}`,
      body: [
        item.summary || "No assessment summary recorded.",
        `Recommendation (not final): ${item.recommendation.replaceAll("_", " ")}`,
        item.recommendation_rationale || "No recommendation rationale recorded.",
      ].join("\n\n"),
    })),
    ...detail.decisions.map((item) => ({
      key: `decision-${item.id}`,
      kind: "Final decision",
      title: item.outcome.replaceAll("_", " "),
      timestamp: item.created_at,
      actor: `Authorized user ${item.actor_id}`,
      body: [
        item.rationale,
        `Review cycle ${item.cycle_number} · Assessment #${item.assessment_id}`,
        `Reporting periods: ${item.reporting_periods.length ? item.reporting_periods.join(", ") : "None linked"}`,
        item.previous_decision_id ? `Previous decision #${item.previous_decision_id}` : "",
      ]
        .filter(Boolean)
        .join("\n"),
    })),
    ...detail.condition_history.map((item, index) => ({
      key: `condition-${item.condition_id}-${item.action}-${item.created_at}-${index}`,
      kind: "Condition follow-up",
      title: `Condition #${item.condition_id} · ${item.action}`,
      timestamp: item.created_at,
      actor: `User ${item.actor_id}`,
      body:
        item.reason ?? String(item.new_value.completion_notes ?? item.new_value.description ?? ""),
    })),
  ].sort((left, right) => {
    const leftTime = left.timestamp ? Date.parse(left.timestamp) : Number.MAX_SAFE_INTEGER;
    const rightTime = right.timestamp ? Date.parse(right.timestamp) : Number.MAX_SAFE_INTEGER;
    return leftTime - rightTime;
  });

  return (
    <OpsLayout
      title={detail.title}
      description={`${detail.company.name} · ${detail.reference} · ${STATUS_LABELS[detail.status]}`}
      actions={
        <Link to="/credit-reviews" className="text-sm text-primary hover:underline">
          Back to review queue
        </Link>
      }
    >
      {actionError && (
        <Card>
          <CardContent className="pt-6 text-sm text-destructive">{actionError}</CardContent>
        </Card>
      )}
      {detail.missing_data_warnings.map((warning) => (
        <div
          key={warning}
          className="rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm"
        >
          {warning}
        </div>
      ))}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Company</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>{detail.company.name}</p>
            <p className="text-muted-foreground">
              {detail.company.industry}
              {detail.company.sector ? ` · ${detail.company.sector}` : ""}
            </p>
            <p className="text-muted-foreground">
              {detail.company.country ?? "Country not provided"}
              {detail.company.is_demo ? " · Demonstration company" : ""}
            </p>
            <p>Analyst: {detail.analyst_id}</p>
            <p>Reviewer: {detail.reviewer_id ?? "Not assigned"}</p>
            <p>Review cycle: {detail.cycle_number}</p>
            <p>
              Reporting periods:{" "}
              {detail.reporting_periods.length
                ? detail.reporting_periods.join(", ")
                : "None linked"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Stored risk profile</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            <ReviewField label="Credit score" value={detail.risk_profile?.credit_score} />
            <ReviewField label="Risk grade" value={detail.risk_profile?.risk_grade} />
            <ReviewField label="Current ratio" value={detail.risk_profile?.current_ratio} />
            <ReviewField label="Quick ratio" value={detail.risk_profile?.quick_ratio} />
            <ReviewField label="Debt / equity" value={detail.risk_profile?.debt_to_equity} />
            <ReviewField label="Interest coverage" value={detail.risk_profile?.interest_coverage} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Portfolio exposure</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            <ReviewField
              label="Exposure"
              value={detail.exposure?.exposure}
              currency={detail.company.currency}
            />
            <ReviewField
              label="Outstanding"
              value={detail.exposure?.outstanding_amount}
              currency={detail.company.currency}
            />
            <ReviewField label="Utilization" value={detail.exposure?.utilization} />
            <ReviewField label="Delinquency days" value={detail.exposure?.delinquency_days} />
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Portfolio limits and covenant evidence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <section>
            <h3 className="mb-2 text-sm font-medium">Applicable exposure limits</h3>
            {detail.portfolio_risk_evidence.limits.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No active portfolio, sector, or company limits apply.
              </p>
            ) : (
              <div className="space-y-2">
                {detail.portfolio_risk_evidence.limits.map((limit) => (
                  <div key={limit.id} className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="font-medium">
                        {limit.scope === "portfolio"
                          ? "Portfolio limit"
                          : `${limit.scope}: ${limit.scope_key}`}
                        {" · "}
                        {displayValue(limit.threshold, limit.currency)}
                      </span>
                      <span>{limit.status.replaceAll("_", " ")}</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {limit.calculation_status === "calculated"
                        ? `${displayValue(limit.eligible_exposure, limit.currency)} used · ${limit.utilization === null ? "utilization unavailable" : `${(limit.utilization * 100).toFixed(1)}% utilized`} · ${displayValue(limit.remaining_headroom, limit.currency)} headroom`
                        : (limit.reason ?? "Exposure calculation is incomplete.")}
                      {limit.breach &&
                        ` · breach ${limit.breach.status}, observed ${displayValue(limit.breach.observed_exposure, limit.currency)}`}
                    </p>
                    {limit.breach?.acknowledgement_reason && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Acknowledged: {limit.breach.acknowledgement_reason}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
          <section>
            <h3 className="mb-2 text-sm font-medium">Company covenants</h3>
            {detail.portfolio_risk_evidence.covenants.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No company covenant definitions are recorded.
              </p>
            ) : (
              <div className="space-y-2">
                {detail.portfolio_risk_evidence.covenants.map((covenant) => {
                  const evaluation = covenant.evaluations[0];
                  return (
                    <div key={covenant.id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">
                        {covenant.name} · {covenant.operator} {covenant.threshold} {covenant.unit}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {evaluation
                          ? `${evaluation.status.replaceAll("_", " ")} · ${evaluation.fiscal_year ?? "No period"} · ${evaluation.evidence_status}${evaluation.calculated_value === null ? "" : ` · value ${evaluation.calculated_value}`}${evaluation.source_document_id === null ? "" : ` · source document ${evaluation.source_document_id}`}`
                          : "No evaluation recorded; no covenant outcome is implied."}
                      </p>
                      {evaluation?.acknowledgement_reason && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Acknowledged: {evaluation.acknowledgement_reason}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </CardContent>
      </Card>

      {detail.actions.can_assign && (
        <Card>
          <CardHeader>
            <CardTitle>Case assignment</CardTitle>
          </CardHeader>
          <CardContent>
            {candidates.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading active tenant reviewers…</p>
            ) : candidates.error ? (
              <p className="text-sm text-destructive">{candidates.error.message}</p>
            ) : (
              <form className="grid gap-4 md:grid-cols-3" onSubmit={submitAssignment}>
                <div className="space-y-2">
                  <Label htmlFor="case-analyst">Assigned analyst</Label>
                  <select
                    id="case-analyst"
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    value={analystId}
                    onChange={(event) => setAnalystId(event.target.value)}
                    required
                  >
                    <option value="">Select analyst</option>
                    {(candidates.data ?? [])
                      .filter((candidate) => candidate.can_be_analyst)
                      .map((candidate) => (
                        <option key={candidate.id} value={candidate.id}>
                          {candidate.name || candidate.email} · {candidate.id}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="case-reviewer">Reviewer / approver</Label>
                  <select
                    id="case-reviewer"
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    value={reviewerId}
                    onChange={(event) => setReviewerId(event.target.value)}
                  >
                    <option value="">No named reviewer</option>
                    {(candidates.data ?? [])
                      .filter((candidate) => candidate.can_be_reviewer)
                      .map((candidate) => (
                        <option key={candidate.id} value={candidate.id}>
                          {candidate.name || candidate.email} · {candidate.id}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="flex items-end">
                  <Button type="submit" disabled={!analystId || assign.isPending}>
                    {assign.isPending ? "Saving…" : "Save assignment"}
                  </Button>
                </div>
              </form>
            )}
            {assign.error && (
              <p className="mt-3 text-sm text-destructive">{assign.error.message}</p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Approved financial statements and provenance</CardTitle>
        </CardHeader>
        <CardContent>
          {detail.financials.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No approved statements are linked. Missing information is not treated as zero.
            </p>
          ) : (
            <div className="space-y-4">
              {detail.financials.map((row) => (
                <section key={row.id} className="space-y-3 rounded-md border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-medium">
                      FY {row.fiscal_year} · {row.currency ?? "Currency not provided"} · {row.unit}
                    </h3>
                    <span className="rounded-full border px-2.5 py-1 text-xs">
                      Approved · Source {row.source_document_name} (#{row.source_document_id})
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    {[
                      ["Revenue", row.revenue],
                      ["EBITDA", row.ebitda],
                      ["EBIT", row.ebit],
                      ["Net income", row.net_income],
                      ["Assets", row.total_assets],
                      ["Liabilities", row.total_liabilities],
                      ["Equity", row.equity],
                      ["Cash", row.cash],
                      ["Debt", row.debt],
                      ["Current assets", row.current_assets],
                      ["Current liabilities", row.current_liabilities],
                      ["Operating cash flow", row.operating_cash_flow],
                      ["Free cash flow", row.free_cash_flow],
                    ].map(([label, value]) => (
                      <ReviewField
                        key={label}
                        label={String(label)}
                        value={value as number | null}
                        currency={row.currency}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {detail.actions.can_assess && (
        <Card>
          <CardHeader>
            <CardTitle>
              Analyst assessment{" "}
              {latestAssessment
                ? `(draft version ${latestAssessment.version + (latestAssessment.submitted_at ? 1 : 0)})`
                : ""}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Each save creates a new history version. Lines in the list fields are stored as
              separate assessment points.
            </p>
            <div className="space-y-2">
              <Label>Financial position summary</Label>
              <Textarea
                rows={4}
                value={assessment.summary}
                onChange={(event) => setAssessment({ ...assessment, summary: event.target.value })}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {(
                [
                  ["strengths", "Key strengths"],
                  ["weaknesses", "Key weaknesses"],
                  ["risk_indicators", "Material risks / indicators"],
                  ["mitigations", "Risk mitigations"],
                  ["data_quality_concerns", "Data quality concerns"],
                  ["outstanding_questions", "Outstanding questions"],
                ] as const
              ).map(([key, label]) => (
                <div key={key} className="space-y-2">
                  <Label>{label} · one per line</Label>
                  <Textarea
                    rows={3}
                    value={assessment[key]}
                    onChange={(event) =>
                      setAssessment({ ...assessment, [key]: event.target.value })
                    }
                  />
                </div>
              ))}
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Recommendation</Label>
                <select
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={assessment.recommendation}
                  onChange={(event) =>
                    setAssessment({
                      ...assessment,
                      recommendation: event.target.value as ReviewRecommendation,
                    })
                  }
                >
                  {RECOMMENDATIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Recommendation rationale</Label>
                <Textarea
                  rows={3}
                  value={assessment.recommendation_rationale}
                  onChange={(event) =>
                    setAssessment({ ...assessment, recommendation_rationale: event.target.value })
                  }
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => void submitAssessment(false)}
                disabled={saveAssessment.isPending}
              >
                Save draft version
              </Button>
              <Button
                onClick={() => void submitAssessment(true)}
                disabled={saveAssessment.isPending}
              >
                Submit assessment
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {detail.actions.can_submit_for_approval && (
        <Card>
          <CardHeader>
            <CardTitle>Approval handoff</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              The analyst recommendation is not a final credit decision.
            </p>
            <Button
              onClick={() => void runAction(() => submitApproval.mutateAsync(undefined))}
              disabled={submitApproval.isPending}
            >
              Send to approval queue
            </Button>
          </CardContent>
        </Card>
      )}

      {detail.actions.can_decide && (
        <Card>
          <CardHeader>
            <CardTitle>Authorized decision</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-md border p-4">
              <p className="font-medium">
                Analyst recommendation:{" "}
                {latestAssessment?.recommendation.replaceAll("_", " ") ?? "Not submitted"}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
                {latestAssessment?.recommendation_rationale}
              </p>
              <p className="mt-3 text-sm">{latestAssessment?.summary}</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Decision outcome</Label>
                <select
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={outcome}
                  onChange={(event) => setOutcome(event.target.value as DecisionOutcome | "")}
                  required
                >
                  <option value="">Select an outcome</option>
                  {DECISIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              {outcome === "approved_with_conditions" && (
                <div className="space-y-2">
                  <Label>Approval condition</Label>
                  <Textarea
                    value={conditionDescription}
                    onChange={(event) => setConditionDescription(event.target.value)}
                    rows={3}
                  />
                </div>
              )}
              <div className="space-y-2 md:col-span-2">
                <Label>Decision rationale</Label>
                <Textarea
                  rows={4}
                  value={decisionRationale}
                  onChange={(event) => setDecisionRationale(event.target.value)}
                />
              </div>
            </div>
            <Button
              onClick={() => void submitDecision()}
              disabled={decide.isPending || !outcome || !decisionRationale.trim()}
            >
              Record decision
            </Button>
          </CardContent>
        </Card>
      )}

      {detail.actions.can_resume && (
        <Card>
          <CardHeader>
            <CardTitle>Resume review</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              aria-label="Resume reason"
              value={actionReason}
              onChange={(event) => setActionReason(event.target.value)}
              placeholder="What changed or was received?"
            />
            <Button
              disabled={!actionReason.trim() || resume.isPending}
              onClick={() => void runAction(() => resume.mutateAsync(actionReason))}
            >
              Resume in review
            </Button>
          </CardContent>
        </Card>
      )}

      {detail.actions.can_reopen && (
        <Card>
          <CardHeader>
            <CardTitle>Start a new review cycle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              The prior decision remains in history and the new decision will reference it.
            </p>
            <Textarea
              aria-label="Reopen reason"
              value={actionReason}
              onChange={(event) => setActionReason(event.target.value)}
              placeholder="Reason for reopening"
            />
            <Button
              variant="outline"
              disabled={!actionReason.trim() || reopen.isPending}
              onClick={() => void runAction(() => reopen.mutateAsync(actionReason))}
            >
              Reopen case
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Conditions and follow-ups</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {detail.conditions.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No decision conditions have been recorded.
            </p>
          )}
          {detail.conditions.map((condition) => (
            <div
              key={condition.id}
              className="flex flex-col gap-3 rounded-md border p-4 md:flex-row md:items-start md:justify-between"
            >
              <div>
                <p className="font-medium">{condition.description}</p>
                <p className="text-xs text-muted-foreground">
                  Status: {condition.status} · Responsible user:{" "}
                  {condition.responsible_user_id ?? "Not assigned"}
                  {condition.due_date ? ` · Due ${condition.due_date}` : ""}
                </p>
                {condition.completion_notes && (
                  <p className="mt-2 whitespace-pre-wrap text-sm">{condition.completion_notes}</p>
                )}
              </div>
              {detail.actions.can_manage_conditions && condition.status === "open" && (
                <div className="flex flex-col gap-2 md:w-72">
                  <Textarea
                    aria-label={`Evidence or waiver reason for condition ${condition.id}`}
                    value={conditionNotes}
                    onChange={(event) => setConditionNotes(event.target.value)}
                    placeholder="Evidence or waiver reason"
                    rows={2}
                  />
                  <div className="flex gap-2">
                    {(["completed", "waived"] as const).map((status) => (
                      <ConditionAction
                        key={status}
                        caseId={caseId}
                        conditionId={condition.id}
                        status={status}
                        notes={conditionNotes}
                        clearNotes={() => setConditionNotes("")}
                        reportError={setActionError}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Decision and assessment history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {timeline.map((item) => (
            <div
              key={item.key}
              className={`border-l-2 pl-4 ${item.kind === "Final decision" ? "border-primary" : "border-muted"}`}
            >
              <p className="font-medium">
                {item.kind}: {item.title}
              </p>
              <p className="text-xs text-muted-foreground">
                {item.actor} · {item.timestamp ?? "Timestamp unavailable"}
              </p>
              {item.body && <p className="mt-2 whitespace-pre-wrap text-sm">{item.body}</p>}
            </div>
          ))}
          {timeline.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No review activity has been recorded yet.
            </p>
          )}
        </CardContent>
      </Card>
    </OpsLayout>
  );
}

function ConditionAction({
  caseId,
  conditionId,
  status,
  notes,
  clearNotes,
  reportError,
}: {
  caseId: number;
  conditionId: number;
  status: "completed" | "waived";
  notes: string;
  clearNotes: () => void;
  reportError: (error: string) => void;
}) {
  const mutation = useUpdateReviewCondition(caseId, conditionId);
  return (
    <Button
      size="sm"
      variant={status === "waived" ? "outline" : "default"}
      disabled={!notes.trim() || mutation.isPending}
      onClick={() => {
        reportError("");
        void mutation
          .mutateAsync({ status, notes })
          .then(clearNotes)
          .catch((error: unknown) =>
            reportError(error instanceof Error ? error.message : "Condition update failed."),
          );
      }}
    >
      {status === "completed" ? "Mark complete" : "Waive"}
    </Button>
  );
}
