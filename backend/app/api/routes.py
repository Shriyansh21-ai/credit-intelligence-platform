from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.schemas.company import CompanyInput
from app.schemas.financials import FinancialInput

from app.services.risk_service import calculate_risk
from app.services.financial_analysis import FinancialAnalyzer
from app.services.document_ai import DocumentProcessor
from app.services.financial_extractor import FinancialExtractor
from app.services.explainability import explain_prediction
from app.services.ai_analyst import generate_credit_analysis
from app.services.simulation import apply_scenario
from app.services.fraud_detection import detect_fraud
from app.services.decision_engine import make_decision, generate_loan_terms
from app.services.drift_detection import detect_drift
from app.services.audit_logger import log_decision
from app.services.ai_chat import credit_chat
from app.services.portfolio import analyze_portfolio
from app.services.alert_engine import generate_alerts
from app.services.pdf_generator import generate_pdf
from app.services.risk_history import save_risk_db, get_risk_history

from app.services.auth_service import hash_password, verify_password, create_access_token
from app.core.security import get_current_user

from app.models.user import User
from app.db.database import get_db


router = APIRouter()

# ================= AUTH ================= #

@router.post("/signup")
def signup(data: dict, db: Session = Depends(get_db)):

    existing = db.query(User).filter(User.email == data.get("email")).first()

    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        email=data.get("email"),
        password=hash_password(data.get("password"))
    )

    db.add(new_user)
    db.commit()

    return {"message": "User created successfully"}


@router.post("/login")
def login(data: dict, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == data.get("email")).first()

    if not user or not verify_password(data.get("password"), user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.email})

    return {"access_token": token}


# ================= CORE APIs ================= #

@router.post("/risk-score")
def get_risk_score(
    data: CompanyInput,
    user=Depends(get_current_user)
):
    return {"risk_score": calculate_risk(data)}


@router.post("/financial-analysis")
def financial_analysis(
    data: FinancialInput,
    user=Depends(get_current_user)
):

    analyzer = FinancialAnalyzer(**data.dict())
    return analyzer.analyze()


@router.post("/upload-financial-document")
async def upload_document(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):

    file_location = f"data/uploads/{file.filename}"

    with open(file_location, "wb") as f:
        f.write(await file.read())

    processor = DocumentProcessor(file_location)
    text = processor.process_document()

    extractor = FinancialExtractor(text)

    return {
        "extracted_text": text[:500],
        "financial_data": extractor.extract_financials()
    }


# ================= MAIN AI PIPELINE ================= #

@router.post("/ai-credit-analysis")
async def ai_credit_analysis(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    file_path = f"data/uploads/{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # OCR + Extraction
    processor = DocumentProcessor(file_path)
    text = processor.process_document()

    extractor = FinancialExtractor(text)
    financials = extractor.extract_financials()

    # Feature engineering
    data = {
        "revenue_growth": 0.1,
        "debt_ratio": (financials.get("liabilities") or 1) / (financials.get("assets") or 1),
        "current_ratio": 1.2,
        "roe": 0.15
    }

    # Risk
    risk_score = calculate_risk(data)

    explanation = explain_prediction(type("obj", (object,), data))
    shap_values = (
        {i["feature"]: i["value"] for i in explanation}
        if isinstance(explanation, list)
        else explanation
    )

    # AI analysis
    analysis = generate_credit_analysis(financials, risk_score, shap_values)

    # Fraud
    ratios = {
        "debt_ratio": data["debt_ratio"],
        "current_ratio": data["current_ratio"],
        "roe": data["roe"]
    }

    fraud_flags = detect_fraud(financials, ratios)
    fraud_score = min(len(fraud_flags) * 20, 100)

    # Decision
    decision = make_decision(risk_score, fraud_score)
    loan_terms = generate_loan_terms(risk_score)

    # Save history
    save_risk_db(user["sub"], risk_score, db)

    # Drift + logging
    drift_status = detect_drift(data)

    log_decision({
        "user": user["sub"],
        "risk_score": risk_score,
        "decision": decision
    })

    alerts = generate_alerts(risk_score, fraud_score, drift_status)

    return {
        "risk_score": risk_score,
        "fraud_score": fraud_score,
        "alerts": alerts,
        "decision": decision,
        "loan_terms": loan_terms,
        "drift_status": drift_status,
        "analysis": analysis,
        "financials": financials,
        "shap_values": shap_values,
        "fraud_flags": fraud_flags
    }


# ================= CHAT ================= #

@router.post("/chat")
def chat_endpoint(
    payload: dict,
    user=Depends(get_current_user)
):

    messages = payload.get("messages", [])
    context = payload.get("context", {})

    return {"reply": credit_chat(messages, context)}


# ================= PORTFOLIO ================= #

@router.post("/portfolio-analysis")
def portfolio_analysis(
    data: dict,
    user=Depends(get_current_user)
):
    return analyze_portfolio(data.get("companies", []))


# ================= PDF ================= #

@router.post("/download-report")
def download_report(
    data: dict,
    user=Depends(get_current_user)
):

    file_path = generate_pdf(data)

    return FileResponse(
        path=file_path,
        filename="credit_report.pdf",
        media_type="application/pdf"
    )


# ================= HISTORY ================= #

@router.get("/risk-history")
def get_history(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    history = get_risk_history(user["sub"], db)

    return {"history": history}