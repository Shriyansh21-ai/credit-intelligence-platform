from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.routes import user, loan, prediction
from app.routes import transaction
from app.routes.fraud import router as fraud_router
from app.routes.portfolio import router as portfolio_router
from app.db.database import Base, engine
from app.models.prediction import Prediction
from app.models.fraud import FraudCheck
from app.models.portfolio import PortfolioAnalysis
from app.routes import history
from app.models.user import User
from app.routes import auth
from app.routes import fraud_history
from app.routes import fraud_summary
from app.routes import dashboard

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
        "http://localhost:8080"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)

# ========================================
# DATABASE TABLES
# ========================================

Base.metadata.create_all(bind=engine)

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

# ========================================
# ROOT
# ========================================

@app.get("/")
def root():

    return {
        "message": "AI Credit Backend Running 🚀"
    }