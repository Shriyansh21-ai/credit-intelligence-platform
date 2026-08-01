# AI Report

## Philosophy: deterministic-first, LLM-where-appropriate
Phase 10 keeps regulated credit decisioning **deterministic and auditable**. Generative
LLMs are confined to the copilot/report surfaces and are governed by the M8 prompt platform
and M9 router. Every AI/decision output carries **confidence, reasoning, evidence and
source references** and never fabricates.

## Deterministic intelligence (no model, fully reproducible)
- **Policy engine (M7):** closed-form rule evaluation; confidence = 1.0 (deterministic);
  evidence = matched rules with decisions.
- **Committee tallying (M4):** weighted vote arithmetic against quorum; tamper-evident
  SHA-256 signatures.
- **Search ranking (M2):** BM25-style TF·IDF + lexical-semantic blend; per-hit signal
  breakdown returned.
- **Workflow engine (M11):** deterministic graph walk, loop-guarded, full step trace.
- **Scenario/Monte Carlo (M5/M6):** seeded RNG → identical results across runs; VaR/ES
  and sensitivity are exact.
- **Fairness/drift (M13):** closed-form disparate-impact, demographic parity, equal
  opportunity, PSI.
- **Marketplace plugins (M12):** each recommendation is a deterministic function over the
  risk context, returning evidence + confidence (scaled by corroborating evidence count).
- **Graph analytics (M1):** UBO effective-ownership products, connected-lending set
  membership, cycle detection — all exact.
- **Executive KPIs (M10):** deterministic aggregation; every card value traces to a source.

## Generative intelligence (governed)
- **Prompt Management (M8):** versioned templates with a draft→approved→deployed lifecycle;
  deterministic evaluation (render-completeness or expected/output token overlap) gates
  quality; the deployed version is the runtime resolution target — auditable, reversible.
- **Multi-LLM Layer (M9):** provider registry (OpenAI/Anthropic/Gemini/Llama/Mistral/Azure/
  Ollama/local); router selects by cost/latency/quality/priority/balanced with explainable
  `routed_reason`, automatic fallback, and a guaranteed offline `local` provider. Real
  vendor SDKs plug in at `_invoke`; all calls logged for cost/latency/quality analytics.

## Anti-hallucination guarantees
1. Decisions are computed, not generated. 2. Evidence carries a `source` and is never
fabricated (`common.evidence`). 3. Confidence is derived (deterministic = 1.0; heuristic =
bounded by corroborating evidence). 4. Generative outputs are grounded and version-pinned
via the prompt platform. 5. `safe_div`/`clamp` prevent fabricated numbers from missing data.
