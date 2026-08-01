# AI Security

_Stage 4, M10 — LLM and agentic-AI security posture for the AI Credit Intelligence Platform._

This document is produced by the AI security engine
(`backend/app/services/security_compliance/ai_ml.py`). It maps the platform's
generative-AI and agentic surfaces to the **OWASP Top 10 for LLM Applications**
(LLM01–LLM10) and records the mitigating controls already in place.

The AI security dimension scores **65 / 100** in the development profile. Several
categories are **partial** by design — the residual risks (prompt injection,
agent abuse) are inherent to LLM systems and are managed by layered controls
plus human-in-the-loop, not eliminated. The highest-residual STRIDE threat on
the platform, **E2 (prompt injection → unauthorised tool use, HIGH)**, lives in
this surface.

---

## 1. API surface

| Endpoint | Method | Permission | Purpose |
|----------|--------|-----------|---------|
| `/api/sec/ai/security` | GET | `sec.aisec.view` | AI security report mapped to OWASP LLM Top 10 + score |

---

## 2. OWASP LLM Top 10 mapping

Status reflects the engine's honest assessment: **Satisfied** — controlled with
low residual; **Partial** — controlled with a documented residual risk.

| ID | Risk | Status | Platform mitigation |
|----|------|--------|---------------------|
| LLM01 | Prompt injection | Partial | Tool allow-lists constrain what an injected instruction can reach; PII masking before prompts; human-in-the-loop on consequential actions. Residual is HIGH (STRIDE E2) |
| LLM02 | Insecure output handling | Partial | Model output is validated and treated as untrusted before use; no direct execution of raw output |
| LLM03 | Training / RAG data poisoning | Partial | Tenant-isolated memory and RAG stores; ingestion is scoped per tenant so cross-tenant poisoning is blocked; content provenance tracked |
| LLM04 | Model denial of service | Satisfied | Request quotas and resource limits bound model spend and compute |
| LLM05 | Supply-chain vulnerabilities | Partial | SBOM covers AI dependencies; model / library provenance tracked (see [SUPPLY_CHAIN_SECURITY.md](SUPPLY_CHAIN_SECURITY.md)) |
| LLM06 | Sensitive information disclosure | Satisfied | `PiiMasker` masks email/phone/card/PAN/Aadhaar before content reaches the model; tenant isolation on retrieval |
| LLM07 | Insecure plugin / tool design | Partial | Tools are allow-listed and permission-gated; arguments validated; no arbitrary tool registration |
| LLM08 | Excessive agency | Partial | Agents operate under bounded tool scopes with human-in-the-loop approval for high-impact actions |
| LLM09 | Overreliance / hallucination | Satisfied | Outputs surfaced as advisory with provenance; consequential decisions require human confirmation |
| LLM10 | Model / memory poisoning | Partial | Per-tenant memory isolation prevents cross-tenant contamination; memory writes are scoped and attributable |

**Score: 65 / 100.**

---

## 3. Threat coverage (milestone scope)

The milestone's named AI threats map onto the controls above:

| Threat | OWASP ref | Primary control |
|--------|-----------|-----------------|
| Prompt injection | LLM01 | Tool allow-lists + human-in-the-loop |
| Jailbreaks | LLM01 | Output validation + bounded tool scope |
| RAG poisoning | LLM03 | Tenant-isolated ingestion & retrieval |
| Hallucinations | LLM09 | Advisory framing + provenance + human confirmation |
| Unsafe tool execution | LLM07 | Allow-listed, permission-gated tools; argument validation |
| Memory poisoning | LLM10 | Per-tenant memory isolation, scoped writes |
| Agent abuse | LLM08 | Bounded agency, approval gates |
| Model misuse | LLM04 | Quotas + resource limits |
| Data leakage | LLM06 | PII masking before prompts + tenant isolation |
| Unsafe outputs | LLM02 | Output treated as untrusted; validated before use |

---

## 4. Defence-in-depth controls

The platform applies five cross-cutting controls across every AI surface:

1. **Tool allow-lists** — agents may only invoke a curated, permission-gated set
   of tools; there is no arbitrary or dynamic tool registration. This is the
   primary containment for prompt injection (LLM01) and excessive agency (LLM08).
2. **Output validation** — model output is treated as untrusted input: it is
   validated and never executed directly, addressing insecure output handling
   (LLM02).
3. **PII masking before prompts** — `core/crypto.py` `PiiMasker` redacts email,
   phone, card, PAN, and Aadhaar values before content is sent to a model,
   limiting sensitive-information disclosure (LLM06).
4. **Tenant memory isolation** — RAG stores and agent memory are partitioned per
   tenant, preventing cross-tenant poisoning and leakage (LLM03, LLM10).
5. **Human-in-the-loop** — consequential or irreversible actions require human
   confirmation, bounding the impact of injection, hallucination, and agent
   abuse (LLM01, LLM08, LLM09).

---

## 5. Residual risk & roadmap

| Item | OWASP ref | Residual | Planned hardening |
|------|-----------|----------|-------------------|
| Prompt injection → tool use | LLM01 / STRIDE E2 | HIGH | Add injection classifiers on inbound context; tighten per-tool scopes |
| Insecure output handling | LLM02 | Medium | Structured output schemas + stricter post-validation |
| RAG poisoning | LLM03 | Medium | Provenance scoring and quarantine on ingest |
| Insecure plugin/tool | LLM07 | Medium | Formal tool-risk classification and per-tool rate limits |
| Excessive agency | LLM08 | Medium | Narrow default scopes; expand approval gates |
| Memory poisoning | LLM10 | Medium | Memory TTL and write attestation (aligns with privacy roadmap) |

Prompt injection is treated as a **managed, not solved** risk: the layered
controls reduce likelihood and blast radius, and human-in-the-loop bounds the
worst-case outcome.

---

## 6. Operating model

- The AI security report is regenerated each release; new AI surfaces are added
  to the OWASP LLM mapping as they ship.
- Tool allow-lists and permission gates are reviewed whenever a new agent tool is
  introduced.
- The HIGH-residual prompt-injection item is tracked in the risk register
  (`sec_risk_register`) with an owner and target hardening date.
