"""Data protection engine (Milestone 6).

Data classification, PII catalog, and a live demonstration of the masking /
encryption primitives from ``core.crypto`` so the report is grounded in the
actual controls the platform ships.
"""

from __future__ import annotations

from typing import Dict, List

from backend.app.core.crypto import PiiMasker, default_retention, mask_pii
from backend.app.core.settings import get_settings

from . import catalog
from .common import clamp


def data_classification() -> List[Dict[str, str]]:
    return [dict(c) for c in catalog.DATA_CLASSIFICATIONS]


def pii_catalog() -> List[Dict[str, str]]:
    return [dict(p) for p in catalog.PII_CATALOG]


def masking_demo() -> Dict[str, str]:
    """Show the masking primitives working on synthetic (non-real) data."""
    return {
        "email": PiiMasker.mask_email("jane.doe@example.com"),
        "phone": PiiMasker.mask_phone("+91 98765 43210"),
        "card": PiiMasker.mask_card("4111 1111 1111 1111"),
        "pan": PiiMasker.mask_pan("ABCDE1234F"),
        "aadhaar": PiiMasker.mask_aadhaar("1234 5678 9012"),
        "free_text": mask_pii("Contact jane.doe@example.com or +91 98765 43210, PAN ABCDE1234F"),
    }


def encryption_controls() -> Dict[str, object]:
    s = get_settings()
    return {
        "field_encryption": {
            "scheme": "AES-256-GCM (with stdlib encrypt-then-MAC fallback)",
            "key_versioning": True,
            "rotation": "KeyRing add/rotate/shred",
            "active_key_version": s.encryption_key_version,
        },
        "tokenization": "Deterministic masking + reference tokens for PAN/card/Aadhaar",
        "database_encryption": "TDE recommended at the storage layer (deployment)",
        "file_encryption": "Object-storage SSE + signed expiring URLs",
        "object_storage_encryption": f"Backend={s.storage_backend}; SSE recommended",
        "backup_encryption": "Encrypted backups (DR module); crypto-shredding for erasure",
        "key_hierarchy": ["Root/KMS master key", "Data-encryption keys (versioned)",
                          "Per-field ciphers", "Signing/HMAC keys"],
        "transit": "TLS 1.2+/HSTS enforced at the edge",
    }


def retention_catalog() -> List[Dict[str, object]]:
    out = []
    for cat, policy in default_retention.all().items():
        out.append({
            "category": cat,
            "retention_days": policy.retention_days,
            "legal_hold": policy.legal_hold,
            "description": policy.description,
        })
    return out


def data_protection_report() -> Dict[str, object]:
    classifications = data_classification()
    pii = pii_catalog()
    restricted = [p for p in pii if p["classification"] == "restricted"]
    encrypted = [p for p in pii if p["encryption"] in ("required", "hashed (bcrypt)")]
    # Score: proportion of restricted PII that is encryption-required.
    coverage = 100.0 * len(encrypted) / max(1, len(pii))
    score = round(clamp(coverage), 1)
    return {
        "classifications": classifications,
        "pii_catalog": pii,
        "pii_field_count": len(pii),
        "restricted_field_count": len(restricted),
        "encryption_controls": encryption_controls(),
        "masking_demo": masking_demo(),
        "retention": retention_catalog(),
        "score": score,
        "findings": [],
    }
