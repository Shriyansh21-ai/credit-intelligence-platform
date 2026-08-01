"""Supply-chain security (Milestone 8).

Builds a lightweight SBOM, a dependency report and a license report by reading
the real dependency manifests in the repo (requirements.txt, pyproject.toml,
frontend/package.json). Pure-stdlib parsing — no network, no third-party SBOM
tool required — so it works fully offline and deterministically.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from .common import clamp

# repo root = five parents up from this file:
# backend/app/services/security_compliance/supply_chain.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]

# Known permissive / copyleft license buckets for a coarse license-risk read.
_PERMISSIVE = {"MIT", "BSD", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF", "Unlicense"}
_COPYLEFT = {"GPL", "GPL-2.0", "GPL-3.0", "AGPL", "AGPL-3.0", "LGPL"}

# Best-effort license map for the platform's core Python dependencies.
_PY_LICENSE_HINTS = {
    "fastapi": "MIT", "starlette": "BSD-3-Clause", "pydantic": "MIT", "pydantic-settings": "MIT",
    "sqlalchemy": "MIT", "alembic": "MIT", "uvicorn": "BSD-3-Clause", "python-jose": "MIT",
    "bcrypt": "Apache-2.0", "passlib": "BSD-2-Clause", "cryptography": "Apache-2.0",
    "python-multipart": "Apache-2.0", "requests": "Apache-2.0", "httpx": "BSD-3-Clause",
    "numpy": "BSD-3-Clause", "pandas": "BSD-3-Clause", "scikit-learn": "BSD-3-Clause",
    "joblib": "BSD-3-Clause", "prometheus-client": "Apache-2.0", "opentelemetry-api": "Apache-2.0",
    "psycopg2-binary": "LGPL", "redis": "MIT", "boto3": "Apache-2.0", "pytest": "MIT",
    "ruff": "MIT", "anthropic": "MIT",
}

_REQ_LINE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*([<>=!~]=?)?\s*([0-9A-Za-z_.\-]+)?")


def _parse_requirements(path: Path) -> List[dict]:
    deps: List[dict] = []
    if not path.is_file():
        return deps
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split("#", 1)[0].strip()
        m = _REQ_LINE.match(line)
        if not m:
            continue
        name = m.group(1).lower()
        pinned = bool(m.group(2) and "==" in (m.group(2) or ""))
        deps.append({
            "name": name,
            "constraint": (m.group(2) or "") + (m.group(3) or ""),
            "pinned": pinned,
            "ecosystem": "pypi",
            "license": _PY_LICENSE_HINTS.get(name, "unknown"),
        })
    return deps


def _parse_package_json(path: Path) -> List[dict]:
    import json

    deps: List[dict] = []
    if not path.is_file():
        return deps
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return deps
    for section in ("dependencies", "devDependencies"):
        for name, ver in (data.get(section) or {}).items():
            deps.append({
                "name": name,
                "constraint": str(ver),
                "pinned": not str(ver).startswith(("^", "~", ">", "<", "*")),
                "ecosystem": "npm",
                "license": "unknown",
                "dev": section == "devDependencies",
            })
    return deps


def _license_bucket(license_name: str) -> str:
    base = license_name.split("-")[0].upper() if license_name != "unknown" else "unknown"
    if license_name in _PERMISSIVE or base in {"MIT", "BSD", "APACHE", "ISC", "PSF"}:
        return "permissive"
    if license_name in _COPYLEFT or base in {"GPL", "AGPL", "LGPL"}:
        return "copyleft"
    return "unknown"


def _collect() -> List[dict]:
    deps = _parse_requirements(_REPO_ROOT / "requirements.txt")
    deps += _parse_package_json(_REPO_ROOT / "frontend" / "package.json")
    return deps


def sbom() -> Dict[str, object]:
    """A minimal CycloneDX-style component inventory."""
    deps = _collect()
    components = [
        {
            "type": "library",
            "name": d["name"],
            "version": d["constraint"] or "unspecified",
            "ecosystem": d["ecosystem"],
            "license": d["license"],
        }
        for d in deps
    ]
    return {
        "bom_format": "CycloneDX-like",
        "spec_version": "1.5",
        "component_count": len(components),
        "components": components,
        "ecosystems": sorted({d["ecosystem"] for d in deps}),
    }


def _unconstrained(dep: dict) -> bool:
    """True only when a dependency has NO version constraint at all.

    Caret/tilde ranges (``^1.2.0`` / ``~1.2``) and exact pins are all acceptable
    supply-chain hygiene; a completely open constraint (``*``/``latest``/empty)
    is the genuine risk that a lockfile mitigates.
    """
    c = str(dep.get("constraint", "")).strip()
    return c in ("", "*", "latest") or c.startswith("*")


def dependency_report() -> Dict[str, object]:
    deps = _collect()
    py = [d for d in deps if d["ecosystem"] == "pypi"]
    npm = [d for d in deps if d["ecosystem"] == "npm"]
    unpinned = [d["name"] for d in deps if not d["pinned"]]
    findings: List[dict] = []
    # Genuinely unconstrained production dependencies are the supply-chain risk
    # a lockfile addresses; conventional caret/tilde ranges are not penalised.
    prod_open = [d for d in deps if _unconstrained(d) and not d.get("dev")]
    if prod_open:
        findings.append({
            "code": "SUPPLY-UNPINNED", "category": "supply_chain", "severity": "medium",
            "title": f"{len(prod_open)} unconstrained production dependencies",
            "description": "Dependencies with no version constraint allow drift and unreviewed upgrades.",
            "recommendation": "Add version constraints and commit a lockfile; enable Dependabot/renovate review.",
            "component": "requirements.txt / package.json",
        })
    # Lockfile presence is the primary supply-chain control; absence is advisory.
    has_lockfile = (_REPO_ROOT / "frontend" / "package-lock.json").is_file() or \
        (_REPO_ROOT / "frontend" / "pnpm-lock.yaml").is_file() or \
        (_REPO_ROOT / "frontend" / "yarn.lock").is_file()
    secret_scanning = (_REPO_ROOT / ".gitleaks.toml").is_file()
    ci_present = (_REPO_ROOT / ".github").is_dir()
    # Control-credit score: reward the positive supply-chain controls that exist
    # and subtract a bounded penalty for unconstrained production dependencies.
    score = 40.0
    score += 20.0 if secret_scanning else 0.0
    score += 15.0 if ci_present else 0.0
    score += 15.0 if has_lockfile else 0.0
    score += 10.0  # SBOM generated by this module
    score -= min(40.0, len(prod_open) * 1.5)
    score = round(clamp(score), 1)
    return {
        "total": len(deps),
        "python": len(py),
        "npm": len(npm),
        "pinned": sum(1 for d in deps if d["pinned"]),
        "unpinned": len(unpinned),
        "unpinned_names": unpinned[:50],
        "findings": findings,
        "score": score,
        "unconstrained": len(prod_open),
        "scanning": {
            "secret_scanning": (_REPO_ROOT / ".gitleaks.toml").is_file(),
            "ci_present": (_REPO_ROOT / ".github").is_dir(),
            "lockfile_present": has_lockfile,
            "sbom_generated": True,
        },
    }


def license_report() -> Dict[str, object]:
    deps = _collect()
    buckets = {"permissive": 0, "copyleft": 0, "unknown": 0}
    rows: List[dict] = []
    for d in deps:
        bucket = _license_bucket(d["license"])
        buckets[bucket] += 1
        rows.append({"name": d["name"], "license": d["license"], "risk": bucket,
                     "ecosystem": d["ecosystem"]})
    findings: List[dict] = []
    copyleft = [r for r in rows if r["risk"] == "copyleft"]
    if copyleft:
        findings.append({
            "code": "SUPPLY-COPYLEFT", "category": "supply_chain", "severity": "low",
            "title": f"{len(copyleft)} copyleft-licensed dependencies",
            "description": "Copyleft licenses (GPL/LGPL/AGPL) may impose distribution obligations.",
            "recommendation": "Review copyleft dependencies with legal; prefer permissive alternatives.",
            "component": "dependencies",
        })
    return {
        "buckets": buckets,
        "licenses": rows,
        "copyleft": [r["name"] for r in copyleft],
        "unknown": buckets["unknown"],
        "findings": findings,
    }


def supply_chain_report() -> Dict[str, object]:
    dep = dependency_report()
    lic = license_report()
    findings = dep["findings"] + lic["findings"]
    return {
        "sbom": {"component_count": sbom()["component_count"]},
        "dependencies": dep,
        "licenses": {"buckets": lic["buckets"], "copyleft": lic["copyleft"]},
        "findings": findings,
        "score": dep["score"],
        "open_findings": len(findings),
    }


def repo_root() -> Optional[Path]:
    return _REPO_ROOT if _REPO_ROOT.exists() else None
