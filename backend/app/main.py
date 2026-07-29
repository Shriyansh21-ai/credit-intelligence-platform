from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .routes import user, loan, prediction
from .routes import transaction
from .routes.fraud import router as fraud_router
from .routes.portfolio import router as portfolio_router
from .models.prediction import Prediction
from .models.fraud import FraudCheck
from .models.portfolio import PortfolioAnalysis
from .models.enterprise_assessment import EnterpriseAssessment
from .routes import history
from .models.user import User
from .routes import auth
from .routes import fraud_history
from .routes import fraud_summary
from .routes import dashboard
from .routes import realtime
from .routes import documents
from .routes import analysis
from .routes import ml
from .routes import rbac as rbac_routes
from .routes import audit as audit_routes
from .routes import applications as applications_routes
from .routes import approvals as approvals_routes
from .routes import covenants as covenants_routes
from .routes import monitoring as monitoring_routes
from .routes import tasks as tasks_routes
from .routes import notifications as notifications_routes
from .routes import collaboration as collaboration_routes
from .routes import search as search_routes
from .routes import reports as reports_routes
from .routes import config as config_routes
from .routes import dashboards as dashboards_routes
from .routes import jobs as jobs_routes
from .models import application as application_models  # noqa: F401
from .models import approval as approval_models  # noqa: F401
from .models import covenant as covenant_models  # noqa: F401
from .models import monitoring as monitoring_models  # noqa: F401
from .models import task as task_models  # noqa: F401
from .models import notification as notification_models  # noqa: F401
from .models import collaboration as collaboration_models  # noqa: F401
from .models import system_config as system_config_models  # noqa: F401
from .models.financial_analysis import FinancialAnalysis
from .models.feature_vector import FeatureVector
from .models.risk_explanation import RiskExplanation
from .models.risk_alert import RiskAlert
from .models import rbac as rbac_models  # noqa: F401  (register RBAC tables)
from .models import audit as audit_models  # noqa: F401  (register audit table)
from .models import ml_platform as ml_platform_models  # noqa: F401  (Phase 6 ML tables)
from .models import integrations as integrations_models  # noqa: F401  (Phase 7 integration tables)
from .models import tenancy as tenancy_models  # noqa: F401  (Phase 8 tenancy tables)
from .models import billing as billing_models  # noqa: F401  (Phase 8 billing tables)
from .models import feature_flags as feature_flag_models  # noqa: F401  (Phase 8 flags)
from .models import platform_ops as platform_ops_models  # noqa: F401  (Phase 8 jobs/storage/realtime/obs)
from .models import saas_security as saas_security_models  # noqa: F401  (Phase 8 security)
from .models import autonomous as autonomous_models  # noqa: F401  (Phase 9 AI-brain tables)
from .models import banking_os as banking_os_models  # noqa: F401  (Phase 10 OS tables)
from .models import ai_platform as ai_platform_models  # noqa: F401  (Track 2 AI platform tables)
from .routes.ml_platform import ROUTERS as ML_PLATFORM_ROUTERS
from .routes.integrations import ROUTERS as INTEGRATION_ROUTERS
from .routes.saas import ROUTERS as SAAS_ROUTERS
from .routes.autonomous import ROUTERS as AUTONOMOUS_ROUTERS
from .routes.banking_os import ROUTERS as BANKING_OS_ROUTERS
from .routes.ai_platform import ROUTERS as AI_PLATFORM_ROUTERS
from .core.audit_middleware import AuditMiddleware
from .core.tenant_middleware import TenantMiddleware
from .core.api_versioning import APIVersionMiddleware
from .core.observability_middleware import ObservabilityMiddleware
from .core.security_middleware import SecurityHeadersMiddleware
from .core.settings import get_settings
from .core.telemetry import instrument_app as _instrument_app
from .core.telemetry import metrics_router as _metrics_router

_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    debug=_settings.debug,
    # OpenAPI enrichment (Phase 11, M10) — additive metadata for the generated
    # spec / developer portal / SDK generation. Does not change any route.
    description=(
        "Enterprise AI credit intelligence platform API. "
        "See docs/API_PLATFORM.md for versioning, deprecation, rate limits, "
        "API keys, and webhook signing/retry/replay."
    ),
    contact={"name": "AI Credit Platform", "url": "https://github.com/Shriyansh21-ai/ai_credit_system"},
    license_info={"name": "Proprietary"},
    openapi_tags=[
        {"name": "Observability", "description": "Metrics, health, and probes."},
        {"name": "Probes", "description": "Kubernetes liveness/readiness probes."},
    ],
)

# ========================================
# CORS MIDDLEWARE
# ========================================
# Allowed origins, credentials and headers come from the centralized settings
# (Phase 11, M1). The default origin list preserves the historical localhost
# development ports; set CORS_ORIGINS in staging/production.

app.add_middleware(

    CORSMiddleware,

    allow_origins=_settings.cors_origins,

    allow_credentials=_settings.cors_allow_credentials,

    allow_methods=["*"],

    allow_headers=["*"],
)

# ========================================
# DATABASE TABLES
# ========================================
# Schema is managed by Alembic migrations (run `alembic upgrade head`).
# `create_all` is intentionally NOT used so migrations remain the single
# source of truth for schema changes across environments.

# ========================================
# ROUTES
# ========================================

app.include_router(
    user.router,
    prefix="/user",
    tags=["User"]
)

app.include_router(
    loan.router,
    prefix="/loan",
    tags=["Loan"]
)

app.include_router(
    portfolio_router,
    prefix="/portfolio",
    tags=["Portfolio"]
)

