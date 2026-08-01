"""Enterprise Security & Compliance APIs (Stage 4).

Additive routers under ``/api/sec/*``. Every route is new; nothing from Stages
1-3 is modified. RBAC is enforced with the Stage 4 permission catalog
(``sec.*``). Read surfaces require a ``*.view`` permission; scans, triage
compliance runs and privacy actions require the corresponding manage permission.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.security_compliance import (
    ComplianceAssessRequest,
    FindingStatusUpdate,
    PrivacyRequestCreate,
    PrivacyRequestUpdate,
    RiskCreate,
    RiskUpdate,
    ScanRequest,
)
from backend.app.services.rbac import require_permission
from backend.app.services.security_compliance import (
    ai_ml,
    authz as authz_svc,
    catalog,
    compliance as compliance_svc,
    data_protection as data_svc,
    hardening,
    owasp as owasp_svc,
    posture as posture_svc,
    privacy as privacy_svc,
    secrets as secrets_svc,
    service as svc,
    supply_chain,
    threat_model,
)


def _tenant(explicit: Optional[int] = None) -> Optional[int]:
    if explicit is not None:
        return explicit
    try:
        from backend.app.services.saas import context as tenant_ctx

        return tenant_ctx.current_tenant_id()
    except Exception:
        return None


def _bad(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


# ===========================================================================
# Posture & dashboard (M14)
# ===========================================================================
posture_router = APIRouter(prefix="/api/sec/posture", tags=["Security: Posture"])


@posture_router.get("")
def get_posture(_u=Depends(require_permission("sec.dashboard.view"))):
    return posture_svc.security_posture()


@posture_router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _u=Depends(require_permission("sec.dashboard.view"))):
    return svc.security_dashboard(db, tenant_id=_tenant())


@posture_router.post("/snapshot")
def snapshot(db: Session = Depends(get_db),
             user: User = Depends(require_permission("sec.findings.manage"))):
    return svc.snapshot_posture(db, tenant_id=_tenant())


@posture_router.get("/snapshots")
def snapshots(db: Session = Depends(get_db), _u=Depends(require_permission("sec.dashboard.view"))):
    return {"snapshots": svc.list_posture_snapshots(db, tenant_id=_tenant())}


# ===========================================================================
# Threat model (M1)
# ===========================================================================
threat_router = APIRouter(prefix="/api/sec/threat", tags=["Security: Threat Model"])


@threat_router.get("")
def threat_model_full(_u=Depends(require_permission("sec.threat.view"))):
    return threat_model.build_threat_model()


@threat_router.get("/stride")
def stride(_u=Depends(require_permission("sec.threat.view"))):
    return threat_model.stride_analysis()


@threat_router.get("/attack-surface")
def attack_surface(_u=Depends(require_permission("sec.threat.view"))):
    return threat_model.attack_surface()


@threat_router.get("/attack-trees")
def attack_trees(_u=Depends(require_permission("sec.threat.view"))):
    return {"attack_trees": threat_model.attack_trees()}


@threat_router.get("/boundaries")
def boundaries(_u=Depends(require_permission("sec.threat.view"))):
    return {"trust_boundaries": threat_model.trust_boundaries()}


# ===========================================================================
# OWASP (M2)
# ===========================================================================
owasp_router = APIRouter(prefix="/api/sec/owasp", tags=["Security: OWASP"])


@owasp_router.get("")
def owasp_all(_u=Depends(require_permission("sec.owasp.view"))):
    return owasp_svc.owasp_assessment()


@owasp_router.get("/top10")
def owasp_top10(_u=Depends(require_permission("sec.owasp.view"))):
    return owasp_svc.owasp_top10()


@owasp_router.get("/api-top10")
def owasp_api(_u=Depends(require_permission("sec.owasp.view"))):
    return owasp_svc.owasp_api_top10()


@owasp_router.get("/asvs")
def owasp_asvs(_u=Depends(require_permission("sec.owasp.view"))):
    return owasp_svc.asvs()


# ===========================================================================
# Auth hardening (M3) + tenant isolation (M4)
# ===========================================================================
authz_router = APIRouter(prefix="/api/sec/authz", tags=["Security: Auth & Tenant"])


@authz_router.get("")
def authz_audit(_u=Depends(require_permission("sec.authz.view"))):
    return authz_svc.authz_audit()


@authz_router.get("/tenant-isolation")
def tenant_isolation(_u=Depends(require_permission("sec.tenant.view"))):
    return authz_svc.tenant_isolation_audit()


# ===========================================================================
# Secrets (M5)
# ===========================================================================
secrets_router = APIRouter(prefix="/api/sec/secrets", tags=["Security: Secrets"])


@secrets_router.get("")
def secret_inventory(_u=Depends(require_permission("sec.secrets.view"))):
    return secrets_svc.secret_inventory()


# ===========================================================================
# Data protection (M6)
# ===========================================================================
data_router = APIRouter(prefix="/api/sec/data", tags=["Security: Data Protection"])


@data_router.get("")
def data_protection(_u=Depends(require_permission("sec.data.view"))):
    return data_svc.data_protection_report()


@data_router.get("/pii-catalog")
def pii_catalog(_u=Depends(require_permission("sec.data.view"))):
    return {"pii_catalog": data_svc.pii_catalog(),
            "classifications": data_svc.data_classification()}


# ===========================================================================
# Compliance (M7)
# ===========================================================================
compliance_router = APIRouter(prefix="/api/sec/compliance", tags=["Security: Compliance"])


@compliance_router.get("/matrix")
def compliance_matrix(_u=Depends(require_permission("sec.compliance.view"))):
    return compliance_svc.compliance_matrix()


@compliance_router.get("/frameworks")
def frameworks(_u=Depends(require_permission("sec.compliance.view"))):
    return {"frameworks": catalog.framework_ids()}


@compliance_router.get("/gap-analysis")
def gap_analysis(_u=Depends(require_permission("sec.compliance.view"))):
    return compliance_svc.gap_analysis()


@compliance_router.get("/readiness")
def readiness(_u=Depends(require_permission("sec.compliance.view"))):
    return compliance_svc.readiness_score()


@compliance_router.get("/framework/{framework}")
def framework_detail(framework: str, _u=Depends(require_permission("sec.compliance.view"))):
    try:
        return compliance_svc.assess_framework(framework)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@compliance_router.post("/assess")
def assess(body: ComplianceAssessRequest, db: Session = Depends(get_db),
           user: User = Depends(require_permission("sec.compliance.manage"))):
    try:
        return svc.record_compliance_assessment(
            db, framework=body.framework, tenant_id=_tenant(body.tenant_id), user_id=user.id)
    except ValueError as exc:
        _bad(exc)


@compliance_router.get("/assessments")
def assessments(framework: Optional[str] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("sec.compliance.view"))):
    return {"assessments": svc.list_compliance_assessments(
        db, tenant_id=_tenant(), framework=framework)}


# ===========================================================================
# Supply chain (M8)
# ===========================================================================
supply_router = APIRouter(prefix="/api/sec/supply-chain", tags=["Security: Supply Chain"])


@supply_router.get("")
def supply_chain_report(_u=Depends(require_permission("sec.supplychain.view"))):
    return supply_chain.supply_chain_report()


@supply_router.get("/sbom")
def sbom(_u=Depends(require_permission("sec.supplychain.view"))):
    return supply_chain.sbom()


@supply_router.get("/dependencies")
def dependencies(_u=Depends(require_permission("sec.supplychain.view"))):
    return supply_chain.dependency_report()


@supply_router.get("/licenses")
def licenses(_u=Depends(require_permission("sec.supplychain.view"))):
    return supply_chain.license_report()


# ===========================================================================
# Container / K8s hardening (M9)
# ===========================================================================
container_router = APIRouter(prefix="/api/sec/container", tags=["Security: Container Hardening"])


@container_router.get("")
def container_hardening(_u=Depends(require_permission("sec.container.view"))):
    return hardening.container_hardening()


# ===========================================================================
# AI (M10) + ML (M11) security
# ===========================================================================
ai_router = APIRouter(prefix="/api/sec/ai", tags=["Security: AI & ML"])


@ai_router.get("/security")
def ai_security(_u=Depends(require_permission("sec.aisec.view"))):
    return ai_ml.ai_security()


@ai_router.get("/ml-security")
def ml_security(_u=Depends(require_permission("sec.mlsec.view"))):
    return ai_ml.ml_security()


# ===========================================================================
# Privacy (M12)
# ===========================================================================
privacy_router = APIRouter(prefix="/api/sec/privacy", tags=["Security: Privacy"])


@privacy_router.get("")
def privacy_overview(_u=Depends(require_permission("sec.privacy.view"))):
    return privacy_svc.privacy_overview()


@privacy_router.get("/requests")
def privacy_requests(status: Optional[str] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("sec.privacy.view"))):
    return {"requests": svc.list_privacy_requests(db, tenant_id=_tenant(), status=status)}


@privacy_router.post("/requests")
def create_privacy_request(body: PrivacyRequestCreate, db: Session = Depends(get_db),
                           user: User = Depends(require_permission("sec.privacy.manage"))):
    try:
        return svc.create_privacy_request(
            db, subject_ref=body.subject_ref, request_type=body.request_type,
            legal_basis=body.legal_basis, notes=body.notes,
            tenant_id=_tenant(body.tenant_id), user_id=user.id)
    except ValueError as exc:
        _bad(exc)


@privacy_router.patch("/requests/{request_id}")
def update_privacy_request(request_id: int, body: PrivacyRequestUpdate,
                           db: Session = Depends(get_db),
                           user: User = Depends(require_permission("sec.privacy.manage"))):
    try:
        res = svc.update_privacy_request(
            db, request_id, status=body.status, notes=body.notes, tenant_id=_tenant())
    except ValueError as exc:
        return _bad(exc)
    if res is None:
        raise HTTPException(status_code=404, detail="Privacy request not found")
    return res


# ===========================================================================
# Scans (M13/M14) — run assessment engines and persist findings
# ===========================================================================
scan_router = APIRouter(prefix="/api/sec/scans", tags=["Security: Scans"])


@scan_router.get("/types")
def scan_types(_u=Depends(require_permission("sec.findings.view"))):
    return {"scan_types": svc.SCAN_TYPES}


@scan_router.post("")
def run_scan(body: ScanRequest, db: Session = Depends(get_db),
             user: User = Depends(require_permission("sec.findings.manage"))):
    try:
        return svc.run_scan(db, scan_type=body.scan_type,
                            tenant_id=_tenant(body.tenant_id), user_id=user.id)
    except ValueError as exc:
        _bad(exc)


@scan_router.get("")
def list_scans(scan_type: Optional[str] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("sec.findings.view"))):
    return {"scans": svc.list_scans(db, tenant_id=_tenant(), scan_type=scan_type)}


@scan_router.get("/{scan_id}")
def get_scan(scan_id: int, db: Session = Depends(get_db),
             _u=Depends(require_permission("sec.findings.view"))):
    res = svc.get_scan(db, scan_id, tenant_id=_tenant())
    if res is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return res


# ===========================================================================
# Findings (M13/M14)
# ===========================================================================
findings_router = APIRouter(prefix="/api/sec/findings", tags=["Security: Findings"])


@findings_router.get("")
def list_findings(status: Optional[str] = None, category: Optional[str] = None,
                  severity: Optional[str] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("sec.findings.view"))):
    return {"findings": svc.list_findings(
        db, tenant_id=_tenant(), status=status, category=category, severity=severity)}


@findings_router.patch("/{finding_id}")
def update_finding(finding_id: int, body: FindingStatusUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_permission("sec.findings.manage"))):
    try:
        res = svc.update_finding_status(
            db, finding_id, status=body.status, user_id=user.id, tenant_id=_tenant())
    except ValueError as exc:
        return _bad(exc)
    if res is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return res


# ===========================================================================
# Risk register (M1 continuity)
# ===========================================================================
risk_router = APIRouter(prefix="/api/sec/risk", tags=["Security: Risk Register"])


@risk_router.get("")
def list_risks(status: Optional[str] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("sec.risk.view"))):
    return {"risks": svc.list_risks(db, tenant_id=_tenant(), status=status)}


@risk_router.post("")
def create_risk(body: RiskCreate, db: Session = Depends(get_db),
                user: User = Depends(require_permission("sec.risk.manage"))):
    try:
        return svc.create_risk(
            db, title=body.title, category=body.category, likelihood=body.likelihood,
            impact=body.impact, description=body.description, treatment=body.treatment,
            residual_likelihood=body.residual_likelihood, residual_impact=body.residual_impact,
            mitigations=body.mitigations, owner=body.owner,
            tenant_id=_tenant(body.tenant_id), user_id=user.id)
    except ValueError as exc:
        _bad(exc)


@risk_router.patch("/{risk_id}")
def update_risk(risk_id: int, body: RiskUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_permission("sec.risk.manage"))):
    try:
        res = svc.update_risk(db, risk_id, tenant_id=_tenant(),
                              **body.model_dump(exclude_unset=True))
    except ValueError as exc:
        return _bad(exc)
    if res is None:
        raise HTTPException(status_code=404, detail="Risk entry not found")
    return res


ROUTERS = [
    posture_router,
    threat_router,
    owasp_router,
    authz_router,
    secrets_router,
    data_router,
    compliance_router,
    supply_router,
    container_router,
    ai_router,
    privacy_router,
    scan_router,
    findings_router,
    risk_router,
]
