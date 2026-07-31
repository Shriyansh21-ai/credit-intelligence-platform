# Branch Protection & Environment Recommendations

_Phase 11, M5. These are recommended repository settings — GitHub does not store
branch-protection or environment rules in the repo, so apply them via
**Settings → Branches / Environments** or the `gh` CLI / Terraform (see below)._

---

## 1. Branch model

| Branch | Role | Deploys to |
|--------|------|------------|
| `main` | Production-ready. Only fast-forward from release PRs. | (tag → prod) |
| `develop` | Integration branch. | `development` (auto on green CI) |
| `feature/*`, `fix/*` | Short-lived; PR into `develop`. | — |
| `release/*` | Release stabilisation; PR into `main`. | `staging` (manual) |
| `hotfix/*` | Urgent prod fix; PR into `main` + back-merge to `develop`. | — |

## 2. Protected branch rules — `main`

- ✅ Require a pull request before merging
  - Require **2** approvals
  - Dismiss stale approvals on new commits
  - **Require review from Code Owners** (activates `.github/CODEOWNERS`)
- ✅ Require status checks to pass before merging
  - Require branches to be up to date
  - Required check: **`CI / CI success`**
- ✅ Require conversation resolution before merging
- ✅ Require signed commits
- ✅ Require linear history
- ✅ Include administrators
- ✅ Restrict who can push (release managers only)
- ✅ Do not allow force pushes or deletions

## 3. Protected branch rules — `develop`

- ✅ Require a pull request (1 approval)
- ✅ Require **`CI / CI success`**
- ✅ Require conversation resolution
- ✅ Require Code Owner review
- 🚫 No force pushes / deletions

## 4. GitHub Environments

| Environment | Reviewers | Wait timer | Allowed branches | Secrets / Vars |
|-------------|-----------|-----------|------------------|----------------|
| `development` | none | 0 | `develop` | `KUBE_CONFIG_B64`, `K8S_NAMESPACE=ai-credit-dev`, `APP_URL` |
| `staging` | 1 (platform) | 0 | `release/*`, `main` | `KUBE_CONFIG_B64`, `K8S_NAMESPACE=ai-credit-staging`, `APP_URL` |
| `production` | **2 (platform + eng lead)** | 10 min | `main` + tags `v*` | `KUBE_CONFIG_B64`, `K8S_NAMESPACE=ai-credit`, `APP_URL` |

Required-reviewer protection on `production` is what enforces the **manual
approval** gate in `deploy.yml` — a production deploy pauses until an authorised
reviewer approves it in the Actions UI.

## 5. Repository-wide settings

- ✅ Enable **Dependabot** alerts + security updates (`.github/dependabot.yml`).
- ✅ Enable **Code scanning** (CodeQL + SARIF uploads from Security workflow).
- ✅ Enable **Secret scanning** + push protection.
- ✅ Restrict GHCR package write to the `Release` workflow's `GITHUB_TOKEN`.
- ✅ Require 2FA for all organisation members.
- ✅ Actions permissions: allow only actions from this org + verified creators;
  pin third-party actions by SHA in high-security environments.

## 6. Apply via `gh` CLI (example)

```bash
gh api -X PUT repos/:owner/:repo/branches/main/protection \
  -F required_status_checks.strict=true \
  -F 'required_status_checks.contexts[]=CI / CI success' \
  -F enforce_admins=true \
  -F required_pull_request_reviews.required_approving_review_count=2 \
  -F required_pull_request_reviews.require_code_owner_reviews=true \
  -F required_linear_history=true \
  -F allow_force_pushes=false \
  -F restrictions=null
```

## 7. Apply via Terraform (example)

The `github` provider can codify all of the above. A ready-to-adapt module lives
at `infra/terraform/modules/github-governance/` (see M6 — optional).
