# AI Security

## Access control

Every `/api/aip/*` endpoint is protected by the existing RBAC layer via
`require_permission("aip.*")`. Track 2 adds a dedicated **"AI Intelligence
Platform"** permission category with 22 fine-grained permissions:

```
aip.rag.view/query/manage        aip.agents.run
aip.memory.view/manage           aip.prompts.view/manage
aip.eval.run                     aip.investigate.run
aip.reports.generate             aip.workflows.view/manage
aip.chat.use                     aip.research.run
aip.learning.view/manage         aip.governance.view/manage
aip.explain.view                 aip.monitoring.view/manage
```

Grants follow least privilege and seniority: read/use for credit-workflow roles;
heavier engines (agents, investigation, research, eval) for analysts and above;
authoring (RAG index, prompts, workflows) for senior analysts + risk managers;
governance and monitoring management for risk managers. Total platform
permissions: **102 → 124**.

## Tenant isolation

Every `aip_*` row carries a nullable `tenant_id`. Every query filters on the
resolved tenant (`_tenant()` reads the SaaS tenant context). The unified
`aip_vectors` table enforces isolation in both RAG and memory retrieval, so no
tenant can retrieve another tenant's knowledge or memories.

## Grounding as a safety control

Because the LLM only phrases pre-computed grounding and never sources numbers,
the platform structurally resists fabrication/prompt-injection-to-invent-facts.
The evaluation layer (M5) additionally measures hallucination and groundedness,
and monitoring (M14) raises incidents when they degrade.

## Data handling

- No external egress by default: offline embeddings, offline LLM, local vector
  store. The gated Claude client is the only outbound path and is opt-in via
  `ANTHROPIC_API_KEY`.
- Documents/knowledge are stored as chunked text + vectors in the app DB; the
  RAG layer never sends raw corpora anywhere in the offline default.
- API/connector workflow nodes are **offline stubs** by default — they record an
  auditable call rather than performing egress until a real connector is wired.

## Auditability & reproducibility

Every AI action persists its inputs, grounding, citations, confidence and
provider. Governance (M12) adds content checksums and immutable event trails so
each AI decision is reproducible for audit and model-risk review.

## Backward compatibility

No existing auth path, middleware, RBAC grant, table or route was modified. The
audit middleware continues to record mutating `/api/aip/*` requests like any other.
