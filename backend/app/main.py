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
from .models.financial_analysis import FinancialAnalysis
from .models.feature_vector import FeatureVector
from .models.risk_explanation import RiskExplanation
from .models.risk_alert import RiskAlert

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

# ========================================
# ROOT
# ========================================

@app.get("/")
def root():

    return {
        "message": "AI Credit Backend Running 🚀"
    }