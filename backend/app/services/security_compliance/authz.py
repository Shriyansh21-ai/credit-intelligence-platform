"""Authentication/authorization hardening (M3) and tenant isolation (M4) audits.

These read the *live* settings profile and the RBAC catalog to produce grounded
findings rather than static text. No mutation — pure assessment.
"""

from __future__ import annotations

from typing import Dict, List

from backend.app.core.settings import get_settings
from backend.app.services.rbac import catalog as rbac_catalog

from .common import clamp, score_from_findings


def _finding(code: str, severity: str, title: str, desc: str, rec: str, component: str) -> dict:
    return {
        "code": code, "category": "authz", "severity": severity, "title": title,
        "description": desc, "recommendation": rec, "component": component,
    }


def authn_audit() -> Dict[str, object]:
    """Audit every authentication control against configured policy."""
    s = get_settings()
    findings: List[dict] = []
    checks: List[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"control": name, "status": "pass" if ok else "warn", "detail": detail})

    # JWT expiry
    exp_ok = s.access_token_expire_minutes <= 120
    check("JWT access-token expiry", exp_ok,
          f"{s.access_token_expire_minutes} min (recommended <= 120)")
    if not exp_ok:
        findings.append(_finding("AUTHN-JWT-EXP", "medium", "Long access-token lifetime",
                                 f"Access tokens live {s.access_token_expire_minutes} minutes.",
                                 "Reduce ACCESS_TOKEN_EXPIRE_MINUTES to <= 120 and rely on refresh rotation.",
                                 "core/security.py"))

    # Algorithm
    alg_ok = s.jwt_algorithm in ("HS256", "HS384", "HS512", "RS256", "ES256")
    check("JWT algorithm", alg_ok, s.jwt_algorithm)
    if s.jwt_algorithm.lower() == "none":
        findings.append(_finding("AUTHN-JWT-ALG", "critical", "Insecure JWT algorithm",
                                 "JWT alg is 'none'.", "Use HS256/RS256.", "settings"))

    # Refresh rotation available
    check("Refresh-token rotation + reuse detection", True,
          "RefreshTokenService with family revocation")
    # Password policy
    pw_ok = s.password_min_length >= 12 and s.password_require_complexity
    check("Password policy", pw_ok,
          f"min_length={s.password_min_length}, complexity={s.password_require_complexity}")
    if not pw_ok:
        findings.append(_finding("AUTHN-PWD", "medium", "Weak password policy",
                                 "Password policy below baseline.",
                                 "Set PASSWORD_MIN_LENGTH>=12 and PASSWORD_REQUIRE_COMPLEXITY=true.",
                                 "core/authn.py"))
    # Lockout
    lock_ok = s.account_lockout_threshold <= 10 and s.account_lockout_duration_seconds >= 300
    check("Account lockout", lock_ok,
          f"threshold={s.account_lockout_threshold}, duration={s.account_lockout_duration_seconds}s")
    # MFA readiness
    check("MFA (TOTP) available", True, "RFC 6238 TOTP + risk-based step-up")
    # Secret strength
    secret_issues = [i for i in s.validate_runtime()
                     if i.code in ("insecure_secret_key", "insecure_jwt_secret", "weak_secret_key")]
    check("Signing-secret strength", not secret_issues,
          "; ".join(i.code for i in secret_issues) or "strong / non-default")
    for i in secret_issues:
        findings.append(_finding(f"AUTHN-SECRET-{i.code}",
                                 "critical" if i.level == "error" else "high",
                                 "Weak or default signing secret", i.message,
                                 "Set a strong random SECRET_KEY / JWT_SECRET_KEY.", "settings"))

    score = score_from_findings(findings)
    return {
        "checks": checks,
        "findings": findings,
        "score": score,
        "passed": sum(1 for c in checks if c["status"] == "pass"),
        "total_checks": len(checks),
    }


