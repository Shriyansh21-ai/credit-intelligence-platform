# Go-Live Checklist

_AI Credit Intelligence Platform — production launch gate. Date: 2026-07-28._

Sign-off required from: **Engineering Lead**, **Platform/SRE**, **Security**,
**Compliance**, **Product**. Complete [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
first (per environment).

## 1. Engineering readiness

- [ ] Full test suite green (**1212 tests**); CI required checks enforced.
- [ ] No high-severity technical debt open ([TECHNICAL_DEBT_REPORT.md](../reports/TECHNICAL_DEBT_REPORT.md)).
- [ ] Production images built, scanned, signed (SBOM + provenance), in GHCR.
- [ ] Database migrations validated (single head; round-trip tested).
- [ ] Feature flags for the launch scope configured.

## 2. Platform / SRE

- [ ] Terraform-provisioned prod infra reviewed (HA Postgres/Redis, storage, LB, CDN, DNS).
- [ ] Kubernetes prod overlay applied; HPA/PDB/NetworkPolicy in place.
- [ ] GitHub Environments configured; **production requires reviewer approval**.
- [ ] Branch protection applied to `main`/`develop` ([BRANCH_PROTECTION.md](../development/BRANCH_PROTECTION.md)).
- [ ] Observability live: Prometheus scraping, Grafana dashboards, Alertmanager
      routing to pager; SLOs + burn-rate alerts armed.
- [ ] Log pipeline (Loki) + tracing (Tempo/Jaeger) receiving data.
- [ ] On-call rotation + escalation set ([INCIDENT_RESPONSE.md](../operations/INCIDENT_RESPONSE.md)).
- [ ] Runbook reviewed by on-call ([RUNBOOK.md](../operations/RUNBOOK.md)).

## 3. Reliability / DR

- [ ] Backups scheduled and running (DB/storage/config/secret-refs).
- [ ] **Full restore drill executed in staging and validated** ([DISASTER_RECOVERY.md](../operations/DISASTER_RECOVERY.md)).
- [ ] PITR window confirmed; RTO/RPO objectives agreed and achievable.
- [ ] Cross-region/BCP plan documented.

## 4. Security

- [ ] Strong secrets set from the secret manager (no defaults); KMS rotation on.
- [ ] Secret scanning + push protection + code scanning enabled on the repo.
- [ ] CSP validated against real frontend origins; HSTS preload verified.
- [ ] Penetration test completed on staging; findings triaged/closed.
- [ ] Least-privilege review of cloud IAM / RBAC roles.

## 5. Compliance / legal

- [ ] Control mapping reviewed; evidence bundle collected ([COMPLIANCE.md](../security/COMPLIANCE.md)).
- [ ] Data residency policy configured for the deployment region(s).
- [ ] Consent flows + DSAR (export/erasure) procedures verified.
- [ ] Retention schedule approved; audit export tested.
- [ ] DPA / regulatory notifications (e.g., RBI) completed as required.

## 6. Product / operations

- [ ] Launch scope, rollout plan (canary/percentage), and comms agreed.
- [ ] Support runbooks + escalation paths shared with support.
- [ ] Rollback criteria and decision owner defined.
- [ ] Status page / customer comms ready.

## 7. Go / No-Go

- [ ] All sections signed off.
- [ ] Error budget healthy; no active S1/S2.
- [ ] **Decision recorded (Go / No-Go) with owner + timestamp.**

---

_On No-Go: capture blockers, assign owners, reschedule. On Go: execute the
rollout plan, watch dashboards through the bake period, and hold the rollback
decision owner on standby._
