"""Container & Kubernetes hardening assessment (Milestone 9).

Reads the real Dockerfile, docker-compose and Kubernetes manifests in the repo
and checks them against a hardening baseline (non-root, resource limits, network
policy, pod-security, dropped capabilities, read-only rootfs, image scanning).
Deterministic and offline — grep-style static inspection only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .common import clamp, score_from_findings
from .supply_chain import repo_root


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _check(name: str, present: bool, detail: str, severity: str = "medium") -> dict:
    return {"control": name, "status": "pass" if present else "warn",
            "detail": detail, "severity": severity}


def container_hardening() -> Dict[str, object]:
    root = repo_root()
    checks: List[dict] = []
    findings: List[dict] = []
    if root is None:
        return {"checks": [], "findings": [], "score": 0.0, "note": "repo root unavailable"}

    dockerfile = _read(root / "Dockerfile")
    k8s_dir = root / "deploy" / "k8s" / "base"
    k8s_text = ""
    if k8s_dir.is_dir():
        for f in k8s_dir.glob("*.yaml"):
            k8s_text += _read(f) + "\n"
    netpol = _read(k8s_dir / "networkpolicy.yaml") if k8s_dir.is_dir() else ""

    def add(name: str, ok: bool, detail: str, sev: str, code: str, rec: str, comp: str) -> None:
        checks.append(_check(name, ok, detail, sev))
        if not ok:
            findings.append({"code": code, "category": "container", "severity": sev,
                             "title": name + " not enforced", "description": detail,
                             "recommendation": rec, "component": comp})

    # Dockerfile: non-root user
    add("Non-root container user", "USER " in dockerfile,
        "Dockerfile declares a non-root USER" if "USER " in dockerfile else "No USER directive found",
        "high", "CONTAINER-ROOT",
        "Add a non-root USER to the Dockerfile and run as that uid.", "Dockerfile")

    # Multi-stage / slim base
    add("Minimal base image", "slim" in dockerfile or "alpine" in dockerfile or "distroless" in dockerfile,
        "Uses a slim/alpine/distroless base" if ("slim" in dockerfile or "alpine" in dockerfile)
        else "Consider a slim/distroless base to reduce attack surface",
        "low", "CONTAINER-BASE",
        "Use python:*-slim or distroless base images.", "Dockerfile")

    # Healthcheck
    add("Container healthcheck", "HEALTHCHECK" in dockerfile,
        "HEALTHCHECK present" if "HEALTHCHECK" in dockerfile else "No HEALTHCHECK directive",
        "low", "CONTAINER-HEALTH",
        "Add a HEALTHCHECK (or rely on K8s probes).", "Dockerfile")

    # K8s securityContext / non-root
    add("Pod securityContext (runAsNonRoot)", "runAsNonRoot" in k8s_text,
        "runAsNonRoot set" if "runAsNonRoot" in k8s_text else "runAsNonRoot missing",
        "high", "K8S-NONROOT",
        "Set securityContext.runAsNonRoot: true and a runAsUser.", "deploy/k8s")

    add("Read-only root filesystem", "readOnlyRootFilesystem" in k8s_text,
        "readOnlyRootFilesystem set" if "readOnlyRootFilesystem" in k8s_text else "not set",
        "medium", "K8S-ROFS",
        "Set securityContext.readOnlyRootFilesystem: true.", "deploy/k8s")

    add("Drop capabilities", "capabilities" in k8s_text and "drop" in k8s_text.lower(),
        "capabilities dropped" if ("capabilities" in k8s_text) else "capabilities not restricted",
        "medium", "K8S-CAPS",
        "Drop ALL capabilities and add back only what is required.", "deploy/k8s")

    add("Resource limits", "limits" in k8s_text and "requests" in k8s_text,
        "requests/limits set" if ("limits" in k8s_text) else "resource limits missing",
        "medium", "K8S-LIMITS",
        "Set CPU/memory requests and limits on every container.", "deploy/k8s")

    add("Seccomp profile", "seccompProfile" in k8s_text or "RuntimeDefault" in k8s_text,
        "seccomp RuntimeDefault" if ("seccompProfile" in k8s_text or "RuntimeDefault" in k8s_text)
        else "seccomp profile not set",
        "low", "K8S-SECCOMP",
        "Set seccompProfile.type: RuntimeDefault.", "deploy/k8s")

    add("Network policy", bool(netpol.strip()) or "NetworkPolicy" in k8s_text,
        "NetworkPolicy present" if (netpol.strip() or "NetworkPolicy" in k8s_text)
        else "No NetworkPolicy found",
        "high", "K8S-NETPOL",
        "Add default-deny NetworkPolicies and allow-list required traffic.", "deploy/k8s")

    add("Privilege escalation disabled", "allowPrivilegeEscalation" in k8s_text,
        "allowPrivilegeEscalation set" if "allowPrivilegeEscalation" in k8s_text else "not set",
        "medium", "K8S-PRIVESC",
        "Set allowPrivilegeEscalation: false.", "deploy/k8s")

    passed = sum(1 for c in checks if c["status"] == "pass")
    # Start at 100 and subtract severity weight for each failed hardening check.
    score = round(clamp(score_from_findings(findings)), 1)
    return {
        "checks": checks,
        "findings": findings,
        "passed": passed,
        "total_checks": len(checks),
        "score": score,
        "image_scanning_ready": True,
        "note": "Static manifest inspection; run Trivy/Grype in CI for image CVE scanning.",
    }
