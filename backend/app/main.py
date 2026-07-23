from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

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
from .routes.ml_platform import ROUTERS as ML_PLATFORM_ROUTERS
from .routes.integrations import ROUTERS as INTEGRATION_ROUTERS
from .core.audit_middleware import AuditMiddleware

app = FastAPI(
    title="AI Credit System",
    version="1.0"
)

# ========================================
# CORS MIDDLEWARE
# ========================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "http://localhost:3000",
        "http://localhost:4173",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080"
    ],

    allow_credentials=True,

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

# Phase 6 — Enterprise ML Platform routers (all under /api/ml/*)
for _ml_router in ML_PLATFORM_ROUTERS:
    app.include_router(_ml_router)

# Phase 7 — Banking Ecosystem Integration Platform routers
for _int_router in INTEGRATION_ROUTERS:
    app.include_router(_int_router)

# ========================================
# AUDIT MIDDLEWARE (Phase 5, Milestone 4)
# ========================================
# Records one audit row per mutating API request. Best-effort and self-contained
# (never breaks a request); read-heavy/static paths are skipped internally.

app.add_middleware(AuditMiddleware)

# ========================================
# STARTUP: RBAC catalog sync (Phase 5, Milestone 3)
# ========================================
# Idempotently reconciles the DB with the RBAC catalog on boot so catalog
# changes take effect without a bespoke migration. Best-effort: a missing schema
# (DB not yet migrated) must not stop the app from starting.


@app.on_event("startup")
def _sync_rbac_on_startup() -> None:
    from .db.database import SessionLocal
    from .services.rbac import sync_rbac

    from .services.approvals import ensure_default_workflow
    from .services.config import sync_config

    from .services.integrations.config import sync_connector_configs

    db = SessionLocal()
    try:
        sync_rbac(db)
        ensure_default_workflow(db)
        sync_config(db)
        sync_connector_configs(db)
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