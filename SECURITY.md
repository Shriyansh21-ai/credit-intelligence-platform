# Security Policy

The security of the **AI Credit Intelligence Platform** and the financial data it
processes is a top priority. This document explains how to report vulnerabilities
and what to expect in return.

> For the platform's internal security **architecture** (encryption, auth
> hardening, RBAC, PII handling), see
> [docs/security/SECURITY_ARCHITECTURE.md](docs/security/SECURITY_ARCHITECTURE.md).

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x (GA) | ✅ Actively supported |
| < 1.0 | ❌ Not supported |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report privately through one of the following channels:

- **GitHub Security Advisories** — use the repository's *Security → Report a
  vulnerability* (private advisory) workflow.
- **Direct contact** — reach the maintainer via
  [github.com/Shriyansh21-ai](https://github.com/Shriyansh21-ai).

When reporting, please include:

1. A clear description of the vulnerability and its impact.
2. Steps to reproduce (proof-of-concept if possible).
3. Affected component, endpoint, or version.
4. Any suggested remediation.

## Our Commitment

| Stage | Target |
|-------|--------|
| **Acknowledgement** | Within **48 hours** of report. |
| **Triage & severity assessment** | Within **5 business days**. |
| **Status updates** | At least every **7 days** until resolution. |
| **Fix & disclosure** | Coordinated with the reporter once a fix is available. |

## Responsible Disclosure

We follow **coordinated disclosure**. We ask that you:

- Give us reasonable time to investigate and remediate before public disclosure.
- Avoid privacy violations, data destruction, and service disruption.
- Only interact with accounts you own or have explicit permission to test.

We will credit reporters who follow this policy (unless anonymity is requested).

## Scope

In scope: the application code in this repository (backend, frontend,
infrastructure-as-code, CI/CD). Out of scope: third-party services, dependencies
with their own disclosure programs, and issues requiring physical access.

## Pipeline Controls

Every change is scanned in CI: SAST (bandit, semgrep, CodeQL), dependency audit
(pip-audit, bun audit), secret scanning (gitleaks — hard gate), and IaC scanning
(trivy). See [docs/deployment/CICD.md](docs/deployment/CICD.md).