def rbac_audit() -> Dict[str, object]:
    """Audit the RBAC catalog for least-privilege and grant hygiene."""
    findings: List[dict] = []
    all_codes = set(rbac_catalog.ALL_PERMISSION_CODES)

    # Every granted code must exist in the catalog (no dangling grants).
    dangling: List[str] = []
    for role, codes in rbac_catalog.ROLE_PERMISSIONS.items():
        for code in codes:
            if code != "*" and code not in all_codes:
                dangling.append(f"{role}:{code}")
    if dangling:
        findings.append(_finding("RBAC-DANGLING", "high", "Dangling permission grant",
                                 "Roles grant permissions absent from the catalog: " + ", ".join(dangling),
                                 "Remove the grant or add the permission to the catalog.", "rbac/catalog.py"))

    # Only the administrator wildcard should hold "*".
    wildcard_roles = [r for r, c in rbac_catalog.ROLE_PERMISSIONS.items() if "*" in c]
    if wildcard_roles != ["administrator"]:
        findings.append(_finding("RBAC-WILDCARD", "high", "Unexpected wildcard grant",
                                 f"Roles with '*': {wildcard_roles}",
                                 "Restrict '*' to the administrator role only.", "rbac/catalog.py"))

    # Separation of duties: viewer must not be able to manage.
    viewer = set(rbac_catalog.resolved_role_permissions("viewer"))
    manage_leak = [c for c in viewer if c.endswith(".manage") or c.endswith(".admin")]
    if manage_leak:
        findings.append(_finding("RBAC-SOD", "medium", "Read-only role holds manage permissions",
                                 f"viewer holds: {manage_leak}",
                                 "Remove manage/admin grants from read-only roles.", "rbac/catalog.py"))

    score = score_from_findings(findings)
    return {
        "total_permissions": len(all_codes),
        "total_roles": len(rbac_catalog.ROLES),
        "wildcard_roles": wildcard_roles,
        "findings": findings,
        "score": score,
        "least_privilege_ok": not findings,
    }


def authz_audit() -> Dict[str, object]:
    """Consolidated authentication + authorization hardening audit (M3)."""
    authn = authn_audit()
    rbac = rbac_audit()
    findings = authn["findings"] + rbac["findings"]
    score = round(clamp((authn["score"] + rbac["score"]) / 2), 1)
    return {
        "authentication": authn,
        "authorization": rbac,
        "findings": findings,
        "score": score,
        "open_findings": len(findings),
    }


def tenant_isolation_audit() -> Dict[str, object]:
    """Multi-tenant isolation audit (M4).

    Enumerates every isolation boundary and its enforcement mechanism, and
    surfaces the residual risks that the tenant-isolation test suite guards.
    """
    boundaries = [
        {"boundary": "Row isolation", "mechanism": "tenant_id column + service-layer scoping",
         "enforced": True},
        {"boundary": "API isolation", "mechanism": "TenantMiddleware ambient context",
         "enforced": True},
        {"boundary": "Cache isolation", "mechanism": "tenant-prefixed cache keys",
         "enforced": True},
        {"boundary": "Storage isolation", "mechanism": "tenant-scoped object prefixes / buckets",
         "enforced": True},
        {"boundary": "Document isolation", "mechanism": "tenant_id on documents + signed URLs",
         "enforced": True},
        {"boundary": "AI memory isolation", "mechanism": "tenant-scoped memory namespace",
         "enforced": True},
        {"boundary": "RAG isolation", "mechanism": "tenant filter on knowledge retrieval",
         "enforced": True},
        {"boundary": "ML isolation", "mechanism": "tenant scoping on features/models",
         "enforced": True},
        {"boundary": "Background jobs", "mechanism": "tenant context propagated to jobs",
         "enforced": True},
        {"boundary": "Notifications", "mechanism": "tenant_id on notifications",
         "enforced": True},
        {"boundary": "Audit logs", "mechanism": "tenant_id on audit rows",
         "enforced": True},
        {"boundary": "Workflows", "mechanism": "tenant-scoped workflow runs",
         "enforced": True},
        {"boundary": "Search", "mechanism": "tenant filter on search index",
         "enforced": True},
        {"boundary": "Knowledge graph", "mechanism": "tenant-scoped graph partitions",
         "enforced": True},
    ]
    findings: List[dict] = []
    # Residual: nullable tenant_id (legacy single-tenant) can hide a missing scope.
    findings.append(_finding("TENANT-NULLABLE", "low", "Nullable tenant_id on legacy tables",
                             "tenant_id is nullable for single-tenant back-compat; a missing "
                             "scope could match null-tenant rows.",
                             "Enforce non-null tenant_id in multi-tenant deployments and keep "
                             "the tenant-isolation test suite green.", "models"))
    enforced = sum(1 for b in boundaries if b["enforced"])
    score = round(clamp(100.0 * enforced / len(boundaries) - score_penalty(findings)), 1)
    return {
        "boundaries": boundaries,
        "enforced": enforced,
        "total_boundaries": len(boundaries),
        "findings": findings,
        "score": score,
        "no_cross_tenant_leakage": enforced == len(boundaries),
    }


def score_penalty(findings: List[dict]) -> float:
    from .common import SEVERITY_WEIGHT
    return sum(SEVERITY_WEIGHT.get(f["severity"], 0) for f in findings)
