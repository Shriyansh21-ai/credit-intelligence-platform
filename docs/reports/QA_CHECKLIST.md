# QA Checklist

**Date:** 2026-08-01
**Target release:** v1.0

## Functional test areas

- [ ] Authentication and session handling.
- [ ] RBAC enforcement — mutating/administrative routes gated by permission.
- [ ] API conventions — 200 success, 400 validation, 403 permission, 404 not found.
- [ ] Multi-tenant isolation — tenant-scoped queries return only tenant data.
- [ ] Pagination on list endpoints returns object-wrapped arrays.

## Regression

- [ ] Full backend suite passes (1,442 tests, 0 failures).
- [ ] No regressions after repository cleanup.
- [ ] Frontend `tsc --noEmit` and `vite build` pass.
- [ ] Migration up/down round-trip clean (head `c3d4e5f6a7b8`).

## End-to-end workflows

- [ ] Enterprise credit assessment flow end to end.
- [ ] Document upload and OCR / statement extraction.
- [ ] Financial analysis computation and output.
- [ ] Risk assessment and scoring.
- [ ] AI report generation.
- [ ] Approval workflow (submission, review, decision).
- [ ] Portfolio views and aggregation.
- [ ] Fraud detection signals.
- [ ] Monitoring and early-warning surfaces.
- [ ] Notifications delivery.
- [ ] Audit trail capture and retrieval.
- [ ] Reports and exports.

## Accessibility

- [ ] Keyboard navigation across primary flows (Radix primitives).
- [ ] ARIA attributes and roles present on interactive components.
- [ ] Light/dark theme rendering verified.
- [ ] Loading/error/empty states render via shared UX components.
- [ ] Run axe-core automated audit and triage findings.
- [ ] Verify WCAG AA colour-contrast ratios; add skip-to-content link.

## Performance smoke

- [ ] Representative read endpoints return within warm p95 targets (18-57 ms).
- [ ] Load test shows zero errors at expected concurrency.
- [ ] Stress test shows graceful degradation, zero failures.
- [ ] Chaos test confirms fault isolation and recovery.
