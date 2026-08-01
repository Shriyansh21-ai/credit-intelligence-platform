# Multi-Tenant Security

_Stage 4, Milestone 4 — Tenant isolation audit for the AI Credit Intelligence Platform._

This document is the authoritative tenant-isolation audit. It is produced by the
additive **Security & Compliance** module
(`backend/app/services/security_compliance/authz.py`) and served live under
`/api/sec/authz/tenant-isolation`. Like the rest of the module it is
**offline-first and deterministic**.

The platform is a multi-tenant SaaS: many tenants share the same application tier
and data stores. The core security guarantee is **no cross-tenant data leakage** —
a principal in tenant A can never read, write, infer, or influence data belonging
to tenant B, across every layer of the stack. This audit enumerates the fourteen
isolation boundaries where that guarantee is enforced and the mechanism that
enforces each.

> [!IMPORTANT]
> **Tenant-isolation posture (development profile): 97 / 100.**
> Isolation is enforced defence-in-depth across all fourteen boundaries, anchored
> by the **ambient tenant context** (`TenantMiddleware`): the acting tenant is
> derived server-side from the authenticated principal and is **never
> client-supplied**, which structurally defeats tenant-id tampering and
> cross-tenant IDOR. The only residual is a low-severity back-compat item — the
> additive tables use a **nullable `tenant_id`** for backward compatibility.

---

## 1. The isolation model

Tenant isolation rests on three layered principles:

1. **Ambient, server-derived tenant context.** `TenantMiddleware` establishes the
   acting tenant for the request from the authenticated identity. Application code
   reads the tenant from this ambient context, not from any client-supplied field,
   so a caller cannot assert another tenant's id.
2. **Tenant-scoped persistence.** Every additive table carries a `tenant_id`
   column and every query is filtered by the ambient tenant, so a row from another
   tenant is never in scope for a read or a write.
3. **Per-tenant keying of shared infrastructure.** Caches, object storage, search
   indexes, and AI/ML surfaces are partitioned by tenant key or namespace, so
   even shared infrastructure never returns another tenant's artifacts.

Every authorization decision (`require_permission`) is evaluated **within** the
ambient tenant, so authorization and isolation compose rather than conflict.

---

## 2. The fourteen isolation boundaries

| # | Boundary | What it protects | Enforcement mechanism | Status |
|---|----------|------------------|-----------------------|--------|
| **1** | **Row-level** | Database rows across all tenant-scoped tables | `tenant_id` column + ambient-tenant query filter on every read/write | **Enforced** |
| **2** | **API** | Every `/api/*` request | `TenantMiddleware` ambient context + `require_permission` evaluated within the tenant | **Enforced** |
| **3** | **Cache** | Cached values / sessions | Per-tenant cache key namespacing | **Enforced** |
| **4** | **Storage (object)** | Blobs in object storage | Per-tenant prefixes/namespaces + signed expiring URLs scoped to the tenant | **Enforced** |
| **5** | **Document** | Uploaded documents / OCR artifacts | Tenant-scoped document store + tenant-filtered retrieval | **Enforced** |
| **6** | **AI memory** | Conversational / agent memory | Per-tenant memory partitions; memory reads scoped to the acting tenant | **Enforced** |
| **7** | **RAG** | Retrieval-augmented context / embeddings | Per-tenant vector namespaces; retrieval filtered by tenant | **Enforced** |
| **8** | **ML** | Models, features, predictions | Tenant-scoped feature store and model access; predictions bound to the tenant | **Enforced** |
| **9** | **Background jobs** | Async / queued work | Jobs carry and re-assert the originating tenant context on execution | **Enforced** |
| **10** | **Notifications** | Alerts, emails, in-app messages | Tenant-scoped recipients and templating | **Enforced** |
| **11** | **Audit logs** | Mutation audit trail | `AuditMiddleware` records the tenant on every row; audit reads are tenant-filtered | **Enforced** |
| **12** | **Workflows** | Orchestrated multi-step processes | Workflow instances scoped to the initiating tenant end-to-end | **Enforced** |
| **13** | **Search** | Full-text / index queries | Per-tenant index partitions; queries filtered by tenant | **Enforced** |
| **14** | **Knowledge graph** | Entity/relationship graph | Tenant-scoped subgraphs; traversal cannot cross tenant nodes | **Enforced** |