app.include_router(
    prediction.router,
    prefix="/predict",
    tags=["Prediction"]
)

app.include_router(
    transaction.router,
    prefix="/transaction",
    tags=["Transaction"]
)

app.include_router(fraud_router)

app.include_router(history.router)

app.include_router(auth.router)

app.include_router(fraud_history.router)
app.include_router(fraud_summary.router)
app.include_router(dashboard.router)
app.include_router(realtime.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(ml.router)
app.include_router(rbac_routes.router)
app.include_router(audit_routes.router)
app.include_router(applications_routes.router)
app.include_router(approvals_routes.router)
app.include_router(covenants_routes.router)
app.include_router(monitoring_routes.router)
app.include_router(tasks_routes.router)
app.include_router(notifications_routes.router)
app.include_router(collaboration_routes.router)
app.include_router(search_routes.router)
app.include_router(reports_routes.router)
app.include_router(config_routes.router)
app.include_router(dashboards_routes.router)
app.include_router(jobs_routes.router)

# Root-level Prometheus scrape endpoint (Phase 11, M7). Additive; the scrape
# target is already declared in deploy/monitoring/prometheus.
app.include_router(_metrics_router)

# Phase 6 — Enterprise ML Platform routers (all under /api/ml/*)
for _ml_router in ML_PLATFORM_ROUTERS:
    app.include_router(_ml_router)

# Phase 7 — Banking Ecosystem Integration Platform routers
for _int_router in INTEGRATION_ROUTERS:
    app.include_router(_int_router)

# Phase 8 — Multi-Tenant Enterprise SaaS Platform routers (/api/saas/* + probes)
for _saas_router in SAAS_ROUTERS:
    app.include_router(_saas_router)

# Phase 9 — Autonomous AI Banking Intelligence Platform routers (/api/ai/*)
for _ai_router in AUTONOMOUS_ROUTERS:
    app.include_router(_ai_router)

# Phase 10 — Enterprise Banking Operating System routers (/api/os/*)
for _os_router in BANKING_OS_ROUTERS:
    app.include_router(_os_router)

# Track 2 — AI Intelligence Platform routers (/api/aip/*)
for _aip_router in AI_PLATFORM_ROUTERS:
    app.include_router(_aip_router)

# ========================================
# AUDIT MIDDLEWARE (Phase 5, Milestone 4)
# ========================================
# Records one audit row per mutating API request. Best-effort and self-contained
# (never breaks a request); read-heavy/static paths are skipped internally.

app.add_middleware(AuditMiddleware)

# ========================================
# PHASE 8 MIDDLEWARE
# ========================================
# Tenant resolution establishes the ambient tenant context (best-effort, never
# rejects). Observability is added last so it is the outermost layer and every
# request gets a correlation id + latency metric. Both are additive and safe on
# requests that carry no tenant / correlation headers.

app.add_middleware(TenantMiddleware)
app.add_middleware(ObservabilityMiddleware)

# Security response headers (Phase 11, M8). Added last so it is the outermost
# layer and stamps OWASP headers on every fully-formed response. Additive: only
# sets headers not already present, and is togglable via SECURITY_HEADERS_ENABLED.
app.add_middleware(SecurityHeadersMiddleware)

# Response compression (Phase 11, M9). Gzips responses above a threshold. Uses
# Starlette's built-in middleware; togglable via COMPRESSION_ENABLED.
if _settings.compression_enabled:
    app.add_middleware(GZipMiddleware, minimum_size=_settings.compression_min_size)

# API lifecycle headers (Phase 11, M10). Stamps X-API-Version and, for
# deprecated versions, Deprecation/Sunset/Link headers. Additive and inert for
# unversioned routes.
app.add_middleware(APIVersionMiddleware)

# ========================================
# STARTUP: RBAC catalog sync (Phase 5, Milestone 3)
# ========================================
# Idempotently reconciles the DB with the RBAC catalog on boot so catalog
# changes take effect without a bespoke migration. Best-effort: a missing schema
# (DB not yet migrated) must not stop the app from starting.


@app.on_event("startup")
def _validate_configuration_on_startup() -> None:
    """Validate configuration before serving traffic (Phase 11, M1).

    Fails fast in staging/production if a fatal misconfiguration is present;
    warns only in development/testing so the zero-config flow is preserved.
    """
    from .core.startup import validate_configuration

    validate_configuration()


@app.on_event("startup")
def _init_telemetry_on_startup() -> None:
    """Wire structured logging + OpenTelemetry tracing (Phase 11, M7).

    Best-effort: telemetry initialisation never blocks serving traffic.
    """
    _instrument_app(app)
    # Attach the SQLAlchemy query profiler when explicitly enabled (Phase 11,
    # M9). Off by default so it never adds overhead to the hot path.
    if _settings.query_profiling_enabled:
        try:
            from .core.performance import profiler
            from .db.database import engine

            profiler.attach(engine)
        except Exception:
            pass


@app.on_event("startup")
def _sync_rbac_on_startup() -> None:
    from .db.database import SessionLocal
    from .services.rbac import sync_rbac

    from .services.approvals import ensure_default_workflow
    from .services.config import sync_config

    from .services.integrations.config import sync_connector_configs

    from .services.saas.seeding import seed_saas

    db = SessionLocal()
    try:
        sync_rbac(db)
        ensure_default_workflow(db)
        sync_config(db)
        sync_connector_configs(db)
        seed_saas(db)  # Phase 8: plans, feature flags, default tenant
    except Exception:
        db.rollback()
    finally:
        db.close()

# ========================================
# ROOT
# ========================================

@app.get("/")
def root():

    return {
        "message": "AI Credit Backend Running 🚀"
    }