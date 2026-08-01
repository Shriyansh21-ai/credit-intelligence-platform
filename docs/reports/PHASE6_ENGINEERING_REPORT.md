# Enterprise Machine Learning Platform (MLOps + Explainable AI)

**Status:** Delivered. Additive to Phases 1–5; no existing API, table, or module removed.
**Migration head:** `a7b8c9d0e1f2` (was `d6f7a8b9c0e1`).
**Backend tests:** 368+ (266 pre-existing + 102 new Phase 6 tests), all green.
**Frontend:** builds cleanly, TypeScript clean; 7 new MLOps dashboards.

Phase 6 converts the platform's previously **deterministic** risk engine into a
production-grade **machine-learning platform**: it now learns from historical
lending data, predicts default probability, serves versioned models, explains
every decision, monitors quality and drift, retrains itself, and scores fraud
and portfolio/stress risk with ML — all behind the same interfaces Phases 1–5
already depended on.

The single most important design decision: the existing, curated
`DeterministicRiskEstimator` (a transparent additive log-odds scorecard over the
63-feature registry) is reused as the **latent risk process** that generates
reproducible synthetic training data. Trained models therefore learn a genuine,
economically-coherent signal, and their learned importances line up with the
scorecard's intuition — while the deterministic model remains the always-available
fallback so nothing ever fails for lack of a trained model.

---

## 1. ML Architecture

```
backend/app/services/ml/
├── data/            (M2)  synthetic latent-process generator + reproducible datasets
├── training/        (M2)  algorithm factory · preprocessing · CV · tuning · evaluation · TrainedRiskModel
├── registry/        (M3)  versioning · approval & production state machines · rollback · lineage
├── serving/         (M4)  real-time / batch / portfolio / async inference · caching · latency · history
├── explainability/  (M5)  SHAP + log-odds attribution · reason codes · narratives · storage  (+ Phase 4 base)
├── monitoring/      (M6/M8) operational monitoring · performance vs realised outcomes
├── drift/           (M7)  PSI · feature/target/schema drift · thresholds · history
├── retraining/      (M9)  triggers · champion/challenger · promotion · rollback · snapshotting
├── fraud/           (M10) IsolationForest · LOF · PCA-reconstruction (autoencoder-ready) · clustering
├── portfolio/       (M11) ml_portfolio: EL/UL · concentration · migration · clustering  (+ Phase 4 engine)
├── stress/          (M12) ml_stress: macro-scenario feature shocks re-scored by the model  (+ Phase 4 engine)
├── features/        (M1)  lineage · point-in-time · catalog  (+ Phase 4 feature store)
└── models/          (Phase 4) BaseRiskModel contract + deterministic estimator (fallback + latent process)
```

Every layer depends only on the `BaseRiskModel` contract (`predict` /
`predict_proba` / `predict_risk` / `feature_importance` / `model_metadata`), so a
`TrainedRiskModel` drops into serving, explainability, portfolio and stress with
**zero business-logic change**. Model choice is never hardcoded: serving resolves
the production model from the registry, falling back to the deterministic
scorecard when none is promoted.