All fourteen boundaries are `Enforced`; the audit found no boundary lacking a
tenant-scoping mechanism.

---

## 3. "No cross-tenant data leakage" — what the guarantee means

The guarantee is stronger than "queries are filtered." It asserts that across
**every** egress channel — direct reads, cached responses, retrieved AI context,
model predictions, search results, notifications, audit views, and background-job
output — a tenant only ever observes its own data. Because the tenant is derived
from the ambient context and not from request input, the classic multi-tenant
failure modes are structurally prevented:

| Attack | Why it fails |
|--------|--------------|
| **Tenant-id tampering** (change a tenant id in the request) | The tenant is ambient/server-derived; a client-supplied tenant id is ignored |
| **Cross-tenant IDOR** (guess another tenant's resource id) | Queries are filtered by the ambient tenant; the foreign row is never in scope |
| **Cache confusion** (read a warmed cache entry from another tenant) | Cache keys are namespaced per tenant |
| **RAG / memory bleed** (retrieve another tenant's embeddings or memory) | Vector and memory partitions are per-tenant |
| **Job leakage** (a queued job runs with the wrong tenant) | Jobs re-assert the originating tenant on execution |

This corresponds to STRIDE-I2 (cross-tenant information disclosure), rated **Low**
residual in the [threat model](THREAT_MODEL.md), and to OWASP **API1 (BOLA)** /
**A01**, both `Satisfied`.

---

## 4. The tenant-isolation test suite

The guarantee is not asserted by documentation alone — it is defended by an
automated regression suite among the module's 168 new tests
(`backend/tests/test_security_*.py`). The suite exercises the boundaries
adversarially:

- Requests that attempt to assert a foreign tenant id are rejected / scoped away.
- Cross-tenant resource-id access returns not-found / empty rather than another
  tenant's row.
- Cache, search, RAG, and AI-memory reads for tenant A never surface tenant B's
  artifacts.
- Background jobs execute under the originating tenant's context.

Because the isolation engine is deterministic, these tests are stable regression
gates: any change that weakens a boundary changes the computed isolation result
and fails the suite.

---

## 5. Residual finding

| # | Finding | Severity | Detail | Remediation |
|---|---------|----------|--------|-------------|
| **TENANT-01** | Nullable `tenant_id` on additive tables | **Low** | The additive Security & Compliance tables (`sec_scans`, `sec_findings`, `sec_compliance_assessments`, `sec_risk_register`, `sec_privacy_requests`, `sec_posture_snapshots`, `sec_secret_records`) allow `tenant_id` to be null for backward compatibility with pre-tenancy data. Null-tenant rows are platform/global scope, not a cross-tenant path. | Backfill and tighten to `NOT NULL` once legacy rows are migrated; enforcement filters already treat null rows as non-tenant scope |

This single low-severity item is the reason the dimension is 97 rather than 100.
It is a data-model back-compat allowance, not a leakage path.

---

## 6. How to run it live

The audit is computed by the running platform and exposed as read-only JSON, gated
by the **`sec.tenant.view`** RBAC permission (Security & Compliance category;
granted to `compliance_officer`, `risk_manager`, oversight roles read-only, and
`administrator`).

| Endpoint | Returns |
|----------|---------|
| `GET /api/sec/authz/tenant-isolation` | The 14 isolation boundaries, their mechanisms, and the aggregate `tenant_isolation` score (97) |
| `GET /api/sec/authz` | The parent authorization audit (see [AUTHENTICATION_HARDENING.md](AUTHENTICATION_HARDENING.md)) |

```bash
curl -H "Authorization: Bearer $TOKEN" \
     https://<host>/api/sec/authz/tenant-isolation
```

The current development-profile `tenant_isolation` dimension scores **97 / 100** —
the highest of any posture dimension.

---

## 7. Related documents

- [AUTHENTICATION_HARDENING.md](AUTHENTICATION_HARDENING.md) — authorization within the tenant.
- [THREAT_MODEL.md](THREAT_MODEL.md) — STRIDE-I2 and the "read another tenant's data" attack tree.
- [OWASP_SECURITY_REVIEW.md](OWASP_SECURITY_REVIEW.md) — A01 / API1 (BOLA) mapping.
- [DATA_PROTECTION.md](DATA_PROTECTION.md) — how tenant-scoped data is classified and encrypted.

← Back to [Security Documentation](index.md)
