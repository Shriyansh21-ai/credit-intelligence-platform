# AI Evaluation (M5)

## Purpose

Automatic, reproducible **scorecards** for AI outputs, computed from observable
evidence with no network dependency, so a bank's model-risk team can gate quality.

## Metrics

| Metric | How it is computed |
|--------|--------------------|
| factual_accuracy | keyword overlap with expected answer, else groundedness |
| groundedness | fraction of output sentences overlapping the grounding |
| hallucination | fraction of numeric claims not present in the grounding (reported as `1 − rate`; higher = better) |
| consistency | mean pairwise lexical similarity across samples (self-consistency) |
| policy_compliance | penalises hedging/fabrication phrases; requires citations when applicable |
| reasoning | structure + presence of causal connectives |
| latency / cost / token_usage | scored from recorded LLM usage vs thresholds |
| business_correctness | expected decision present in the output |

`score_output` returns per-metric scores, a weighted `overall_score`, a letter
`grade` (A–F) and `passed` (≥ 0.7). `evaluate` persists to `aip_evaluations`.

## Convenience evaluators

- `evaluate_rag_query(query_id)` — pulls the persisted answer + citations.
- `evaluate_agent_run(run_id)` — evaluates the executive summary vs contributions.
- `evaluate_report(report_id)` — evaluates report body vs evidence.

## Suites & rollups

`add_case` stores regression cases (`aip_eval_cases`). `summary` rolls up mean
overall score, pass rate and per-target-type means — consumed by monitoring (M14).

## Endpoints

`POST /api/aip/eval/score`, `POST /rag/{id}`, `POST /agent-run/{id}`,
`POST /report/{id}`, `POST /cases`, `GET /list`, `GET /summary`.
RBAC: `aip.eval.run`.
