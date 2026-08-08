"""User profile helpers.

Single source of truth for turning a stored ``User`` row into the profile the
frontend renders (name, first name, job title, department, organisation, role,
avatar, initials). Stored columns win; when a column is empty we derive a
sensible value from the email so a brand-new account still looks personalised.
No value is ever hardcoded to a specific person — the only fallbacks are the
generic "User", "Risk Analyst" and "Unknown Organization".
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# Generic fallbacks (never a real person's details).
GENERIC_NAME = "User"
GENERIC_TITLE = "Risk Analyst"
GENERIC_ORG = "Unknown Organization"

# Map well-known email domains to their organisation / bank name so demo and
# real bank accounts get the right employer without needing it typed in.
BANK_BY_DOMAIN = {
    "hdfcbank.com": "HDFC Bank",
    "icicibank.com": "ICICI Bank",
    "sbi.co.in": "State Bank of India",
    "axisbank.com": "Axis Bank",
    "kotak.com": "Kotak Mahindra Bank",
    "kotakbank.com": "Kotak Mahindra Bank",
    "yesbank.in": "Yes Bank",
    "pnb.co.in": "Punjab National Bank",
    "bankofbaroda.com": "Bank of Baroda",
    "idfcfirstbank.com": "IDFC First Bank",
    "bank.com": "Demo Bank",
    "test.com": "Test Organization",
}

# Personal / provider domains that carry no employer signal.
PERSONAL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "yahoo.in",
    "icloud.com",
    "proton.me",
    "protonmail.com",
}


def _split_domain(email: str) -> tuple[str, str]:
    """Return (local_part, domain) lower-cased; blanks if malformed."""
    if not email or "@" not in email:
        return (email or "").strip().lower(), ""
    local, _, domain = email.partition("@")
    return local.strip().lower(), domain.strip().lower()


def derive_name_from_email(email: str) -> str:
    """Turn an email local-part into a readable name, e.g.
    ``priya.sharma@hdfcbank.com`` -> ``Priya Sharma``. Returns "" if nothing
    usable can be derived (caller falls back to the generic name)."""
    local, _ = _split_domain(email)
    if not local:
        return ""
    # Split on common separators, drop pure-digit chunks.
    tokens = [t for t in re.split(r"[._\-+]+", local) if t and not t.isdigit()]
    if not tokens:
        return ""
    # Strip trailing digits from each token ("rahul24" -> "rahul").
    cleaned = [re.sub(r"\d+$", "", t) or t for t in tokens]
    return " ".join(t.capitalize() for t in cleaned)


def derive_organization_from_email(email: str) -> str:
    """Best-effort organisation name from the email domain."""
    _, domain = _split_domain(email)
    if not domain:
        return GENERIC_ORG
    if domain in BANK_BY_DOMAIN:
        return BANK_BY_DOMAIN[domain]
    if domain in PERSONAL_DOMAINS:
        return GENERIC_ORG
    # Fall back to a title-cased second-level label ("acmebank.co.in" -> "Acmebank").
    label = domain.split(".")[0]
    return label.capitalize() if label else GENERIC_ORG


def initials_from(name: str, email: str) -> str:
    """Two-letter uppercase initials from a name (falls back to the email)."""
    source = (name or "").strip()
    if not source:
        local, _ = _split_domain(email)
        source = local
    parts = [p for p in re.split(r"[\s._\-]+", source) if p]
    if len(parts) >= 2:
        letters = parts[0][0] + parts[1][0]
    elif parts:
        letters = parts[0][:2]
    else:
        letters = "?"
    return letters.upper()


def humanize_role(role: str) -> str:
    """`credit_analyst` -> `Credit Analyst`."""
    return " ".join(w.capitalize() for w in re.split(r"[._\-\s]+", role) if w)


def primary_role_label(roles: Iterable[str]) -> Optional[str]:
    """Pick the most senior role for display, humanised."""
    roles = [r for r in roles if r]
    if not roles:
        return None
    # Rough seniority ordering; anything unknown sorts last but is still shown.
    priority = {
        "administrator": 0,
        "chief_risk_officer": 1,
        "risk_manager": 2,
        "credit_manager": 3,
        "senior_credit_analyst": 4,
        "portfolio_manager": 5,
        "compliance_officer": 6,
        "credit_analyst": 7,
        "auditor": 8,
        "viewer": 9,
    }
    best = min(roles, key=lambda r: priority.get(r, 50))
    return humanize_role(best)


def compute_profile(user, roles: Iterable[str]) -> dict:
    """Build the full profile payload for a ``User`` ORM row.

    Stored columns take precedence; empty columns are derived from the email.
    """
    email = user.email or ""
    roles = list(roles)

    full_name = (getattr(user, "full_name", None) or "").strip()
    if not full_name:
        full_name = derive_name_from_email(email) or GENERIC_NAME

    first_name = full_name.split()[0] if full_name.split() else GENERIC_NAME

    job_title = (getattr(user, "job_title", None) or "").strip() or GENERIC_TITLE

    organization = (getattr(user, "organization_name", None) or "").strip()
    if not organization:
        organization = derive_organization_from_email(email)

    department = (getattr(user, "department", None) or "").strip() or None
    avatar_url = (getattr(user, "avatar_url", None) or "").strip() or None

    return {
        "user_id": user.id,
        "email": email or None,
        "full_name": full_name,
        "first_name": first_name,
        "job_title": job_title,
        "department": department,
        "organization": organization,
        "avatar_url": avatar_url,
        "initials": initials_from(full_name, email),
        "role": primary_role_label(roles),
        "roles": sorted(roles),
    }
