# Changelog

All notable changes to the AI Credit Intelligence Platform are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Per-release notes are generated automatically by `.github/workflows/release.yml`
from the commit history and published to GitHub Releases.

## [Unreleased]

### Added
- **Phase 11, M5 — CI/CD.** GitHub Actions pipeline: `ci.yml` (lint, matrix
  tests, migration round-trip, Docker build), `security.yml` (SAST, dependency
  audit, secret scan, IaC scan, CodeQL), `deploy.yml` (environment-gated k8s
  rollout with rollback), `release.yml` (semver image publish + release).
  Added `CODEOWNERS`, Dependabot, PR template, Kustomize environment overlays,
  `pyproject.toml` tooling config, and CI/CD + branch-protection docs.

---

_Earlier phases (1–10, and Phase 11 M1–M4) predate this changelog; see the
`docs/PHASE*_*_REPORT.md` engineering reports for their history._
