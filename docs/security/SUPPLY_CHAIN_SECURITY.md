# Supply-Chain Security

_Stage 4, M8 — SBOM, dependency, and license posture for the AI Credit Intelligence Platform._

This document is produced by the supply-chain engine
(`backend/app/services/security_compliance/supply_chain.py`). It inventories the
platform's software components, evaluates dependency hygiene, and classifies
license obligations. All figures are deterministic and reproducible from the
live API; nothing is asserted by hand.

The supply-chain dimension scores **60 / 100** in the development profile. This
is driven by one real, accurate finding (unpinned Python dependencies) that is
fully remediable; the positive controls below already hold.

---

## 1. API surface

| Endpoint | Method | Permission | Purpose |
|----------|--------|-----------|---------|
| `/api/sec/supply-chain` | GET | `sec.supplychain.view` | Consolidated supply-chain report + score |
| `/api/sec/supply-chain/sbom` | GET | `sec.supplychain.view` | Software Bill of Materials (CycloneDX-like) |
| `/api/sec/supply-chain/dependencies` | GET | `sec.supplychain.view` | Dependency hygiene findings |
| `/api/sec/supply-chain/licenses` | GET | `sec.supplychain.view` | License classification report |

---

## 2. Scope

The engine reasons over the full build and deployment supply chain:

| Surface | Source | Notes |
|---------|--------|-------|
| Python packages | `requirements.txt` | 27 production dependencies |
| Node packages | `package.json` | Frontend dependency tree |
| Container images | `Dockerfile` | Base image + build stages |
| Kubernetes | `deploy/k8s` manifests | Workload + policy objects |
| CI / CD | `.github` workflows | Build, scan, SBOM generation |
| Infrastructure | Terraform | Provisioned cloud resources |

---

## 3. Software Bill of Materials (SBOM)

The SBOM is emitted in a **CycloneDX-like** structure and enumerates **97
components** resolved from `requirements.txt` and `package.json`. Each component
carries name, version (where declared), ecosystem, and license.

| SBOM attribute | Value |
|----------------|-------|
| Format | CycloneDX-like (component inventory) |
| Total components | 97 |
| Sources | `requirements.txt`, `package.json` |
| Ecosystems | PyPI (Python), npm (Node) |
| Regeneration | On demand via `/supply-chain/sbom`; wired into CI |

The SBOM is the authoritative asset inventory feeding compliance controls
(ISO A.8.8 vulnerability management, RBI-Cyber CS-1 asset inventory, NIST ID.AM).
It should be regenerated on every release and archived as audit evidence.

---

## 4. Dependency report

### 4.1 Primary finding (medium severity)

`requirements.txt` lists **27 production Python dependencies with no version
constraints** — packages are declared by name only, without pinned versions.

| Attribute | Value |
|-----------|-------|
| Finding | Unpinned production Python dependencies |
| Count | 27 packages |
| Severity | Medium |
| Source | `requirements.txt` |
| Risk | Non-reproducible builds; silent upstream drift; exposure to dependency-confusion and malicious-release vectors |

**Remediation**

1. Pin every dependency to an exact version (`package==x.y.z`).
2. Commit a lockfile (`requirements.lock` / `pip-tools` compiled output, or a
   hash-verified `requirements.txt`) so builds are byte-reproducible.
3. Enforce the lockfile in CI — fail the build on drift.
4. Adopt a scheduled dependency-update flow (e.g. Dependabot / Renovate) so
   pinning does not stall security patching.

Pinning plus a committed lockfile closes this finding and lifts the
supply-chain dimension out of the 60 band into the production range.

### 4.2 Positive controls (already present)

| Control | Status | Detail |
|---------|--------|--------|
| Secret scanning | Present | `gitleaks` scans the repository for committed secrets |
| CI pipeline | Present | `.github` workflows build, test, and gate merges |
| SBOM generation | Present | Component inventory produced in the pipeline |
| Branch protection | Present | Reviewed, gated merges into protected branches |

These controls satisfy the change-management and integrity requirements
referenced in [COMPLIANCE_FRAMEWORKS.md](COMPLIANCE_FRAMEWORKS.md) (SOC 2 CC8.1,
PCI Req 6.4, ISO A.8.28); the residual gap is dependency pinning.

---

## 5. License report

Licenses are bucketed to surface distribution and obligation risk. Copyleft and
unknown components are the material categories for a commercial platform.

| Bucket | Meaning | Action |
|--------|---------|--------|
| Permissive | MIT / BSD / Apache-2.0 and similar | Low obligation; attribution retained |
| Copyleft | GPL / LGPL / MPL family | Review distribution model; confirm no source-disclosure trigger |
| Unknown | No declared / unresolved license | Investigate and resolve before release |

The license report is generated from SBOM metadata via
`/supply-chain/licenses`. Any component landing in the **unknown** bucket is
treated as a release blocker until its license is resolved; **copyleft**
components are reviewed against the SaaS distribution model.

---

## 6. Image scanning & CI integration

Supply-chain assurance extends into the container pipeline:

- **SBOM in CI** — the component inventory is generated on each build and
  archived alongside the image.
- **Secret scanning** — `gitleaks` runs in the pipeline to block committed
  credentials.
- **Image scanning readiness** — the pipeline is structured to run a vulnerability
  scanner (Trivy / Grype) against built images before promotion; see
  [CONTAINER_KUBERNETES_SECURITY.md](CONTAINER_KUBERNETES_SECURITY.md).

---

## 7. Operating model

- The SBOM is regenerated and archived every release as auditor evidence.
- Dependency findings are tracked to closure; pinning + lockfile is the single
  open medium-severity item.
- License classification is reviewed before each release; unknown-license
  components block promotion.
- Scores are honest to the environment: the development profile's **60** reflects
  the unpinned-dependency finding, not a control failure — a
  production-configured build with pinned dependencies scores materially higher.
