# Production Security Checklist — Stage 4

Pre-deployment security checklist for a regulated (bank / NBFC) production
deployment. Items marked **[BLOCKER]** must be satisfied before go-live; the
platform's startup validation (`settings.validate_runtime()`) fails fast on most
of them in staging/production profiles.

## Secrets & configuration

- [ ] **[BLOCKER]** Set a strong random `SECRET_KEY` (`openssl rand -hex 32`).
- [ ] **[BLOCKER]** Set a dedicated `JWT_SECRET_KEY` (distinct from `SECRET_KEY`).
- [ ] **[BLOCKER]** Set `ENCRYPTION_KEY` and `CONNECTOR_MASTER_KEY` (non-default).
- [ ] **[BLOCKER]** `APP_ENV=production`; `DEBUG=false`.
- [ ] Store secrets in a managed store (`SECRETS_PROVIDER=vault|aws`), not `.env`.
- [ ] Rotate JWT keys via `JwtKeyRing`; rotate field keys via `KeyRing` versioning.
- [ ] Verify `/api/sec/secrets` reports **0 insecure critical secrets**.

## Transport & headers

- [ ] **[BLOCKER]** TLS 1.2+ terminated at the edge; HTTP → HTTPS redirect.
- [ ] `SECURITY_HEADERS_ENABLED=true`; HSTS `max-age` ≥ 1 year, preload.
- [ ] Tighten `CONTENT_SECURITY_POLICY` for the deployed frontend origin.
- [ ] **[BLOCKER]** `CORS_ORIGINS` explicit (no `*`); credentials only with exact origins.

## Database & storage

- [ ] **[BLOCKER]** `DATABASE_URL` → PostgreSQL (SQLite rejected in prod).
- [ ] Least-privilege DB user; enable TDE / storage-layer encryption.
- [ ] `alembic upgrade head` (head = `c3d4e5f6a7b8`); backups + PITR configured.
- [ ] Object storage SSE enabled; signed-URL TTL appropriate.

## Identity & access

- [ ] Assign least-privilege roles (do not leave users on `administrator`).
- [ ] Enforce MFA (TOTP) for privileged roles; enable `RiskEngine` step-up.
- [ ] Verify `/api/sec/authz` least-privilege audit is clean.
- [ ] Confirm password policy: `PASSWORD_MIN_LENGTH>=12`, complexity on.
- [ ] Confirm `AccountLockout` thresholds set.

## Multi-tenancy

- [ ] Enforce non-null `tenant_id` in multi-tenant deployments.
- [ ] Run the tenant-isolation test suite; `/api/sec/authz/tenant-isolation` = 14/14.

## Supply chain

- [ ] **[BLOCKER]** Pin `requirements.txt` versions; commit a frontend lockfile.
- [ ] Run Trivy/Grype image CVE scans in CI; gate on critical/high.
- [ ] Enable Dependabot/renovate; review `/api/sec/supply-chain` findings.

## Containers & Kubernetes

- [ ] Non-root `USER`; `runAsNonRoot: true`; `readOnlyRootFilesystem: true`.
- [ ] Drop `ALL` capabilities; `allowPrivilegeEscalation: false`; seccomp `RuntimeDefault`.
- [ ] Resource requests/limits set; default-deny `NetworkPolicy`.
- [ ] Verify `/api/sec/container` = 10/10 checks pass.

## AI/ML

- [ ] Tool allow-lists enforced; agent high-impact actions require approval.
- [ ] PII masked before prompts; per-tenant AI-memory isolation verified.
- [ ] Model registry promotion gated by RBAC + approval; drift monitoring on.

## Privacy

- [ ] DSAR workflow staffed; verify SLA (30 days) tracked in `/api/sec/privacy/requests`.
- [ ] Retention policies reviewed; erasure via crypto-shredding validated.
- [ ] Define AI-memory TTL policy (open finding `PRIVACY-AI-TTL`).

## Monitoring & response

- [ ] Ship logs + traces + metrics to the SOC/SIEM.
- [ ] Alert on critical `/api/sec/findings`; snapshot posture on a schedule.
- [ ] Formalise incident response + CERT-In / breach-notification runbooks.

## Go-live gate

- [ ] Overall posture (`/api/sec/posture`) ≥ **B+ (87)** with production config.
- [ ] `/api/sec/posture/dashboard` shows **0 open critical findings**.
- [ ] External penetration test complete (see [PENETRATION_TEST_GUIDE.md](PENETRATION_TEST_GUIDE.md)).
