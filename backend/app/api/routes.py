from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

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
from app.services.risk_history import save_risk
from app.services.drift_detection import detect_drift
from app.services.audit_logger import log_decision
from app.services.ai_chat import credit_chat
from app.services.portfolio import analyze_portfolio
from app.services.alert_engine import generate_alerts
from app.services.pdf_generator import generate_pdf

from app.services.auth_service import hash_password, verify_password, create_access_token
from app.db.fake_users import users_db
from app.core.security import get_current_user


router = APIRouter()

# ---------------- AUTH ROUTES ---------------- #

@router.post("/signup")
def signup(data: dict):
    email = data["email"]
    password = data["password"]

    if email in users_db:
        raise HTTPException(status_code=400, detail="User already exists")

    users_db[email] = hash_password(password)

    return {"message": "User created successfully"}


@router.post("/login")
def login(data: dict):
    email = data["email"]
    password = data["password"]

    user = users_db.get(email)

    if not user or not verify_password(password, user):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": email})

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ---------------- PROTECTED ROUTES ---------------- #

@router.post("/risk-score")
def get_risk_score(
    data: CompanyInput,
    user = Depends(get_current_user)
):
    score = calculate_risk(data)
    return {"risk_score": score}


@router.post("/financial-analysis")
def financial_analysis(
    data: FinancialInput,
    user = Depends(get_current_user)
):
    analyzer = FinancialAnalyzer(
        revenue=data.revenue,
        expenses=data.expenses,
        total_assets=data.total_assets,
        total_liabilities=data.total_liabilities,
        equity=data.equity,
        current_assets=data.current_assets,
        current_liabilities=data.current_liabilities
    )

    return analyzer.analyze()


@router.post("/upload-financial-document")
async def upload_document(
    file: UploadFile = File(...),
    user = Depends(get_current_user)
):
    file_location = f"data/uploads/{file.filename}"

    with open(file_location, "wb") as f:
        f.write(await file.read())

    processor = DocumentProcessor(file_location)
    text = processor.process_document()

    extractor = FinancialExtractor(text)
    financial_data = extractor.extract_financials()

    return {
        "extracted_text": text[:500],
        "financial_data": financial_data
    }


@router.post("/ai-credit-analysis")
async def ai_credit_analysis(
    file: UploadFile = File(...),
    user = Depends(get_current_user)
):

    file_path = f"data/uploads/{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    processor = DocumentProcessor(file_path)
    text = processor.process_document()

    extractor = FinancialExtractor(text)
    financials = extractor.extract_financials()

    data = {
        "revenue_growth": 0.1,
        "debt_ratio": (financials["liabilities"] or 1) / (financials["assets"] or 1),
        "current_ratio": 1.2,
        "roe": 0.15
    }

    risk_score = calculate_risk(data)

    explanation = explain_prediction(type("obj", (object,), data))

    shap_values = (
        {item["feature"]: item["value"] for item in explanation}
        if isinstance(explanation, list)
        else explanation
    )

    analysis = generate_credit_analysis(
        financials=financials,
        risk_score=risk_score,
        shap_values=shap_values
    )

    ratios = {
        "debt_ratio": data["debt_ratio"],
        "current_ratio": data["current_ratio"],
        "roe": data["roe"]
    }

    fraud_flags = detect_fraud(financials, ratios)
    fraud_score = min(len(fraud_flags) * 20, 100)

    decision = make_decision(risk_score, fraud_score)
    loan_terms = generate_loan_terms(risk_score)

    save_risk(user["sub"], risk_score)

    drift_status = detect_drift(data)

    log_decision({
        "user": user["sub"],
        "input": data,
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


@router.post("/chat")
def chat_endpoint(
    payload: dict,
    user = Depends(get_current_user)
):
    messages = payload["messages"]
    context = payload["context"]

    reply = credit_chat(messages, context)

    return {"reply": reply}


@router.post("/portfolio-analysis")
def portfolio_analysis(
    data: dict,
    user = Depends(get_current_user)
):
    return analyze_portfolio(data["companies"])


@router.post("/download-report")
def download_report(
    data: dict,
    user = Depends(get_current_user)
):
    file_path = generate_pdf(data)

    return FileResponse(
        path=file_path,
        filename="credit_report.pdf",
        media_type='application/pdf'
    )