**Dependencies added:** `xgboost`, `lightgbm` (real gradient boosting). CatBoost
is registered but **degrades gracefully** when its library is absent (the
platform's established optional-dependency pattern). scikit-learn / shap / pandas
/ numpy / scipy / joblib were already present.

---

## 2. Feature Store Design

Built on the Phase 4 versioned feature store (63 features across 16 categories,
each carrying value / source / version / confidence / generated-time). Phase 6
adds the enterprise-store capabilities:

- **Catalog** — `GET /api/ml/feature-store/catalog`: the full versioned feature
  set grouped by category, for discovery and reuse.
- **Lineage** — `GET /api/ml/feature-store/lineage/{feature}`: a feature's
  definition, data source, unit, version **and the registered models that were
  trained on it** (traced via each model's stored `feature_names`).
- **Point-in-time retrieval** — `GET /api/ml/feature-store/point-in-time/{id}?as_of=…`:
  the exact feature vector that was *current for an entity as of a timestamp*, so
  a historical decision is reproduced with the features it actually saw (no
  leakage from later recomputes).

Feature reuse and point-in-time correctness are what let a model trained today be
reconciled and reproduced years later.

---

## 3. Training Pipeline

One entrypoint, `training.train(dataset, algorithm, …)`, runs the full flow:

```
load → clean → feature engineering → encode/scale → cross-validate →
(optional) hyperparameter tuning → fit → evaluate → serialize → training report
```

- **Data** — a seeded synthetic generator (`data/synthetic.py`) samples plausible
  feature values, runs them through the deterministic estimator to obtain a *true*
  PD, and draws the observed default label from it. Fully reproducible by seed;
  never leaks the true PD into features; supports injected **drift** for testing.
- **Algorithms** — Logistic Regression, Random Forest, Gradient Boosting, Neural
  Network (scikit-learn), XGBoost, LightGBM, CatBoost (graceful degrade). Each has
  fixed random seeds and sensible defaults, plus a small tuning grid.
- **Preprocessing** — median imputation + standardisation in one sklearn
  `Pipeline` (uniform across algorithms).
- **Cross-validation** — dependency-light stratified k-fold ROC-AUC.
- **Evaluation** — the full credit-risk suite (§7 below).
- **Artifact** — `TrainedRiskModel` wraps the fitted pipeline + feature order +
  importances + a median **baseline** row + a small **background sample** (for
  SHAP), and implements `BaseRiskModel`. Serialised with joblib.
- **Report** — metrics, cross-validation, hyperparameters, ranked importances,
  dataset snapshot (spec + content hash), timing — persisted verbatim by the
  registry.

---

## 4. Model Registry

`MLModel` (one row per version) + `MLDataset` (reproducible snapshots) +
`MLDeploymentEvent` (append-only history).

- **Versioning** — monotonic per `model_key`; latest is `is_current`.
- **Approval state machine** — `draft → pending → approved / rejected`.
- **Production state machine** — `none → staging → production → archived / rolled_back`
  (exactly one production model per key; promoting archives the incumbent).
- **Rollback** — restores the most recently archived version and demotes the
  current one to `rolled_back`.
- **Lineage** — `parent_model_id`, `dataset_id`, feature set version, full
  deployment history.
- **Reproducibility endpoint** — `GET …/models/{id}/reproducibility` returns
  dataset spec + content hash + hyperparameters + feature set + lineage.

Tracked fields cover the entire brief: model id, version, training dataset,
hyperparameters, metrics, features used, training time, author, approval status,
production status, rollback support, deployment history.

---

## 5. Serving Architecture

One service, five modes, one logging core:

- **Real-time** (`POST /api/ml/serving/predict`), **batch**, **portfolio**
  (scores current feature vectors), **async** (returns a `request_id`; queue-ready
  contract, inline execution), **bulk** (batch).
- **Model resolution precedence:** explicit `model_id` → production for a key →
  any production model → **deterministic fallback** (serving never fails for lack
  of a trained model).
- **Caching:** loaded artifacts (long TTL) and identical requests (short TTL).
- **Latency + history:** every inference persists to `MLPredictionLog` with
  latency, cache flag, success/error — the substrate for monitoring.

---

## 6. Explainable AI

Extends the Phase 4 presentation layer (waterfall, top factors, narrative) to
trained models:

- **SHAP** — genuine mean-|SHAP| **global importance** for tree models (XGBoost /
  LightGBM / RF / GB), computed on the stored background sample, with a documented
  fall-back to native importances. Genuine **per-instance SHAP values** are also
  returned for the SHAP view.
- **Local attribution** — a signed, baseline-relative one-at-a-time **log-odds
  decomposition** drives the waterfall and top ± factors (consistent units,
  additive, model-agnostic).
- **Reason codes** — adverse-action-style codes from the risk-increasing drivers.
- **Narratives** — executive summary, analyst explanation, business-friendly
  explanation, plus a decision recommendation and explicit decision path.
- **Storage** — every explanation persists to `MLExplanation` (auditable,
  retrievable by entity/model).

---

## 7. Drift Detection

`drift.detect(model, current_rows)` compares the live population to the model's
**regenerated training reference** (from the dataset spec):

- **PSI** per feature and overall, with conventional bands (<0.1 stable,
  0.1–0.25 moderate, >0.25 significant).
- **Feature drift** (PSI + mean shift), **target drift** (predicted-PD
  distribution), **distribution shift** (share of features drifted),
  **missing-feature rate**, **schema changes** (appeared/disappeared features).
- **Breach** when overall PSI ≥ threshold, drifted share ≥ 30%, or a feature went
  missing. Reports persist to `MLDriftReport`; a breach emits a best-effort
  notification and is the trigger consumed by retraining.

Validated: identical distribution → PSI ≈ 0.015 (stable); a 4-feature macro shift
→ PSI ≈ 0.40 (significant), correctly naming exactly the shifted features.

---

## 8. Retraining Pipeline

`retraining.run_retraining(model_key, …)` composes training + registry + drift:

- **Triggers** — manual, scheduled (job `ml_drift_retrain_scan`), drift-triggered
  (`should_retrain` reads the latest drift breach).
- **Dataset snapshotting** — each retrain trains on a freshly snapshotted,
  registered, reproducible dataset.
- **Champion / challenger** — challenger vs the live production model on ROC-AUC;
  the winner is reported.
- **Approval + promotion** — a winning challenger is submitted; `auto_promote`
  approves+promotes it, otherwise a human owns the decision.
- **Rollback** — delegated to the registry.

Retraining always produces a new versioned model — never mutates or deletes a
prior one.

---

## 9. Stress Testing

`stress/ml_stress.py` applies macro scenarios **directly to model features**,
re-scores through the trained model, and measures portfolio impact (complementing
the Phase 4 raw-financials engine, which is untouched). Seven scenarios — GDP
decline, interest-rate hike, inflation, currency depreciation, sector downturn,
supply-chain disruption, commodity shock — each a set of additive/multiplicative
feature shocks scaled by severity (optimistic / expected / worst). Output: baseline
vs stressed portfolio default rate, expected loss and EL multiplier; `run-all`
ranks scenarios by projected impact. Validated monotonic: e.g. interest-rate hike
default rate 0.43 → 0.47 → 0.53 across severities (EL multiplier up to ~1.35).

---

## 10. Portfolio ML

`portfolio/ml_portfolio.py` aggregates model-scored positions into portfolio
analytics: exposure-weighted **portfolio default rate**, **expected loss** and
**unexpected loss** (independent-obligor approximation), **sector concentration**
(HHI + band), **rating-migration** (risk-band distribution + downgrade-prone
share), **exposure risk** (top EL contributors) and **risk clustering** of the
book (KMeans over PD × exposure). Runs over explicit positions or the current
feature-vector portfolio.

---

## 11. Fraud ML

`fraud/detectors.py` unifies unsupervised detectors behind one interface and
ensembles them:

- **Isolation Forest**, **Local Outlier Factor**, **PCA reconstruction error**
  (the *autoencoder-ready* abstraction — swap PCA for a trained autoencoder
  without changing callers).
- **Ensemble** anomaly score + percentile-based **fraud probability** + a robust
  **is_anomaly** flag (Isolation-Forest outlier OR top-contamination tail).
- **Behavioural / transaction / network** anomaly views over feature subsets;
  **contributing factors** (top feature z-scores); **KMeans risk clustering** with
  per-cluster profiles (higher-anomaly clusters correlate with higher default
  rates). Results persist to `MLFraudResult`.

---

## 12. Governance

- **Model & dataset approvals** — registry approval state machine; datasets are
  versioned, hashed and reproducible.
- **Training audit** — deployment events (`register` / `retrain`) + full training
  report stored per model.
- **Prediction audit** — every inference in `MLPredictionLog`; every mutating
  `/api/ml/*` call is captured by the existing `AuditMiddleware`.
- **Feature & model lineage** — feature→models, model→parent+dataset.
- **Reproducibility** — the dedicated endpoint returns everything to regenerate a
  model byte-for-byte (dataset spec + hash + hyperparameters + feature set).
- **RBAC** — 5 new permissions (`mlops.view / train / deploy / predict / fraud`)
  granted across roles (admin = all; risk_manager includes deploy;
  senior_analyst trains but cannot deploy; analysts view/predict; auditor &
  compliance view).

---

## 13. APIs Added

All additive under `/api/ml/*` (existing AI Risk Intelligence endpoints intact):

| Prefix | Milestone | Highlights |
|---|---|---|
| `/api/ml/feature-store` | M1 | `catalog`, `lineage/{f}`, `point-in-time/{id}` |
| `/api/ml/training` | M2 | `algorithms`, `train` |
| `/api/ml/registry` | M3/M14 | `models`, `models/{id}`, `versions`, `submit`/`approve`/`reject`/`promote`/`rollback`, `history`, `datasets`, `reproducibility` |
| `/api/ml/serving` | M4 | `predict`, `batch`, `portfolio`, `async`, `history`, `request/{id}` |
| `/api/ml/explainability` | M5 | `explain`, `history`, `{id}` |
| `/api/ml/monitoring` | M6/M8 | `summary`, `latency`, `failures`, `usage`, `volume`, `performance/{id}/evaluate`, `performance/{id}/trend` |
| `/api/ml/drift` | M7 | `detect`, `target`, `history` |
| `/api/ml/retraining` | M9 | `should-retrain/{key}`, `run`, `champion-challenger/{key}/{id}` |
| `/api/ml/fraud` | M10 | `score`, `batch`, `clusters`, `history` |
| `/api/ml/portfolio-ml` | M11 | `analyze`, `current` |
| `/api/ml/stress-ml` | M12 | `scenarios`, `run`, `run-all` |

---

## 14. Database Changes

Migration `a7b8c9d0e1f2` adds 8 tables (all additive, indexed on FKs and filter
columns, round-trips up/down cleanly):

`ml_datasets`, `ml_models`, `ml_deployment_history`, `ml_prediction_logs`,
`ml_explanations`, `ml_drift_reports`, `ml_performance_records`, `ml_fraud_results`.

No existing table was modified or dropped.

---

## 15. Performance Benchmarks

Synthetic dataset (seed 42, ~4k rows, ~32% default rate). Discrimination:

| Algorithm | ROC-AUC | KS | Gini | Brier |
|---|---|---|---|---|
| Logistic Regression | 0.848 | 0.574 | 0.696 | 0.157 |
| XGBoost | 0.801 | 0.475 | 0.601 | 0.164 |
| LightGBM | 0.798 | 0.455 | 0.595 | 0.172 |
| Random Forest | 0.792 | 0.450 | 0.584 | 0.200 |
| Gradient Boosting | 0.792 | 0.457 | 0.584 | 0.167 |
| Neural Network | 0.728 | 0.370 | 0.455 | 0.249 |

Logistic Regression leads because the latent process is log-odds — the honest,
expected result. **Out-of-sample holdout** (different seed) for XGBoost: ROC-AUC
0.809 vs training 0.801 — genuine generalisation, no overfit.

- **Real-time inference:** ~70 ms (includes explanation contributions); **cache
  hit:** sub-millisecond.
- **Drift PSI:** stable ≈ 0.015 vs significant ≈ 0.40 on a 4-feature shift.
- **Stress:** monotonic default-rate escalation across severities; EL multiplier
  up to ~1.35 at worst-case.

---

## Testing

- **102 new backend tests** (`test_ml_platform.py` — 82 service-level;
  `test_ml_platform_api.py` — HTTP + RBAC), covering training, registry, serving,
  explainability/SHAP, monitoring, performance, drift, retraining, fraud,
  portfolio, stress and the feature store.
- All **266 pre-existing tests** maintained (only the RBAC permission count
  assertions updated 41 → 46 for the new `mlops.*` permissions).
- **Frontend** builds cleanly; **TypeScript** clean; 7 new MLOps dashboards
  (Training, Model Registry, Inference, Performance, Feature Importance, Drift,
  Stress) wired into a new "ML Platform" sidebar group, all using real backend
  APIs.

---

## Deployment Notes

The platform is Kubernetes/CI-CD ready: models are versioned artifacts with a
DB-backed registry, serving falls back safely, retraining is a job hook, and
every prediction/training/deployment action is audited and reproducible. Trained
artifacts are written under `backend/app/services/ml/artifacts/registry/`
(recommend a persistent volume or object-store backend in production). The only
pre-existing tech-debt item remains the dev JWT secret flagged in Phase 5
(`core/security.py`) — untouched here.
