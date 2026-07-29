# Prompt Engineering Guide (M4)

## Principle: no hardcoded prompts

Prompts live in a governed registry (`aip_prompts` / `aip_prompt_versions`), not
in application code. Application code renders a **deployed** version by key.

## Lifecycle

```
register → add_version (draft) → evaluate → submit_for_review → approve → deploy
                                                                     ↑        │
                                                                     └ rollback┘
```

- **Templates** are parameterised with `{{variable}}` placeholders; declared
  variables are auto-extracted. `render()` validates that every required variable
  is supplied and fails loudly otherwise.
- **Versions** move through `draft → in_review → approved → deployed → archived`.
  Only an approved version may be deployed; deploying demotes the previously
  deployed version; `rollback` re-deploys an earlier version.
- **Evaluation** (`evaluate_version`) scores a version over a dataset of
  `{variables, must_include?}` cases: render-rate, keyword coverage and a
  template-quality heuristic → a 0–1 score and pass/fail.

## A/B testing

`start_experiment(prompt_id, variant_a_version, variant_b_version, allocation)`
creates an experiment; `assign_variant` buckets a unit deterministically by a
stable hash vs the allocation; `record_experiment_result` accumulates scores;
`conclude_experiment` picks the higher-mean winner.

## Defaults

`seed_defaults` ships governed prompts (`rag_answer`, `credit_memo`,
`investigation_summary`) that are created, approved and deployed idempotently, so
the platform starts with a working, versioned prompt set rather than string
literals.

## Endpoints

`GET/POST /api/aip/prompts`, `POST /seed-defaults`, `GET /{id}/versions`,
`POST /versions`, `POST /render`, `POST /evaluate`, `POST /approve`,
`POST /deploy`, `POST /rollback`, `POST /experiments`, `POST /experiments/result`,
`POST /experiments/{id}/conclude`. RBAC: `aip.prompts.view` / `aip.prompts.manage`.
