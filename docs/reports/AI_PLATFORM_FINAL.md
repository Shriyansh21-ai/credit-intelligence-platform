# AI Platform — Final (v1.0.0)

The platform's AI capability spans three layers, all additive and grounding-first.

## Layers

1. **Autonomous Intelligence** — the AI Brain: knowledge
   graph, monitoring, early-warning, copilot, simulation, stress, optimization,
   NLQ, recommendations, workflow, governance, data lake.
2. **Enterprise AI Intelligence** — RAG, multi-agent,
   long-term memory, prompt engineering, evaluation, autonomous investigation,
   report generation, workflow builder, conversational AI, research, continuous
   learning, governance, explainability, monitoring.
3. **AI embedded in Financial & Enterprise layers (Tracks 3–4)** — grounded
   narratives in portfolio insights, strategic reports, executive dashboards,
   customer-success recommendations and operations RCA.

## Grounding-first principle

Every AI narrative only *phrases* deterministic facts; it never sources numbers.
Each grounded result carries a `grounding` block (facts + SHA-256 checksum). The
Track-4 quality bar adds a shared `confidence_block` envelope so every AI
response includes **confidence, reasoning, citations and evidence**:

```json
{
  "confidence": 0.78,
  "reasoning": "Health 42 and adoption 30 with 2 open tickets drive these actions.",
  "citations": [{"source": "ent_customers", "ref": 12}],
  "evidence": {"health_score": 42, "adoption_score": 30, "open_tickets": 2}
}
```

## Providers

The LLM layer is pluggable (`AIP_LLM_PROVIDER`): a deterministic-local default
(offline, reproducible) with a gated Claude provider. Embeddings and vector store
are similarly pluggable. This keeps the platform fully functional and testable
offline while allowing production LLM integration.

## Governance & reproducibility

- Prompt registry with versioning, approval, deployment, rollback and A/B tests.
- AI asset governance registry with lineage and checksums.
- Evaluation framework scores RAG/agent/report outputs; monitoring aggregates
  evals + feedback into metrics and incidents.
- Every grounded output is reproducible via its stored checksum.

## Integration

Track 3/4 engines reuse the AI conventions: strategic reports mirror the Track 2
investigation→report pattern; executive and customer-success surfaces reuse the
grounding/confidence envelopes; the command palette and BI surfaces expose AI
outputs consistently.
