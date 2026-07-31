# Phase 10 — Testing Report

## Result
**Full backend suite: 961 passed, 0 failed** (`pytest backend/tests`, ~13 min).
Baseline before Phase 10 was **807**; Phase 10 adds **154 net-new tests**. The 750+ target
is exceeded by a wide margin. **Zero regressions** — every pre-existing test still passes.

**Frontend:** `npm run build` clean (exit 0, TypeScript typechecked, route tree generated).

## Coverage by milestone (new tests)

| Test file | Milestone(s) | Focus |
|-----------|--------------|-------|
| `test_banking_os_common.py` | foundation | tokenizer, BM25 idf, signatures, content hash |
| `test_banking_os_policy.py` | M7 | operators, dotted paths, combine modes, validation, lifecycle, eval, playground, RBAC |
| `test_banking_os_committee.py` | M4 | quorum, weighted majority, re-votes, signatures, closed-meeting guard, minutes, analytics, RBAC |
| `test_banking_os_search.py` | M2 | keyword/semantic/hybrid ranking, filters, autocomplete, facets, saved/history, reindex |
| `test_banking_os_prompt.py` | M8 | variable extraction, lifecycle (approve→deploy demotes prior), render, evaluation modes |
| `test_banking_os_llm.py` | M9 | routing strategies, capability filter, fallback, local always-available, analytics, RBAC |
| `test_banking_os_fabric.py` | M14 | contract validation, upsert, lineage/impact, cycle guard, contract versioning, quality, stats |
| `test_banking_os_rbac.py` | RBAC | Phase 10 catalog + grants; sync persistence; grants reference real perms |
| `test_banking_os_workflow.py` | M11 | graph validation, auto/decline/waiting paths, loop guard, versioning, run/resume, RBAC |
| `test_banking_os_marketplace.py` | M12 | plugin playbook, silence conditions, seed+run, disable, priority sort, assessment resolve |
| `test_banking_os_scenario.py` | M5/M6 | expected loss, scenario shocks, deterministic Monte Carlo, monotone sensitivity, plan persistence |
| `test_banking_os_governance.py` | M13/M1/M10 | disparate impact, equal opportunity, PSI, UBO, connected-lending, cross-holdings, timeline, persona dashboards |

## Test design
- **Pure cores tested without a DB:** rule evaluator, tokenizer/idf/signatures, contract
  validator, workflow engine, Monte Carlo, fairness math — fast and deterministic.
- **API tests** spin up the real routers with `get_db` + `get_current_user` overridden and
  RBAC seeded; they assert both happy paths and **403 permission denials** per role.
- **Determinism asserted** where it matters (Monte Carlo with a fixed seed returns identical
  results; playground/eval reproducible).
- `test_rbac.py` permission-count assertions updated **86 → 102** (16 new Banking OS perms).

## Migration testing
Applied on a scratch DB across the full Phase 1→10 chain (head `e2f3a4b5c6d7`, 25 `os_*`
tables) and confirmed **reversible** (downgrade → 0 `os_*` tables).

## Not yet automated (recommended next)
Load/performance tests, API contract tests (schema snapshotting), and Playwright E2E over
the new pages — scaffolding recommended in the Deployment report.
