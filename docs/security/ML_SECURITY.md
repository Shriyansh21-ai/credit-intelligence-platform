# ML Security

_Stage 4, M11 — machine-learning pipeline and model security posture for the AI Credit Intelligence Platform._

This document is produced by the ML security engine
(`backend/app/services/security_compliance/ai_ml.py`). It evaluates the seven
stages of the platform's credit-model lifecycle — from training through
explanation — against model-integrity and pipeline-security controls.

The ML security dimension scores **78.6 / 100** in the development profile. The
controls that protect model integrity and detect drift are in place; the partial
areas concern end-to-end provenance and continuous integrity attestation.

---

## 1. API surface

| Endpoint | Method | Permission | Purpose |
|----------|--------|-----------|---------|
| `/api/sec/ai/ml-security` | GET | `sec.mlsec.view` | ML security report across the 7 lifecycle areas + score |

---

## 2. Lifecycle area assessment

Status: **Satisfied** — control implemented and evidenced; **Partial** —
implemented with a documented residual gap.

| # | Area | Threat | Control | Status |
|---|------|--------|---------|--------|
| 1 | Training pipeline | Poisoned / tampered training data | Scoped, access-controlled training inputs; provenance recorded | Partial |
| 2 | Model registry | Unauthorised or unattributed model promotion | RBAC-gated registry; versioned, attributable model entries | Satisfied |
| 3 | Feature store | Feature tampering / leakage across tenants | Access-controlled, tenant-scoped features | Partial |
| 4 | Dataset lineage | Untraceable data provenance | Lineage captured from source to training set | Partial |
| 5 | Model integrity | Model artifact tampering | Content hashing of model artifacts; hash verified on load | Satisfied |
| 6 | SHAP integrity | Manipulated / inconsistent explanations | Explanation artifacts bound to the model version that produced them | Satisfied |
| 7 | Drift detection | Silent model degradation / manipulation | Continuous drift monitoring on inputs and predictions | Satisfied |

**Score: 78.6 / 100.**

---

## 3. Threat coverage (milestone scope)

| Threat | Area | Primary control |
|--------|------|-----------------|
| Model tampering | Model integrity | Content hashing + hash verification on load |
| Model integrity | Model integrity / registry | Versioned, hashed, attributable artifacts |
| Drift detection | Drift detection | Continuous input/prediction drift monitoring |
| SHAP integrity | SHAP integrity | Explanations bound to producing model version |
| Data poisoning | Training pipeline / feature store | Scoped, access-controlled inputs + lineage |
| Provenance loss | Dataset lineage | Source-to-training lineage capture |

---

## 4. Control detail

### Model integrity — content hashing
Every registered model artifact carries a content hash. The hash is verified when
the artifact is loaded for serving, so a tampered or substituted model is
detected before it can score a live application. This is the backbone control for
credit-model trustworthiness and provides evidence for NIST PR.DS and RBI-Cyber
data-protection requirements.

### SHAP integrity
Explanations must faithfully reflect the model that produced a decision. SHAP
artifacts are bound to the exact model version, so an explanation cannot be
silently swapped or recomputed against a different model — preserving the
auditability of adverse-action reasoning.

### Drift detection
Input and prediction distributions are monitored continuously. Drift is both a
model-quality signal and a **security** signal: a sudden distribution shift can
indicate data poisoning or feature-store tampering, not only natural population
change.

### Model registry
The registry is RBAC-gated; model promotion is attributable and versioned, so no
model reaches production without an accountable, auditable promotion event.

---

## 5. Residual risk & roadmap

| Area | Status | Residual | Planned hardening |
|------|--------|----------|-------------------|
| Training pipeline | Partial | Medium | Signed training-data manifests; ingestion attestation |
| Feature store | Partial | Medium | Per-feature integrity checks; tighter tenant scoping proofs |
| Dataset lineage | Partial | Medium | End-to-end signed lineage graph from source to serving |

The partial areas share a theme — **verifiable end-to-end provenance**. The
roadmap closes them by extending the existing hashing and lineage capture into
signed, attestable manifests across the full pipeline.

---

## 6. Mapping to compliance

| Control | Framework | Provided by |
|---------|-----------|-------------|
| Data security / integrity | NIST PR.DS, RBI-Cyber CS-4 | Model content hashing, drift detection |
| Explainability / auditability | RBI Digital Lending, model governance | SHAP integrity binding |
| Access control | ISO A.5.15, SOC 2 CC6.1 | RBAC-gated registry & feature store |
| Asset inventory | NIST ID.AM | Versioned model registry |

---

## 7. Operating model

- The ML security report is regenerated each release and on model promotion.
- Model artifacts are hash-verified on load; a hash mismatch blocks serving.
- Drift alerts are triaged as both quality and security events and routed to the
  findings workflow (`sec_findings`).
- The three partial (provenance) areas are tracked in the risk register with
  owners and target dates.
