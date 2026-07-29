# Model Management (M11 + M12 + M13)

## Continuous learning loop (M11)

`services/ai_platform/learning.py` closes the loop from production outcomes back
to model improvement:

- **Capture:** `record_feedback` (ratings, corrections, approval outcomes,
  analyst notes) → `aip_feedback`; `record_signal` (repayment, default, approval,
  correction, drift) → `aip_learning_signals`.
- **Triggers:** `evaluate_triggers` checks thresholds — negative-feedback volume,
  observed defaults, corrections, drift — and proposes **versioned** training
  events (`aip_training_events`) when breached, marking signals processed.
- **Training events** are proposals (`proposed → running → completed`) that flow
  into the model registry; nothing retrains automatically here.

## Model & AI-asset governance (M12)

Training events and the resulting models are registered as governed AI assets
(see `AI_GOVERNANCE.md`) so each has a version, checksum, lineage and lifecycle
state — the audit trail from a retrain to a deployed model.

## Explainability (M13)

`services/ai_platform/explainability.py` explains model/AI decisions with an
additive driver table whose signed contributions **sum to the decision logit**
(exact SHAP-style attribution), plus a LIME-style local view, counterfactuals
("what would flip the decision"), a decision-tree/rule path, feature importance,
a natural-language explanation, an evidence trace, a calibrated confidence
interval and an ordered reasoning chain. Results persist to `aip_explanations`.

## Registries in the platform (summary)

| Layer | Registry | Scope |
|-------|----------|-------|
| Phase 6 | ML model registry | trained ML models |
| Phase 9 | model-governance events | model validation/approval |
| Track 2 M12 | `aip_ai_assets` | prompts, agents, workflows, RAG indexes, datasets, reports, models |

## Endpoints

Learning: `POST /api/aip/learning/{feedback,signal,evaluate-triggers}`,
`POST /training-events/update`, `GET /{feedback,training-events,stats}`.
Explain: `POST /api/aip/explain/decision`, `GET /list`, `GET /{id}`.
RBAC: `aip.learning.*`, `aip.explain.view`.
