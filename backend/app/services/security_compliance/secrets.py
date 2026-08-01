"""Secret management audit.

Inventories the platform's managed secrets from the live settings, reports the
configured secrets provider, and flags weak / default / missing values using the
same rules as startup validation. Never returns any secret *value*.
"""

from __future__ import annotations

from typing import Dict, List

from backend.app.core.settings import INSECURE_CONNECTOR_KEYS, INSECURE_SECRETS, get_settings

from .common import clamp, score_from_findings

# Logical secrets the platform manages, with rotation guidance.
_MANAGED_SECRETS = [
    {"name": "SECRET_KEY", "purpose": "App signing / HMAC", "rotation_days": 180, "critical": True},
    {"name": "JWT_SECRET_KEY", "purpose": "JWT signing", "rotation_days": 90, "critical": True},
    {"name": "ENCRYPTION_KEY", "purpose": "Field-level encryption", "rotation_days": 365, "critical": True},
    {"name": "CONNECTOR_MASTER_KEY", "purpose": "Connector credential encryption", "rotation_days": 180, "critical": True},
    {"name": "DATABASE_URL", "purpose": "Datastore credentials", "rotation_days": 90, "critical": True},
    {"name": "REDIS_URL", "purpose": "Cache/broker credentials", "rotation_days": 180, "critical": False},
    {"name": "S3_SECRET_ACCESS_KEY", "purpose": "Object storage", "rotation_days": 90, "critical": False},
    {"name": "SMTP_PASSWORD", "purpose": "Mail relay", "rotation_days": 180, "critical": False},
    {"name": "ANTHROPIC_API_KEY", "purpose": "LLM provider", "rotation_days": 180, "critical": False},
    {"name": "STRIPE_API_KEY", "purpose": "Payments", "rotation_days": 90, "critical": False},
]


def _status_for(name: str, value: object) -> str:
    """weak | default | missing | configured — never reveals the value."""
    if value is None or value == "":
        return "missing"
    sval = str(value)
    if sval in INSECURE_SECRETS or sval in INSECURE_CONNECTOR_KEYS:
        return "default"
    if name in ("SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY") and len(sval) < 32:
        return "weak"
    return "configured"


def secret_inventory() -> Dict[str, object]:
    s = get_settings()
    values = {
        "SECRET_KEY": s.secret_key,
        "JWT_SECRET_KEY": s.jwt_secret_key,
        "ENCRYPTION_KEY": s.encryption_key,
        "CONNECTOR_MASTER_KEY": s.connector_master_key,
        "DATABASE_URL": s.database_url,
        "REDIS_URL": s.redis_url,
        "S3_SECRET_ACCESS_KEY": s.s3_secret_access_key,
        "SMTP_PASSWORD": s.smtp_password,
        "ANTHROPIC_API_KEY": s.anthropic_api_key,
        "STRIPE_API_KEY": s.stripe_api_key,
    }
    inventory: List[dict] = []
    findings: List[dict] = []
    for meta in _MANAGED_SECRETS:
        name = meta["name"]
        status = _status_for(name, values.get(name))
        # DATABASE_URL default sqlite is acceptable in dev; only flag prod.
        healthy = status == "configured"
        inventory.append({
            "name": name, "purpose": meta["purpose"], "provider": s.secrets_provider,
            "rotation_days": meta["rotation_days"], "critical": meta["critical"],
            "status": status, "configured": values.get(name) not in (None, ""),
        })
        if meta["critical"] and status in ("default", "weak"):
            findings.append({
                "code": f"SECRET-{name}", "category": "secrets",
                "severity": "critical" if status == "default" else "high",
                "title": f"{name} is {status}",
                "description": f"The critical secret {name} uses a {status} value.",
                "recommendation": f"Set a strong random {name} (e.g. `openssl rand -hex 32`) "
                                  "and store it in a managed secret store.",
                "component": "settings",
            })
    score = score_from_findings(findings)
    return {
        "provider": s.secrets_provider,
        "provider_options": ["env", "file", "aws", "vault"],
        "encryption_key_version": s.encryption_key_version,
        "key_rotation_supported": True,
        "inventory": inventory,
        "findings": findings,
        "score": score,
        "missing_critical": sum(1 for i in inventory if i["critical"] and i["status"] == "missing"),
        "insecure_critical": len(findings),
        "rotation": {
            "field_encryption": "KeyRing versioned keys — add new version, re-encrypt, shred old",
            "jwt": "JwtKeyRing kid rotation — sign with active, verify against all",
        },
    }
