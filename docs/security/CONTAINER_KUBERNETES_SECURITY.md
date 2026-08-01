# Container & Kubernetes Security

_Stage 4, M9 — container and Kubernetes hardening baseline for the AI Credit Intelligence Platform._

This document is produced by the hardening engine
(`backend/app/services/security_compliance/hardening.py`). It evaluates the
platform's real `Dockerfile` and `deploy/k8s` manifests against a
defence-in-depth hardening baseline and scores compliance deterministically.

The container dimension scores **100 / 100 — all 10 hardening checks pass.**
This document records the baseline so the posture is maintained, not re-earned.

---

## 1. API surface

| Endpoint | Method | Permission | Purpose |
|----------|--------|-----------|---------|
| `/api/sec/container` | GET | `sec.container.view` | Container & Kubernetes hardening report + score |

---

## 2. Hardening baseline

The scanner runs ten checks spanning image construction, runtime security
context, and cluster policy. Each is currently **Passed**.

| # | Control | Layer | Check | Status | Why it matters |
|---|---------|-------|-------|--------|----------------|
| 1 | Non-root `USER` | Image | Container declares a non-root `USER` | Passed | A container breakout inherits the process UID; non-root limits blast radius |
| 2 | Minimal base image | Image | Slim / distroless base | Passed | Fewer packages means fewer CVEs and a smaller attack surface |
| 3 | Healthcheck | Image | `HEALTHCHECK` defined | Passed | Enables liveness signalling and safe rollout |
| 4 | `runAsNonRoot` | Runtime | Pod securityContext enforces non-root | Passed | Cluster-level guarantee independent of the image |
| 5 | `readOnlyRootFilesystem` | Runtime | Root filesystem mounted read-only | Passed | Blocks tampering and payload persistence |
| 6 | Drop capabilities | Runtime | Linux capabilities dropped (`drop: ["ALL"]`) | Passed | Removes privileged kernel operations |
| 7 | Resource limits | Runtime | CPU / memory requests & limits set | Passed | Contains DoS and noisy-neighbour blast radius |
| 8 | Seccomp `RuntimeDefault` | Runtime | Seccomp profile `RuntimeDefault` | Passed | Restricts the syscall surface available to the container |
| 9 | NetworkPolicy | Cluster | Default-deny / scoped `NetworkPolicy` | Passed | Segments east-west traffic between workloads |
| 10 | `allowPrivilegeEscalation: false` | Runtime | Privilege escalation disabled | Passed | Prevents `setuid`-style escalation inside the container |

**Score: 10 / 10 = 100.**

---

## 3. Remediation guidance (baseline maintenance)

Each control below is currently satisfied; the guidance documents the intended
implementation so regressions are caught in review.

### Image controls
- **Non-root USER** — declare a dedicated unprivileged user in the `Dockerfile`
  and `USER` to it before the entrypoint. Never run as UID 0.
- **Minimal base** — build from a slim or distroless base; keep build tooling in
  a separate multi-stage layer that does not ship in the final image.
- **Healthcheck** — define a `HEALTHCHECK` (or rely on Kubernetes liveness /
  readiness probes) so orchestration can detect and replace unhealthy pods.

### Runtime security context
- **runAsNonRoot / allowPrivilegeEscalation** — set both in the pod
  `securityContext`; these are cluster-enforced and survive a compromised image.
- **readOnlyRootFilesystem** — mount root read-only and grant writable
  `emptyDir` volumes only where genuinely required.
- **Drop capabilities** — `capabilities.drop: ["ALL"]`, adding back only the
  minimum a workload provably needs.
- **Seccomp** — set `seccompProfile.type: RuntimeDefault` on the pod.
- **Resource limits** — always set CPU and memory requests and limits to contain
  resource-exhaustion attacks and enable fair scheduling.

### Cluster policy
- **NetworkPolicy** — apply a default-deny policy and explicitly allow only
  required flows, enforcing the tenant and service trust boundaries.

---

## 4. Image scanning readiness

Static hardening is complemented by vulnerability scanning in CI:

| Capability | Status | Detail |
|-----------|--------|--------|
| Image vulnerability scan | Ready | Pipeline structured to run Trivy / Grype against built images before promotion |
| SBOM correlation | Present | SBOM (see [SUPPLY_CHAIN_SECURITY.md](SUPPLY_CHAIN_SECURITY.md)) maps scan findings to components |
| Secret scanning | Present | `gitleaks` blocks committed credentials |
| Fail-the-build gate | Recommended | Promote only images passing scan thresholds |

Trivy / Grype scan the assembled image layers for known CVEs; pairing the scan
with the SBOM lets findings be triaged to specific dependencies and remediated
via the pinning workflow.

---

## 5. Mapping to compliance

The hardening baseline provides direct evidence for several framework controls
(see [COMPLIANCE_FRAMEWORKS.md](COMPLIANCE_FRAMEWORKS.md)):

| Control | Framework | Provided by |
|---------|-----------|-------------|
| Secure configuration baseline | RBI-Cyber CS-3 | Checks 1–10 |
| Boundary protection | SOC 2 CC6.6 | NetworkPolicy |
| Data security | NIST PR.DS | Read-only FS, dropped capabilities |
| Vulnerability management | ISO A.8.8 | Image scanning + SBOM |

---

## 6. Operating model

- The hardening report is regenerated on each release; any check dropping below
  Passed is a release blocker.
- Security-context defaults live in the deployment manifests under version
  control; changes are reviewed against this baseline.
- Image scanning is enforced in CI so newly disclosed CVEs are caught between
  releases, not only at build time.
