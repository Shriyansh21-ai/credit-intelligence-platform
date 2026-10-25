import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";
import type { ReviewFilters } from "./types";

const reviewKey = ["credit-reviews"] as const;

export function useReviewDashboard() {
  return useQuery({
    queryKey: [...reviewKey, "dashboard"],
    queryFn: api.getReviewDashboard,
  });
}

export function useReviewCompanies(enabled: boolean) {
  return useQuery({
    queryKey: [...reviewKey, "companies"],
    queryFn: api.getReviewCompanies,
    enabled,
  });
}

export function useReviewAssignmentCandidates(enabled: boolean) {
  return useQuery({
    queryKey: [...reviewKey, "assignment-candidates"],
    queryFn: api.getReviewAssignmentCandidates,
    enabled,
  });
}

export function useReviewCases(filters: ReviewFilters) {
  return useQuery({
    queryKey: [...reviewKey, "cases", filters],
    queryFn: () => api.getReviewCases(filters),
  });
}

export function useReviewCase(caseId: number) {
  return useQuery({
    queryKey: [...reviewKey, "case", caseId],
    queryFn: () => api.getReviewCase(caseId),
    enabled: Number.isInteger(caseId) && caseId > 0,
  });
}

function useReviewMutation<TVariables, TData>(
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: reviewKey });
    },
  });
}

export function useCreateReviewCase() {
  return useReviewMutation(api.createReviewCase);
}

export function useAssignReviewCase(caseId: number) {
  return useReviewMutation((payload: { analyst_id: number; reviewer_id?: number | null }) =>
    api.assignReviewCase(caseId, payload),
  );
}

export function useSaveReviewAssessment(caseId: number) {
  return useReviewMutation((payload: Parameters<typeof api.saveReviewAssessment>[1]) =>
    api.saveReviewAssessment(caseId, payload),
  );
}

export function useSubmitReviewForApproval(caseId: number) {
  return useReviewMutation(() => api.submitReviewForApproval(caseId));
}

export function useDecideReview(caseId: number) {
  return useReviewMutation((payload: Parameters<typeof api.decideReview>[1]) =>
    api.decideReview(caseId, payload),
  );
}

export function useResumeReview(caseId: number) {
  return useReviewMutation((reason: string) => api.resumeReview(caseId, reason));
}

export function useReopenReview(caseId: number) {
  return useReviewMutation((reason: string) => api.reopenReview(caseId, reason));
}

export function useUpdateReviewCondition(caseId: number, conditionId: number) {
  return useReviewMutation((payload: { status: "completed" | "waived"; notes: string }) =>
    api.updateReviewCondition(caseId, conditionId, payload),
  );
}
