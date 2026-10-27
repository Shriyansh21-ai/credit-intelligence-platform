# Machine Learning Documentation

*Model lifecycle, experiment tracking, and MLOps for the AI Credit Intelligence Platform.*

The ML layer is responsible for governed model development, versioned deployment,
continuous learning, and explainable risk intelligence across the credit lifecycle.
It complements the AI platform, which handles LLM orchestration, RAG, prompts,
agent workflows, and grounded explanations.

| Document | Description |
| --- | --- |
| [MODEL_MANAGEMENT](MODEL_MANAGEMENT.md) | Model registry, versioning, deployment, and lifecycle management for trained ML assets. |
| [AI_GOVERNANCE](../ai/AI_GOVERNANCE.md) | Governance model for regulated AI/ML assets, review gates, lineage, and approvals. |
| [AI_EVALUATION](../ai/AI_EVALUATION.md) | Evaluation harness, metrics, and quality gates for LLM and model performance. |
| [AI_OPERATIONS](../ai/AI_OPERATIONS.md) | Production operations, monitoring, and runbooks for AI/ML workloads. |
| [AI_SECURITY](../ai/AI_SECURITY.md) | Security controls for model, prompt, and agentic AI attack surfaces. |
| [AI_ARCHITECTURE](../ai/AI_ARCHITECTURE.md) | End-to-end AI subsystem design spanning ML, LLMs, retrieval, agents, and orchestration. |
| [PHASE7_ENGINEERING_REPORT](../reports/PHASE7_ENGINEERING_REPORT.md) | Phase 7 architecture report covering the banking ecosystem connector layer and platform expansion. |

## Core ML capabilities

- Model registry and version management for credit, fraud, and portfolio models.
- Continuous learning loop from production outcomes back into retraining proposals.
- Explainability and attribution for decisions, including SHAP-style and rule-based views.
- Drift, performance, and feedback monitoring tied to governed training events.
- MLOps controls that keep retraining reviewable, traceable, and auditable.

> [!NOTE]
> For AI/LLM-specific design and governance, see the [AI documentation](../ai/index.md).

← Back to [Documentation Home](../index.md)
