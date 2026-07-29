# LLM Integration

## Philosophy: grounding-first

The platform never trusts an LLM for facts. Every feature assembles deterministic
`grounding` from real platform data; the LLM only **phrases** it. This guarantees
no fabricated numbers, reproducible outputs, and safe offline operation.

## Client (`services/ai_platform/llm.py`)

`LLMClient` ABC with an instrumented `generate(prompt, system, grounding, ...)`
returning an `LLMResult`: `text`, `provider`, `model`, `prompt_tokens`,
`completion_tokens`, `latency_ms`, `cost_usd` (estimate), `grounded`.

- **LocalDeterministicLLM** (default) — composes grounding (headline, narrative,
  facts, recommended actions, citations) into readable prose. No network,
  reproducible. Ideal for air-gapped banks and tests.
- **ClaudeLLM** (gated) — uses the Anthropic SDK + `ANTHROPIC_API_KEY` to phrase
  the same grounding with a strict system instruction ("use ONLY the grounding;
  never invent numbers"). Falls back to local on any error or if unavailable.

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `AIP_LLM_PROVIDER` | `local` or `claude` for the AI platform | falls back to `COPILOT_LLM_PROVIDER` → `local` |
| `COPILOT_CLAUDE_MODEL` | Claude model id (shared with Phase 9) | `claude-sonnet-5` |
| `ANTHROPIC_API_KEY` | enables the Claude client | unset (→ local) |
| `AIP_EMBEDDING_PROVIDER` | embedding backend | `hashing` (offline) |
| `AIP_VECTOR_STORE` | `sql` or `pgvector` | `sql` |

Resolution never raises: an unavailable/unknown provider degrades to the offline
default. Call sites never change when a provider is switched on.

## Cost & usage

`generate()` estimates cost from a public per-1K price table for reporting only
(never billed). The local provider is always free. Usage feeds the evaluation
(M5) latency/cost/token metrics and the monitoring (M14) dashboards.

## Upgrading to real Claude

Set `AIP_LLM_PROVIDER=claude` and `ANTHROPIC_API_KEY`; install `anthropic`. No
code change is needed. Because grounding is still assembled deterministically, the
factual content is identical — only the phrasing quality improves. Use the latest
Claude models (Opus 4.8 / Sonnet 5) for best results.
